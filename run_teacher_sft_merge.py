from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acidnet.training import export_sft_jsonl, export_sft_parquet, load_jsonl, merge_prompt_pack_with_teacher_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge teacher prompt packs with teacher outputs into SFT data.")
    parser.add_argument(
        "--prompt-pack",
        default=str(Path("data") / "prompt_packs" / "teacher_requests.jsonl"),
        help="Prompt-pack JSONL path.",
    )
    parser.add_argument(
        "--teacher-output",
        required=True,
        help="Teacher output JSONL path.",
    )
    parser.add_argument(
        "--jsonl-output",
        default=str(Path("data") / "sft" / "teacher_sft_dataset.jsonl"),
        help="Merged SFT JSONL output path.",
    )
    parser.add_argument(
        "--parquet-output",
        default=str(Path("data") / "sft" / "teacher_sft_dataset.parquet"),
        help="Merged SFT Parquet output path.",
    )
    parser.add_argument(
        "--format",
        choices=("jsonl", "parquet", "both"),
        default="jsonl",
        help="Artifact formats to export.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    prompt_rows = load_jsonl(args.prompt_pack)
    teacher_rows = load_jsonl(args.teacher_output)
    examples = merge_prompt_pack_with_teacher_outputs(prompt_rows, teacher_rows)

    print(f"Merged rows: {len(examples)}")
    if args.format in {"jsonl", "both"}:
        jsonl_path = export_sft_jsonl(args.jsonl_output, examples)
        print(f"JSONL: {jsonl_path}")
    if args.format in {"parquet", "both"}:
        parquet_path = export_sft_parquet(args.parquet_output, examples)
        print(f"Parquet: {parquet_path}")


if __name__ == "__main__":
    main()
