from __future__ import annotations

import argparse
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
    build_unsloth_run_spec,
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
    return parser


def main() -> None:
    args = build_parser().parse_args()
    baseline = build_finetune_manifest(vram_gb=24)[0]
    run_spec = build_unsloth_run_spec(
        baseline,
        RunPaths(
            train_dataset_path=args.train_dataset,
            eval_dataset_path=args.eval_dataset,
            output_dir=args.output_dir,
        ),
    )
    spec_path = export_unsloth_run_spec(args.spec_output, run_spec)
    script_path = export_unsloth_training_script(args.script_output, run_spec)
    print(f"Experiment: {baseline.key}")
    print(f"Run spec: {spec_path}")
    print(f"Training script: {script_path}")

    if args.prepare_only:
        return
    if not args.skip_dependency_check:
        _assert_training_dependencies()

    subprocess.run([args.python_bin, str(script_path)], check=True)


def _assert_training_dependencies() -> None:
    missing: list[str] = []
    for module_name in ("datasets", "trl", "unsloth"):
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(module_name)
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Missing training dependencies: {joined}. "
            "Install the training environment before launching the baseline run."
        )


if __name__ == "__main__":
    main()
