from acidnet.llm import (
    TradeDialogueOption,
    TradeDialogueOutcome,
    parse_trade_dialogue_intent,
    parse_trade_dialogue_intent_payload,
    render_trade_dialogue_outcome,
    validate_trade_dialogue_text,
)


def test_parse_trade_dialogue_intent_quotes_exact_item_price() -> None:
    intent = parse_trade_dialogue_intent("How much is bread?")

    assert intent is not None
    assert intent.kind == "trade_quote"
    assert intent.item == "bread"


def test_parse_trade_dialogue_intent_detects_stock_question() -> None:
    intent = parse_trade_dialogue_intent("What do you have in stock right now?")

    assert intent is not None
    assert intent.kind == "trade_stock"


def test_parse_trade_dialogue_intent_detects_simple_offer() -> None:
    intent = parse_trade_dialogue_intent("Would you take 3 gold for one bread?")

    assert intent is not None
    assert intent.kind == "trade_offer"
    assert intent.item == "bread"
    assert intent.quantity == 1
    assert intent.offered_total_gold == 3


def test_parse_trade_dialogue_intent_payload_accepts_json_tool_result() -> None:
    intent = parse_trade_dialogue_intent_payload('{"kind":"trade_offer","item":"bread","quantity":1,"offered_total_gold":5}')

    assert intent is not None
    assert intent.kind == "trade_offer"
    assert intent.item == "bread"
    assert intent.quantity == 1
    assert intent.offered_total_gold == 5


def test_render_trade_dialogue_outcome_uses_english_canonical_text() -> None:
    outcome = TradeDialogueOutcome(
        kind="trade_stock",
        stock=(
            TradeDialogueOption(item="bread", quantity=6, price=6),
            TradeDialogueOption(item="fish", quantity=2, price=5),
        ),
    )

    rendered = render_trade_dialogue_outcome(outcome)

    assert rendered == "What I can sell right now is bread x6 (6 gold), fish x2 (5 gold)."


def test_validate_trade_dialogue_text_rejects_wrong_quote_price() -> None:
    outcome = TradeDialogueOutcome(kind="trade_quote", item="bread", listed_unit_price=6)

    reason = validate_trade_dialogue_text("Bread is 5 gold right now.", outcome)

    assert reason == "missing_listed_price"


def test_validate_trade_dialogue_text_requires_counter_offer_total() -> None:
    outcome = TradeDialogueOutcome(
        kind="trade_offer",
        item="bread",
        quantity=1,
        offered_total_gold=3,
        counter_total_gold=4,
    )

    reason = validate_trade_dialogue_text("Bread is 6 gold right now.", outcome)

    assert reason == "missing_counter_total"
