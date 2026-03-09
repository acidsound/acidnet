from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from acidnet.llm import TradeDialogueIntent
from acidnet.simulator import Simulation
from acidnet.simulator.models import Rumor, RumorCategory
from acidnet.training.experiment_registry import recommended_experiment_order
from acidnet.training.teacher_prompts import TeacherConfig, dialogue_user_prompt, planner_user_prompt, teacher_system_prompt

WEATHER_VARIANTS = ("dry_wind", "clear", "cool_rain", "storm_front", "market_day", "dusty_heat")
EDIBLE_ITEMS = ("bread", "fish", "stew", "wheat")

RUMOR_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "stub": "bread_price",
        "origin": "npc.mara",
        "subject": "market",
        "category": RumorCategory.ECONOMY,
        "content": "Mara expects bread prices to rise before the next market bell.",
        "confidence": 0.66,
        "value": 0.72,
    },
    {
        "stub": "river_catch",
        "origin": "npc.toma",
        "subject": "riverside",
        "category": RumorCategory.EVENT,
        "content": "Toma says the river is running fast and the fish are shifting north.",
        "confidence": 0.63,
        "value": 0.52,
    },
    {
        "stub": "shrine_traveler",
        "origin": "npc.serin",
        "subject": "shrine",
        "category": RumorCategory.SOCIAL,
        "content": "A traveler left an offering at the shrine and asked about the village guard.",
        "confidence": 0.58,
        "value": 0.61,
    },
    {
        "stub": "tool_shortage",
        "origin": "npc.doran",
        "subject": "smithy",
        "category": RumorCategory.SHORTAGE,
        "content": "Doran is warning people that spare tools may run short if field repairs keep rising.",
        "confidence": 0.69,
        "value": 0.78,
    },
)


@dataclass(slots=True)
class PromptPackRow:
    custom_id: str
    teacher_model: str
    task: str
    system_prompt: str
    user_prompt: str
    metadata: dict[str, Any]


def generate_demo_prompt_pack(num_turns: int = 6, config: TeacherConfig | None = None) -> list[PromptPackRow]:
    config = config or TeacherConfig()
    simulation = Simulation.create_demo()
    rows: list[PromptPackRow] = []
    rng = random.Random(7)

    for turn in range(max(1, num_turns)):
        rows.extend(_collect_turn_rows(simulation, config, scenario_id="demo_base", turn=turn, rng=rng))
        simulation.advance_turn(1)
    return rows


def generate_synthetic_prompt_pack(
    *,
    num_scenarios: int = 128,
    turns_per_scenario: int = 4,
    config: TeacherConfig | None = None,
    seed: int = 7,
) -> list[PromptPackRow]:
    config = config or TeacherConfig()
    rows: list[PromptPackRow] = []
    rng = random.Random(seed)

    for scenario_index in range(max(1, num_scenarios)):
        simulation = Simulation.create_demo()
        scenario_id = f"scenario_{scenario_index:04d}"
        _apply_scenario_variation(simulation, scenario_id=scenario_id, rng=rng)
        for turn in range(max(1, turns_per_scenario)):
            rows.extend(_collect_turn_rows(simulation, config, scenario_id=scenario_id, turn=turn, rng=rng))
            simulation.advance_turn(1)
    return rows


def export_prompt_pack_jsonl(path: str | Path, rows: list[PromptPackRow]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")
    return output_path


def export_prompt_pack_parquet(path: str | Path, rows: list[PromptPackRow]) -> Path:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError(
            "Parquet export requires pyarrow. Install it with `python -m pip install -e .[training]`."
        ) from exc

    records = [_row_to_record(row) for row in rows]
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(records)
    pq.write_table(table, output_path)
    return output_path


def _collect_turn_rows(
    simulation: Simulation,
    config: TeacherConfig,
    *,
    scenario_id: str,
    turn: int,
    rng: random.Random,
) -> list[PromptPackRow]:
    rows: list[PromptPackRow] = []
    candidate_order = [candidate.key for candidate in recommended_experiment_order()]

    for npc in simulation.npcs.values():
        dialogue_cases = _dialogue_interactions(simulation, npc.npc_id, turn=turn, rng=rng)
        planner_case_id, planner_interaction = dialogue_cases[0]
        sample = _build_world_sample(simulation, npc.npc_id, interaction=planner_interaction)
        metadata = _row_metadata(
            candidate_order=candidate_order,
            scenario_id=scenario_id,
            npc_id=npc.npc_id,
            turn=turn,
            player_location=simulation.player.location_id,
            interaction_case=planner_case_id,
            interaction_mode=planner_interaction["player_goal"],
        )
        rows.append(
            PromptPackRow(
                custom_id=f"planner.{scenario_id}.{turn}.{npc.npc_id}",
                teacher_model=config.teacher_model,
                task="planner",
                system_prompt=teacher_system_prompt(config),
                user_prompt=planner_user_prompt(sample),
                metadata=metadata,
            )
        )
        for interaction_case, interaction in dialogue_cases:
            sample = _build_world_sample(simulation, npc.npc_id, interaction=interaction)
            dialogue_metadata = _row_metadata(
                candidate_order=candidate_order,
                scenario_id=scenario_id,
                npc_id=npc.npc_id,
                turn=turn,
                player_location=simulation.player.location_id,
                interaction_case=interaction_case,
                interaction_mode=interaction["player_goal"],
            )
            custom_id = (
                f"dialogue.{scenario_id}.{turn}.{npc.npc_id}"
                if interaction_case == "base"
                else f"dialogue.{scenario_id}.{turn}.{npc.npc_id}.{interaction_case}"
            )
            rows.append(
                PromptPackRow(
                    custom_id=custom_id,
                    teacher_model=config.teacher_model,
                    task="dialogue",
                    system_prompt=teacher_system_prompt(config),
                    user_prompt=dialogue_user_prompt(sample),
                    metadata=dialogue_metadata,
                )
            )
    return rows


def _apply_scenario_variation(simulation: Simulation, *, scenario_id: str, rng: random.Random) -> None:
    simulation.world.tick = rng.randint(0, 720)
    simulation.world.day = 1 + (simulation.world.tick // (12 * 60 * 24))
    simulation.world.weather = rng.choice(WEATHER_VARIANTS)
    location_ids = list(simulation.world.locations)

    simulation.player.location_id = rng.choice(location_ids)
    simulation.player.hunger = round(rng.uniform(8.0, 68.0), 1)
    simulation.player.money = rng.randint(8, 90)
    simulation.player.inventory = _jitter_inventory(dict(simulation.player.inventory), rng, allow_tool=False)
    if not any(qty > 0 for qty in simulation.player.inventory.values()):
        simulation.player.inventory["bread"] = 1

    for npc in simulation.npcs.values():
        location_options = {npc.location_id, npc.home_location_id, npc.workplace_id}
        if npc.location_id in simulation.world.locations:
            location_options.update(simulation.world.locations[npc.location_id].neighbors)
        valid_options = [loc_id for loc_id in location_options if loc_id in simulation.world.locations]
        npc.location_id = rng.choice(valid_options)
        npc.hunger = round(min(95.0, max(5.0, npc.hunger + rng.uniform(-8.0, 26.0))), 1)
        npc.money = max(0, npc.money + rng.randint(-12, 20))
        npc.inventory = _jitter_inventory(dict(npc.inventory), rng, allow_tool=True)
        for relationship in npc.relationships.values():
            relationship.trust = _clamp(relationship.trust + rng.uniform(-0.2, 0.2), -1.0, 1.0)
            relationship.closeness = _clamp(relationship.closeness + rng.uniform(-0.2, 0.2), -1.0, 1.0)

    _inject_scenario_rumors(simulation, scenario_id=scenario_id, rng=rng)
    simulation._refresh_market_snapshot()

    for _ in range(rng.randint(0, 2)):
        simulation.advance_turn(1)


def _jitter_inventory(inventory: dict[str, int], rng: random.Random, *, allow_tool: bool) -> dict[str, int]:
    item_ids = ["wheat", "bread", "fish", "stew"]
    if allow_tool:
        item_ids.append("tool")
    for item_id in item_ids:
        delta = rng.randint(-2, 3)
        next_value = max(0, inventory.get(item_id, 0) + delta)
        if next_value == 0:
            inventory.pop(item_id, None)
        else:
            inventory[item_id] = next_value
    return inventory


def _inject_scenario_rumors(simulation: Simulation, *, scenario_id: str, rng: random.Random) -> None:
    selected_templates = rng.sample(list(RUMOR_TEMPLATES), k=rng.randint(1, min(3, len(RUMOR_TEMPLATES))))
    for index, template in enumerate(selected_templates):
        rumor_id = f"rumor.synthetic.{scenario_id}.{template['stub']}.{index}"
        rumor = Rumor(
            rumor_id=rumor_id,
            origin_npc_id=template["origin"],
            subject_id=template["subject"],
            content=template["content"],
            category=template["category"],
            confidence=_clamp(template["confidence"] + rng.uniform(-0.08, 0.08), 0.25, 0.95),
            value=_clamp(template["value"] + rng.uniform(-0.1, 0.1), 0.1, 1.0),
            distortion=_clamp(rng.uniform(0.0, 0.2), 0.0, 1.0),
            hop_count=rng.randint(0, 4),
            created_tick=max(0, simulation.world.tick - rng.randint(0, 120)),
            last_shared_tick=simulation.world.tick,
        )
        simulation.rumors[rumor_id] = rumor
        carriers = [template["origin"]]
        carriers.extend(rng.sample(list(simulation.npcs), k=rng.randint(1, 3)))
        for npc_id in carriers:
            if rumor_id not in simulation.npcs[npc_id].known_rumor_ids:
                simulation.npcs[npc_id].known_rumor_ids.append(rumor_id)


def _build_world_sample(simulation: Simulation, npc_id: str, *, interaction: dict[str, str]) -> dict[str, Any]:
    npc = simulation.npcs[npc_id]
    persona = simulation.personas[npc.persona_id]
    location = simulation.world.locations[npc.location_id]
    rumors = [simulation.rumors[rumor_id].content for rumor_id in npc.known_rumor_ids if rumor_id in simulation.rumors]
    buy_options = _trade_option_records(simulation.player_trade_options(npc_id, mode="buy"))
    sell_options = _trade_option_records(simulation.player_trade_options(npc_id, mode="sell"))
    ask_options = _trade_option_records(simulation.player_trade_options(npc_id, mode="ask"))
    give_options = _trade_option_records(simulation.player_trade_options(npc_id, mode="give"))
    debt_options = _trade_option_records(simulation.player_trade_options(npc_id, mode="debt"))
    nearby_npcs = [
        {
            "npc_id": other.npc_id,
            "name": other.name,
            "profession": other.profession,
            "relationship_score": round(simulation._relationship_score(npc, other.npc_id), 3),
        }
        for other in simulation.npcs.values()
        if other.location_id == npc.location_id and other.npc_id != npc.npc_id
    ]
    relationship_summary = [
        {
            "other_npc_id": relation.other_npc_id,
            "trust": relation.trust,
            "closeness": relation.closeness,
            "fear": relation.fear,
            "respect": relation.respect,
        }
        for relation in npc.relationships.values()
    ]
    recent_memories = [memory.model_dump(mode="json") for memory in simulation.memories.get(npc_id, [])[-4:]]

    npc_payload = {
        "npc_id": npc.npc_id,
        "name": npc.name,
        "profession": npc.profession,
        "persona_id": npc.persona_id,
        "traits": list(npc.traits),
        "location_id": npc.location_id,
        "home_location_id": npc.home_location_id,
        "home_location_name": simulation.world.locations[npc.home_location_id].name
        if npc.home_location_id in simulation.world.locations
        else None,
        "workplace_id": npc.workplace_id,
        "workplace_name": simulation.world.locations[npc.workplace_id].name
        if npc.workplace_id in simulation.world.locations
        else None,
        "inventory": dict(npc.inventory),
        "money": npc.money,
        "hunger": npc.hunger,
        "buy_options": buy_options,
        "sell_options": sell_options,
        "ask_options": ask_options,
        "give_options": give_options,
        "debt_options": debt_options,
        "goals": list(npc.goals),
        "beliefs": [belief.model_dump(mode="json") for belief in simulation._derive_beliefs(npc)],
        "known_rumors": rumors,
        "recent_memories": recent_memories,
        "relationships": relationship_summary,
        "current_intent": npc.current_intent.model_dump(mode="json") if npc.current_intent is not None else None,
        "is_vendor": npc.is_vendor,
    }
    trade_fact = interaction.get("trade_fact")
    if trade_fact is not None:
        npc_payload["trade_fact"] = dict(trade_fact)

    return {
        "world": {
            "tick": simulation.world.tick,
            "day": simulation.world.day,
            "weather": simulation.world.weather,
            "scarcity_index": simulation.world.market.scarcity_index,
            "market_prices": {
                item_id: state.current_price for item_id, state in sorted(simulation.world.market.items.items())
            },
            "recent_events": list(simulation.tick_log)[-6:],
        },
        "location": location.model_dump(mode="json"),
        "player": {
            "player_id": simulation.player.player_id,
            "name": simulation.player.name,
            "location_id": simulation.player.location_id,
            "inventory": dict(simulation.player.inventory),
            "money": simulation.player.money,
            "hunger": simulation.player.hunger,
            "known_rumors": list(simulation.player.known_rumor_ids),
        },
        "npc": npc_payload,
        "persona": persona.model_dump(mode="json"),
        "nearby_npcs": nearby_npcs,
        "known_player_rumors": [
            simulation.rumors[rumor_id].content
            for rumor_id in simulation.player.known_rumor_ids
            if rumor_id in simulation.rumors
        ],
        "interaction_context": interaction,
    }


def _dialogue_interactions(
    simulation: Simulation,
    npc_id: str,
    *,
    turn: int,
    rng: random.Random,
) -> list[tuple[str, dict[str, Any]]]:
    interactions: list[tuple[str, dict[str, Any]]] = [("base", _base_interaction_context(simulation, npc_id, rng=rng))]
    seen_prompts = {interactions[0][1]["player_prompt"]}

    for anchor_case_id, anchor_case in _prompt_only_eval_anchor_contexts(simulation, npc_id):
        if anchor_case["player_prompt"] in seen_prompts:
            continue
        interactions.append((anchor_case_id, anchor_case))
        seen_prompts.add(anchor_case["player_prompt"])

    # Always keep one explicit hunger-direct example in the prompt pack so
    # no-food redirects stay present even when the rotating hard case lands elsewhere.
    hunger_case = (
        "hunger_direct",
        {
            "player_prompt": "I am hungry.",
            "player_goal": "direct_say",
            "expected_focus": "React to immediate need and mention relevant food reality only if the NPC can ground it in state.",
        },
    )
    interactions.append(hunger_case)
    seen_prompts.add(hunger_case[1]["player_prompt"])

    hard_case_id, hard_case = _hard_direct_say_context(simulation, npc_id, turn=turn)
    if hard_case["player_prompt"] not in seen_prompts:
        interactions.append((hard_case_id, hard_case))
        seen_prompts.add(hard_case["player_prompt"])

    for extra_case_id, extra_case in _supplemental_food_pressure_contexts(simulation, npc_id):
        if extra_case["player_prompt"] in seen_prompts:
            continue
        interactions.append((extra_case_id, extra_case))
        seen_prompts.add(extra_case["player_prompt"])
    return interactions


def _prompt_only_eval_anchor_contexts(
    simulation: Simulation,
    npc_id: str,
) -> list[tuple[str, dict[str, Any]]]:
    npc = simulation.npcs[npc_id]
    contexts: list[tuple[str, dict[str, Any]]] = [
        (
            "origin_direct",
            {
                "player_prompt": "Where did you come from?",
                "player_goal": "direct_say",
                "expected_focus": "Answer the origin or usual-place question directly before any extra detail.",
            },
        ),
        (
            "identity_direct",
            {
                "player_prompt": "I do not think we have met. Who are you?",
                "player_goal": "direct_say",
                "expected_focus": "Introduce the NPC directly and briefly, without drifting into generic village commentary.",
            },
        ),
    ]
    if npc.is_vendor:
        contexts.append(
            (
                "trade_request_stock",
                {
                    "player_prompt": "I need food. What can you sell me right now?",
                    "player_goal": "trade_request",
                    "expected_focus": "Answer from the current sellable food contract or plainly say when no edible sale is available.",
                },
            )
        )
    if npc.known_rumor_ids:
        contexts.append(
            (
                "rumor_request_known",
                {
                    "player_prompt": "Have you heard any useful rumors?",
                    "player_goal": "rumor_request",
                    "expected_focus": "Surface a known rumor directly instead of falling back to generic atmosphere.",
                },
            )
        )
    return contexts


def _base_interaction_context(simulation: Simulation, npc_id: str, *, rng: random.Random) -> dict[str, Any]:
    npc = simulation.npcs[npc_id]
    prompts: list[dict[str, str]] = [
        {
            "player_prompt": f"Hello {npc.name}. What is going on around {simulation.world.locations[npc.location_id].name}?",
            "player_goal": "talk",
            "expected_focus": "Give a grounded in-world response that reflects current mood and social context.",
        },
        {
            "player_prompt": "You look tense. What changed around here today?",
            "player_goal": "direct_say",
            "expected_focus": "Handle a natural player utterance without leaving the current world state.",
        }
    ]
    if npc.known_rumor_ids:
        prompts.append(
            {
                "player_prompt": f"{npc.name}, have you heard any useful rumors today?",
                "player_goal": "rumor_request",
                "expected_focus": "Surface the most relevant rumor without breaking world facts.",
            }
        )
    if npc.is_vendor:
        prompts.append(
            {
                "player_prompt": f"I need food. What can you sell me right now, {npc.name}?",
                "player_goal": "trade_request",
                "expected_focus": "Mention available stock, price pressure, and the NPC's trade personality.",
            }
        )
    if npc.profession == "farmer":
        prompts.append(
            {
                "player_prompt": "How are the fields holding up?",
                "player_goal": "direct_say",
                "expected_focus": "Talk about crop pressure, weather, and grain supply if relevant.",
            }
        )
    if npc.profession == "guard":
        prompts.append(
            {
                "player_prompt": "Anything I should avoid causing trouble over?",
                "player_goal": "direct_say",
                "expected_focus": "Reflect order, danger, and any rumor-driven tension in the village.",
            }
        )
    if npc.profession == "priest":
        prompts.append(
            {
                "player_prompt": "Who in the village seems to need help most?",
                "player_goal": "direct_say",
                "expected_focus": "Respond with empathy and grounded social observation.",
            }
        )
    return rng.choice(prompts)


def _hard_direct_say_context(simulation: Simulation, npc_id: str, *, turn: int) -> tuple[str, dict[str, Any]]:
    npc = simulation.npcs[npc_id]
    cases: list[tuple[str, dict[str, Any]]] = [
        (
            "origin_direct",
            {
                "player_prompt": "Where did you come from?",
                "player_goal": "direct_say",
                "expected_focus": "Answer the origin or usual-place question directly before any extra detail.",
            },
        ),
        (
            "identity_direct",
            {
                "player_prompt": "I do not think we have met. Who are you?",
                "player_goal": "direct_say",
                "expected_focus": "Introduce the NPC directly and briefly, without drifting into generic village commentary.",
            },
        ),
        (
            "hunger_direct",
            {
                "player_prompt": "I am hungry.",
                "player_goal": "direct_say",
                "expected_focus": "React to immediate need and mention relevant food reality only if the NPC can ground it in state.",
            },
        ),
    ]
    if npc.profession == "baker":
        cases.append(
            (
                "baker_stock_direct",
                {
                    "player_prompt": "If I am hungry, can you actually spare bread right now?",
                    "player_goal": "direct_say",
                    "expected_focus": "Answer with current bread reality, not generic market chatter.",
                },
            )
        )
    if npc.profession == "merchant":
        cases.append(
            (
                "merchant_stock_direct",
                {
                    "player_prompt": "What do you really have on hand right now?",
                    "player_goal": "direct_say",
                    "expected_focus": "Answer with grounded visible stock or scarcity, not a generic sales line.",
                },
            )
        )
    if npc.is_vendor:
        cases.extend(_vendor_trade_hard_cases(simulation, npc_id))
    if npc.profession == "guard":
        cases.append(
            (
                "guard_safety_direct",
                {
                    "player_prompt": "What should I avoid if I do not want trouble today?",
                    "player_goal": "direct_say",
                    "expected_focus": "Answer the safety question directly from visible tension, rumors, and route conditions.",
                },
            )
        )
    if npc.profession == "farmer":
        cases.append(
            (
                "farmer_recovery_direct",
                {
                    "player_prompt": "Can the fields recover if the weather turns?",
                    "player_goal": "direct_say",
                    "expected_focus": "Answer the recovery question directly with field stress and weather context.",
                },
            )
        )
    if npc.profession == "priest":
        cases.append(
            (
                "priest_need_direct",
                {
                    "player_prompt": "Who needs help first today?",
                    "player_goal": "direct_say",
                    "expected_focus": "Name the clearest need or say that no single case stands out.",
                },
            )
        )
    if npc.profession == "fisher":
        cases.append(
            (
                "fisher_route_direct",
                {
                    "player_prompt": "Is the riverside still worth the walk today?",
                    "player_goal": "direct_say",
                    "expected_focus": "Answer the route and catch question directly with weather or catch pressure.",
                },
            )
        )
    if npc.profession == "blacksmith":
        cases.append(
            (
                "smith_supply_direct",
                {
                    "player_prompt": "Are you holding tools back, or can people still get one?",
                    "player_goal": "direct_say",
                    "expected_focus": "Answer directly about tool availability and pressure.",
                },
            )
        )
    case_index = (sum(ord(ch) for ch in npc_id) + turn) % len(cases)
    return cases[case_index]


def _supplemental_food_pressure_contexts(
    simulation: Simulation,
    npc_id: str,
) -> list[tuple[str, dict[str, Any]]]:
    npc = simulation.npcs[npc_id]
    has_edible_goods = _has_edible_inventory(npc.inventory)
    if has_edible_goods:
        return [
            (
                "food_offer_direct",
                {
                    "player_prompt": "I am hungry. What can you actually spare right now?",
                    "player_goal": "direct_say",
                    "expected_focus": "Offer only edible help that exists in current state and keep the answer direct.",
                },
            )
        ]
    return [
        (
            "no_food_hunger_spare_direct",
            {
                "player_prompt": "I am hungry. Do you have food to spare?",
                "player_goal": "direct_say",
                "expected_focus": "Say plainly when there is no edible food in state and redirect instead of inventing stock.",
            },
        ),
        (
            "no_food_hunger_redirect_direct",
            {
                "player_prompt": "I am hungry. Should I try the bakery or the shrine instead?",
                "player_goal": "direct_say",
                "expected_focus": "Confirm the likely food source if the NPC has no edible food and do not pretend otherwise.",
            },
        ),
    ]


def _row_metadata(
    *,
    candidate_order: list[str],
    scenario_id: str,
    npc_id: str,
    turn: int,
    player_location: str,
    interaction_case: str,
    interaction_mode: str,
) -> dict[str, Any]:
    return {
        "candidate_order": candidate_order,
        "scenario_id": scenario_id,
        "npc_id": npc_id,
        "turn": turn,
        "player_location": player_location,
        "interaction_case": interaction_case,
        "interaction_mode": interaction_mode,
    }


def _row_to_record(row: PromptPackRow) -> dict[str, Any]:
    metadata = row.metadata
    return {
        "custom_id": row.custom_id,
        "teacher_model": row.teacher_model,
        "task": row.task,
        "system_prompt": row.system_prompt,
        "user_prompt": row.user_prompt,
        "scenario_id": metadata.get("scenario_id"),
        "npc_id": metadata.get("npc_id"),
        "turn": metadata.get("turn"),
        "player_location": metadata.get("player_location"),
        "metadata_json": json.dumps(metadata, ensure_ascii=False),
    }


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _has_edible_inventory(inventory: dict[str, int]) -> bool:
    return any(inventory.get(item_id, 0) > 0 for item_id in EDIBLE_ITEMS)


def _trade_option_records(options: list[Any]) -> list[dict[str, Any]]:
    return [
        {"item": option.item, "quantity": option.quantity, "price": option.price}
        for option in options
    ]


def _vendor_trade_hard_cases(simulation: Simulation, npc_id: str) -> list[tuple[str, dict[str, Any]]]:
    buy_options = [option for option in simulation.player_trade_options(npc_id, mode="buy") if option.quantity > 0]
    if not buy_options:
        return []

    primary = buy_options[0]
    cases: list[tuple[str, dict[str, Any]]] = []

    quote_fact = _trade_fact_payload(
        simulation,
        npc_id,
        TradeDialogueIntent(kind="trade_quote", item=primary.item),
    )
    if quote_fact is not None:
        cases.append(
            (
                "vendor_price_direct",
                {
                    "player_prompt": f"How much is {primary.item} today?",
                    "player_goal": "direct_say",
                    "expected_focus": "Quote the exact current vendor price for the named item from live trade adjudication.",
                    "trade_fact": quote_fact,
                    "trade_parse_target": {"kind": "trade_quote", "item": primary.item},
                },
            )
        )

    stock_fact = _trade_fact_payload(
        simulation,
        npc_id,
        TradeDialogueIntent(kind="trade_stock"),
    )
    if stock_fact is not None:
        cases.append(
            (
                "vendor_stock_direct",
                {
                    "player_prompt": "What can you sell right now?",
                    "player_goal": "direct_say",
                    "expected_focus": "Answer from the current sellable stock contract instead of generic market flavor.",
                    "trade_fact": stock_fact,
                    "trade_parse_target": {"kind": "trade_stock"},
                },
            )
        )

    accepted_fact = _trade_fact_payload(
        simulation,
        npc_id,
        TradeDialogueIntent(kind="trade_offer", item=primary.item, quantity=1, offered_total_gold=primary.price),
    )
    if accepted_fact is not None:
        cases.append(
            (
                "vendor_offer_accept_direct",
                {
                    "player_prompt": f"Would you take {primary.price} gold for one {primary.item}?",
                    "player_goal": "direct_say",
                    "expected_focus": "Answer from the current accepted trade outcome instead of restating the market price abstractly.",
                    "trade_fact": accepted_fact,
                    "trade_parse_target": {
                        "kind": "trade_offer",
                        "item": primary.item,
                        "quantity": 1,
                        "offered_total_gold": primary.price,
                    },
                },
            )
        )

    counter_offer_total, counter_fact = _counter_offer_case(simulation, npc_id, primary.item, listed_unit_price=primary.price)
    if counter_offer_total is not None and counter_fact is not None:
        cases.append(
            (
                "vendor_offer_counter_direct",
                {
                    "player_prompt": f"Would you take {counter_offer_total} gold for one {primary.item}?",
                    "player_goal": "direct_say",
                    "expected_focus": "Answer from the current counteroffer outcome and keep the exact adjudicated number.",
                    "trade_fact": counter_fact,
                    "trade_parse_target": {
                        "kind": "trade_offer",
                        "item": primary.item,
                        "quantity": 1,
                        "offered_total_gold": counter_offer_total,
                    },
                },
            )
        )

    negative_fact = _trade_fact_payload(
        simulation,
        npc_id,
        TradeDialogueIntent(kind="trade_offer", item=primary.item, quantity=1, offered_total_gold=-2),
    )
    if negative_fact is not None:
        cases.append(
            (
                "vendor_negative_offer_direct",
                {
                    "player_prompt": f"Would you take -2 gold for one {primary.item}?",
                    "player_goal": "direct_say",
                    "expected_focus": "Reject invalid negative-gold bargaining plainly from the server-authored trade outcome.",
                    "trade_fact": negative_fact,
                    "trade_parse_target": {
                        "kind": "trade_offer",
                        "item": primary.item,
                        "quantity": 1,
                        "offered_total_gold": -2,
                    },
                },
            )
        )

    cases.append(
        (
            "vendor_debt_direct",
            {
                "player_prompt": f"Could I take one {primary.item} on debt?",
                "player_goal": "direct_say",
                "expected_focus": "Answer from the current debt contract instead of guessing from market prices.",
            },
        )
    )

    if primary.item in EDIBLE_ITEMS:
        cases.append(
            (
                "vendor_free_food_direct",
                {
                    "player_prompt": f"I am hungry. Can you give me one {primary.item} for free?",
                    "player_goal": "direct_say",
                    "expected_focus": "Ground any free or spare help in the current zero-cash sharing contract instead of drifting into prices.",
                },
            )
        )
    return cases


def _trade_fact_payload(
    simulation: Simulation,
    npc_id: str,
    intent: TradeDialogueIntent,
) -> dict[str, Any] | None:
    npc = simulation.npcs[npc_id]
    outcome = simulation._trade_dialogue_outcome(npc, intent)
    if outcome is None:
        return None
    return simulation._dialogue_trade_fact(outcome).model_dump(mode="json")


def _counter_offer_case(
    simulation: Simulation,
    npc_id: str,
    item: str,
    *,
    listed_unit_price: int,
) -> tuple[int | None, dict[str, Any] | None]:
    for offered_total in range(0, max(0, listed_unit_price)):
        trade_fact = _trade_fact_payload(
            simulation,
            npc_id,
            TradeDialogueIntent(kind="trade_offer", item=item, quantity=1, offered_total_gold=offered_total),
        )
        if trade_fact is None:
            continue
        if trade_fact.get("counter_total_gold") is not None:
            return offered_total, trade_fact
    return None, None
