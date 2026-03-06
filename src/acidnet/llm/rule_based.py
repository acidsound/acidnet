from __future__ import annotations

from dataclasses import dataclass

from acidnet.llm.prompt_builder import preferred_output_language
from acidnet.llm.protocols import DialogueContext, DialogueModelAdapter, DialogueResult
from acidnet.models import Rumor


class RuleBasedDialogueAdapter(DialogueModelAdapter):
    def prepare(self) -> str | None:
        return "Heuristic dialogue ready."

    def generate(self, context: DialogueContext) -> DialogueResult:
        language = preferred_output_language(context.system_prompt)
        opener = _profession_opener(context, language=language)
        memory_line = _memory_line(context, language=language)
        pressure_line = _pressure_line(context, language=language)
        rumor_line, rumor_ids = _rumor_line(context, language=language)
        trade_line = _trade_line(context, language=language)

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

    def prepare(self) -> str | None:
        try:
            return self.primary.prepare()
        except Exception as exc:
            fallback_status = self.fallback.prepare() or type(self.fallback).__name__
            return f"Primary dialogue load failed ({exc}). {fallback_status}"

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
    adapter_path: str | None = None,
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
    if backend == "local_peft":
        from acidnet.llm.local_peft import LocalPeftDialogueAdapter

        if not adapter_path:
            raise ValueError("`adapter_path` is required for the local_peft dialogue backend.")
        primary = LocalPeftDialogueAdapter(
            model=model or "Qwen/Qwen3.5-4B",
            adapter_path=adapter_path,
        )
        return FallbackDialogueAdapter(primary=primary, fallback=RuleBasedDialogueAdapter())
    raise ValueError(f"Unsupported dialogue backend: {backend}")


def _profession_opener(context: DialogueContext, *, language: str) -> str:
    openers = {
        "en": {
            "merchant": "Prices move faster than patience here.",
            "farmer": "Fields answer to weather, not wishes.",
            "baker": "Bread is honest work and honest news.",
            "cook": "Say it before the pot turns on me.",
            "blacksmith": "If it matters, speak straight.",
            "guard": "Keep it clean and we can talk.",
            "fisher": "River changes its mind every hour.",
            "priest": "Breathe first. Then tell me what you need.",
            "tailor": "Stories travel faster than thread in this village.",
        },
        "ko": {
            "merchant": "여긴 값이 사람 마음보다 빨리 움직여.",
            "farmer": "밭은 소원보다 날씨에 먼저 대답해.",
            "baker": "빵이랑 소문은 둘 다 금방 퍼져.",
            "cook": "필요한 말이면 빨리 해.",
            "blacksmith": "중요하면 돌려 말하지 마.",
            "guard": "문제만 만들지 않으면 얘기해도 돼.",
            "fisher": "강은 한 시간마다 표정이 달라져.",
            "priest": "숨부터 고르고 말해.",
            "tailor": "이 마을에선 실보다 이야기가 더 빨라.",
        },
    }
    localized = openers.get(language, openers["en"])
    if localized is not openers["en"]:
        line = localized.get(context.npc.profession, f"{context.npc.name}이 네 말을 기다린다.")
    else:
        line = openers["en"].get(context.npc.profession, f"{context.npc.name} waits for your question.")
    if context.relationship_score >= 0.7:
        if language == "ko":
            return f'{context.npc.name}이 너를 알아본다. "{line}"'
        return f"{context.npc.name} recognizes you. \"{line}\""
    if context.relationship_score <= -0.2:
        if language == "ko":
            return f'{context.npc.name}이 너를 유심히 본다. "{line}"'
        return f"{context.npc.name} studies you carefully. \"{line}\""
    if language == "ko":
        return f'{context.npc.name}이 말한다. "{line}"'
    return f"{context.npc.name} says, \"{line}\""


def _memory_line(context: DialogueContext, *, language: str) -> str:
    if not context.salient_memories:
        return ""
    memory = context.salient_memories[0]
    if "trade" in memory.tags:
        if language == "ko":
            return "전에도 거래한 기억이 있어."
        return "You remember we have done business before."
    if "npc_talk" in memory.tags or "player_talk" in memory.tags:
        if language == "ko":
            return "이제 넌 완전히 낯선 사람은 아니야."
        return "You are not entirely new to me anymore."
    if "heard_rumor" in memory.tags:
        if language == "ko":
            return "요즘은 다들 평소보다 더 많이 떠들어."
        return "People have been talking more than usual."
    return ""


def _pressure_line(context: DialogueContext, *, language: str) -> str:
    parts: list[str] = []
    if context.npc.hunger >= 60:
        if language == "ko":
            parts.append("먹을거리를 계속 신경 쓰고 있어.")
        else:
            parts.append("I am trying to keep one eye on food.")
    if context.world.market.scarcity_index >= 1.2:
        if language == "ko":
            parts.append("마을 살림이 평소보다 팍팍해.")
        else:
            parts.append("The village feels tighter than usual.")
    for belief in context.salient_beliefs:
        if belief.predicate == "expects_grain_shortage" and belief.confidence >= 0.6:
            if language == "ko":
                parts.append("이 날씨가 계속되면 곡물이 모자랄 거야.")
            else:
                parts.append("Grain looks thin if this weather keeps up.")
            break
    return " ".join(parts)


def _rumor_line(context: DialogueContext, *, language: str) -> tuple[str, list[str]]:
    rumor = _best_rumor(context.visible_rumors)
    if rumor is None:
        return "", []
    if language == "ko":
        summary = _localized_rumor_summary(rumor)
        if context.interaction_mode == "rumor_request":
            return f"잘 들어. {summary}", [rumor.rumor_id]
        return f"조용히 들어 둬. {summary}", [rumor.rumor_id]
    if context.interaction_mode == "rumor_request":
        return f"Listen closely: {rumor.content}", [rumor.rumor_id]
    return f"Keep this to yourself: {rumor.content}", [rumor.rumor_id]


def _trade_line(context: DialogueContext, *, language: str) -> str:
    if not context.npc.is_vendor:
        if language == "ko":
            return "지금은 내놓을 만한 물건이 없어."
        return "I am not selling anything worth your time."
    goods = [f"{item} x{qty}" for item, qty in context.npc.inventory.items() if qty > 0]
    if not goods:
        if language == "ko":
            return "지금은 재고가 많이 비었어."
        return "Stock is thin right now."
    if language == "ko":
        return f"지금은 {', '.join(goods[:3])} 정도는 내줄 수 있어."
    return f"I can move {', '.join(goods[:3])} if your coin is ready."


def _localized_rumor_summary(rumor: Rumor) -> str:
    if rumor.category.value == "shortage":
        return "식량이나 곡물이 곧 빠듯해질 거라는 말이 돌아."
    if rumor.category.value == "economy":
        return "장터에선 값이 흔들릴 거라는 얘기가 많아."
    if rumor.category.value == "danger":
        return "마을 공기가 평소보다 거칠다는 소문이 있어."
    if rumor.category.value == "event":
        return "날씨랑 현장 분위기가 일을 꼬이게 만들고 있다는 얘기가 돌아."
    return "사람들 입에 오르는 이야기가 하나 있어."


def _best_rumor(rumors: list[Rumor]) -> Rumor | None:
    if not rumors:
        return None
    return sorted(rumors, key=lambda rumor: (rumor.value, rumor.confidence, -rumor.hop_count), reverse=True)[0]
