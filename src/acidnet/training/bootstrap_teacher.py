from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path

from acidnet.llm.prompt_builder import normalize_interaction_mode
from acidnet.llm.trade_dialogue import TradeDialogueOption, TradeDialogueOutcome, render_trade_dialogue_outcome
from acidnet.training.openai_batch import TeacherOutputRow, export_teacher_output_jsonl

FOOD_VALUES = {"stew": 34.0, "bread": 26.0, "fish": 21.0, "wheat": 10.0}
ORIGIN_TOKENS = ("where did you come from", "where are you from", "where do you stay")
IDENTITY_TOKENS = ("who are you", "we have met", "we've met", "first time")
HUNGER_TOKENS = ("i am hungry", "i'm hungry", "hungry")
STOCK_TOKENS = ("what do you have", "on hand", "spare", "sell", "stock", "bread right now", "tool")
FOOD_REQUEST_TOKENS = ("food", "hungry", "eat", "meal", "bread", "stew", "fish", "wheat")
PRICE_TOKENS = ("how much", "price", "prices", "cost", "gold", "coin")
DEBT_TOKENS = ("on debt", "debt", "owe", "credit", "tab")
FREE_REQUEST_TOKENS = ("for free", "free", "spare", "give", "gift", "share")
SAFETY_TOKENS = ("avoid", "trouble", "unsafe", "safe")
RECOVERY_TOKENS = ("recover", "fields", "weather turns")


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
    player_prompt = str(interaction.get("player_prompt", "")).strip()
    normalized_prompt = " ".join(player_prompt.lower().split())
    rumors = npc.get("known_rumors", [])
    buy_options = list(npc.get("buy_options", []))
    debt_options = list(npc.get("debt_options", []))
    ask_options = list(npc.get("ask_options", []))
    goods = [
        f'{option["item"]} x{option["quantity"]}' if option.get("price") is None else f'{option["item"]} x{option["quantity"]} at {option["price"]} gold'
        for option in buy_options
    ]
    edible_goods = [
        f'{option["item"]} x{option["quantity"]}' if option.get("price") is None else f'{option["item"]} x{option["quantity"]} at {option["price"]} gold'
        for option in buy_options
        if option["item"] in FOOD_VALUES
    ]
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

    trade_fact_response = _trade_fact_response(npc)
    if trade_fact_response is not None:
        return trade_fact_response

    direct_response = _direct_dialogue_response(
        sample,
        interaction_mode=interaction_mode,
        normalized_prompt=normalized_prompt,
        goods=goods,
    )
    if direct_response:
        return direct_response

    if interaction_mode == "rumor_request" and rumors:
        return f"The clearest rumor I know is this: {rumors[0]}"
    if interaction_mode == "trade_request":
        quoted_item = _mentioned_trade_item(sample, normalized_prompt)
        quoted_buy = _find_trade_option(buy_options, quoted_item) if quoted_item else None
        if quoted_buy is not None and any(token in normalized_prompt for token in PRICE_TOKENS):
            return f'{opening} {quoted_buy["item"].capitalize()} is {quoted_buy["price"]} gold right now.'
        asks_for_food = any(token in normalized_prompt for token in FOOD_REQUEST_TOKENS)
        if asks_for_food and edible_goods:
            return f"I can sell {', '.join(edible_goods[:3])} right now. The weather is already pushing the food line thin."
        if asks_for_food and not edible_goods:
            return f"{opening} I do not have food to sell from {location['name']} right now. Try the bakery or the tavern before the shelves thin further."
        if any(token in normalized_prompt for token in FREE_REQUEST_TOKENS):
            free_help = _free_help_response(ask_options, normalized_prompt)
            if free_help is not None:
                return free_help
        if goods:
            return f"I can sell {', '.join(goods[:3])} right now. That is all I would promise cleanly."
        return "I am not selling anything cleanly right now."
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


def _direct_dialogue_response(
    sample: dict,
    *,
    interaction_mode: str,
    normalized_prompt: str,
    goods: list[str],
) -> str | None:
    npc = sample["npc"]
    location = sample["location"]
    world = sample["world"]
    rumors = npc.get("known_rumors", [])
    best_food = _best_food_in_inventory(npc["inventory"])
    buy_options = list(npc.get("buy_options", []))
    debt_options = list(npc.get("debt_options", []))
    ask_options = list(npc.get("ask_options", []))
    mentioned_item = _mentioned_trade_item(sample, normalized_prompt)
    if mentioned_item is not None:
        quoted_buy = _find_trade_option(buy_options, mentioned_item)
        quoted_debt = _find_trade_option(debt_options, mentioned_item)
        quoted_ask = _find_trade_option(ask_options, mentioned_item)
        if any(token in normalized_prompt for token in PRICE_TOKENS):
            if quoted_buy is not None:
                if quoted_debt is not None:
                    return f'{quoted_buy["item"].capitalize()} is {quoted_buy["price"]} gold right now, and I can still put it on debt for {quoted_debt["price"]} gold.'
                return f'{quoted_buy["item"].capitalize()} is {quoted_buy["price"]} gold right now.'
            if quoted_debt is not None:
                return f'I will not sell {mentioned_item} cleanly right now, but I can still let it go on debt for {quoted_debt["price"]} gold.'
            return f'I am not offering {mentioned_item} right now.'
        if any(token in normalized_prompt for token in DEBT_TOKENS):
            if quoted_debt is not None:
                return f'I can still let {quoted_debt["item"]} go on debt for {quoted_debt["price"]} gold.'
            return f'I am not putting {mentioned_item} on debt right now.'
        if any(token in normalized_prompt for token in FREE_REQUEST_TOKENS):
            if quoted_ask is not None and quoted_ask["item"] in FOOD_VALUES:
                return f'I can spare {_quantity_phrase(quoted_ask["item"], quoted_ask["quantity"])} for free, but not more than that.'
            if quoted_buy is not None:
                return f'If you want {mentioned_item}, I can sell it cleanly, but I am not giving it away.'

    if interaction_mode != "direct_say":
        return None

    if any(token in normalized_prompt for token in FREE_REQUEST_TOKENS):
        free_help = _free_help_response(ask_options, normalized_prompt)
        if free_help is not None:
            return free_help

    if any(token in normalized_prompt for token in IDENTITY_TOKENS):
        return f'I am {npc["name"]}, the village {npc["profession"]}.'

    if any(token in normalized_prompt for token in ORIGIN_TOKENS):
        home_location = str(npc.get("home_location_name") or "").strip()
        workplace = str(npc.get("workplace_name") or "").strip()
        if home_location and workplace and home_location != workplace:
            return f"I am from {home_location}. Most days my work keeps me close to {workplace}."
        if workplace:
            return f"My work keeps me close to {workplace} most days."
        if home_location:
            return f"I am from {home_location}. I do not range much farther than that."
        return f'I keep close to {location["name"]} most days. Nothing farther than the village has me right now.'

    if any(token in normalized_prompt for token in HUNGER_TOKENS):
        if best_food is not None and npc.get("is_vendor"):
            return f'If you can pay, I still have {best_food} on hand. Do not wait until the shelves thin further.'
        if best_food is not None:
            return f'I still have {best_food} nearby, but not enough to pretend the village is comfortable.'
        return "I do not have food to spare. Try the bakery or the shrine before the square runs thin."

    if any(token in normalized_prompt for token in STOCK_TOKENS):
        if goods:
            return f'I can sell {", ".join(goods[:3])} right now. I will not promise more than that.'
        return "I am not selling anything cleanly right now."

    if npc["profession"] == "guard" and any(token in normalized_prompt for token in SAFETY_TOKENS):
        if world["weather"] == "storm_front":
            return "Keep clear of the riverside and do not test the road while the storm front is pressing through."
        return "Do not crowd hungry people or push a bad bargain in the square. That is how trouble starts here."

    if npc["profession"] == "farmer" and any(token in normalized_prompt for token in RECOVERY_TOKENS):
        if world["weather"] == "cool_rain":
            return "Yes, if the cool rain holds. The field can settle faster than people expect when the ground drinks properly."
        return f"It can recover, but not for free. Right now the {world['weather']} is still deciding how much the field will give back."

    if rumors and "rumor" in normalized_prompt:
        return f'The cleanest rumor I can give is this: {rumors[0]}'

    if "?" in normalized_prompt:
        return f'Around {location["name"]}, I can only answer from what is in front of me right now.'

    return None


def _best_food_in_inventory(inventory: dict[str, int]) -> str | None:
    best_item: str | None = None
    best_value = -1.0
    for item, value in FOOD_VALUES.items():
        if inventory.get(item, 0) > 0 and value > best_value:
            best_item = item
            best_value = value
    return best_item


def _mentioned_trade_item(sample: dict, normalized_prompt: str) -> str | None:
    npc = sample["npc"]
    option_items = {str(option.get("item", "")) for option in npc.get("buy_options", []) + npc.get("debt_options", [])}
    option_items.update(item for item, qty in npc.get("inventory", {}).items() if qty > 0)
    for item in sorted(option_items):
        if item and item in normalized_prompt:
            return item
    return None


def _find_trade_option(options: list[dict], item: str | None) -> dict | None:
    if item is None:
        return None
    for option in options:
        if option.get("item") == item:
            return option
    return None


def _trade_fact_response(npc: dict) -> str | None:
    trade_fact = npc.get("trade_fact")
    if not isinstance(trade_fact, dict):
        return None
    stock = tuple(
        TradeDialogueOption(
            item=str(option.get("item", "")),
            quantity=int(option.get("quantity", 0)),
            price=int(option["price"]) if option.get("price") is not None else None,
        )
        for option in trade_fact.get("stock", [])
    )
    outcome = TradeDialogueOutcome(
        kind=str(trade_fact.get("kind", "")),
        item=trade_fact.get("item"),
        quantity=int(trade_fact.get("quantity", 1) or 1),
        available_quantity=int(trade_fact.get("available_quantity", 0) or 0),
        listed_unit_price=trade_fact.get("listed_unit_price"),
        debt_unit_price=trade_fact.get("debt_unit_price"),
        offered_total_gold=trade_fact.get("offered_total_gold"),
        minimum_total_gold=trade_fact.get("minimum_total_gold"),
        accepted_total_gold=trade_fact.get("accepted_total_gold"),
        counter_total_gold=trade_fact.get("counter_total_gold"),
        error_code=trade_fact.get("error_code"),
        stock=stock,
    )
    rendered = render_trade_dialogue_outcome(outcome).strip()
    return rendered or None


def _free_help_response(ask_options: list[dict], normalized_prompt: str) -> str | None:
    mentioned_item = next(
        (option for option in ask_options if option.get("item") and option.get("item") in normalized_prompt),
        None,
    )
    if mentioned_item is not None and mentioned_item.get("item") in FOOD_VALUES:
        return f'I can spare {_quantity_phrase(str(mentioned_item["item"]), int(mentioned_item.get("quantity", 1) or 1))} for free, but not more than that.'
    edible_option = next(
        (option for option in ask_options if option.get("item") in FOOD_VALUES and int(option.get("quantity", 0) or 0) > 0),
        None,
    )
    if edible_option is not None:
        return f'I can spare {_quantity_phrase(str(edible_option["item"]), int(edible_option.get("quantity", 1) or 1))} for free, but not more than that.'
    if any(token in normalized_prompt for token in FOOD_REQUEST_TOKENS):
        return "I do not have food to spare. Try the bakery or the shrine before the square runs thin."
    return None


def _quantity_phrase(item: str, quantity: int) -> str:
    if quantity == 1:
        article = "an" if item[:1].lower() in {"a", "e", "i", "o", "u"} else "a"
        return f"{article} {item}"
    return f"{item} x{quantity}"
