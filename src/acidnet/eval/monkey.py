from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from acidnet.engine import Simulation
from acidnet.engine.simulation import TurnEvent

FOOD_ITEMS = ("stew", "bread", "fish", "wheat")


@dataclass(slots=True)
class MonkeyStep:
    index: int
    command: str
    entries: list[TurnEvent]
    lines: list[str]
    day: int
    tick: int


@dataclass(slots=True)
class MonkeyReport:
    seed: int
    steps_executed: int
    backend: str
    final_day: int
    final_tick: int
    final_player_location: str
    final_player_hunger: float
    known_rumors: int
    steps: list[MonkeyStep]


class SimulationMonkeyRunner:
    def __init__(self, simulation: Simulation, *, seed: int = 7) -> None:
        self.simulation = simulation
        self.seed = seed
        self.rng = random.Random(seed)
        self.step_index = 0

    def run_one_step(self) -> MonkeyStep:
        command = self.choose_command()
        result = self.simulation.handle_command(command)
        self._assert_invariants()
        step = MonkeyStep(
            index=self.step_index,
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
            steps_executed=len(history),
            backend=type(self.simulation.dialogue_adapter).__name__,
            final_day=self.simulation.world.day,
            final_tick=self.simulation.world.tick,
            final_player_location=self.simulation.player.location_id,
            final_player_hunger=self.simulation.player.hunger,
            known_rumors=len(self.simulation.player.known_rumor_ids),
            steps=history,
        )

    def choose_command(self) -> str:
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
            if npc.is_vendor:
                for item in ("bread", "stew", "fish"):
                    if npc.inventory.get(item, 0) > 0 and self.simulation.player.money >= 1:
                        weighted_commands.append(f"trade {npc.name} buy {item} 1")

        food_item = self._best_player_food()
        if food_item is not None and self.simulation.player.hunger >= 18:
            weighted_commands.extend([f"eat {food_item}"] * 2)

        if not weighted_commands:
            return "wait 1"
        return self.rng.choice(weighted_commands)

    def _best_player_food(self) -> str | None:
        for item in FOOD_ITEMS:
            if self.simulation.player.inventory.get(item, 0) > 0:
                return item
        return None

    def _assert_invariants(self) -> None:
        assert 0.0 <= self.simulation.player.hunger <= 100.0
        for npc in self.simulation.npcs.values():
            assert 0.0 <= npc.hunger <= 100.0
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
