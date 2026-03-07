from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from acidnet.simulator import Simulation
from acidnet.simulator.runtime import CONSUMPTION_VALUE, FOOD_ITEMS, TradeOption, TurnEvent


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
    final_player_fatigue: float
    known_rumors: int
    peak_field_stress: float
    observed_event_types: list[str]
    observed_route_delay_ids: list[str]
    visited_regions: list[str]
    observed_regional_stock_regions: list[str]
    observed_regional_stock_items: list[str]
    regional_stock_shift_events: int
    peak_regional_transits: int
    peak_load_ratio: float
    storage_pressure_events: int
    peak_market_scarcity: float
    observed_market_price_items: list[str]
    market_price_shift_events: int
    observed_constrained_vendor_ids: list[str]
    observed_exchange_refusal_types: list[str]
    reserve_refusal_events: int
    reserve_refusal_npc_ids: list[str]
    successful_exchange_modes: dict[str, int]
    score: float
    success: bool
    goal_counts: dict[str, int]
    command_counts: dict[str, int]
    failure_reasons: list[str]
    steps: list[MonkeyStep]


class SimulationMonkeyRunner:
    def __init__(self, simulation: Simulation, *, seed: int = 7, role: str = "wanderer") -> None:
        self.simulation = simulation
        self.seed = seed
        self.role = role.lower()
        self.rng = random.Random(seed)
        self.step_index = 0
        self.asked_rumor_npc_ids: set[str] = set()
        self.start_player_money = simulation.player.money
        self.start_known_rumors = len(simulation.player.known_rumor_ids)
        self.peak_field_stress = simulation.world.field_stress
        self.observed_event_types: set[str] = {event.event_type for event in simulation.world.active_events}
        self.observed_route_delay_ids: set[str] = {
            event.route_id for event in simulation._visible_world_events_for_player() if event.event_type == "route_delay" and event.route_id
        }
        current_region = simulation.current_region()
        self.visited_regions: set[str] = set()
        if current_region is not None:
            self.visited_regions.add(current_region.region_id)
        self.observed_regional_stock_regions: set[str] = set()
        self.observed_regional_stock_items: set[str] = set()
        self.regional_stock_shift_events = 0
        self.last_regional_stock_signals = {
            region_id: dict(region.stock_signals) for region_id, region in simulation.world.regions.items()
        }
        self.peak_regional_transits = len(simulation.world.regional_transits)
        self.peak_load_ratio = 0.0
        self.storage_pressure_events = 0
        self.peak_market_scarcity = simulation.world.market.scarcity_index
        self.observed_market_price_items: set[str] = set()
        self.market_price_shift_events = 0
        self.last_market_prices = {
            item_id: state.current_price for item_id, state in simulation.world.market.items.items()
        }
        self.observed_constrained_vendor_ids: set[str] = set()
        self.observed_exchange_refusal_types: set[str] = set()
        self.reserve_refusal_events = 0
        self.reserve_refusal_npc_ids: set[str] = set()
        self.successful_exchange_modes: Counter[str] = Counter()
        self._record_visible_exchange_constraints()

    def run_one_step(self) -> MonkeyStep:
        goal, command = self.choose_action()
        targeted_npc_id = self._targeted_npc_id(command)
        targeted_trade_npc_id = self._targeted_trade_npc_id(command)
        trade_mode = self._trade_mode(command)
        result = self.simulation.handle_command(command)
        self.peak_field_stress = max(self.peak_field_stress, self.simulation.world.field_stress)
        self.observed_event_types.update(event.event_type for event in self.simulation.world.active_events)
        self.observed_route_delay_ids.update(
            event.route_id
            for event in self.simulation._visible_world_events_for_player()
            if event.event_type == "route_delay" and event.route_id is not None
        )
        current_region = self.simulation.current_region()
        if current_region is not None:
            self.visited_regions.add(current_region.region_id)
        self.peak_regional_transits = max(self.peak_regional_transits, len(self.simulation.world.regional_transits))
        self.peak_market_scarcity = max(self.peak_market_scarcity, self.simulation.world.market.scarcity_index)
        self.simulation._refresh_actor_loads()
        if self.simulation.player.carry_capacity > 0:
            self.peak_load_ratio = max(
                self.peak_load_ratio,
                self.simulation.player.carried_weight / self.simulation.player.carry_capacity,
            )
        self.storage_pressure_events += sum(1 for line in result.lines if "leave" in line.lower() and "behind" in line.lower())
        if command.startswith("ask ") and command.endswith(" rumor") and targeted_npc_id is not None:
            self.asked_rumor_npc_ids.add(targeted_npc_id)
        self._record_exchange_outcome(result.lines, trade_mode=trade_mode, targeted_trade_npc_id=targeted_trade_npc_id)
        self._record_regional_stock_shifts()
        self._record_market_price_shifts()
        self._record_visible_exchange_constraints()
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
        goal_counts = Counter(step.goal for step in history)
        command_counts = Counter(step.command.split()[0] for step in history if step.command)
        failure_reasons = self._collect_failure_reasons(history, goal_counts, command_counts)
        score = self._score_run(failure_reasons)
        return MonkeyReport(
            seed=self.seed,
            role=self.role,
            steps_executed=len(history),
            backend=type(self.simulation.dialogue_adapter).__name__,
            final_day=self.simulation.world.day,
            final_tick=self.simulation.world.tick,
            final_player_location=self.simulation.player.location_id,
            final_player_hunger=self.simulation.player.hunger,
            final_player_fatigue=self.simulation.player.fatigue,
            known_rumors=len(self.simulation.player.known_rumor_ids),
            peak_field_stress=round(self.peak_field_stress, 3),
            observed_event_types=sorted(self.observed_event_types),
            observed_route_delay_ids=sorted(self.observed_route_delay_ids),
            visited_regions=sorted(self.visited_regions),
            observed_regional_stock_regions=sorted(self.observed_regional_stock_regions),
            observed_regional_stock_items=sorted(self.observed_regional_stock_items),
            regional_stock_shift_events=self.regional_stock_shift_events,
            peak_regional_transits=self.peak_regional_transits,
            peak_load_ratio=round(self.peak_load_ratio, 3),
            storage_pressure_events=self.storage_pressure_events,
            peak_market_scarcity=round(self.peak_market_scarcity, 3),
            observed_market_price_items=sorted(self.observed_market_price_items),
            market_price_shift_events=self.market_price_shift_events,
            observed_constrained_vendor_ids=sorted(self.observed_constrained_vendor_ids),
            observed_exchange_refusal_types=sorted(self.observed_exchange_refusal_types),
            reserve_refusal_events=self.reserve_refusal_events,
            reserve_refusal_npc_ids=sorted(self.reserve_refusal_npc_ids),
            successful_exchange_modes=dict(self.successful_exchange_modes),
            score=score,
            success=not failure_reasons,
            goal_counts=dict(goal_counts),
            command_counts=dict(command_counts),
            failure_reasons=failure_reasons,
            steps=history,
        )

    def choose_action(self) -> tuple[str, str]:
        if self.simulation.player.travel_state.is_traveling:
            return "complete_travel", self._travel_advance_command()
        if self.role == "survivor":
            return self._choose_survivor_action()
        if self.role == "hoarder":
            return self._choose_hoarder_action()
        if self.role == "exploit_observer":
            return self._choose_exploit_observer_action()
        if self.role == "shock_observer":
            return self._choose_shock_observer_action()
        if self.role == "regional_observer":
            return self._choose_regional_observer_action()
        if self.role == "downstream_observer":
            return self._choose_downstream_observer_action()
        if self.role == "rumor_verifier":
            return self._choose_rumor_verifier_action()
        if self.role == "altruist":
            return self._choose_altruist_action()
        if self.role == "trader":
            return self._choose_trader_action()
        return self._choose_wanderer_action()

    def choose_command(self) -> str:
        return self.choose_action()[1]

    def _travel_advance_command(self) -> str:
        if self.role in {"regional_observer", "downstream_observer"}:
            return "next 3"
        return "next 1"

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

    def _choose_shock_observer_action(self) -> tuple[str, str]:
        if self.simulation.player.hunger >= 32 and self._best_player_food() is not None:
            return "maintain_self", "meal"
        if self.simulation.player.fatigue >= 72:
            shelter = self.simulation._shelter_rating(self.simulation.player.location_id)
            return ("recover_sleep", "sleep 1") if shelter >= 0.65 else ("recover_rest", "rest 1")
        if self.simulation.player.location_id != "farm":
            next_hop = self._next_hop_toward({"farm"})
            if next_hop is not None:
                return "reach_shock_site", next_hop
        if self.simulation.world.active_events:
            unasked_here = self._unasked_npcs_here()
            if unasked_here:
                return "verify_local_shock_rumor", f"ask {unasked_here[0].name} rumor"
        if self.simulation.world.field_stress >= 0.45:
            return "observe_peak_stress", "next 1"
        if self.simulation.player.location_id == "farm":
            local_npcs = self._unasked_npcs_here()
            if local_npcs:
                return "sample_local_context", f"talk {local_npcs[0].name}"
        return "wait_for_world_shift", "next 1"

    def _choose_hoarder_action(self) -> tuple[str, str]:
        if self.simulation.player.hunger >= 36 and self._best_player_food() is not None:
            return "maintain_self", "meal"
        if self.simulation.player.fatigue >= 70:
            shelter = self.simulation._shelter_rating(self.simulation.player.location_id)
            return ("recover_sleep", "sleep 1") if shelter >= 0.65 else ("recover_rest", "rest 1")
        if self.simulation.player.location_id in {"farm", "riverside"}:
            return "hoard_resources", "work"
        next_hop = self._next_hop_toward({"farm", "riverside"})
        if next_hop is not None:
            return "reach_resource_site", next_hop
        return "advance_time", "next 1"

    def _choose_exploit_observer_action(self) -> tuple[str, str]:
        if self.simulation.player.hunger >= 42 and self._best_player_food() is not None:
            return "maintain_self", "meal"
        if self.simulation.player.fatigue >= 74:
            shelter = self.simulation._shelter_rating(self.simulation.player.location_id)
            return ("recover_sleep", "sleep 1") if shelter >= 0.65 else ("recover_rest", "rest 1")

        hobb = self.simulation.npcs.get("npc.hobb")
        if hobb is None:
            return self._choose_wanderer_action()
        if hobb.travel_state.is_traveling:
            return "wait_for_bakery_vendor", "next 1"
        if self.simulation.player.location_id != hobb.location_id:
            next_hop = self._next_hop_toward({hobb.location_id})
            if next_hop is not None:
                return "reach_bakery_vendor", next_hop
        if hobb.location_id != self.simulation.player.location_id:
            return "wait_for_bakery_vendor", "next 1"
        if hobb.npc_id not in self.observed_constrained_vendor_ids:
            return "inspect_bakery_vendor", f"inspect {hobb.name}"

        buy_option = self._best_food_option(hobb.npc_id, "buy")
        if buy_option is not None and self.successful_exchange_modes.get("buy", 0) < 2:
            return "probe_vendor_buy_floor", f"trade {hobb.name} buy {buy_option.item} 1"
        if hobb.npc_id not in self.reserve_refusal_npc_ids:
            return "force_vendor_buy_refusal", f"trade {hobb.name} buy bread 1"
        return "observe_post_probe", "status"

    def _choose_regional_observer_action(self) -> tuple[str, str]:
        if self.simulation.player.hunger >= 30 and self._best_player_food() is not None:
            return "maintain_self", "meal"
        if self.simulation.player.fatigue >= 72:
            shelter = self.simulation._shelter_rating(self.simulation.player.location_id)
            return ("recover_sleep", "sleep 1") if shelter >= 0.65 else ("recover_rest", "rest 1")
        visible_events = self.simulation._visible_world_events_for_player()
        if any(event.event_type == "route_delay" for event in visible_events):
            return "inspect_route_status", "regions"
        if self.simulation.world.regional_transits:
            return "inspect_regional_flow", "regions"
        current_region = self.simulation.current_region()
        current_region_id = current_region.region_id if current_region is not None else None
        if current_region_id == "region.greenfall" and "region.hollowmarket" not in self.visited_regions:
            return "visit_hollowmarket", "travel-region hollow"
        if current_region_id == "region.hollowmarket" and "region.stonewatch" not in self.visited_regions:
            return "return_to_hub", "travel-region greenfall"
        if current_region_id == "region.greenfall" and "region.hollowmarket" in self.visited_regions and "region.stonewatch" not in self.visited_regions:
            return "visit_stonewatch", "travel-region stonewatch"
        if current_region_id == "region.stonewatch" and len(self.visited_regions) < 3:
            return "return_to_hub", "travel-region greenfall"
        return "advance_regional_time", "next 1"

    def _choose_downstream_observer_action(self) -> tuple[str, str]:
        if self.simulation.player.hunger >= 30 and self._best_player_food() is not None:
            return "maintain_self", "meal"
        if self.simulation.player.fatigue >= 72:
            shelter = self.simulation._shelter_rating(self.simulation.player.location_id)
            return ("recover_sleep", "sleep 1") if shelter >= 0.65 else ("recover_rest", "rest 1")

        route_delay_visible = any(
            event.event_type == "route_delay" for event in self.simulation._visible_world_events_for_player()
        )
        if route_delay_visible and self.peak_regional_transits == 0:
            return "wait_for_transit_flow", "next 3"
        if route_delay_visible and self.step_index % 2 == 0 and (
            self.peak_regional_transits > 0
            or self.regional_stock_shift_events > 0
            or self.market_price_shift_events > 0
        ):
            return "inspect_supply_chain", "regions"
        if route_delay_visible:
            return "wait_for_downstream_response", "next 1"
        if self.step_index == 0:
            return "sample_regional_baseline", "regions"
        return "wait_for_route_pressure", "next 1"

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
        weighted_commands.extend(["next 1"] * 3)

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
            return "idle", "next 1"
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

    def _targeted_trade_npc_id(self, command: str) -> str | None:
        parts = command.split()
        if len(parts) < 5 or parts[0] != "trade":
            return None
        npc = self.simulation._resolve_npc_here(" ".join(parts[1:-3]))
        return npc.npc_id if npc is not None else None

    def _trade_mode(self, command: str) -> str | None:
        parts = command.split()
        if len(parts) < 5 or parts[0] != "trade":
            return None
        return parts[-3]

    def _record_exchange_outcome(self, lines: list[str], *, trade_mode: str | None, targeted_trade_npc_id: str | None) -> None:
        if trade_mode is not None and any(self._line_matches_trade_success(line, trade_mode) for line in lines):
            self.successful_exchange_modes[trade_mode] += 1
        for line in lines:
            refusal_type = self._classify_exchange_refusal(line)
            if refusal_type is None:
                continue
            self.observed_exchange_refusal_types.add(refusal_type)
            if refusal_type in {"reserve_floor_refusal", "stock_floor_refusal"}:
                self.reserve_refusal_events += 1
                if targeted_trade_npc_id is not None:
                    self.reserve_refusal_npc_ids.add(targeted_trade_npc_id)

    def _record_market_price_shifts(self) -> None:
        for item_id, state in self.simulation.world.market.items.items():
            previous_price = self.last_market_prices.get(item_id, state.current_price)
            if state.current_price != previous_price:
                self.observed_market_price_items.add(item_id)
                self.market_price_shift_events += 1
            self.last_market_prices[item_id] = state.current_price

    def _record_regional_stock_shifts(self) -> None:
        for region_id, region in self.simulation.world.regions.items():
            previous_signals = self.last_regional_stock_signals.get(region_id, {})
            for item_id, quantity in region.stock_signals.items():
                if quantity == previous_signals.get(item_id, quantity):
                    continue
                self.observed_regional_stock_regions.add(region_id)
                self.observed_regional_stock_items.add(item_id)
                self.regional_stock_shift_events += 1
            self.last_regional_stock_signals[region_id] = dict(region.stock_signals)

    def _record_visible_exchange_constraints(self) -> None:
        if self.simulation.player.travel_state.is_traveling:
            return
        for npc in self.simulation._npcs_at(self.simulation.player.location_id):
            if not npc.is_vendor:
                continue
            buy_options = {option.item: option.quantity for option in self.simulation.player_trade_options(npc.npc_id, mode="buy")}
            for item, quantity in npc.inventory.items():
                if quantity <= 0:
                    continue
                exposed_quantity = buy_options.get(item, 0)
                if 0 <= exposed_quantity < quantity:
                    self.observed_constrained_vendor_ids.add(npc.npc_id)
                    break

    def _line_matches_trade_success(self, line: str, trade_mode: str) -> bool:
        normalized = line.lower()
        if trade_mode == "buy":
            return normalized.startswith("you buy ")
        if trade_mode == "sell":
            return normalized.startswith("you sell ")
        if trade_mode == "ask":
            return " gives you " in normalized
        if trade_mode == "give":
            return normalized.startswith("you give ")
        return False

    def _classify_exchange_refusal(self, line: str) -> str | None:
        normalized = line.lower()
        if "cannot spare that much" in normalized or "without cutting into your reserve" in normalized:
            return "reserve_floor_refusal"
        if "does not have enough" in normalized:
            return "stock_floor_refusal"
        if "is not willing to give you that much" in normalized:
            return "willingness_refusal"
        return None

    def _collect_failure_reasons(
        self,
        history: list[MonkeyStep],
        goal_counts: Counter[str],
        command_counts: Counter[str],
    ) -> list[str]:
        failures: list[str] = []
        if self.simulation.player.hunger >= 88.0:
            failures.append("player_starving")
        if self.simulation.player.fatigue >= 90.0:
            failures.append("player_exhausted")

        if self.role == "wanderer":
            if self._movement_count(history) == 0:
                failures.append("wanderer_never_moved")
            if self._social_count(history) == 0:
                failures.append("wanderer_never_engaged_socially")
        elif self.role == "survivor":
            if self.simulation.player.hunger >= 60.0:
                failures.append("survivor_failed_to_stabilize_hunger")
            if not any(
                goal_counts.get(goal, 0) > 0
                for goal in {"eat_available_food", "request_food", "buy_food", "secure_food_or_income"}
            ):
                failures.append("survivor_never_pursued_food")
            if self.simulation.player.fatigue >= 78.0:
                failures.append("survivor_failed_to_recover")
        elif self.role == "rumor_verifier":
            if len(self.asked_rumor_npc_ids) < 2:
                failures.append("rumor_verifier_insufficient_sources")
            if (len(self.simulation.player.known_rumor_ids) - self.start_known_rumors) < 2:
                failures.append("rumor_verifier_low_rumor_gain")
        elif self.role == "shock_observer":
            if self.peak_field_stress < 0.45:
                failures.append("shock_observer_never_reached_stress_window")
            if "harvest_shortfall" not in self.observed_event_types:
                failures.append("shock_observer_missed_world_event")
            if goal_counts.get("verify_local_shock_rumor", 0) == 0:
                failures.append("shock_observer_never_cross_checked_rumor")
        elif self.role == "hoarder":
            if goal_counts.get("hoard_resources", 0) < 2:
                failures.append("hoarder_never_gathered_enough")
            if self.storage_pressure_events == 0:
                failures.append("hoarder_never_triggered_storage_pressure")
            if self.peak_load_ratio < 0.85:
                failures.append("hoarder_never_loaded_up")
        elif self.role == "exploit_observer":
            if "npc.hobb" not in self.observed_constrained_vendor_ids:
                failures.append("exploit_observer_never_observed_reserved_stock")
            if self.successful_exchange_modes.get("buy", 0) == 0:
                failures.append("exploit_observer_never_probed_vendor")
        elif self.role == "regional_observer":
            if len(self.visited_regions) < 2:
                failures.append("regional_observer_never_left_home_region")
            if not self.observed_route_delay_ids:
                failures.append("regional_observer_missed_route_delay")
            if self.peak_regional_transits == 0:
                failures.append("regional_observer_never_saw_transit_flow")
            if self.market_price_shift_events == 0:
                failures.append("regional_observer_missed_market_shift")
        elif self.role == "downstream_observer":
            if command_counts.get("regions", 0) == 0:
                failures.append("downstream_observer_never_inspected_supply_chain")
            if not self.observed_route_delay_ids:
                failures.append("downstream_observer_missed_route_delay")
            if self.peak_regional_transits == 0:
                failures.append("downstream_observer_never_saw_transit_flow")
            if self.regional_stock_shift_events == 0:
                failures.append("downstream_observer_missed_regional_stock_shift")
            if self.market_price_shift_events == 0:
                failures.append("downstream_observer_missed_market_shift")
        elif self.role == "altruist":
            if self._exchange_count(history, {"give"}) == 0:
                failures.append("altruist_never_shared_resources")
            if self.simulation.player.hunger >= 70.0:
                failures.append("altruist_overextended_self")
        elif self.role == "trader":
            if self._exchange_count(history, {"buy", "sell"}) == 0:
                failures.append("trader_never_completed_cash_exchange")
            if self.simulation.player.money <= self.start_player_money and self._exchange_count(history, {"sell"}) == 0:
                failures.append("trader_never_realized_value")

        if command_counts.get("next", 0) == len(history) and history:
            failures.append("monkey_stalled_into_pure_time_advance")
        return failures

    def _score_run(self, failure_reasons: list[str]) -> float:
        penalties = {
            "player_starving": 0.4,
            "player_exhausted": 0.25,
            "wanderer_never_moved": 0.18,
            "wanderer_never_engaged_socially": 0.18,
            "survivor_failed_to_stabilize_hunger": 0.3,
            "survivor_never_pursued_food": 0.22,
            "survivor_failed_to_recover": 0.18,
            "rumor_verifier_insufficient_sources": 0.25,
            "rumor_verifier_low_rumor_gain": 0.25,
            "shock_observer_never_reached_stress_window": 0.24,
            "shock_observer_missed_world_event": 0.32,
            "shock_observer_never_cross_checked_rumor": 0.18,
            "hoarder_never_gathered_enough": 0.2,
            "hoarder_never_triggered_storage_pressure": 0.28,
            "hoarder_never_loaded_up": 0.18,
            "exploit_observer_never_observed_reserved_stock": 0.3,
            "exploit_observer_never_probed_vendor": 0.22,
            "regional_observer_never_left_home_region": 0.3,
            "regional_observer_missed_route_delay": 0.28,
            "regional_observer_never_saw_transit_flow": 0.24,
            "regional_observer_missed_market_shift": 0.2,
            "downstream_observer_never_inspected_supply_chain": 0.24,
            "downstream_observer_missed_route_delay": 0.28,
            "downstream_observer_never_saw_transit_flow": 0.24,
            "downstream_observer_missed_regional_stock_shift": 0.22,
            "downstream_observer_missed_market_shift": 0.2,
            "altruist_never_shared_resources": 0.28,
            "altruist_overextended_self": 0.2,
            "trader_never_completed_cash_exchange": 0.28,
            "trader_never_realized_value": 0.18,
            "monkey_stalled_into_pure_time_advance": 0.25,
        }
        score = 1.0
        for reason in failure_reasons:
            score -= penalties.get(reason, 0.15)
        return round(max(0.0, score), 3)

    def _movement_count(self, history: list[MonkeyStep]) -> int:
        return sum(1 for step in history if step.command.startswith("go ") or step.goal == "complete_travel")

    def _social_count(self, history: list[MonkeyStep]) -> int:
        return sum(1 for step in history if step.command.startswith("talk ") or step.command.startswith("ask "))

    def _exchange_count(self, history: list[MonkeyStep], modes: set[str]) -> int:
        count = 0
        for step in history:
            parts = step.command.split()
            if len(parts) >= 4 and parts[0] == "trade" and parts[-3] in modes:
                count += 1
        return count

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
