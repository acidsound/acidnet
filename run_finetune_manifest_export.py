from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acidnet.training import build_finetune_manifest, export_finetune_manifest_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export fine-tuning experiment manifests for acidnet.")
    parser.add_argument("--vram", type=int, default=24, help="Available GPU VRAM in GB.")
    parser.add_argument("--train-rows", type=int, default=50000, help="Target train rows.")
    parser.add_argument("--eval-rows", type=int, default=4000, help="Target eval rows.")
    parser.add_argument(
        "--output",
        default=str(Path("data") / "training" / "finetune_manifest.json"),
        help="Output manifest path.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest = build_finetune_manifest(
        vram_gb=args.vram,
        train_rows_target=args.train_rows,
        eval_rows_target=args.eval_rows,
    )
    output_path = export_finetune_manifest_json(args.output, manifest)
    print(f"Experiments: {len(manifest)}")
    print(f"Output: {output_path}")
    for experiment in manifest:
        print(f"- {experiment.key}: {experiment.train_model_id} [{experiment.track}]")


if __name__ == "__main__":
    main()
