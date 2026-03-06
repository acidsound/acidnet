from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from acidnet.training.experiment_registry import ModelCandidate, recommended_experiment_order


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    train_rows_target: int
    eval_rows_target: int
    prompt_format: str
    train_jsonl_path: str
    train_parquet_path: str
    eval_jsonl_path: str
    eval_parquet_path: str
    merged_sft_jsonl_path: str
    merged_sft_parquet_path: str
    train_sft_jsonl_path: str
    train_sft_parquet_path: str
    eval_sft_jsonl_path: str
    eval_sft_parquet_path: str
    teacher_model: str


@dataclass(frozen=True, slots=True)
class FineTuneExperiment:
    key: str
    label: str
    track: str
    train_model_id: str
    runtime_repo_id: str
    runtime_gguf_filename: str
    runtime_gguf_url: str
    method: str
    precision: str
    max_seq_length: int
    lora_rank: int
    lora_alpha: int
    learning_rate: float
    per_device_batch_size: int
    gradient_accumulation_steps: int
    num_epochs: int
    warmup_ratio: float
    eval_steps: int
    save_steps: int
    dataset: DatasetSpec
    objective: str
    selection_notes: list[str]


def build_finetune_manifest(
    *,
    vram_gb: int = 24,
    train_rows_target: int = 50_000,
    eval_rows_target: int = 4_000,
) -> list[FineTuneExperiment]:
    ordered = recommended_experiment_order(vram_gb)
    return [
        _build_experiment(
            ordered[0],
            track="baseline",
            train_rows_target=train_rows_target,
            eval_rows_target=eval_rows_target,
        ),
        _build_experiment(
            ordered[1],
            track="challenger",
            train_rows_target=train_rows_target,
            eval_rows_target=eval_rows_target,
        ),
    ]


def export_finetune_manifest_json(path: str | Path, experiments: list[FineTuneExperiment]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(experiment) for experiment in experiments]
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _build_experiment(
    candidate: ModelCandidate,
    *,
    track: str,
    train_rows_target: int,
    eval_rows_target: int,
) -> FineTuneExperiment:
    if candidate.key == "qwen3_5_4b":
        return FineTuneExperiment(
            key=f"{candidate.key}_{track}",
            label=f"{candidate.label} {track}",
            track=track,
            train_model_id=candidate.train_model_id,
            runtime_repo_id=candidate.runtime_repo_id,
            runtime_gguf_filename=candidate.runtime_gguf_filename,
            runtime_gguf_url=candidate.runtime_gguf_url,
            method="bf16_lora",
            precision="bf16",
            max_seq_length=4096,
            lora_rank=32,
            lora_alpha=32,
            learning_rate=2e-4,
            per_device_batch_size=2,
            gradient_accumulation_steps=8,
            num_epochs=2,
            warmup_ratio=0.05,
            eval_steps=200,
            save_steps=200,
            dataset=_dataset_spec(train_rows_target, eval_rows_target),
            objective="Primary cost-efficient persona/dialogue baseline on 24GB VRAM.",
            selection_notes=[
                "Use this run to set the minimum acceptable persona fidelity and latency.",
                "Keep prompt template identical to runtime export expectations.",
                "Prefer broad scenario coverage over aggressive stylistic overfitting.",
            ],
        )

    return FineTuneExperiment(
        key=f"{candidate.key}_{track}",
        label=f"{candidate.label} {track}",
        track=track,
        train_model_id=candidate.train_model_id,
        runtime_repo_id=candidate.runtime_repo_id,
        runtime_gguf_filename=candidate.runtime_gguf_filename,
        runtime_gguf_url=candidate.runtime_gguf_url,
        method="bf16_lora",
        precision="bf16",
        max_seq_length=3072,
        lora_rank=32,
        lora_alpha=32,
        learning_rate=1.5e-4,
        per_device_batch_size=1,
        gradient_accumulation_steps=16,
        num_epochs=2,
        warmup_ratio=0.05,
        eval_steps=150,
        save_steps=150,
        dataset=_dataset_spec(train_rows_target, eval_rows_target),
        objective="Higher-capacity challenger run that must justify its added cost and latency.",
        selection_notes=[
            "Run only after the 4B baseline dataset and evaluation flow are stable.",
            "Watch sequence length and throughput closely on 24GB hardware.",
            "Promote only if gains are clear on persona fidelity and world consistency.",
        ],
    )


def _dataset_spec(train_rows_target: int, eval_rows_target: int) -> DatasetSpec:
    return DatasetSpec(
        train_rows_target=train_rows_target,
        eval_rows_target=eval_rows_target,
        prompt_format="teacher_prompt_pack_v1",
        train_jsonl_path="data/prompt_packs/train_teacher_requests.jsonl",
        train_parquet_path="data/prompt_packs/train_teacher_requests.parquet",
        eval_jsonl_path="data/prompt_packs/eval_teacher_requests.jsonl",
        eval_parquet_path="data/prompt_packs/eval_teacher_requests.parquet",
        merged_sft_jsonl_path="data/sft/teacher_sft_dataset.jsonl",
        merged_sft_parquet_path="data/sft/teacher_sft_dataset.parquet",
        train_sft_jsonl_path="data/sft/train_teacher_sft_dataset.jsonl",
        train_sft_parquet_path="data/sft/train_teacher_sft_dataset.parquet",
        eval_sft_jsonl_path="data/sft/eval_teacher_sft_dataset.jsonl",
        eval_sft_parquet_path="data/sft/eval_teacher_sft_dataset.parquet",
        teacher_model="gpt-5.3",
    )
