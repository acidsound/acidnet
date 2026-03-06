from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from acidnet.engine import Simulation


@dataclass(slots=True)
class CirculationReport:
    turns: int
    average_active_locations: float
    min_active_locations: int
    max_active_locations: int
    peak_location_occupancy: int
    peak_hunger_seen: float
    average_final_hunger: float
    starving_npc_count: int
    zero_money_npc_count: int
    scarcity_index: float
    circulation_score: float
    action_counts: dict[str, int]
    final_location_counts: dict[str, int]
    final_hunger_by_npc: dict[str, float]
    final_money_by_npc: dict[str, int]
    flags: list[str]


def run_circulation_eval(simulation: Simulation, *, turns: int = 120) -> CirculationReport:
    action_counts: Counter[str] = Counter()
    active_location_counts: list[int] = []
    peak_location_occupancy = 0
    peak_hunger_seen = max(npc.hunger for npc in simulation.npcs.values())

    for _ in range(turns):
        lines = simulation.advance_turn(1).lines
        occupancy = Counter(npc.location_id for npc in simulation.npcs.values())
        active_location_counts.append(sum(1 for count in occupancy.values() if count > 0))
        peak_location_occupancy = max(peak_location_occupancy, max(occupancy.values(), default=0))
        peak_hunger_seen = max(peak_hunger_seen, max(npc.hunger for npc in simulation.npcs.values()))
        for line in lines:
            action_counts[_classify_event(line)] += 1

    final_location_counts = Counter(npc.location_id for npc in simulation.npcs.values())
    final_hunger_by_npc = {npc.name: round(npc.hunger, 1) for npc in simulation.npcs.values()}
    final_money_by_npc = {npc.name: npc.money for npc in simulation.npcs.values()}
    starving_npc_count = sum(1 for npc in simulation.npcs.values() if npc.hunger >= 90.0)
    zero_money_npc_count = sum(1 for npc in simulation.npcs.values() if npc.money <= 0)
    average_final_hunger = sum(npc.hunger for npc in simulation.npcs.values()) / max(1, len(simulation.npcs))
    average_active_locations = sum(active_location_counts) / max(1, len(active_location_counts))
    diversity_score = average_active_locations / max(1, len(simulation.world.locations))
    activity_total = sum(action_counts.values())
    activity_score = min(1.0, activity_total / max(1, turns * len(simulation.npcs) * 0.65))
    stability_score = max(0.0, 1.0 - (starving_npc_count / max(1, len(simulation.npcs))))
    circulation_score = round((0.4 * diversity_score) + (0.35 * activity_score) + (0.25 * stability_score), 3)

    flags: list[str] = []
    if average_active_locations < 4.0 or min(active_location_counts, default=0) < 3:
        flags.append("location_collapse_risk")
    if peak_location_occupancy >= max(1, len(simulation.npcs) - 1):
        flags.append("hard_clustering")
    if starving_npc_count > 1:
        flags.append("npc_starvation")
    if simulation.world.market.scarcity_index >= 1.5:
        flags.append("food_scarcity")

    return CirculationReport(
        turns=turns,
        average_active_locations=round(average_active_locations, 3),
        min_active_locations=min(active_location_counts, default=0),
        max_active_locations=max(active_location_counts, default=0),
        peak_location_occupancy=peak_location_occupancy,
        peak_hunger_seen=round(peak_hunger_seen, 3),
        average_final_hunger=round(average_final_hunger, 3),
        starving_npc_count=starving_npc_count,
        zero_money_npc_count=zero_money_npc_count,
        scarcity_index=round(simulation.world.market.scarcity_index, 3),
        circulation_score=circulation_score,
        action_counts=dict(action_counts),
        final_location_counts=dict(final_location_counts),
        final_hunger_by_npc=final_hunger_by_npc,
        final_money_by_npc=final_money_by_npc,
        flags=flags,
    )


def export_circulation_report_json(path: str | Path, report: CirculationReport) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    return output_path


def _classify_event(line: str) -> str:
    if (
        " moves to " in line
        or " heads toward " in line
        or " sets out toward " in line
        or " arrives at " in line
    ):
        return "move"
    if " buys " in line:
        return "buy"
    if " shares a rumor " in line:
        return "share_rumor"
    if " eats " in line:
        return "eat"
    if (
        " works and produces " in line
        or " bakes " in line
        or " cooks " in line
        or " forages " in line
        or " gathers emergency " in line
        or " secures a small backup " in line
        or " completes " in line
    ):
        return "work"
    return "other"
