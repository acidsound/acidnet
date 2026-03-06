from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path

from acidnet.llm.prompt_builder import normalize_interaction_mode
from acidnet.training.openai_batch import TeacherOutputRow, export_teacher_output_jsonl

FOOD_VALUES = {"stew": 34.0, "bread": 26.0, "fish": 21.0, "wheat": 10.0}


@dataclass(frozen=True, slots=True)
class BootstrapTeacherArtifacts:
    output_path: str
    rows: int
    tasks: list[str]


def build_bootstrap_teacher_outputs(
    prompt_rows: list[dict],
    *,
    tasks: tuple[str, ...] = ("dialogue", "planner"),
) -> list[TeacherOutputRow]:
    allowed_tasks = set(tasks)
    rows: list[TeacherOutputRow] = []
    for prompt_row in prompt_rows:
        task = str(prompt_row.get("task", ""))
        if task not in allowed_tasks:
            continue
        sample = _extract_world_sample(prompt_row["user_prompt"])
        if task == "dialogue":
            assistant_json = _bootstrap_dialogue_output(sample)
        elif task == "planner":
            assistant_json = _bootstrap_planner_output(sample)
        else:
            continue
        rows.append(
            TeacherOutputRow(
                custom_id=prompt_row["custom_id"],
                assistant_json=assistant_json,
                metadata={
                    "teacher_type": "bootstrap_rule_teacher",
                    "task": task,
                    "npc_id": sample["npc"]["npc_id"],
                    "scenario_id": prompt_row.get("metadata", {}).get("scenario_id"),
                },
            )
        )
    return rows


def export_bootstrap_teacher_outputs(path: str | Path, rows: list[TeacherOutputRow]) -> BootstrapTeacherArtifacts:
    output_path = export_teacher_output_jsonl(path, rows)
    return BootstrapTeacherArtifacts(
        output_path=str(output_path),
        rows=len(rows),
        tasks=sorted({row.metadata.get("task", "") for row in rows}),
    )


def bootstrap_teacher_artifacts_to_dict(artifacts: BootstrapTeacherArtifacts) -> dict[str, object]:
    return asdict(artifacts)


def _extract_world_sample(user_prompt: str) -> dict:
    marker = "World sample:"
    _, sample_text = user_prompt.split(marker, 1)
    return ast.literal_eval(sample_text.strip())


def _bootstrap_dialogue_output(sample: dict) -> dict:
    npc = sample["npc"]
    world = sample["world"]
    interaction = sample["interaction_context"]
    location = sample["location"]
    persona_summary = _persona_summary(npc)
    situation_summary = _situation_summary(sample)
    response = _dialogue_response(sample)
    return {
        "task": "dialogue",
        "npc_id": npc["npc_id"],
        "persona_summary": persona_summary,
        "situation_summary": situation_summary,
        "player_prompt": interaction["player_prompt"],
        "interaction_goal": interaction["player_goal"],
        "target_style_tags": _style_tags(sample),
        "response": response,
        "memory_write": {
            "summary": f"Spoke with the player at {location['name']} during {world['weather']}.",
            "importance": 0.45,
        },
    }


def _bootstrap_planner_output(sample: dict) -> dict:
    npc = sample["npc"]
    location_id = npc["location_id"]
    hunger = float(npc["hunger"])
    inventory = npc["inventory"]
    nearby_npcs = sample.get("nearby_npcs", [])
    food_item = _best_food_in_inventory(inventory)
    if hunger >= 45 and food_item is not None:
        top_goal = f"eat:{food_item}"
        intent = {
            "intent_type": "eat",
            "target_id": food_item,
            "target_location": location_id,
            "reason": "Hunger is pressing and food is already in inventory.",
            "dialogue": "",
            "priority": 0.95,
        }
    elif sample["npc"].get("known_rumors") and nearby_npcs:
        target = max(nearby_npcs, key=lambda other: other.get("relationship_score", 0.0))
        top_goal = f"share_rumor:{target['npc_id']}"
        intent = {
            "intent_type": "share_rumor",
            "target_id": target["npc_id"],
            "target_location": location_id,
            "reason": "A nearby social contact can receive useful information now.",
            "dialogue": "I heard something worth passing along.",
            "priority": 0.82,
        }
    elif npc.get("workplace_id") and npc["workplace_id"] != location_id:
        top_goal = f"move:{npc['workplace_id']}"
        intent = {
            "intent_type": "move",
            "target_id": "",
            "target_location": npc["workplace_id"],
            "reason": "Routine work is more valuable from the workplace.",
            "dialogue": "",
            "priority": 0.7,
        }
    else:
        top_goal = f"work:{npc.get('workplace_id') or location_id}"
        intent = {
            "intent_type": "work",
            "target_id": "",
            "target_location": npc.get("workplace_id") or location_id,
            "reason": "Routine work keeps the local economy moving.",
            "dialogue": "",
            "priority": 0.6,
        }
    return {
        "task": "planner",
        "npc_id": npc["npc_id"],
        "top_goal": top_goal,
        "intent": intent,
        "memory_write": {
            "summary": f"Committed to {intent['intent_type']} at {intent['target_location']}.",
            "importance": 0.35,
        },
    }


def _persona_summary(npc: dict) -> str:
    parts = [npc["profession"]]
    if npc.get("is_vendor"):
        parts.append("vendor")
    if npc.get("beliefs"):
        parts.append("belief-aware")
    return ", ".join(parts)


def _situation_summary(sample: dict) -> str:
    npc = sample["npc"]
    world = sample["world"]
    location = sample["location"]
    details = [f"at {location['name']}", f"weather {world['weather']}"]
    if npc["hunger"] >= 45:
        details.append("under hunger pressure")
    if world["scarcity_index"] >= 1.0:
        details.append("with food scarcity pressure")
    if npc.get("known_rumors"):
        details.append("holding live rumors")
    return ", ".join(details)


def _style_tags(sample: dict) -> list[str]:
    npc = sample["npc"]
    tags = [npc["profession"], "grounded", "concise"]
    if npc["hunger"] >= 45:
        tags.append("pressured")
    if npc.get("is_vendor"):
        tags.append("trade-aware")
    if npc.get("known_rumors"):
        tags.append("rumor-aware")
    return tags[:5]


def _dialogue_response(sample: dict) -> str:
    npc = sample["npc"]
    interaction = sample["interaction_context"]
    interaction_mode = normalize_interaction_mode(
        interaction.get("player_goal"),
        player_prompt=interaction.get("player_prompt"),
    )
    world = sample["world"]
    location = sample["location"]
    rumors = npc.get("known_rumors", [])
    goods = [f"{item} x{qty}" for item, qty in npc["inventory"].items() if qty > 0]
    opening = {
        "merchant": "The square moves on coin and timing.",
        "farmer": "The field answers to weather before it answers to people.",
        "baker": "Bread tells the truth about the village faster than gossip does.",
        "cook": "If you want something useful, ask before the pot cools.",
        "blacksmith": "If it matters, keep it plain.",
        "guard": "Keep the peace and we can talk plainly.",
        "fisher": "The river changes moods quicker than most people here.",
        "priest": "Take a breath first. Then ask.",
        "tailor": "Stories and status travel together in this place.",
    }.get(npc["profession"], f"{npc['name']} watches the room before answering.")

    if interaction_mode == "rumor_request" and rumors:
        return f"{opening} The clearest thing going around is this: {rumors[0]}"
    if interaction_mode == "trade_request":
        if goods:
            return f"{opening} Right now I can move {', '.join(goods[:3])}, and the weather is already pushing the market."
        return f"{opening} Stock is thin right now, so I would not promise more than I have."
    if interaction_mode == "direct_say" and npc["profession"] == "farmer":
        return f"{opening} Around {location['name']}, the {world['weather']} is shaping every harvest decision."
    if interaction_mode == "direct_say" and npc["profession"] == "guard":
        if rumors:
            return f"{opening} Tension follows rumor as much as hunger here, so mind the square and listen carefully."
        return f"{opening} Trouble starts when people ignore hunger, coin, and timing."
    if interaction_mode == "direct_say" and npc["profession"] == "priest":
        if npc["hunger"] >= 45:
            return f"{opening} People act shorter with each other when food gets tight, and today you can feel that strain."
        return f"{opening} Watch who looks tired, hungry, or too quiet. That usually tells the truth first."
    if rumors:
        return f"{opening} Something worth hearing is already moving through {location['name']}: {rumors[0]}"
    if npc["hunger"] >= 45:
        return f"{opening} I am keeping one eye on food and one on the weather, same as everyone else."
    return f"{opening} {location['name']} feels steady for the moment, but that can change by dusk."


def _best_food_in_inventory(inventory: dict[str, int]) -> str | None:
    best_item: str | None = None
    best_value = -1.0
    for item, value in FOOD_VALUES.items():
        if inventory.get(item, 0) > 0 and value > best_value:
            best_item = item
            best_value = value
    return best_item
