from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acidnet.training import (
    baseline_pipeline_artifacts_to_dict,
    bootstrap_teacher_artifacts_to_dict,
    build_bootstrap_teacher_outputs,
    export_bootstrap_teacher_outputs,
    export_prompt_pack_jsonl,
    export_prompt_pack_parquet,
    generate_demo_prompt_pack,
    generate_synthetic_prompt_pack,
    prepare_qwen4b_baseline_artifacts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate bootstrap teacher data and prepare the Qwen3.5-4B baseline in one pass.")
    parser.add_argument("--mode", choices=("demo", "synthetic"), default="synthetic", help="Prompt-pack source.")
    parser.add_argument("--scenarios", type=int, default=2048, help="Number of synthetic scenarios.")
    parser.add_argument("--turns", type=int, default=4, help="Number of turns per scenario.")
    parser.add_argument("--seed", type=int, default=7, help="Deterministic generation seed.")
    parser.add_argument(
        "--tasks",
        choices=("dialogue", "planner", "both"),
        default="dialogue",
        help="Which bootstrap teacher tasks to include.",
    )
    parser.add_argument(
        "--prompt-pack-jsonl",
        default=str(Path("data") / "prompt_packs" / "bootstrap_teacher_requests.jsonl"),
        help="Filtered prompt-pack JSONL output path.",
    )
    parser.add_argument(
        "--prompt-pack-parquet",
        default=str(Path("data") / "prompt_packs" / "bootstrap_teacher_requests.parquet"),
        help="Filtered prompt-pack Parquet output path.",
    )
    parser.add_argument(
        "--teacher-output",
        default=str(Path("data") / "prompt_packs" / "bootstrap_teacher_outputs.jsonl"),
        help="Bootstrap teacher output JSONL path.",
    )
    parser.add_argument(
        "--manifest-output",
        default=str(Path("data") / "training" / "bootstrap_qwen4b_pipeline.json"),
        help="Pipeline manifest JSON output path.",
    )
    parser.add_argument("--train-rows", type=int, default=50_000, help="Target train rows.")
    parser.add_argument("--eval-rows", type=int, default=4_000, help="Target eval rows.")
    parser.add_argument(
        "--format",
        choices=("jsonl", "parquet", "both"),
        default="both",
        help="Whether to export JSONL only or JSONL plus Parquet.",
    )
    parser.add_argument("--vram", type=int, default=24, help="VRAM hint for choosing the baseline manifest.")
    parser.add_argument(
        "--trainer-backend",
        choices=("auto", "unsloth", "hf_peft"),
        default="auto",
        help="Training backend used if `--launch-train` is supplied.",
    )
    parser.add_argument(
        "--sft-variant",
        choices=("auto", "teacher_json", "runtime_dialogue"),
        default="auto",
        help="SFT dataset variant. `auto` uses runtime-aligned dialogue training for dialogue-only tasks.",
    )
    parser.add_argument(
        "--python-bin",
        default=sys.executable,
        help="Python interpreter used to launch the baseline trainer.",
    )
    parser.add_argument(
        "--training-output-dir",
        default=str(Path("data") / "training" / "qwen3_5_4b_bootstrap_baseline"),
        help="Output directory for the trained LoRA adapter.",
    )
    parser.add_argument(
        "--run-spec-output",
        default=str(Path("data") / "training" / "qwen3_5_4b_bootstrap_baseline_run_spec.json"),
        help="Training run-spec JSON output path.",
    )
    parser.add_argument(
        "--training-script-output",
        default=str(Path("data") / "training" / "train_qwen3_5_4b_bootstrap_baseline.py"),
        help="Generated training script output path.",
    )
    parser.add_argument(
        "--launch-train",
        action="store_true",
        help="Launch the baseline trainer after dataset and run artifacts are prepared.",
    )
    parser.add_argument(
        "--skip-dependency-check",
        action="store_true",
        help="Skip dependency checks when launching the baseline trainer.",
    )
    parser.add_argument(
        "--memory-profile",
        choices=("default", "low_vram"),
        default="default",
        help="Optional training override profile for constrained VRAM when launching the trainer.",
    )
    parser.add_argument("--max-seq-length", type=int, default=None, help="Optional max sequence length override for training launch.")
    parser.add_argument("--batch-size", type=int, default=None, help="Optional per-device batch size override for training launch.")
    parser.add_argument("--grad-accum", type=int, default=None, help="Optional gradient accumulation override for training launch.")
    parser.add_argument("--lora-rank", type=int, default=None, help="Optional LoRA rank override for training launch.")
    parser.add_argument("--lora-alpha", type=int, default=None, help="Optional LoRA alpha override for training launch.")
    parser.add_argument("--optimizer", default=None, help="Optional optimizer override for training launch.")
    parser.add_argument("--epochs", type=int, default=None, help="Optional train-epoch override for training launch.")
    parser.add_argument("--eval-steps", type=int, default=None, help="Optional eval interval override for training launch.")
    parser.add_argument("--save-steps", type=int, default=None, help="Optional checkpoint-save interval override for training launch.")
    parser.add_argument(
        "--load-in-4bit",
        action="store_true",
        help="Launch HF/PEFT training in 4-bit QLoRA mode.",
    )
    parser.add_argument(
        "--run-gate",
        action="store_true",
        help="Run the combined prompt-quality and circulation gate against the resulting local_peft adapter.",
    )
    parser.add_argument("--gate-turns", type=int, default=120, help="Number of circulation turns for the post-train gate.")
    parser.add_argument(
        "--gate-output",
        default=str(Path("data") / "eval" / "qwen3_5_4b_bootstrap_baseline_gate_report.json"),
        help="Post-train model gate JSON report path.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    trainer_backend = _resolve_trainer_backend(args.trainer_backend)
    selected_tasks = ("dialogue", "planner") if args.tasks == "both" else (args.tasks,)
    sft_variant = _resolve_sft_variant(args.sft_variant, selected_tasks)
    if args.mode == "demo":
        rows = generate_demo_prompt_pack(num_turns=args.turns)
    else:
        rows = generate_synthetic_prompt_pack(
            num_scenarios=args.scenarios,
            turns_per_scenario=args.turns,
            seed=args.seed,
        )
    rows = [row for row in rows if row.task in selected_tasks]

    prompt_jsonl_path = export_prompt_pack_jsonl(args.prompt_pack_jsonl, rows)
    prompt_parquet_path = None
    if args.format in {"parquet", "both"}:
        prompt_parquet_path = export_prompt_pack_parquet(args.prompt_pack_parquet, rows)

    prompt_row_dicts = []
    with Path(prompt_jsonl_path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                prompt_row_dicts.append(json.loads(line))
    teacher_rows = build_bootstrap_teacher_outputs(prompt_row_dicts, tasks=selected_tasks)
    teacher_artifacts = export_bootstrap_teacher_outputs(args.teacher_output, teacher_rows)

    baseline_artifacts = prepare_qwen4b_baseline_artifacts(
        prompt_pack_path=str(prompt_jsonl_path),
        teacher_output_path=args.teacher_output,
        merged_jsonl_path=str(Path("data") / "sft" / "bootstrap_teacher_sft_dataset.jsonl"),
        merged_parquet_path=str(Path("data") / "sft" / "bootstrap_teacher_sft_dataset.parquet"),
        train_jsonl_path=str(Path("data") / "sft" / "train_bootstrap_teacher_sft_dataset.jsonl"),
        train_parquet_path=str(Path("data") / "sft" / "train_bootstrap_teacher_sft_dataset.parquet"),
        eval_jsonl_path=str(Path("data") / "sft" / "eval_bootstrap_teacher_sft_dataset.jsonl"),
        eval_parquet_path=str(Path("data") / "sft" / "eval_bootstrap_teacher_sft_dataset.parquet"),
        training_output_dir=args.training_output_dir,
        run_spec_path=args.run_spec_output,
        training_script_path=args.training_script_output,
        export_format=args.format,
        trainer_backend=trainer_backend,
        sft_variant=sft_variant,
        seed=args.seed,
        train_rows_target=args.train_rows,
        eval_rows_target=args.eval_rows,
        vram_gb=args.vram,
    )

    manifest = {
        "mode": args.mode,
        "tasks": list(selected_tasks),
        "prompt_rows": len(rows),
        "prompt_pack_jsonl": str(prompt_jsonl_path),
        "prompt_pack_parquet": str(prompt_parquet_path) if prompt_parquet_path else None,
        "teacher": bootstrap_teacher_artifacts_to_dict(teacher_artifacts),
        "baseline": baseline_pipeline_artifacts_to_dict(baseline_artifacts),
    }
    manifest_path = Path(args.manifest_output)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Prompt rows: {len(rows)}")
    print(f"Teacher rows: {teacher_artifacts.rows}")
    print(f"Train rows: {baseline_artifacts.train_rows}")
    print(f"Eval rows: {baseline_artifacts.eval_rows}")
    print(f"Trainer backend: {trainer_backend}")
    print(f"SFT variant: {sft_variant}")
    print(f"Training output dir: {Path(args.training_output_dir)}")
    print(f"Pipeline manifest: {manifest_path}")

    if args.launch_train:
        launch_args = [
            args.python_bin,
            "run_qwen4b_baseline_train.py",
            "--train-dataset",
            baseline_artifacts.train_jsonl_path,
            "--eval-dataset",
            baseline_artifacts.eval_jsonl_path,
            "--output-dir",
            args.training_output_dir,
            "--script-output",
            args.training_script_output,
            "--spec-output",
            args.run_spec_output,
            "--trainer-backend",
            trainer_backend,
            "--memory-profile",
            args.memory_profile,
        ]
        if args.max_seq_length is not None:
            launch_args.extend(["--max-seq-length", str(args.max_seq_length)])
        if args.batch_size is not None:
            launch_args.extend(["--batch-size", str(args.batch_size)])
        if args.grad_accum is not None:
            launch_args.extend(["--grad-accum", str(args.grad_accum)])
        if args.lora_rank is not None:
            launch_args.extend(["--lora-rank", str(args.lora_rank)])
        if args.lora_alpha is not None:
            launch_args.extend(["--lora-alpha", str(args.lora_alpha)])
        if args.optimizer:
            launch_args.extend(["--optimizer", args.optimizer])
        if args.epochs is not None:
            launch_args.extend(["--epochs", str(args.epochs)])
        if args.eval_steps is not None:
            launch_args.extend(["--eval-steps", str(args.eval_steps)])
        if args.save_steps is not None:
            launch_args.extend(["--save-steps", str(args.save_steps)])
        if args.load_in_4bit:
            launch_args.append("--load-in-4bit")
        if args.skip_dependency_check:
            launch_args.append("--skip-dependency-check")
        subprocess.run(launch_args, check=True)

    adapter_path = Path(args.training_output_dir)
    if args.run_gate:
        if not adapter_path.exists():
            raise FileNotFoundError(
                f"Adapter directory '{adapter_path}' does not exist yet. Run with --launch-train first or point --training-output-dir at an existing adapter."
            )

    if args.run_gate:
        gate_args = [
            args.python_bin,
            "run_model_gate.py",
            "--dialogue-backend",
            "local_peft",
            "--dialogue-model",
            "Qwen/Qwen3.5-4B",
            "--dialogue-adapter-path",
            str(adapter_path),
            "--turns",
            str(args.gate_turns),
            "--output",
            args.gate_output,
        ]
        subprocess.run(gate_args, check=True)

def _resolve_trainer_backend(requested_backend: str) -> str:
    if requested_backend != "auto":
        return requested_backend
    try:
        importlib.import_module("unsloth")
        importlib.import_module("trl")
        return "unsloth"
    except ImportError:
        return "hf_peft"


def _resolve_sft_variant(requested_variant: str, selected_tasks: tuple[str, ...]) -> str:
    if requested_variant != "auto":
        return requested_variant
    if selected_tasks == ("dialogue",):
        return "runtime_dialogue"
    return "teacher_json"


if __name__ == "__main__":
    main()
