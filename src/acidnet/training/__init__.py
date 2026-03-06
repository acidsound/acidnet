"""Training experiment and dataset generation helpers."""

from acidnet.training.baseline_pipeline import (
    BaselinePipelineArtifacts,
    baseline_pipeline_artifacts_to_dict,
    prepare_qwen4b_baseline_artifacts,
)
from acidnet.training.bootstrap_teacher import (
    BootstrapTeacherArtifacts,
    bootstrap_teacher_artifacts_to_dict,
    build_bootstrap_teacher_outputs,
    export_bootstrap_teacher_outputs,
)
from acidnet.training.dataset_builder import (
    export_prompt_pack_jsonl,
    export_prompt_pack_parquet,
    generate_demo_prompt_pack,
    generate_synthetic_prompt_pack,
)
from acidnet.training.experiment_registry import ModelCandidate, recommended_experiment_order
from acidnet.training.finetune_manifest import FineTuneExperiment, build_finetune_manifest, export_finetune_manifest_json
from acidnet.training.hf_peft_runner import (
    HFPeftRunSpec,
    build_hf_peft_run_spec,
    export_hf_peft_run_spec,
    export_hf_peft_training_script,
)
from acidnet.training.dpo_runner import (
    DPORunSpec,
    build_dpo_run_spec,
    export_dpo_run_spec,
    export_dpo_training_script,
)
from acidnet.training.gguf_export import (
    GGUFExportArtifacts,
    LlamaCppToolchain,
    build_hf_to_gguf_command,
    build_lora_to_gguf_command,
    build_quantize_command,
    export_lora_adapter_to_gguf,
    export_merged_checkpoint_to_gguf,
    gguf_export_artifacts_to_dict,
    merge_lora_adapter,
    resolve_llama_cpp_toolchain,
)
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
from acidnet.training.preference_dataset import (
    PreferenceExample,
    build_bootstrap_rejected_outputs,
    build_dialogue_preference_examples,
    export_preference_jsonl,
    export_preference_parquet,
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
    "BaselinePipelineArtifacts",
    "BootstrapTeacherArtifacts",
    "DPORunSpec",
    "GGUFExportArtifacts",
    "HFPeftRunSpec",
    "LlamaCppToolchain",
    "PreferenceExample",
    "TeacherConfig",
    "TeacherOutputRow",
    "UnslothRunSpec",
    "bootstrap_teacher_artifacts_to_dict",
    "baseline_pipeline_artifacts_to_dict",
    "build_bootstrap_rejected_outputs",
    "build_dialogue_preference_examples",
    "build_dpo_run_spec",
    "build_hf_to_gguf_command",
    "build_hf_peft_run_spec",
    "build_lora_to_gguf_command",
    "build_openai_batch_requests",
    "build_bootstrap_teacher_outputs",
    "build_finetune_manifest",
    "build_quantize_command",
    "build_unsloth_run_spec",
    "export_dpo_run_spec",
    "export_dpo_training_script",
    "export_hf_peft_run_spec",
    "export_hf_peft_training_script",
    "export_openai_batch_jsonl",
    "export_bootstrap_teacher_outputs",
    "export_lora_adapter_to_gguf",
    "export_merged_checkpoint_to_gguf",
    "export_preference_jsonl",
    "export_preference_parquet",
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
    "gguf_export_artifacts_to_dict",
    "load_jsonl",
    "merge_lora_adapter",
    "merge_prompt_pack_with_teacher_outputs",
    "normalize_openai_batch_output",
    "prepare_qwen4b_baseline_artifacts",
    "recommended_experiment_order",
    "resolve_llama_cpp_toolchain",
    "split_sft_examples",
]
