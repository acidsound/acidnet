"""Dialogue model adapters and prompt builders for runtime NPC interaction."""

from acidnet.llm.backend_catalog import (
    DEFAULT_OPENAI_COMPAT_ENDPOINT,
    DEFAULT_OPENAI_COMPAT_MODEL,
    EVAL_DIALOGUE_BACKENDS,
    RUNTIME_DIALOGUE_BACKENDS,
)
from acidnet.llm.openai_compat import OpenAICompatDialogueAdapter
from acidnet.llm.protocols import DialogueContext, DialogueModelAdapter, DialogueResult, DialogueTradeFact, DialogueTradeOption
from acidnet.llm.rule_based import FallbackDialogueAdapter, RuleBasedDialogueAdapter, build_dialogue_adapter
from acidnet.llm.trade_dialogue import (
    TradeDialogueIntent,
    TradeDialogueOption,
    TradeDialogueOutcome,
    parse_trade_dialogue_intent,
    parse_trade_dialogue_intent_payload,
    render_trade_dialogue_outcome,
    validate_trade_dialogue_text,
)

__all__ = [
    "DEFAULT_OPENAI_COMPAT_ENDPOINT",
    "DEFAULT_OPENAI_COMPAT_MODEL",
    "DialogueContext",
    "DialogueModelAdapter",
    "DialogueResult",
    "DialogueTradeFact",
    "TradeDialogueIntent",
    "TradeDialogueOption",
    "TradeDialogueOutcome",
    "parse_trade_dialogue_intent",
    "parse_trade_dialogue_intent_payload",
    "render_trade_dialogue_outcome",
    "validate_trade_dialogue_text",
    "DialogueTradeOption",
    "EVAL_DIALOGUE_BACKENDS",
    "FallbackDialogueAdapter",
    "OpenAICompatDialogueAdapter",
    "RUNTIME_DIALOGUE_BACKENDS",
    "RuleBasedDialogueAdapter",
    "build_dialogue_adapter",
]
