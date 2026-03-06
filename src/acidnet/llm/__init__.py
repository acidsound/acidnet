"""Dialogue model adapters and prompt builders for runtime NPC interaction."""

from acidnet.llm.openai_compat import OpenAICompatDialogueAdapter
from acidnet.llm.protocols import DialogueContext, DialogueModelAdapter, DialogueResult
from acidnet.llm.rule_based import FallbackDialogueAdapter, RuleBasedDialogueAdapter, build_dialogue_adapter

__all__ = [
    "DialogueContext",
    "DialogueModelAdapter",
    "DialogueResult",
    "FallbackDialogueAdapter",
    "OpenAICompatDialogueAdapter",
    "RuleBasedDialogueAdapter",
    "build_dialogue_adapter",
]
