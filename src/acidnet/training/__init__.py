"""Training experiment and dataset generation helpers."""

from acidnet.training.dataset_builder import (
    export_prompt_pack_jsonl,
    export_prompt_pack_parquet,
    generate_demo_prompt_pack,
    generate_synthetic_prompt_pack,
)
from acidnet.training.experiment_registry import ModelCandidate, recommended_experiment_order
from acidnet.training.finetune_manifest import FineTuneExperiment, build_finetune_manifest, export_finetune_manifest_json
from acidnet.training.sft_dataset import export_sft_jsonl, export_sft_parquet, load_jsonl, merge_prompt_pack_with_teacher_outputs
from acidnet.training.teacher_prompts import TeacherConfig

__all__ = [
    "FineTuneExperiment",
    "ModelCandidate",
    "TeacherConfig",
    "build_finetune_manifest",
    "export_prompt_pack_jsonl",
    "export_prompt_pack_parquet",
    "export_finetune_manifest_json",
    "generate_demo_prompt_pack",
    "generate_synthetic_prompt_pack",
    "export_sft_jsonl",
    "export_sft_parquet",
    "load_jsonl",
    "merge_prompt_pack_with_teacher_outputs",
    "recommended_experiment_order",
]
