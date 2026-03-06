from __future__ import annotations

from dataclasses import dataclass

from acidnet.llm.protocols import DialogueContext, DialogueModelAdapter, DialogueResult
from acidnet.models import Rumor


class RuleBasedDialogueAdapter(DialogueModelAdapter):
    def generate(self, context: DialogueContext) -> DialogueResult:
        opener = _profession_opener(context)
        memory_line = _memory_line(context)
        pressure_line = _pressure_line(context)
        rumor_line, rumor_ids = _rumor_line(context)
        trade_line = _trade_line(context)

        parts = [opener]
        for optional in (memory_line, pressure_line):
            if optional:
                parts.append(optional)

        if context.interaction_mode == "rumor_request" and rumor_line:
            parts.append(rumor_line)
        elif context.interaction_mode == "trade_request" and trade_line:
            parts.append(trade_line)
        elif rumor_line and context.relationship_score > 0.45:
            parts.append(rumor_line)

        return DialogueResult(
            text=" ".join(parts).strip(),
            adapter_name="rule_based",
            latency_ms=0.0,
            used_memory_ids=[memory.memory_id for memory in context.salient_memories[:2]],
            used_rumor_ids=rumor_ids,
        )


@dataclass(slots=True)
class FallbackDialogueAdapter(DialogueModelAdapter):
    primary: DialogueModelAdapter
    fallback: DialogueModelAdapter

    def generate(self, context: DialogueContext) -> DialogueResult:
        try:
            return self.primary.generate(context)
        except Exception:
            return self.fallback.generate(context)


def build_dialogue_adapter(
    backend: str,
    *,
    model: str | None = None,
    endpoint: str | None = None,
    api_key_env: str = "OPENAI_API_KEY",
) -> DialogueModelAdapter:
    backend = backend.lower()
    if backend == "heuristic":
        return RuleBasedDialogueAdapter()
    if backend == "openai_compat":
        from acidnet.llm.openai_compat import OpenAICompatDialogueAdapter

        primary = OpenAICompatDialogueAdapter(
            model=model or "local-npc-model",
            endpoint=endpoint or "http://127.0.0.1:8000/v1/chat/completions",
            api_key_env=api_key_env,
        )
        return FallbackDialogueAdapter(primary=primary, fallback=RuleBasedDialogueAdapter())
    raise ValueError(f"Unsupported dialogue backend: {backend}")


def _profession_opener(context: DialogueContext) -> str:
    openers = {
        "merchant": "Prices move faster than patience here.",
        "farmer": "Fields answer to weather, not wishes.",
        "baker": "Bread is honest work and honest news.",
        "cook": "Say it before the pot turns on me.",
        "blacksmith": "If it matters, speak straight.",
        "guard": "Keep it clean and we can talk.",
        "fisher": "River changes its mind every hour.",
        "priest": "Breathe first. Then tell me what you need.",
        "tailor": "Stories travel faster than thread in this village.",
    }
    line = openers.get(context.npc.profession, f"{context.npc.name} waits for your question.")
    if context.relationship_score >= 0.7:
        return f"{context.npc.name} recognizes you. \"{line}\""
    if context.relationship_score <= -0.2:
        return f"{context.npc.name} studies you carefully. \"{line}\""
    return f"{context.npc.name} says, \"{line}\""


def _memory_line(context: DialogueContext) -> str:
    if not context.salient_memories:
        return ""
    memory = context.salient_memories[0]
    if "trade" in memory.tags:
        return "You remember we have done business before."
    if "npc_talk" in memory.tags or "player_talk" in memory.tags:
        return "You are not entirely new to me anymore."
    if "heard_rumor" in memory.tags:
        return "People have been talking more than usual."
    return ""


def _pressure_line(context: DialogueContext) -> str:
    parts: list[str] = []
    if context.npc.hunger >= 60:
        parts.append("I am trying to keep one eye on food.")
    if context.world.market.scarcity_index >= 1.2:
        parts.append("The village feels tighter than usual.")
    for belief in context.salient_beliefs:
        if belief.predicate == "expects_grain_shortage" and belief.confidence >= 0.6:
            parts.append("Grain looks thin if this weather keeps up.")
            break
    return " ".join(parts)


def _rumor_line(context: DialogueContext) -> tuple[str, list[str]]:
    rumor = _best_rumor(context.visible_rumors)
    if rumor is None:
        return "", []
    if context.interaction_mode == "rumor_request":
        return f"Listen closely: {rumor.content}", [rumor.rumor_id]
    return f"Keep this to yourself: {rumor.content}", [rumor.rumor_id]


def _trade_line(context: DialogueContext) -> str:
    if not context.npc.is_vendor:
        return "I am not selling anything worth your time."
    goods = [f"{item} x{qty}" for item, qty in context.npc.inventory.items() if qty > 0]
    if not goods:
        return "Stock is thin right now."
    return f"I can move {', '.join(goods[:3])} if your coin is ready."


def _best_rumor(rumors: list[Rumor]) -> Rumor | None:
    if not rumors:
        return None
    return sorted(rumors, key=lambda rumor: (rumor.value, rumor.confidence, -rumor.hop_count), reverse=True)[0]
