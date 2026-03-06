from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelCandidate:
    key: str
    label: str
    train_model_id: str
    runtime_repo_id: str
    runtime_gguf_filename: str
    runtime_gguf_url: str
    recommended_lora_dtype: str
    estimated_bf16_lora_vram_gb: int
    context_length: int
    why_consider: str
    why_not_primary: str


QWEN35_4B = ModelCandidate(
    key="qwen3_5_4b",
    label="Qwen3.5-4B",
    train_model_id="Qwen/Qwen3.5-4B-Base",
    runtime_repo_id="unsloth/Qwen3.5-4B-GGUF",
    runtime_gguf_filename="Qwen3.5-4B-Q4_K_M.gguf",
    runtime_gguf_url="https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf",
    recommended_lora_dtype="bf16",
    estimated_bf16_lora_vram_gb=10,
    context_length=262144,
    why_consider="Safest training fit on a 24GB GPU while still leaving room for sequence length, optimizer state, and evaluation.",
    why_not_primary="Lower headroom than 9B on nuanced multi-NPC dialogue, deception, and social style consistency.",
)

QWEN35_9B = ModelCandidate(
    key="qwen3_5_9b",
    label="Qwen3.5-9B",
    train_model_id="unsloth/Qwen3.5-9B",
    runtime_repo_id="unsloth/Qwen3.5-9B-GGUF",
    runtime_gguf_filename="Qwen3.5-9B-Q4_K_M.gguf",
    runtime_gguf_url="https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-Q4_K_M.gguf",
    recommended_lora_dtype="bf16",
    estimated_bf16_lora_vram_gb=22,
    context_length=262144,
    why_consider="Best candidate for richer persona fidelity and tighter world-aware dialogue if it fits within the available training envelope.",
    why_not_primary="At 24GB VRAM, bf16 LoRA is close to the hardware ceiling and leaves much less room for robust batch/sequence tuning.",
)


def all_candidates() -> list[ModelCandidate]:
    return [QWEN35_4B, QWEN35_9B]


def recommended_experiment_order(vram_gb: int = 24) -> list[ModelCandidate]:
    if vram_gb <= 24:
        return [QWEN35_4B, QWEN35_9B]
    return [QWEN35_9B, QWEN35_4B]


def selection_summary(vram_gb: int = 24) -> str:
    ordered = recommended_experiment_order(vram_gb)
    first = ordered[0]
    second = ordered[1]
    return (
        f"Primary training candidate on {vram_gb}GB VRAM: {first.label} "
        f"(estimated bf16 LoRA VRAM {first.estimated_bf16_lora_vram_gb}GB). "
        f"Secondary challenger: {second.label}."
    )

