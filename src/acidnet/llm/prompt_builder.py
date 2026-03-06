from __future__ import annotations

from typing import Any

from acidnet.llm.protocols import DialogueContext

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
RUMOR_KEYWORDS = ("rumor", "rumors", "heard", "hear", "gossip", "news")
TRADE_KEYWORDS = ("buy", "sell", "trade", "price", "prices", "cost", "coin", "bread", "stew", "food", "stock")
TALK_KEYWORDS = ("hello", "hi", "hey", "what is going on", "what's going on", "how are things", "what happened")
DEFAULT_SYSTEM_PROMPT = """You are a small NPC dialogue model inside a village simulation.

Respond as exactly one NPC.
Stay grounded in the supplied state.
Do not invent inventory, map facts, rumors, or relationships not present in context.
Never output analysis, hidden reasoning, "Thinking Process", JSON, bullet lists, or tags.
Reply with one or two short in-character sentences only.
Keep the answer compact and game-usable.
Do not explain your reasoning.
"""


def build_system_prompt(context: DialogueContext | None = None) -> str:
    if context is not None and context.system_prompt:
        return context.system_prompt
    return DEFAULT_SYSTEM_PROMPT


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

World:
- day: {world["day"]}
- tick: {world["tick"]}
- weather: {world["weather"]}
- location: {location["name"]}
- npc_hunger: {float(npc["hunger"]):.1f}
- player_hunger: {float(player.get("hunger", 0.0)):.1f}
- scarcity_index: {float(world.get("scarcity_index", 0.0)):.2f}
- relationship_score_to_player: {float(sample.get("relationship_score", 0.0)):.2f}
- market_prices: {", ".join(f"{item}={price}" for item, price in sorted(market_prices.items())) or "none"}

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
    normalized_prompt = " ".join(str(player_prompt).lower().split())
    if any(keyword in normalized_prompt for keyword in RUMOR_KEYWORDS):
        return "rumor_request"
    if any(keyword in normalized_prompt for keyword in TRADE_KEYWORDS):
        return "trade_request"
    if any(keyword in normalized_prompt for keyword in TALK_KEYWORDS):
        return "talk"
    return fallback


def _format_beliefs(beliefs: list) -> list[str]:
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
    return lines or ["none"]


def _format_memories(memories: list) -> list[str]:
    if not memories:
        return ["none"]
    lines: list[str] = []
    for memory in memories[:3]:
        if isinstance(memory, str):
            lines.append(memory)
        elif isinstance(memory, dict):
            lines.append(str(memory.get("summary", "")).strip() or "memory")
    return lines or ["none"]


def _format_rumors(rumors: list) -> list[str]:
    if not rumors:
        return ["none"]
    lines: list[str] = []
    for rumor in rumors[:3]:
        if isinstance(rumor, str):
            lines.append(rumor)
        elif isinstance(rumor, dict):
            lines.append(str(rumor.get("content", "")).strip() or "rumor")
    return lines or ["none"]
