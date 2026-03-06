from __future__ import annotations

import argparse
from dataclasses import replace
import importlib
import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acidnet.training import (
    RunPaths,
    build_finetune_manifest,
    build_hf_peft_run_spec,
    build_unsloth_run_spec,
    export_hf_peft_run_spec,
    export_hf_peft_training_script,
    export_unsloth_run_spec,
    export_unsloth_training_script,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and optionally launch the Qwen3.5-4B baseline Unsloth run.")
    parser.add_argument(
        "--train-dataset",
        default=str(Path("data") / "sft" / "train_teacher_sft_dataset.jsonl"),
        help="Train SFT JSONL path.",
    )
    parser.add_argument(
        "--eval-dataset",
        default=str(Path("data") / "sft" / "eval_teacher_sft_dataset.jsonl"),
        help="Eval SFT JSONL path.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path("data") / "training" / "qwen3_5_4b_baseline"),
        help="Training output directory.",
    )
    parser.add_argument(
        "--script-output",
        default=str(Path("data") / "training" / "train_qwen3_5_4b_baseline.py"),
        help="Generated training script path.",
    )
    parser.add_argument(
        "--trainer-backend",
        choices=("auto", "unsloth", "hf_peft"),
        default="auto",
        help="Training backend to prepare and launch.",
    )
    parser.add_argument(
        "--spec-output",
        default=str(Path("data") / "training" / "qwen3_5_4b_baseline_run_spec.json"),
        help="Run spec JSON path.",
    )
    parser.add_argument("--python-bin", default=sys.executable, help="Python interpreter used to launch training.")
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Only generate the run spec and training script without launching training.",
    )
    parser.add_argument(
        "--skip-dependency-check",
        action="store_true",
        help="Skip checking for `datasets`, `trl`, and `unsloth` before launch.",
    )
    parser.add_argument(
        "--memory-profile",
        choices=("default", "low_vram"),
        default="default",
        help="Optional runtime-safe override profile for constrained VRAM.",
    )
    parser.add_argument("--max-seq-length", type=int, default=None, help="Override max sequence length.")
    parser.add_argument("--batch-size", type=int, default=None, help="Override per-device train batch size.")
    parser.add_argument("--grad-accum", type=int, default=None, help="Override gradient accumulation steps.")
    parser.add_argument("--lora-rank", type=int, default=None, help="Override LoRA rank.")
    parser.add_argument("--lora-alpha", type=int, default=None, help="Override LoRA alpha.")
    parser.add_argument("--optimizer", default=None, help="Override optimizer name for the generated trainer script.")
    parser.add_argument("--epochs", type=int, default=None, help="Override the number of train epochs.")
    parser.add_argument("--eval-steps", type=int, default=None, help="Override evaluation interval in optimizer steps.")
    parser.add_argument("--save-steps", type=int, default=None, help="Override checkpoint save interval in optimizer steps.")
    parser.add_argument(
        "--load-in-4bit",
        action="store_true",
        help="Load the base model in 4-bit QLoRA mode for lower VRAM use.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    baseline = build_finetune_manifest(vram_gb=24)[0]
    backend = _resolve_backend(args.trainer_backend)
    run_paths = RunPaths(
        train_dataset_path=args.train_dataset,
        eval_dataset_path=args.eval_dataset,
        output_dir=args.output_dir,
    )
    if backend == "unsloth":
        run_spec = build_unsloth_run_spec(baseline, run_paths)
        spec_path = export_unsloth_run_spec(args.spec_output, run_spec)
        script_path = export_unsloth_training_script(args.script_output, run_spec)
    else:
        run_spec = build_hf_peft_run_spec(baseline, run_paths)
        run_spec = _apply_hf_peft_overrides(run_spec, args)
        spec_path = export_hf_peft_run_spec(args.spec_output, run_spec)
        script_path = export_hf_peft_training_script(args.script_output, run_spec)
    print(f"Experiment: {baseline.key}")
    print(f"Trainer backend: {backend}")
    if backend == "hf_peft":
        print(
            "Memory profile: "
            f"{args.memory_profile} | seq={run_spec.max_seq_length} | batch={run_spec.per_device_train_batch_size} "
            f"| grad_accum={run_spec.gradient_accumulation_steps} | load_in_4bit={run_spec.load_in_4bit}"
        )
    print(f"Run spec: {spec_path}")
    print(f"Training script: {script_path}")

    if args.prepare_only:
        return
    if not args.skip_dependency_check:
        _assert_training_dependencies(
            backend,
            requires_4bit=bool(
                backend == "hf_peft"
                and (
                    getattr(run_spec, "load_in_4bit", False)
                    or args.load_in_4bit
                    or args.memory_profile == "low_vram"
                )
            ),
        )

    subprocess.run([args.python_bin, str(script_path)], check=True)


def _resolve_backend(requested_backend: str) -> str:
    if requested_backend != "auto":
        return requested_backend
    try:
        importlib.import_module("unsloth")
        importlib.import_module("trl")
        return "unsloth"
    except ImportError:
        return "hf_peft"


def _apply_hf_peft_overrides(run_spec, args):
    updates: dict[str, object] = {}
    if args.memory_profile == "low_vram":
        updates.update(
            {
                "max_seq_length": min(run_spec.max_seq_length, 2048),
                "per_device_train_batch_size": 1,
                "gradient_accumulation_steps": max(run_spec.gradient_accumulation_steps, 16),
                "lora_rank": min(run_spec.lora_rank, 16),
                "lora_alpha": min(run_spec.lora_alpha, 16),
                "load_in_4bit": True,
                "optimizer": "paged_adamw_8bit",
            }
        )
    if args.max_seq_length is not None:
        updates["max_seq_length"] = args.max_seq_length
    if args.batch_size is not None:
        updates["per_device_train_batch_size"] = args.batch_size
    if args.grad_accum is not None:
        updates["gradient_accumulation_steps"] = args.grad_accum
    if args.lora_rank is not None:
        updates["lora_rank"] = args.lora_rank
    if args.lora_alpha is not None:
        updates["lora_alpha"] = args.lora_alpha
    if args.optimizer is not None:
        updates["optimizer"] = args.optimizer
    if args.epochs is not None:
        updates["num_train_epochs"] = args.epochs
    if args.eval_steps is not None:
        updates["eval_steps"] = args.eval_steps
    if args.save_steps is not None:
        updates["save_steps"] = args.save_steps
    if args.load_in_4bit:
        updates["load_in_4bit"] = True
        updates.setdefault("optimizer", "paged_adamw_8bit")
    return replace(run_spec, **updates) if updates else run_spec


def _assert_training_dependencies(backend: str, *, requires_4bit: bool = False) -> None:
    missing: list[str] = []
    required_modules = ("datasets", "trl", "unsloth") if backend == "unsloth" else ("datasets", "peft", "transformers")
    if requires_4bit and backend == "hf_peft":
        required_modules = required_modules + ("bitsandbytes",)
    for module_name in required_modules:
        try:
            if module_name == "peft":
                from acidnet.training.windows_env import ensure_windows_shims_on_path

                ensure_windows_shims_on_path()
            importlib.import_module(module_name)
        except ImportError:
            missing.append(module_name)
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Missing training dependencies: {joined}. "
            f"Install the dependencies required for the {backend} backend before launching the baseline run."
        )


if __name__ == "__main__":
    main()
