from __future__ import annotations

from dataclasses import dataclass, field
import json
import re

ITEM_DIALOGUE_ALIASES = {
    "bread": ("bread", "breads"),
    "fish": ("fish", "fishes"),
    "stew": ("stew", "stews"),
    "wheat": ("wheat", "grain", "grains"),
    "tool": ("tool", "tools"),
}
TRADE_QUOTE_TOKENS = ("how much", "price", "prices", "cost")
TRADE_STOCK_TOKENS = (
    "what do you have",
    "what do you sell",
    "what can you sell",
    "on hand",
    "in stock",
    "available",
    "stock",
)
TRADE_OFFER_TOKENS = ("for", "at", "deal", "offer", "take")


@dataclass(slots=True, frozen=True)
class TradeDialogueIntent:
    kind: str
    item: str | None = None
    quantity: int = 1
    offered_total_gold: int | None = None


@dataclass(slots=True, frozen=True)
class TradeDialogueOption:
    item: str
    quantity: int
    price: int | None = None


@dataclass(slots=True, frozen=True)
class TradeDialogueOutcome:
    kind: str
    item: str | None = None
    quantity: int = 1
    available_quantity: int = 0
    listed_unit_price: int | None = None
    debt_unit_price: int | None = None
    offered_total_gold: int | None = None
    minimum_total_gold: int | None = None
    accepted_total_gold: int | None = None
    counter_total_gold: int | None = None
    error_code: str | None = None
    stock: tuple[TradeDialogueOption, ...] = field(default_factory=tuple)


def parse_trade_dialogue_intent(text: str) -> TradeDialogueIntent | None:
    normalized = " ".join(str(text or "").lower().split())
    if not normalized:
        return None
    item = resolve_dialogue_item(normalized)
    offered_total = extract_trade_offer_total(normalized)

    if item is not None and offered_total is not None and any(token in normalized for token in TRADE_OFFER_TOKENS):
        return TradeDialogueIntent(
            kind="trade_offer",
            item=item,
            quantity=extract_trade_dialogue_quantity(normalized, item=item),
            offered_total_gold=offered_total,
        )
    if item is not None and any(token in normalized for token in TRADE_QUOTE_TOKENS):
        return TradeDialogueIntent(kind="trade_quote", item=item)
    if any(token in normalized for token in TRADE_STOCK_TOKENS):
        return TradeDialogueIntent(kind="trade_stock")
    return None


def parse_trade_dialogue_intent_payload(text: str) -> TradeDialogueIntent | None:
    payload = _load_trade_intent_payload(text)
    if payload is None:
        return None
    kind = str(payload.get("kind", "")).strip().lower()
    if kind in {"", "none", "null"}:
        return None
    if kind not in {"trade_quote", "trade_stock", "trade_offer"}:
        return None
    item = payload.get("item")
    if item is not None:
        item = str(item).strip().lower()
        if item not in ITEM_DIALOGUE_ALIASES:
            return None
    quantity = payload.get("quantity", 1)
    try:
        quantity_value = max(1, int(quantity))
    except (TypeError, ValueError):
        quantity_value = 1
    offered_total = payload.get("offered_total_gold")
    if offered_total is not None:
        try:
            offered_total = int(offered_total)
        except (TypeError, ValueError):
            return None
    return TradeDialogueIntent(
        kind=kind,
        item=item,
        quantity=quantity_value,
        offered_total_gold=offered_total,
    )


def render_trade_dialogue_outcome(outcome: TradeDialogueOutcome) -> str:
    if outcome.kind == "trade_stock":
        return _render_trade_stock(outcome)
    if outcome.kind == "trade_quote":
        return _render_trade_quote(outcome)
    if outcome.kind == "trade_offer":
        return _render_trade_offer(outcome)
    return ""


def validate_trade_dialogue_text(text: str, outcome: TradeDialogueOutcome) -> str | None:
    normalized = " ".join(str(text or "").lower().split())
    if not normalized:
        return "empty_text"
    if outcome.kind == "trade_stock":
        return None
    if outcome.kind == "trade_quote":
        return _validate_trade_quote_text(normalized, outcome)
    if outcome.kind == "trade_offer":
        return _validate_trade_offer_text(normalized, outcome)
    return None


def resolve_dialogue_item(text: str) -> str | None:
    lowered = str(text or "").lower()
    for item, aliases in ITEM_DIALOGUE_ALIASES.items():
        if any(_contains_alias(lowered, alias) for alias in aliases):
            return item
    return None


def extract_trade_offer_total(text: str) -> int | None:
    match = re.search(r"(-?\d+)\s*gold\b", str(text or "").lower())
    if match is None:
        return None
    return int(match.group(1))


def extract_trade_dialogue_quantity(text: str, *, item: str) -> int:
    lowered = str(text or "").lower()
    for alias in ITEM_DIALOGUE_ALIASES.get(item, (item,)):
        patterns = (
            rf"{re.escape(alias)}\s*x?(\d+)\b",
            rf"\b(\d+)\s*x?\s*{re.escape(alias)}\b",
            rf"\b(?:a|an|one)\s+{re.escape(alias)}\b",
            rf"{re.escape(alias)}\s+\b(?:a|an|one)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if match is None:
                continue
            if match.lastindex:
                return max(1, int(match.group(1)))
            return 1
    return 1


def _render_trade_stock(outcome: TradeDialogueOutcome) -> str:
    if not outcome.stock:
        return "I do not have anything I would promise cleanly right now."
    listed = ", ".join(
        f"{option.item} x{option.quantity} ({option.price} gold)"
        if option.price is not None
        else f"{option.item} x{option.quantity}"
        for option in outcome.stock[:4]
    )
    return f"What I can sell right now is {listed}."


def _render_trade_quote(outcome: TradeDialogueOutcome) -> str:
    item_label = outcome.item or "item"
    if outcome.error_code == "not_offered":
        if outcome.debt_unit_price is not None:
            return (
                f"I am not offering {item_label} cleanly right now, "
                f"but I could still talk about {outcome.debt_unit_price} gold on debt."
            )
        return f"I am not offering {item_label} right now."
    if outcome.debt_unit_price is not None:
        return (
            f"{item_label.capitalize()} is {outcome.listed_unit_price} gold right now. "
            f"On debt I would call it {outcome.debt_unit_price} gold."
        )
    return f"{item_label.capitalize()} is {outcome.listed_unit_price} gold right now."


def _render_trade_offer(outcome: TradeDialogueOutcome) -> str:
    item_label = outcome.item or "item"
    if outcome.error_code == "negative_offer":
        return "I will not treat a negative gold offer as a real trade."
    if outcome.error_code == "invalid_quantity":
        return "A trade needs a positive quantity."
    if outcome.error_code == "not_offered":
        return f"I am not putting {item_label} up for trade right now."
    if outcome.error_code == "insufficient_stock":
        return f"I cannot spare {outcome.quantity} {item_label} right now."
    if outcome.accepted_total_gold is not None:
        if outcome.listed_unit_price is not None and outcome.accepted_total_gold == outcome.listed_unit_price * outcome.quantity:
            return f"For {item_label} x{outcome.quantity}, {outcome.accepted_total_gold} gold is enough. That price works."
        return f"All right. I would take {outcome.accepted_total_gold} gold for {item_label} x{outcome.quantity}."
    if outcome.counter_total_gold is not None:
        return f"That is too low. For {item_label} x{outcome.quantity}, I would need {outcome.counter_total_gold} gold."
    return "I cannot treat that as a workable offer right now."


def _validate_trade_quote_text(text: str, outcome: TradeDialogueOutcome) -> str | None:
    gold_amounts = _extract_gold_amounts(text)
    allowed_amounts = {
        amount
        for amount in (outcome.listed_unit_price, outcome.debt_unit_price)
        if amount is not None
    }
    if outcome.error_code == "not_offered":
        if outcome.debt_unit_price is None:
            return None
        if outcome.debt_unit_price not in gold_amounts:
            return "missing_debt_price"
        if gold_amounts - allowed_amounts:
            return "unexpected_gold_amount"
        return None
    if outcome.listed_unit_price is None:
        return None
    if outcome.listed_unit_price not in gold_amounts:
        return "missing_listed_price"
    if outcome.debt_unit_price is not None and outcome.debt_unit_price not in gold_amounts:
        return "missing_debt_price"
    if gold_amounts - allowed_amounts:
        return "unexpected_gold_amount"
    return None


def _validate_trade_offer_text(text: str, outcome: TradeDialogueOutcome) -> str | None:
    gold_amounts = _extract_gold_amounts(text)
    if outcome.accepted_total_gold is not None and outcome.accepted_total_gold not in gold_amounts:
        return "missing_accepted_total"
    if outcome.counter_total_gold is not None and outcome.counter_total_gold not in gold_amounts:
        return "missing_counter_total"
    return None


def _extract_gold_amounts(text: str) -> set[int]:
    return {int(match.group(1)) for match in re.finditer(r"(-?\d+)\s*gold\b", text)}


def _contains_alias(text: str, alias: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])", text) is not None


def _load_trade_intent_payload(text: str) -> dict[str, object] | None:
    cleaned = str(text or "").strip()
    if not cleaned:
        return None
    candidates = [cleaned]
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if fence_match is not None:
        candidates.append(fence_match.group(1).strip())
    if "{" in cleaned and "}" in cleaned:
        candidates.append(cleaned[cleaned.find("{") : cleaned.rfind("}") + 1].strip())
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return None
