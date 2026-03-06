from __future__ import annotations

from dataclasses import dataclass

from acidnet.llm.prompt_builder import select_heuristic_language
from acidnet.llm.protocols import DialogueContext, DialogueModelAdapter, DialogueResult
from acidnet.models import Rumor

_KO_PROFESSIONS = {
    "merchant": "상인",
    "farmer": "농부",
    "baker": "제빵사",
    "cook": "요리사",
    "blacksmith": "대장장이",
    "guard": "경비",
    "fisher": "어부",
    "priest": "사제",
    "tailor": "재단사",
}


class RuleBasedDialogueAdapter(DialogueModelAdapter):
    def prepare(self) -> str | None:
        return "Heuristic dialogue ready."

    def generate(self, context: DialogueContext) -> DialogueResult:
        language = select_heuristic_language(
            context.system_prompt,
            player_prompt=context.player_prompt,
        )
        rumor_line, rumor_ids = _rumor_line(context, language=language)
        trade_line = _trade_line(context, language=language)
        direct_line = _direct_response_line(context, language=language)

        if direct_line:
            parts = [direct_line]
        else:
            opener = _profession_opener(context, language=language)
            memory_line = _memory_line(context, language=language)
            pressure_line = _pressure_line(context, language=language)
            parts = [opener]
            for optional in (memory_line, pressure_line):
                if optional:
                    parts.append(optional)

        if context.interaction_mode == "rumor_request" and rumor_line:
            parts.append(rumor_line)
        elif context.interaction_mode == "trade_request" and trade_line:
            parts.append(trade_line)
        elif rumor_line and context.relationship_score > 0.45 and not direct_line:
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
            "merchant": "여긴 참을성보다 값이 먼저 움직여.",
            "farmer": "밭은 소원보다 날씨에 먼저 대답해.",
            "baker": "빵 굽는 일엔 소식도 같이 따라붙지.",
            "cook": "솥이 타기 전에 할 말이 있으면 해.",
            "blacksmith": "중요한 얘기면 곧게 말해.",
            "guard": "문제만 만들지 않으면 얘기는 들어줄 수 있어.",
            "fisher": "강물은 한 시간마다도 마음을 바꿔.",
            "priest": "숨부터 고르고 말해.",
            "tailor": "이 마을에선 실보다 소문이 더 빨리 돈다.",
        },
    }
    localized = openers.get(language, openers["en"])
    line = localized.get(context.npc.profession, f"{context.npc.name} waits for your question.")
    if context.relationship_score >= 0.7:
        return (
            f'{context.npc.name}이 널 알아본다. "{line}"'
            if language == "ko"
            else f'{context.npc.name} recognizes you. "{line}"'
        )
    if context.relationship_score <= -0.2:
        return (
            f'{context.npc.name}이 너를 조심스럽게 살핀다. "{line}"'
            if language == "ko"
            else f'{context.npc.name} studies you carefully. "{line}"'
        )
    return f'{context.npc.name}이 말한다. "{line}"' if language == "ko" else f'{context.npc.name} says, "{line}"'


def _memory_line(context: DialogueContext, *, language: str) -> str:
    if not context.salient_memories:
        return ""
    memory = context.salient_memories[0]
    if "trade" in memory.tags:
        return "전에 거래한 기억은 남아 있어." if language == "ko" else "You remember we have done business before."
    if "npc_talk" in memory.tags or "player_talk" in memory.tags:
        return "이제 넌 완전히 낯선 사람은 아니야." if language == "ko" else "You are not entirely new to me anymore."
    if "heard_rumor" in memory.tags:
        return "요즘은 평소보다 입들이 더 바쁘더라." if language == "ko" else "People have been talking more than usual."
    return ""


def _pressure_line(context: DialogueContext, *, language: str) -> str:
    parts: list[str] = []
    if context.npc.hunger >= 60:
        parts.append("먹을거리부터 챙겨야 해서 마음이 바쁘다." if language == "ko" else "I am trying to keep one eye on food.")
    if context.world.market.scarcity_index >= 1.2:
        parts.append("마을 공기가 평소보다 더 팽팽하다." if language == "ko" else "The village feels tighter than usual.")
    for belief in context.salient_beliefs:
        if belief.predicate == "expects_grain_shortage" and belief.confidence >= 0.6:
            parts.append("이 날씨가 계속되면 곡물이 모자랄 거다." if language == "ko" else "Grain looks thin if this weather keeps up.")
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
        return f"조용히 말해 두지. {summary}", [rumor.rumor_id]
    if context.interaction_mode == "rumor_request":
        return f"Listen closely: {rumor.content}", [rumor.rumor_id]
    return f"Keep this to yourself: {rumor.content}", [rumor.rumor_id]


def _trade_line(context: DialogueContext, *, language: str) -> str:
    if not context.npc.is_vendor:
        return "지금은 내놓을 만한 물건이 없다." if language == "ko" else "I am not selling anything worth your time."
    goods = [f"{item} x{qty}" for item, qty in context.npc.inventory.items() if qty > 0]
    if not goods:
        return "지금은 진열이 많이 비었다." if language == "ko" else "Stock is thin right now."
    return (
        f"지금은 {', '.join(goods[:3])} 정도는 내줄 수 있다."
        if language == "ko"
        else f"I can move {', '.join(goods[:3])} if your coin is ready."
    )


def _direct_response_line(context: DialogueContext, *, language: str) -> str:
    if context.interaction_mode != "direct_say":
        return ""
    prompt = context.player_prompt.lower()
    npc_profession = _localized_profession(context.npc.profession, language=language)
    if any(token in prompt for token in ("처음", "처음보", "who are you", "first time", "new here")):
        if language == "ko":
            return f'{context.npc.name}이 어깨를 으쓱한다. "난 이 마을에서 일하는 {npc_profession} {context.npc.name}야."'
        return f'{context.npc.name} shrugs. "I am {context.npc.name}, one of the village {context.npc.profession}s."'
    if any(token in prompt for token in ("어디서 왔", "where are you from", "where did you come from")):
        location_name = context.location.name
        if language == "ko":
            return f'{context.npc.name}이 담담히 말한다. "멀리서 온 건 아니고, 보통은 {location_name} 근처에 머물러."'
        return f'{context.npc.name} answers plainly. "Nowhere far. Most days I stay around {location_name}."'
    if any(token in prompt for token in ("안녕", "hello", "hi", "hey")):
        return f'{context.npc.name}이 고개를 든다. "안녕. 무슨 일이야?"' if language == "ko" else f'{context.npc.name} nods. "Hello. What do you need?"'
    return ""


def _localized_profession(profession: str, *, language: str) -> str:
    if language == "ko":
        return _KO_PROFESSIONS.get(profession, profession)
    return profession


def _localized_rumor_summary(rumor: Rumor) -> str:
    if rumor.category.value == "shortage":
        return "식량이나 곡물이 곧 빠듯해질 거라는 말이 돈다."
    if rumor.category.value == "economy":
        return "값과 거래 분위기가 크게 흔들릴 거라는 말이 돈다."
    if rumor.category.value == "danger":
        return "마을 사람들이 주변 위험을 더 경계하고 있다는 말이 돈다."
    if rumor.category.value == "event":
        return "요즘 마을 분위기가 예사롭지 않다는 말이 돈다."
    return "마을 안에서 무언가 심상치 않은 이야기가 돌고 있다."


def _best_rumor(rumors: list[Rumor]) -> Rumor | None:
    if not rumors:
        return None
    return sorted(rumors, key=lambda rumor: (rumor.value, rumor.confidence, -rumor.hop_count), reverse=True)[0]
