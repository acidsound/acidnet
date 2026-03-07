from __future__ import annotations

DEFAULT_OPENAI_COMPAT_MODEL = "qwen3.5-4b"
DEFAULT_OPENAI_COMPAT_ENDPOINT = "http://127.0.0.1:8000/v1/chat/completions"

# Runtime entrypoints should stay aligned with the promoted GGUF deployment path.
RUNTIME_DIALOGUE_BACKENDS = ("heuristic", "openai_compat")

# Evaluation and parity harnesses still keep the in-process HF/PEFT path available.
EVAL_DIALOGUE_BACKENDS = RUNTIME_DIALOGUE_BACKENDS + ("local_peft",)
