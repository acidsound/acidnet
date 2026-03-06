"""Training experiment and dataset generation helpers."""

from acidnet.training.dataset_builder import (
    export_prompt_pack_jsonl,
    export_prompt_pack_parquet,
    generate_demo_prompt_pack,
    generate_synthetic_prompt_pack,
)
from acidnet.training.experiment_registry import ModelCandidate, recommended_experiment_order
from acidnet.training.finetune_manifest import FineTuneExperiment, build_finetune_manifest, export_finetune_manifest_json
from acidnet.training.openai_batch import (
    OpenAIBatchRequest,
    TeacherOutputRow,
    build_openai_batch_requests,
    export_openai_batch_jsonl,
    export_teacher_output_jsonl,
    normalize_openai_batch_output,
)
from acidnet.training.sft_dataset import (
    coerce_sft_examples,
    export_sft_jsonl,
    export_sft_parquet,
    load_jsonl,
    merge_prompt_pack_with_teacher_outputs,
    split_sft_examples,
)
from acidnet.training.teacher_prompts import TeacherConfig
from acidnet.training.unsloth_runner import (
    RunPaths,
    UnslothRunSpec,
    build_unsloth_run_spec,
    export_unsloth_run_spec,
    export_unsloth_training_script,
)

__all__ = [
    "FineTuneExperiment",
    "ModelCandidate",
    "OpenAIBatchRequest",
    "RunPaths",
    "TeacherConfig",
    "TeacherOutputRow",
    "UnslothRunSpec",
    "build_openai_batch_requests",
    "build_finetune_manifest",
    "build_unsloth_run_spec",
    "export_openai_batch_jsonl",
    "export_prompt_pack_jsonl",
    "export_prompt_pack_parquet",
    "export_finetune_manifest_json",
    "coerce_sft_examples",
    "export_sft_jsonl",
    "export_sft_parquet",
    "export_teacher_output_jsonl",
    "export_unsloth_run_spec",
    "export_unsloth_training_script",
    "generate_demo_prompt_pack",
    "generate_synthetic_prompt_pack",
    "load_jsonl",
    "merge_prompt_pack_with_teacher_outputs",
    "normalize_openai_batch_output",
    "recommended_experiment_order",
    "split_sft_examples",
]
