from __future__ import annotations

from dataclasses import dataclass
import re

from acidnet.llm.backend_catalog import DEFAULT_OPENAI_COMPAT_ENDPOINT, DEFAULT_OPENAI_COMPAT_MODEL
from acidnet.llm.prompt_builder import finalize_dialogue_text
from acidnet.llm.protocols import DialogueContext, DialogueModelAdapter, DialogueResult, DialogueTradeOption
from acidnet.llm.trade_dialogue import TradeDialogueOption as RenderTradeDialogueOption
from acidnet.llm.trade_dialogue import TradeDialogueOutcome, render_trade_dialogue_outcome
from acidnet.simulator.models import Rumor

_OPENERS = {
    "merchant": "Prices move faster than patience here.",
    "farmer": "Fields answer to weather, not wishes.",
    "baker": "Bread is honest work and honest news.",
    "cook": "Say it before the pot turns on me.",
    "blacksmith": "If it matters, speak straight.",
    "guard": "Keep it clean and we can talk.",
    "fisher": "The river changes its mind every hour.",
    "priest": "Breathe first. Then tell me what you need.",
    "tailor": "Stories travel faster than thread in this village.",
}

_FIRST_MEETING_TOKENS = (
    "who are you",
    "first time",
    "new here",
    "never met",
    "we have met",
)
_ORIGIN_TOKENS = (
    "where are you from",
    "where did you come from",
    "where do you stay",
)
_HUNGER_TOKENS = (
    "hungry",
    "starving",
    "need food",
    "something to eat",
)
_GREETING_TOKENS = (
    "hello",
    "hi",
    "hey",
)
_RUMOR_TOKENS = (
    "rumor",
    "rumors",
    "news",
    "gossip",
)
_PRICE_TOKENS = (
    "how much",
    "price",
    "prices",
    "cost",
    "gold",
    "coin",
)
_TRADE_AVAILABILITY_TOKENS = (
    "sell",
    "spare",
    "have",
    "holding",
    "get",
    "offer",
    "available",
    "on hand",
)
_FOOD_REQUEST_TOKENS = (
    "food",
    "hungry",
    "eat",
    "meal",
    "bread",
    "fish",
    "stew",
    "wheat",
)
_EDIBLE_ITEMS = {"bread", "fish", "stew", "wheat"}


class RuleBasedDialogueAdapter(DialogueModelAdapter):
    def prepare(self) -> str | None:
        return "Heuristic dialogue ready."

    def generate(self, context: DialogueContext) -> DialogueResult:
        rumor_line, rumor_ids = _rumor_line(context)
        trade_line = _trade_line(context)
        direct_line = _direct_response_line(context)
        trade_fact_line = _trade_fact_line(context)

        opener = _profession_opener(context)
        memory_line = _memory_line(context)
        pressure_line = _pressure_line(context)

        if trade_fact_line:
            parts = [trade_fact_line]
        elif direct_line:
            parts = [direct_line]
        elif context.interaction_mode == "trade_request":
            parts = [_first_non_empty(trade_line, pressure_line, opener)]
        elif context.interaction_mode == "rumor_request":
            parts = [_first_non_empty(rumor_line, pressure_line, opener)]
        else:
            parts = [_first_non_empty(memory_line, rumor_line, pressure_line, opener)]

        text = finalize_dialogue_text(" ".join(part for part in parts if part).strip(), context)

        return DialogueResult(
            text=text,
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

    def parse_trade_intent(self, context: DialogueContext):
        parser = getattr(self.primary, "parse_trade_intent", None)
        if parser is None:
            parser = getattr(self.fallback, "parse_trade_intent", None)
        if parser is None:
            return None
        try:
            return parser(context)
        except Exception:
            return None

    @property
    def temperature(self) -> float:
        return self._get_forwarded_attr("temperature")

    @temperature.setter
    def temperature(self, value: float) -> None:
        self._set_forwarded_attr("temperature", value)

    def _get_forwarded_attr(self, name: str):
        for adapter in (self.primary, self.fallback):
            if hasattr(adapter, name):
                return getattr(adapter, name)
        raise AttributeError(name)

    def _set_forwarded_attr(self, name: str, value: object) -> None:
        forwarded = False
        for adapter in (self.primary, self.fallback):
            if hasattr(adapter, name):
                setattr(adapter, name, value)
                forwarded = True
        if not forwarded:
            raise AttributeError(name)


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
            model=model or DEFAULT_OPENAI_COMPAT_MODEL,
            endpoint=endpoint or DEFAULT_OPENAI_COMPAT_ENDPOINT,
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


def _profession_opener(context: DialogueContext) -> str:
    line = _OPENERS.get(context.npc.profession, f"{context.npc.name} waits for your question.")
    if context.relationship_score >= 0.7:
        return f'{context.npc.name} recognizes you. "{line}"'
    if context.relationship_score <= -0.2:
        return f'{context.npc.name} studies you carefully. "{line}"'
    return f'{context.npc.name} says, "{line}"'


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
    rumor = _best_rumor(context.visible_rumors, known_rumor_ids=context.player.known_rumor_ids)
    if rumor is None:
        return "", []
    if context.interaction_mode == "rumor_request":
        return f"Listen closely: {rumor.content}", [rumor.rumor_id]
    return f"Keep this to yourself: {rumor.content}", [rumor.rumor_id]


def _trade_line(context: DialogueContext) -> str:
    if not context.npc.is_vendor:
        return "I am not selling anything worth your time."
    normalized_prompt = " ".join(context.player_prompt.lower().split())
    asks_for_food = any(token in normalized_prompt for token in _FOOD_REQUEST_TOKENS)
    goods = _format_trade_options(context.buy_options)
    edible_goods = _format_trade_options(option for option in context.buy_options if option.item in _EDIBLE_ITEMS)
    if asks_for_food and edible_goods:
        return f"I can sell {', '.join(edible_goods[:3])} if your coin is ready."
    if asks_for_food:
        return "I do not have food to sell right now. Try the bakery or the tavern before it gets worse."
    if not goods:
        return "Stock is thin right now."
    return f"I can move {', '.join(goods[:3])} if your coin is ready."


def _direct_response_line(context: DialogueContext) -> str:
    if context.interaction_mode != "direct_say":
        return ""
    normalized_prompt = " ".join(context.player_prompt.lower().split())
    location_name = context.location.name
    trade_line = _direct_trade_response_line(context, normalized_prompt)
    if trade_line:
        return trade_line

    if any(token in normalized_prompt for token in _FIRST_MEETING_TOKENS):
        return f"I am {context.npc.name}, one of the village {context.npc.profession}s."

    if any(token in normalized_prompt for token in _ORIGIN_TOKENS):
        return f"I keep close to {location_name}; nowhere far from here."

    if any(token in normalized_prompt for token in _HUNGER_TOKENS):
        stocked_items = [item for item, qty in context.npc.inventory.items() if qty > 0 and item in _EDIBLE_ITEMS]
        if stocked_items and context.npc.is_vendor:
            item_name = stocked_items[0]
            return f"If you need food now, I can spare {item_name} if we settle the exchange."
        if stocked_items:
            item_name = stocked_items[0]
            return f"I can spare a little {item_name}, but not much more than that."
        return "I do not have food to hand; try the bakery or the square before it gets worse."

    if any(token in normalized_prompt for token in _RUMOR_TOKENS):
        rumor_line, _ = _rumor_line(context)
        if rumor_line:
            return rumor_line

    if any(token in normalized_prompt for token in _GREETING_TOKENS):
        return "Hello, what do you need?"

    if _looks_like_question(context.player_prompt):
        return f"I only know what I have seen around {location_name}."

    return "I will keep that in mind."


def _direct_trade_response_line(context: DialogueContext, normalized_prompt: str) -> str:
    if context.trade_fact is not None:
        return ""
    if not any(token in normalized_prompt for token in (*_PRICE_TOKENS, *_TRADE_AVAILABILITY_TOKENS)):
        return ""
    mentioned_item = _mentioned_trade_item(context, normalized_prompt)
    if mentioned_item is None:
        return ""
    buy_option = _find_trade_option(context.buy_options, mentioned_item)
    debt_option = _find_trade_option(context.debt_options, mentioned_item)
    if any(token in normalized_prompt for token in _PRICE_TOKENS):
        if buy_option is not None and buy_option.price is not None:
            if debt_option is not None and debt_option.price is not None:
                return f"{mentioned_item.capitalize()} is {buy_option.price} gold right now. I can still put it on debt for {debt_option.price} gold."
            return f"{mentioned_item.capitalize()} is {buy_option.price} gold right now."
        if debt_option is not None and debt_option.price is not None:
            return f"I am not selling {mentioned_item} cleanly right now, but I can still let it go on debt for {debt_option.price} gold."
        return f"I am not offering {mentioned_item} right now."
    if buy_option is not None:
        return f"I can still move {buy_option.item} x{buy_option.quantity} right now."
    if context.npc.inventory.get(mentioned_item, 0) > 0:
        return f"I have some {mentioned_item}, but not enough to promise it cleanly right now."
    return f"I am not offering {mentioned_item} right now."


def _prompt_excerpt(text: str, *, limit: int = 48) -> str:
    compact = " ".join(text.split()).strip().strip('"')
    if not compact:
        return "that"
    compact = compact.rstrip("?.! ")
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _looks_like_question(text: str) -> bool:
    compact = " ".join(str(text or "").strip().lower().split())
    if not compact:
        return False
    if compact.endswith("?"):
        return True
    return compact.startswith(("why", "how", "what", "where", "who", "when", "can", "do", "is", "are"))


def _best_rumor(rumors: list[Rumor], *, known_rumor_ids: list[str] | None = None) -> Rumor | None:
    if not rumors:
        return None
    ranked = sorted(rumors, key=lambda rumor: (rumor.value, rumor.confidence, -rumor.hop_count), reverse=True)
    if not known_rumor_ids:
        return ranked[0]
    for rumor in ranked:
        if rumor.rumor_id not in known_rumor_ids:
            return rumor
    return ranked[0]


def _first_non_empty(*parts: str) -> str:
    for part in parts:
        if part:
            return part
    return ""


def _trade_fact_line(context: DialogueContext) -> str:
    if context.trade_fact is None:
        return ""
    outcome = TradeDialogueOutcome(
        kind=context.trade_fact.kind,
        item=context.trade_fact.item,
        quantity=context.trade_fact.quantity,
        available_quantity=context.trade_fact.available_quantity,
        listed_unit_price=context.trade_fact.listed_unit_price,
        debt_unit_price=context.trade_fact.debt_unit_price,
        offered_total_gold=context.trade_fact.offered_total_gold,
        minimum_total_gold=context.trade_fact.minimum_total_gold,
        accepted_total_gold=context.trade_fact.accepted_total_gold,
        counter_total_gold=context.trade_fact.counter_total_gold,
        error_code=context.trade_fact.error_code,
        stock=tuple(
            RenderTradeDialogueOption(item=option.item, quantity=option.quantity, price=option.price)
            for option in context.trade_fact.stock
        ),
    )
    return render_trade_dialogue_outcome(outcome)


def _format_trade_options(options) -> list[str]:
    return [
        f"{option.item} x{option.quantity}" if option.price is None else f"{option.item} x{option.quantity} at {option.price} gold"
        for option in options
    ]


def _mentioned_trade_item(context: DialogueContext, normalized_prompt: str) -> str | None:
    option_items = {
        option.item
        for option in [*context.buy_options, *context.debt_options, *context.sell_options]
    }
    option_items.update(item for item, qty in context.npc.inventory.items() if qty > 0)
    for item in sorted(option_items):
        if re.search(rf"\b{re.escape(item)}s?\b", normalized_prompt):
            return item
    return None


def _find_trade_option(options: list[DialogueTradeOption], item: str) -> DialogueTradeOption | None:
    for option in options:
        if option.item == item:
            return option
    return None
