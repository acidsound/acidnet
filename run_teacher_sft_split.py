from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acidnet.training import coerce_sft_examples, export_sft_jsonl, export_sft_parquet, load_jsonl, split_sft_examples


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Split merged teacher SFT data into deterministic train/eval artifacts.")
    parser.add_argument(
        "--input",
        default=str(Path("data") / "sft" / "bootstrap_teacher_sft_dataset.jsonl"),
        help="Merged SFT JSONL input path.",
    )
    parser.add_argument(
        "--train-output",
        default=str(Path("data") / "sft" / "train_bootstrap_teacher_sft_dataset.jsonl"),
        help="Train SFT JSONL output path.",
    )
    parser.add_argument(
        "--eval-output",
        default=str(Path("data") / "sft" / "eval_bootstrap_teacher_sft_dataset.jsonl"),
        help="Eval SFT JSONL output path.",
    )
    parser.add_argument(
        "--train-parquet-output",
        default=str(Path("data") / "sft" / "train_bootstrap_teacher_sft_dataset.parquet"),
        help="Train SFT Parquet output path.",
    )
    parser.add_argument(
        "--eval-parquet-output",
        default=str(Path("data") / "sft" / "eval_bootstrap_teacher_sft_dataset.parquet"),
        help="Eval SFT Parquet output path.",
    )
    parser.add_argument("--train-rows", type=int, default=50_000, help="Target number of train rows.")
    parser.add_argument("--eval-rows", type=int, default=4_000, help="Target number of eval rows.")
    parser.add_argument("--eval-ratio", type=float, default=0.08, help="Fallback eval ratio when eval rows are not fixed.")
    parser.add_argument("--seed", type=int, default=7, help="Deterministic split seed.")
    parser.add_argument(
        "--format",
        choices=("jsonl", "parquet", "both"),
        default="both",
        help="Artifact formats to export.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows = load_jsonl(args.input)
    examples = coerce_sft_examples(rows)
    train_examples, eval_examples = split_sft_examples(
        examples,
        train_rows_target=args.train_rows,
        eval_rows_target=args.eval_rows,
        eval_ratio=args.eval_ratio,
        seed=args.seed,
    )

    print(f"Input rows: {len(examples)}")
    print(f"Train rows: {len(train_examples)}")
    print(f"Eval rows: {len(eval_examples)}")
    if args.format in {"jsonl", "both"}:
        train_path = export_sft_jsonl(args.train_output, train_examples)
        eval_path = export_sft_jsonl(args.eval_output, eval_examples)
        print(f"Train JSONL: {train_path}")
        print(f"Eval JSONL: {eval_path}")
    if args.format in {"parquet", "both"}:
        train_parquet = export_sft_parquet(args.train_parquet_output, train_examples)
        eval_parquet = export_sft_parquet(args.eval_parquet_output, eval_examples)
        print(f"Train Parquet: {train_parquet}")
        print(f"Eval Parquet: {eval_parquet}")


if __name__ == "__main__":
    main()
