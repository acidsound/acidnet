from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from acidnet.training.finetune_manifest import build_finetune_manifest
from acidnet.training.hf_peft_runner import (
    build_hf_peft_run_spec,
    export_hf_peft_run_spec,
    export_hf_peft_training_script,
)
from acidnet.training.sft_dataset import (
    export_sft_jsonl,
    export_sft_parquet,
    load_jsonl,
    merge_prompt_pack_with_teacher_outputs,
    merge_prompt_pack_with_teacher_outputs_runtime_dialogue,
    split_sft_examples,
)
from acidnet.training.unsloth_runner import (
    RunPaths,
    build_unsloth_run_spec,
    export_unsloth_run_spec,
    export_unsloth_training_script,
)


@dataclass(frozen=True, slots=True)
class BaselinePipelineArtifacts:
    merged_jsonl_path: str
    merged_parquet_path: str | None
    train_jsonl_path: str
    train_parquet_path: str | None
    eval_jsonl_path: str
    eval_parquet_path: str | None
    run_spec_path: str
    training_script_path: str
    train_rows: int
    eval_rows: int
    experiment_key: str
    trainer_backend: str
    sft_variant: str


def prepare_qwen4b_baseline_artifacts(
    *,
    prompt_pack_path: str,
    teacher_output_path: str,
    merged_jsonl_path: str,
    merged_parquet_path: str,
    train_jsonl_path: str,
    train_parquet_path: str,
    eval_jsonl_path: str,
    eval_parquet_path: str,
    training_output_dir: str,
    run_spec_path: str,
    training_script_path: str,
    export_format: Literal["jsonl", "parquet", "both"] = "both",
    trainer_backend: Literal["unsloth", "hf_peft"] = "unsloth",
    sft_variant: Literal["teacher_json", "runtime_dialogue"] = "teacher_json",
    seed: int = 7,
    train_rows_target: int = 50_000,
    eval_rows_target: int = 4_000,
    vram_gb: int = 24,
) -> BaselinePipelineArtifacts:
    prompt_rows = load_jsonl(prompt_pack_path)
    teacher_rows = load_jsonl(teacher_output_path)
    if sft_variant == "runtime_dialogue":
        merged_examples = merge_prompt_pack_with_teacher_outputs_runtime_dialogue(prompt_rows, teacher_rows)
    else:
        merged_examples = merge_prompt_pack_with_teacher_outputs(prompt_rows, teacher_rows)
    train_examples, eval_examples = split_sft_examples(
        merged_examples,
        train_rows_target=train_rows_target,
        eval_rows_target=eval_rows_target,
        seed=seed,
    )

    merged_parquet_result: str | None = None
    train_parquet_result: str | None = None
    eval_parquet_result: str | None = None

    export_sft_jsonl(merged_jsonl_path, merged_examples)
    export_sft_jsonl(train_jsonl_path, train_examples)
    export_sft_jsonl(eval_jsonl_path, eval_examples)
    if export_format in {"parquet", "both"}:
        merged_parquet_result = str(export_sft_parquet(merged_parquet_path, merged_examples))
        train_parquet_result = str(export_sft_parquet(train_parquet_path, train_examples))
        eval_parquet_result = str(export_sft_parquet(eval_parquet_path, eval_examples))

    baseline = build_finetune_manifest(
        vram_gb=vram_gb,
        train_rows_target=train_rows_target,
        eval_rows_target=eval_rows_target,
    )[0]
    run_paths = RunPaths(
        train_dataset_path=train_jsonl_path,
        eval_dataset_path=eval_jsonl_path,
        output_dir=training_output_dir,
    )
    if trainer_backend == "hf_peft":
        run_spec = build_hf_peft_run_spec(baseline, run_paths)
        spec_path = export_hf_peft_run_spec(run_spec_path, run_spec)
        script_path = export_hf_peft_training_script(training_script_path, run_spec)
    else:
        run_spec = build_unsloth_run_spec(baseline, run_paths)
        spec_path = export_unsloth_run_spec(run_spec_path, run_spec)
        script_path = export_unsloth_training_script(training_script_path, run_spec)

    return BaselinePipelineArtifacts(
        merged_jsonl_path=str(Path(merged_jsonl_path)),
        merged_parquet_path=merged_parquet_result,
        train_jsonl_path=str(Path(train_jsonl_path)),
        train_parquet_path=train_parquet_result,
        eval_jsonl_path=str(Path(eval_jsonl_path)),
        eval_parquet_path=eval_parquet_result,
        run_spec_path=str(spec_path),
        training_script_path=str(script_path),
        train_rows=len(train_examples),
        eval_rows=len(eval_examples),
        experiment_key=baseline.key,
        trainer_backend=trainer_backend,
        sft_variant=sft_variant,
    )


def baseline_pipeline_artifacts_to_dict(artifacts: BaselinePipelineArtifacts) -> dict[str, object]:
    return asdict(artifacts)
