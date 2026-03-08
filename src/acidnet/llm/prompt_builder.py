from __future__ import annotations

import json
import re
from typing import Any

from acidnet.llm.protocols import DialogueContext, DialogueTradeFact, DialogueTradeOption

INTERACTION_MODE_ALIASES = {
    "open_conversation": "talk",
    "conversation": "talk",
    "talk": "talk",
    "ask_rumor": "rumor_request",
    "rumor": "rumor_request",
    "rumor_request": "rumor_request",
    "trade_food": "trade_request",
    "trade": "trade_request",
    "trade_request": "trade_request",
    "buy_food": "trade_request",
    "player_say": "direct_say",
    "free_talk": "direct_say",
    "freeform": "direct_say",
    "direct_say": "direct_say",
    "ask_harvest": "direct_say",
    "ask_safety": "direct_say",
    "ask_social_state": "direct_say",
}
RUMOR_KEYWORDS = (
    "rumor",
    "rumors",
    "heard",
    "hear",
    "gossip",
    "news",
)
TRADE_KEYWORDS = (
    "buy",
    "sell",
    "trade",
    "price",
    "prices",
    "cost",
    "coin",
    "bread",
    "stew",
    "food",
    "stock",
)
TALK_KEYWORDS = (
    "hello",
    "hi",
    "hey",
    "what is going on",
    "what's going on",
    "how are things",
    "what happened",
)
DEFAULT_SYSTEM_PROMPT = """You are a small NPC dialogue model inside a village simulation.

Respond as exactly one NPC.
Stay grounded in the supplied state.
Do not invent inventory, map facts, rumors, or relationships not present in context.
Answer the player's latest words directly before adding any extra detail.
If the player asks a concrete question, answer that question in the first sentence.
If the answer is unknown from the supplied state, say so plainly instead of improvising.
If the player asks for food or says they are hungry, never present non-food goods as edible help.
Treat edible help as the edible subset of available_goods only.
If the NPC has no edible food in the supplied state, say that plainly and redirect toward likely food help instead of offering unrelated stock.
If available_goods lists no edible items, never claim bread, fish, stew, wheat, meals, or food are on hand.
If the player asks to buy or sell food and available_goods has no edible items, say that plainly and redirect instead of substituting unrelated stock.
When mentioning what the NPC has on hand, can spare, or can sell, only name exact items that appear in available_goods.
When the player asks what the NPC can sell right now or what an item costs, ground the answer in buy_options or debt_options instead of raw market_prices.
Only quote an exact current price when that item appears in buy_options or debt_options, and use the listed price for that item.
If trade_fact is present, treat it as the server-authored trade adjudication for the current player request.
Do not change any quantity, price, debt price, accepted total, counter offer, or error meaning that appears in trade_fact.
Use trade_fact to answer naturally in character, but keep every trade number and outcome exactly aligned with it.
When trade_fact is present, lead with that adjudicated trade outcome instead of general stock chatter.
If trade_fact contains a counter_total_gold, the first sentence should make the counteroffer plain.
If trade_fact contains a counter_total_gold, quote that counter_total_gold as the amount the NPC would take for this deal instead of falling back to listed_unit_price.
If trade_fact contains an accepted_total_gold, the first sentence should make that accepted amount plain.
If trade_fact contains an accepted_total_gold, quote that accepted_total_gold as the amount the NPC would take for this deal instead of falling back to listed_unit_price.
If trade_fact contains an error_code, answer from that failure reason plainly instead of improvising around it.
If trade_fact_summary is present, do not blur or omit the numbers in it.
Do not default to generic village mood, rumors, or trade chatter unless they are relevant to the player's latest words.
Do not repeat or translate the player's message unless a short echo is the most natural in-character reply.
Never output analysis, hidden reasoning, "Thinking Process", JSON, bullet lists, or tags.
Reply with one or two short in-character sentences only.
Keep the answer compact and game-usable.
Do not explain your reasoning.
"""

TRADE_PARSER_SYSTEM_PROMPT = """You are a strict trade-intent parser for a village simulation.

Read the latest player utterance plus the supplied NPC/world context.
Return JSON only, with no prose and no markdown fences.
Use exactly one of these kinds:
- "trade_quote"
- "trade_stock"
- "trade_offer"
- "none"

Use canonical item ids only when an item is present:
- bread
- fish
- stew
- wheat
- tool

Rules:
- Infer an omitted item only when the recent dialogue context makes it clear.
- For trade_quote, include {"kind":"trade_quote","item":"bread"}.
- For trade_stock, include {"kind":"trade_stock"}.
- For trade_offer, include {"kind":"trade_offer","item":"bread","quantity":1,"offered_total_gold":5}.
- offered_total_gold is the total gold for the whole deal, not unit price.
- Quantity must be a positive integer, defaulting to 1 when the player does not state one.
- If the latest utterance is not clearly one of those trade intents, return {"kind":"none"}.
- Do not invent hidden items, prices, or quantities from outside the supplied context.
"""


def build_system_prompt(context: DialogueContext | None = None) -> str:
    if context is not None and context.system_prompt:
        return context.system_prompt
    return DEFAULT_SYSTEM_PROMPT


def build_trade_parser_system_prompt() -> str:
    return TRADE_PARSER_SYSTEM_PROMPT


def finalize_dialogue_text(text: str, context: DialogueContext) -> str:
    cleaned = sanitize_dialogue_text(text)
    cleaned = " ".join(cleaned.split()).strip()
    sentence_limit = _sentence_limit(context)
    if not cleaned or sentence_limit is None or sentence_limit <= 0:
        return cleaned
    sentences = _split_sentences(cleaned)
    if len(sentences) <= sentence_limit:
        return cleaned
    return " ".join(sentences[:sentence_limit]).strip()


def build_user_prompt(context: DialogueContext) -> str:
    interaction_mode = normalize_interaction_mode(context.interaction_mode, player_prompt=context.player_prompt)
    return build_user_prompt_from_sample(
        {
            "world": {
                "day": context.world.day,
                "tick": context.world.tick,
                "weather": context.world.weather,
                "scarcity_index": context.world.market.scarcity_index,
                "market_prices": {
                    item_id: state.current_price for item_id, state in sorted(context.world.market.items.items())
                },
            },
            "location": {
                "name": context.location.name,
            },
            "player": {
                "hunger": context.player.hunger,
            },
            "npc": {
                "name": context.npc.name,
                "profession": context.npc.profession,
                "traits": list(context.persona.traits),
                "hunger": context.npc.hunger,
                "inventory": dict(context.npc.inventory),
                "buy_options": [option.model_dump(mode="json") for option in context.buy_options],
                "sell_options": [option.model_dump(mode="json") for option in context.sell_options],
                "ask_options": [option.model_dump(mode="json") for option in context.ask_options],
                "give_options": [option.model_dump(mode="json") for option in context.give_options],
                "debt_options": [option.model_dump(mode="json") for option in context.debt_options],
                "trade_fact": context.trade_fact.model_dump(mode="json") if context.trade_fact is not None else None,
            },
            "persona": {
                "speech_style": list(context.persona.speech_style),
                "values": list(context.persona.values),
            },
            "interaction_context": {
                "player_prompt": context.player_prompt,
                "player_goal": interaction_mode,
            },
            "beliefs": [
                f"{belief.subject_id}:{belief.predicate}:{belief.confidence:.2f}"
                for belief in context.salient_beliefs[:4]
            ],
            "recent_memories": [memory.summary for memory in context.salient_memories[:3]],
            "visible_rumors": [rumor.content for rumor in context.visible_rumors[:3]],
            "relationship_score": context.relationship_score,
        }
    )


def build_trade_parser_user_prompt(context: DialogueContext) -> str:
    buy_options = _format_trade_options(context.buy_options)
    recent_memories = "\n".join(f"- {line}" for line in _format_memories(context.salient_memories))
    visible_rumors = "\n".join(f"- {line}" for line in _format_rumors(context.visible_rumors))
    return f"""NPC:
- name: {context.npc.name}
- profession: {context.npc.profession}
- available_goods: {_format_inventory_hint(context.npc.inventory)}
- buy_options: {buy_options}

World:
- location: {context.location.name}
- weather: {context.world.weather}

Recent dialogue memory:
{recent_memories}

Visible rumors:
{visible_rumors}

Latest player utterance:
- mode_hint: {context.interaction_mode}
- player_prompt: {context.player_prompt}

Return JSON only.
"""


def build_trade_parser_user_prompt_from_sample(sample: dict[str, Any]) -> str:
    npc = sample["npc"]
    world = sample["world"]
    location = sample["location"]
    interaction = sample.get("interaction_context", {})
    beliefs = sample.get("beliefs", npc.get("beliefs", []))
    memories = sample.get("recent_memories", npc.get("recent_memories", []))
    rumors = sample.get("visible_rumors", npc.get("known_rumors", []))
    return f"""NPC:
- name: {npc["name"]}
- profession: {npc["profession"]}
- available_goods: {_format_inventory_hint(npc.get("inventory", {}))}
- buy_options: {_format_trade_options(npc.get("buy_options", []))}

World:
- location: {location["name"]}
- weather: {world["weather"]}

Recent dialogue memory:
{chr(10).join(f"- {line}" for line in _format_memories(memories))}

Visible rumors:
{chr(10).join(f"- {line}" for line in _format_rumors(rumors))}

Latest player utterance:
- mode_hint: {interaction.get("player_goal", interaction.get("mode", "talk"))}
- player_prompt: {interaction.get("player_prompt", "")}

Return JSON only.
"""


def build_user_prompt_from_sample(sample: dict[str, Any]) -> str:
    npc = sample["npc"]
    world = sample["world"]
    location = sample["location"]
    player = sample.get("player", {})
    persona = sample.get("persona", {})
    interaction = sample.get("interaction_context", {})
    player_prompt = interaction.get("player_prompt", "What is going on around here?")
    interaction_mode = normalize_interaction_mode(
        interaction.get("player_goal", interaction.get("mode", "talk")),
        player_prompt=player_prompt,
    )
    beliefs = sample.get("beliefs", npc.get("beliefs", []))
    memories = sample.get("recent_memories", npc.get("recent_memories", []))
    rumors = sample.get("visible_rumors", npc.get("known_rumors", []))
    market_prices = world.get("market_prices", {})
    available_goods = [f"{item} x{qty}" for item, qty in npc.get("inventory", {}).items() if qty > 0]
    trade_hint = ", ".join(available_goods[:4]) if available_goods else "none"
    trade_fact_payload = npc.get("trade_fact")
    buy_options = _format_trade_options(npc.get("buy_options", []))
    debt_options = _format_trade_options(npc.get("debt_options", []))
    trade_fact = _format_trade_fact(trade_fact_payload)
    market_price_line = (
        "hidden during exact trade adjudication; use buy_options and trade_fact instead"
        if trade_fact_payload is not None
        else ", ".join(f"{item}={price}" for item, price in sorted(market_prices.items())) or "none"
    )
    belief_lines = "\n".join(f"- {line}" for line in _format_beliefs(beliefs))
    memory_lines = "\n".join(f"- {line}" for line in _format_memories(memories))
    rumor_lines = "\n".join(f"- {line}" for line in _format_rumors(rumors))
    return f"""NPC:
- name: {npc["name"]}
- profession: {npc["profession"]}
- traits: {", ".join(persona.get("traits", npc.get("traits", []))) or "none"}
- speech_style: {", ".join(persona.get("speech_style", [])) or "none"}
- values: {", ".join(persona.get("values", [])) or "none"}
- available_goods: {trade_hint}

Trade Adjudication:
{_format_trade_fact_lines(npc.get("trade_fact"))}

Trade Fact Summary:
- {_trade_fact_summary(npc.get("trade_fact"))}

World:
- day: {world["day"]}
- tick: {world["tick"]}
- weather: {world["weather"]}
- location: {location["name"]}
- npc_hunger: {float(npc["hunger"]):.1f}
- player_hunger: {float(player.get("hunger", 0.0)):.1f}
- scarcity_index: {float(world.get("scarcity_index", 0.0)):.2f}
- relationship_score_to_player: {float(sample.get("relationship_score", 0.0)):.2f}
- market_prices: {market_price_line}
- buy_options: {buy_options}
- debt_options: {debt_options}
- trade_fact: {trade_fact}

Beliefs:
{belief_lines}

Memories:
{memory_lines}

Rumors:
{rumor_lines}

Interaction:
- mode: {interaction_mode}
- player_prompt: {player_prompt}

Output one short in-character reply only.
"""


def normalize_interaction_mode(mode: str | None, *, player_prompt: str | None = None) -> str:
    normalized = str(mode or "").strip().lower().replace("-", "_")
    if normalized in INTERACTION_MODE_ALIASES:
        return INTERACTION_MODE_ALIASES[normalized]
    if player_prompt:
        inferred = infer_interaction_mode(player_prompt, fallback="")
        if inferred:
            return inferred
    return "talk"


def infer_interaction_mode(player_prompt: str, *, fallback: str = "direct_say") -> str:
    prompt = " ".join(str(player_prompt or "").lower().split())
    if any(keyword in prompt for keyword in RUMOR_KEYWORDS):
        return "rumor_request"
    if any(keyword in prompt for keyword in TRADE_KEYWORDS):
        return "trade_request"
    if any(keyword in prompt for keyword in TALK_KEYWORDS):
        return "talk"
    return fallback


def _format_beliefs(beliefs: list[Any]) -> list[str]:
    if not beliefs:
        return ["none"]
    lines: list[str] = []
    for belief in beliefs[:4]:
        if isinstance(belief, str):
            lines.append(belief)
        elif isinstance(belief, dict):
            lines.append(
                f'{belief.get("subject_id", "unknown")}:{belief.get("predicate", "unknown")}:{float(belief.get("confidence", 0.0)):.2f}'
            )
        else:
            lines.append(str(belief))
    return lines or ["none"]


def _format_memories(memories: list[Any]) -> list[str]:
    if not memories:
        return ["none"]
    lines: list[str] = []
    for memory in memories[:3]:
        if isinstance(memory, str):
            lines.append(memory)
        elif isinstance(memory, dict):
            lines.append(str(memory.get("summary", "")).strip() or "memory")
        else:
            lines.append(str(memory))
    return lines or ["none"]


def _format_rumors(rumors: list[Any]) -> list[str]:
    if not rumors:
        return ["none"]
    lines: list[str] = []
    for rumor in rumors[:3]:
        if isinstance(rumor, str):
            lines.append(rumor)
        elif isinstance(rumor, dict):
            lines.append(str(rumor.get("content", "")).strip() or "rumor")
        else:
            lines.append(str(rumor))
    return lines or ["none"]


def _format_trade_options(options: list[Any]) -> str:
    if not options:
        return "none"
    formatted: list[str] = []
    for option in options[:4]:
        if isinstance(option, DialogueTradeOption):
            price = option.price
            item = option.item
            quantity = option.quantity
        elif isinstance(option, dict):
            price = option.get("price")
            item = str(option.get("item", "unknown"))
            quantity = int(option.get("quantity", 0))
        else:
            continue
        if price is None:
            formatted.append(f"{item} x{quantity}")
        else:
            formatted.append(f"{item} x{quantity} @ {price} gold")
    return ", ".join(formatted) if formatted else "none"


def _format_inventory_hint(inventory: dict[str, int]) -> str:
    visible = [f"{item} x{qty}" for item, qty in sorted(inventory.items()) if qty > 0]
    return ", ".join(visible[:6]) if visible else "none"


def _format_trade_fact(trade_fact: Any) -> str:
    if trade_fact is None:
        return "none"
    if isinstance(trade_fact, DialogueTradeFact):
        payload = trade_fact.model_dump(mode="json")
    elif isinstance(trade_fact, dict):
        payload = dict(trade_fact)
    else:
        return "none"
    if payload.get("stock"):
        payload["stock"] = _format_trade_options(payload["stock"])
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _format_trade_fact_lines(trade_fact: Any) -> str:
    if trade_fact is None:
        return "- none"
    if isinstance(trade_fact, DialogueTradeFact):
        payload = trade_fact.model_dump(mode="json")
    elif isinstance(trade_fact, dict):
        payload = dict(trade_fact)
    else:
        return "- none"
    lines = ["- authoritative: true"]
    ordered_keys = (
        "kind",
        "item",
        "quantity",
        "offered_total_gold",
        "accepted_total_gold",
        "counter_total_gold",
        "minimum_total_gold",
        "available_quantity",
        "listed_unit_price",
        "debt_unit_price",
        "error_code",
    )
    for key in ordered_keys:
        value = payload.get(key)
        if value is None:
            continue
        lines.append(f"- {key}: {value}")
    stock = payload.get("stock")
    if stock:
        lines.append(f"- stock: {_format_trade_options(stock)}")
    return "\n".join(lines)


def _trade_fact_summary(trade_fact: Any) -> str:
    if trade_fact is None:
        return "none"
    if isinstance(trade_fact, DialogueTradeFact):
        payload = trade_fact.model_dump(mode="json")
    elif isinstance(trade_fact, dict):
        payload = dict(trade_fact)
    else:
        return "none"
    kind = payload.get("kind")
    item = payload.get("item") or "item"
    quantity = int(payload.get("quantity") or 1)
    if kind == "trade_quote":
        listed = payload.get("listed_unit_price")
        debt = payload.get("debt_unit_price")
        if payload.get("error_code") == "not_offered":
            if debt is not None:
                return f"{item} is not on clean cash sale right now, but debt can be discussed at {debt} gold."
            return f"{item} is not being offered right now."
        if debt is not None:
            return f"{item} is {listed} gold right now, and debt is {debt} gold."
        return f"{item} is {listed} gold right now."
    if kind == "trade_stock":
        stock = payload.get("stock")
        if stock:
            return f"Current sellable stock: {_format_trade_options(stock)}."
        return "No clean sellable stock is available right now."
    if kind == "trade_offer":
        offered = payload.get("offered_total_gold")
        accepted = payload.get("accepted_total_gold")
        counter = payload.get("counter_total_gold")
        error_code = payload.get("error_code")
        if error_code == "negative_offer":
            return "The offered gold is invalid because it is negative."
        if error_code == "invalid_quantity":
            return "The offered quantity is invalid because it is not positive."
        if error_code == "not_offered":
            return f"{item} is not being offered for trade right now."
        if error_code == "insufficient_stock":
            available = payload.get("available_quantity")
            return f"{item} x{quantity} cannot be spared right now; available clean stock is {available}."
        if accepted is not None:
            return f"The NPC would accept {accepted} gold for {item} x{quantity} right now."
        if counter is not None:
            return (
                f"The player's {offered} gold offer for {item} x{quantity} is too low; "
                f"the NPC would require {counter} gold for this deal, not the listed unit price."
            )
    return "none"


def _strip_hidden_reasoning(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()
    cleaned = re.sub(r"^(assistant|response)\s*:\s*", "", cleaned, flags=re.IGNORECASE).strip()
    lowered = cleaned.lower()
    if lowered.startswith(("thinking process:", "reasoning:", "analysis:")):
        parts = re.split(r"\n\s*\n", cleaned, maxsplit=1)
        cleaned = parts[-1].strip() if parts else ""
    if cleaned.startswith("1.") and "\n\n" in cleaned:
        cleaned = cleaned.split("\n\n")[-1].strip()
    return cleaned


def sanitize_dialogue_text(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    for _ in range(3):
        previous = cleaned
        cleaned = _strip_code_fence(cleaned)
        cleaned = _unwrap_text_payload(cleaned)
        cleaned = _strip_hidden_reasoning(cleaned)
        cleaned = _strip_outer_quotes(cleaned).strip()
        if cleaned == previous:
            break
    return cleaned


def _strip_code_fence(text: str) -> str:
    match = re.fullmatch(r"```(?:[a-zA-Z0-9_-]+)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if match is None:
        return text
    return match.group(1).strip()


def _unwrap_text_payload(text: str) -> str:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text
    extracted = _extract_text_payload(payload)
    if extracted is None:
        return text
    return extracted.strip()


def _extract_text_payload(payload: Any, *, depth: int = 0) -> str | None:
    if depth > 4:
        return None
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        if len(payload) != 1:
            return None
        return _extract_text_payload(payload[0], depth=depth + 1)
    if not isinstance(payload, dict):
        return None
    for key in ("response", "text", "content", "message", "reply", "answer", "output", "choices"):
        if key not in payload:
            continue
        extracted = _extract_text_payload(payload[key], depth=depth + 1)
        if extracted is not None:
            return extracted
    return None


def _strip_outer_quotes(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1].strip()
    return text


def _sentence_limit(context: DialogueContext) -> int | None:
    prompt = " ".join(build_system_prompt(context).lower().split())
    if any(marker in prompt for marker in _TWO_SENTENCE_MARKERS):
        return 2
    if any(marker in prompt for marker in _ONE_SENTENCE_MARKERS):
        return 1
    return None


def _split_sentences(text: str) -> list[str]:
    return [match.group(0).strip() for match in re.finditer(r'[^.!?]+[.!?]["\')\]]*|[^.!?]+$', text) if match.group(0).strip()]


_TWO_SENTENCE_MARKERS = (
    "one or two short in-character sentences",
    "one or two short sentences",
    "one or two sentences",
)

_ONE_SENTENCE_MARKERS = (
    "reply with one short in-character sentence",
    "reply with one short sentence",
    "respond with one short in-character sentence",
    "respond with one short sentence",
    "reply with one short in-character answer",
    "reply with one short answer",
    "respond with one short in-character answer",
    "respond with one short answer",
    "exactly one sentence",
    "one sentence only",
)
