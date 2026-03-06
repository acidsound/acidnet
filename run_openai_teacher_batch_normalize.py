from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acidnet.training import export_teacher_output_jsonl, load_jsonl, normalize_openai_batch_output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize OpenAI Batch output JSONL into teacher output JSONL.")
    parser.add_argument(
        "--batch-output",
        required=True,
        help="OpenAI Batch output JSONL file downloaded from the Files API.",
    )
    parser.add_argument(
        "--output",
        default=str(Path("data") / "prompt_packs" / "teacher_outputs.jsonl"),
        help="Normalized teacher output JSONL path.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    batch_rows = load_jsonl(args.batch_output)
    rows = normalize_openai_batch_output(batch_rows)
    output_path = export_teacher_output_jsonl(args.output, rows)
    print(f"Normalized teacher rows: {len(rows)}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
