from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acidnet.training.baseline_pipeline import (
    baseline_pipeline_artifacts_to_dict,
    prepare_qwen4b_baseline_artifacts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare merged SFT, split datasets, and baseline run artifacts in one pass.")
    parser.add_argument(
        "--prompt-pack",
        default=str(Path("data") / "prompt_packs" / "teacher_requests.jsonl"),
        help="Teacher prompt pack JSONL path.",
    )
    parser.add_argument(
        "--teacher-output",
        required=True,
        help="Teacher output JSONL path.",
    )
    parser.add_argument(
        "--merged-jsonl-output",
        default=str(Path("data") / "sft" / "teacher_sft_dataset.jsonl"),
        help="Merged SFT JSONL output path.",
    )
    parser.add_argument(
        "--merged-parquet-output",
        default=str(Path("data") / "sft" / "teacher_sft_dataset.parquet"),
        help="Merged SFT Parquet output path.",
    )
    parser.add_argument(
        "--train-jsonl-output",
        default=str(Path("data") / "sft" / "train_teacher_sft_dataset.jsonl"),
        help="Train SFT JSONL output path.",
    )
    parser.add_argument(
        "--train-parquet-output",
        default=str(Path("data") / "sft" / "train_teacher_sft_dataset.parquet"),
        help="Train SFT Parquet output path.",
    )
    parser.add_argument(
        "--eval-jsonl-output",
        default=str(Path("data") / "sft" / "eval_teacher_sft_dataset.jsonl"),
        help="Eval SFT JSONL output path.",
    )
    parser.add_argument(
        "--eval-parquet-output",
        default=str(Path("data") / "sft" / "eval_teacher_sft_dataset.parquet"),
        help="Eval SFT Parquet output path.",
    )
    parser.add_argument(
        "--training-output-dir",
        default=str(Path("data") / "training" / "qwen3_5_4b_baseline"),
        help="Training output directory.",
    )
    parser.add_argument(
        "--run-spec-output",
        default=str(Path("data") / "training" / "qwen3_5_4b_baseline_run_spec.json"),
        help="Run spec JSON output path.",
    )
    parser.add_argument(
        "--training-script-output",
        default=str(Path("data") / "training" / "train_qwen3_5_4b_baseline.py"),
        help="Generated Unsloth training script path.",
    )
    parser.add_argument(
        "--manifest-output",
        default=str(Path("data") / "training" / "qwen3_5_4b_baseline_pipeline.json"),
        help="Pipeline summary JSON output path.",
    )
    parser.add_argument("--train-rows", type=int, default=50_000, help="Target train rows.")
    parser.add_argument("--eval-rows", type=int, default=4_000, help="Target eval rows.")
    parser.add_argument(
        "--trainer-backend",
        choices=("unsloth", "hf_peft"),
        default="unsloth",
        help="Training backend used for the exported run spec and training script.",
    )
    parser.add_argument("--seed", type=int, default=7, help="Deterministic split seed.")
    parser.add_argument("--vram", type=int, default=24, help="Target VRAM used to choose the baseline manifest.")
    parser.add_argument(
        "--format",
        choices=("jsonl", "parquet", "both"),
        default="both",
        help="Whether to export JSONL only or JSONL plus Parquet.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    artifacts = prepare_qwen4b_baseline_artifacts(
        prompt_pack_path=args.prompt_pack,
        teacher_output_path=args.teacher_output,
        merged_jsonl_path=args.merged_jsonl_output,
        merged_parquet_path=args.merged_parquet_output,
        train_jsonl_path=args.train_jsonl_output,
        train_parquet_path=args.train_parquet_output,
        eval_jsonl_path=args.eval_jsonl_output,
        eval_parquet_path=args.eval_parquet_output,
        training_output_dir=args.training_output_dir,
        run_spec_path=args.run_spec_output,
        training_script_path=args.training_script_output,
        export_format=args.format,
        trainer_backend=args.trainer_backend,
        seed=args.seed,
        train_rows_target=args.train_rows,
        eval_rows_target=args.eval_rows,
        vram_gb=args.vram,
    )
    manifest_path = Path(args.manifest_output)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(baseline_pipeline_artifacts_to_dict(artifacts), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Experiment: {artifacts.experiment_key}")
    print(f"Train rows: {artifacts.train_rows}")
    print(f"Eval rows: {artifacts.eval_rows}")
    print(f"Pipeline manifest: {manifest_path}")
    print(f"Training script: {artifacts.training_script_path}")


if __name__ == "__main__":
    main()
