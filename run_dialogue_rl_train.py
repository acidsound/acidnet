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

from acidnet.training import build_finetune_manifest
from acidnet.training.dpo_runner import build_dpo_run_spec, export_dpo_run_spec, export_dpo_training_script


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and optionally launch optional dialogue DPO refinement.")
    parser.add_argument(
        "--train-dataset",
        default=str(Path("data") / "preferences" / "bootstrap_dialogue_preferences.jsonl"),
        help="Preference train JSONL path.",
    )
    parser.add_argument(
        "--eval-dataset",
        default=str(Path("data") / "preferences" / "bootstrap_dialogue_preferences.jsonl"),
        help="Preference eval JSONL path.",
    )
    parser.add_argument(
        "--sft-adapter-path",
        default=None,
        help="Optional SFT adapter directory to continue from before DPO.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path("data") / "training" / "qwen3_5_4b_dialogue_dpo"),
        help="DPO output directory.",
    )
    parser.add_argument(
        "--script-output",
        default=str(Path("data") / "training" / "train_qwen3_5_4b_dialogue_dpo.py"),
        help="Generated DPO training script path.",
    )
    parser.add_argument(
        "--spec-output",
        default=str(Path("data") / "training" / "qwen3_5_4b_dialogue_dpo_run_spec.json"),
        help="DPO run-spec JSON path.",
    )
    parser.add_argument("--python-bin", default=sys.executable, help="Python interpreter used to launch training.")
    parser.add_argument("--prepare-only", action="store_true", help="Generate the run spec and script without launching.")
    parser.add_argument(
        "--skip-dependency-check",
        action="store_true",
        help="Skip checking for datasets, peft, transformers, and trl.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    baseline = build_finetune_manifest(vram_gb=24)[0]
    run_spec = build_dpo_run_spec(
        baseline,
        train_dataset_path=args.train_dataset,
        eval_dataset_path=args.eval_dataset,
        output_dir=args.output_dir,
        sft_adapter_path=args.sft_adapter_path,
    )
    spec_path = export_dpo_run_spec(args.spec_output, run_spec)
    script_path = export_dpo_training_script(args.script_output, run_spec)
    print(f"Experiment: {run_spec.experiment_key}")
    print(f"Run spec: {spec_path}")
    print(f"Training script: {script_path}")

    if args.prepare_only:
        return
    if not args.skip_dependency_check:
        _assert_rl_dependencies()

    subprocess.run([args.python_bin, str(script_path)], check=True)


def _assert_rl_dependencies() -> None:
    missing: list[str] = []
    for module_name in ("datasets", "peft", "transformers", "trl"):
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(module_name)
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Missing RL dependencies: {joined}. Install the optional dialogue-RL environment before launching DPO."
        )


if __name__ == "__main__":
    main()
