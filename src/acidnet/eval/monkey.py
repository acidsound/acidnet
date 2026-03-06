from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from acidnet.engine import Simulation
from acidnet.engine.simulation import CONSUMPTION_VALUE, FOOD_ITEMS, TradeOption, TurnEvent


@dataclass(slots=True)
class MonkeyStep:
    index: int
    goal: str
    command: str
    entries: list[TurnEvent]
    lines: list[str]
    day: int
    tick: int


@dataclass(slots=True)
class MonkeyReport:
    seed: int
    role: str
    steps_executed: int
    backend: str
    final_day: int
    final_tick: int
    final_player_location: str
    final_player_hunger: float
    known_rumors: int
    steps: list[MonkeyStep]


class SimulationMonkeyRunner:
    def __init__(self, simulation: Simulation, *, seed: int = 7, role: str = "wanderer") -> None:
        self.simulation = simulation
        self.seed = seed
        self.role = role.lower()
        self.rng = random.Random(seed)
        self.step_index = 0
        self.asked_rumor_npc_ids: set[str] = set()

    def run_one_step(self) -> MonkeyStep:
        goal, command = self.choose_action()
        targeted_npc_id = self._targeted_npc_id(command)
        result = self.simulation.handle_command(command)
        if command.startswith("ask ") and command.endswith(" rumor") and targeted_npc_id is not None:
            self.asked_rumor_npc_ids.add(targeted_npc_id)
        self._assert_invariants()
        step = MonkeyStep(
            index=self.step_index,
            goal=goal,
            command=command,
            entries=result.entries,
            lines=result.lines,
            day=self.simulation.world.day,
            tick=self.simulation.world.tick,
        )
        self.step_index += 1
        return step

    def run_steps(self, steps: int) -> MonkeyReport:
        history = [self.run_one_step() for _ in range(max(0, steps))]
        return MonkeyReport(
            seed=self.seed,
            role=self.role,
            steps_executed=len(history),
            backend=type(self.simulation.dialogue_adapter).__name__,
            final_day=self.simulation.world.day,
            final_tick=self.simulation.world.tick,
            final_player_location=self.simulation.player.location_id,
            final_player_hunger=self.simulation.player.hunger,
            known_rumors=len(self.simulation.player.known_rumor_ids),
            steps=history,
        )

    def choose_action(self) -> tuple[str, str]:
        if self.simulation.player.travel_state.is_traveling:
            return "complete_travel", "wait 1"
        if self.role == "survivor":
            return self._choose_survivor_action()
        if self.role == "rumor_verifier":
            return self._choose_rumor_verifier_action()
        if self.role == "altruist":
            return self._choose_altruist_action()
        if self.role == "trader":
            return self._choose_trader_action()
        return self._choose_wanderer_action()

    def choose_command(self) -> str:
        return self.choose_action()[1]

    def _choose_survivor_action(self) -> tuple[str, str]:
        if self.simulation.player.fatigue >= 72:
            shelter = self.simulation._shelter_rating(self.simulation.player.location_id)
            return ("recover_sleep", "sleep 1") if shelter >= 0.65 else ("recover_rest", "rest 1")

        if self.simulation.player.hunger >= 24:
            if self._best_player_food() is not None:
                return "eat_available_food", "meal"
            request_command = self._best_food_exchange_command("ask")
            if request_command is not None:
                return "request_food", request_command
            buy_command = self._best_food_exchange_command("buy")
            if buy_command is not None:
                return "buy_food", buy_command
            if self.simulation.player.location_id in {"farm", "riverside", "square", "bakery", "tavern"}:
                return "secure_food_or_income", "work"
            next_hop = self._next_hop_toward({"farm", "riverside", "square", "bakery", "tavern"})
            if next_hop is not None:
                return "seek_food_source", next_hop

        unasked_here = self._unasked_npcs_here()
        if unasked_here:
            return "check_local_rumor", f"ask {unasked_here[0].name} rumor"
        if self.simulation.player.location_id in {"farm", "riverside", "square", "bakery", "tavern", "smithy", "shrine"}:
            return "routine_work", "work"
        return self._choose_wanderer_action()

    def _choose_rumor_verifier_action(self) -> tuple[str, str]:
        unasked_here = self._unasked_npcs_here()
        if unasked_here:
            return "collect_rumor", f"ask {unasked_here[0].name} rumor"
        next_hop = self._next_hop_toward(self._locations_with_unasked_npcs())
        if next_hop is not None:
            return "move_to_new_witness", next_hop
        if self.simulation.player.known_rumor_ids:
            npcs_here = self.simulation._npcs_at(self.simulation.player.location_id)
            if npcs_here:
                return "cross_check_social_context", f"talk {npcs_here[0].name}"
        return self._choose_wanderer_action()

    def _choose_altruist_action(self) -> tuple[str, str]:
        if self.simulation.player.hunger >= 34 and self._best_player_food() is not None:
            return "self_preserve", "meal"
        give_command = self._best_give_food_command()
        if give_command is not None:
            return "share_food", give_command
        if self._best_giftable_food() is None:
            if self.simulation.player.location_id in {"farm", "riverside", "square", "bakery", "tavern"}:
                return "gather_shareable_food", "work"
            next_hop = self._next_hop_toward({"farm", "riverside", "square", "bakery", "tavern"})
            if next_hop is not None:
                return "seek_shareable_food", next_hop
        unasked_here = self._unasked_npcs_here()
        if unasked_here:
            return "check_need_signals", f"talk {unasked_here[0].name}"
        return self._choose_wanderer_action()

    def _choose_trader_action(self) -> tuple[str, str]:
        if self.simulation.player.hunger >= 30 and self._best_player_food() is not None:
            return "self_preserve", "meal"
        sell_command = self._best_sale_command()
        if sell_command is not None:
            return "sell_surplus", sell_command
        if self._best_sellable_inventory_item() is not None:
            next_hop = self._next_hop_toward({"square", "bakery"})
            if next_hop is not None:
                return "reach_vendor", next_hop
        if self.simulation.player.location_id in {"farm", "riverside", "smithy", "square"}:
            return "work_for_trade_goods", "work"
        next_hop = self._next_hop_toward({"farm", "riverside", "smithy", "square"})
        if next_hop is not None:
            return "seek_trade_goods", next_hop
        return self._choose_wanderer_action()

    def _choose_wanderer_action(self) -> tuple[str, str]:
        weighted_commands: list[str] = []

        weighted_commands.extend(["look", "status"])
        weighted_commands.extend(["wait 1"] * 3)

        current_location = self.simulation.world.locations[self.simulation.player.location_id]
        for neighbor_id in current_location.neighbors:
            weighted_commands.extend([f"go {neighbor_id}"] * 2)

        npcs_here = self.simulation._npcs_at(self.simulation.player.location_id)
        for npc in npcs_here:
            weighted_commands.extend([f"talk {npc.name}"] * 3)
            weighted_commands.extend([f"ask {npc.name} rumor"] * 2)
            for item in ("bread", "stew", "fish"):
                if self.simulation.player_trade_options(npc.npc_id, mode="buy"):
                    option = self._best_food_option(npc.npc_id, "buy")
                    if option is not None:
                        weighted_commands.append(f"trade {npc.name} buy {option.item} 1")
                        break

        food_item = self._best_player_food()
        if food_item is not None and self.simulation.player.hunger >= 18:
            weighted_commands.extend([f"eat {food_item}"] * 2)

        if not weighted_commands:
            return "idle", "wait 1"
        return "wander", self.rng.choice(weighted_commands)

    def _best_player_food(self) -> str | None:
        best_item: str | None = None
        best_value = -1.0
        for item in FOOD_ITEMS:
            if self.simulation.player.inventory.get(item, 0) <= 0:
                continue
            value = CONSUMPTION_VALUE[item]
            if value > best_value:
                best_item = item
                best_value = value
        return best_item

    def _best_food_option(self, npc_id: str, mode: str) -> TradeOption | None:
        options = [
            option
            for option in self.simulation.player_trade_options(npc_id, mode=mode)
            if option.item in FOOD_ITEMS and option.quantity > 0
        ]
        if not options:
            return None
        options.sort(key=lambda option: (CONSUMPTION_VALUE[option.item], option.quantity, -(option.price or 0)), reverse=True)
        return options[0]

    def _best_food_exchange_command(self, mode: str) -> str | None:
        candidates: list[tuple[float, str]] = []
        for npc in self.simulation._npcs_at(self.simulation.player.location_id):
            option = self._best_food_option(npc.npc_id, mode)
            if option is None:
                continue
            candidates.append((CONSUMPTION_VALUE[option.item], f"trade {npc.name} {mode} {option.item} 1"))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def _best_giftable_food(self) -> str | None:
        for item in sorted(
            FOOD_ITEMS,
            key=lambda food: CONSUMPTION_VALUE[food],
            reverse=True,
        ):
            if self.simulation._giftable_quantity(self.simulation.player, item) > 0:
                return item
        return None

    def _best_give_food_command(self) -> str | None:
        food_item = self._best_giftable_food()
        if food_item is None:
            return None
        hungry_npcs = sorted(
            (npc for npc in self.simulation._npcs_at(self.simulation.player.location_id) if npc.hunger >= 62),
            key=lambda npc: npc.hunger,
            reverse=True,
        )
        for npc in hungry_npcs:
            options = self.simulation.player_trade_options(npc.npc_id, mode="give")
            if any(option.item == food_item and option.quantity > 0 for option in options):
                return f"trade {npc.name} give {food_item} 1"
        return None

    def _best_sellable_inventory_item(self) -> str | None:
        best_item: str | None = None
        best_value = -1
        for item, qty in self.simulation.player.inventory.items():
            if qty <= 0:
                continue
            if item in FOOD_ITEMS and self.simulation.player.hunger >= 40:
                continue
            value = CONSUMPTION_VALUE.get(item, 0) if item in FOOD_ITEMS else 50
            if value > best_value:
                best_item = item
                best_value = value
        return best_item

    def _best_sale_command(self) -> str | None:
        best_command: str | None = None
        best_price = -1
        for npc in self.simulation._npcs_at(self.simulation.player.location_id):
            options = self.simulation.player_trade_options(npc.npc_id, mode="sell")
            for option in options:
                if option.quantity <= 0:
                    continue
                if option.item in FOOD_ITEMS and self.simulation.player.hunger >= 40:
                    continue
                if option.price is not None and option.price > best_price:
                    best_price = option.price
                    best_command = f"trade {npc.name} sell {option.item} 1"
        return best_command

    def _unasked_npcs_here(self) -> list:
        return [
            npc
            for npc in self.simulation._npcs_at(self.simulation.player.location_id)
            if npc.npc_id not in self.asked_rumor_npc_ids
        ]

    def _locations_with_unasked_npcs(self) -> set[str]:
        return {
            npc.location_id
            for npc in self.simulation.npcs.values()
            if not npc.travel_state.is_traveling and npc.npc_id not in self.asked_rumor_npc_ids
        }

    def _next_hop_toward(self, location_ids: set[str]) -> str | None:
        current_id = self.simulation.player.location_id
        best_target: str | None = None
        best_distance = 999
        for location_id in sorted(location_ids):
            if location_id == current_id:
                continue
            distance = self.simulation._path_length(current_id, location_id)
            if distance < best_distance:
                best_distance = distance
                best_target = location_id
        if best_target is None or best_distance >= 999:
            return None
        next_hop = self.simulation._next_hop(current_id, best_target)
        if next_hop is None or next_hop == current_id:
            return None
        return f"go {next_hop}"

    def _targeted_npc_id(self, command: str) -> str | None:
        parts = command.split()
        if not parts:
            return None
        if parts[0] == "ask" and len(parts) >= 3 and parts[-1] == "rumor":
            npc = self.simulation._resolve_npc_here(" ".join(parts[1:-1]))
            return npc.npc_id if npc is not None else None
        return None

    def _assert_invariants(self) -> None:
        assert 0.0 <= self.simulation.player.hunger <= 100.0
        assert 0.0 <= self.simulation.player.fatigue <= 100.0
        for npc in self.simulation.npcs.values():
            assert 0.0 <= npc.hunger <= 100.0
            assert 0.0 <= npc.fatigue <= 100.0
            assert npc.money >= 0
            assert npc.location_id in self.simulation.world.locations
            for qty in npc.inventory.values():
                assert qty > 0
        assert self.simulation.player.money >= 0
        assert self.simulation.player.location_id in self.simulation.world.locations
        for qty in self.simulation.player.inventory.values():
            assert qty > 0
        for rumor in self.simulation.rumors.values():
            assert 0.0 <= rumor.confidence <= 1.0
            assert rumor.hop_count >= 0
        for market_item in self.simulation.world.market.items.values():
            assert market_item.stock >= 0
            assert market_item.current_price >= 1


def export_monkey_report_json(path: str | Path, report: MonkeyReport) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
