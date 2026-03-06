from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acidnet.training import build_openai_batch_requests, export_openai_batch_jsonl, load_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare OpenAI Batch JSONL requests from teacher prompt packs.")
    parser.add_argument(
        "--prompt-pack",
        default=str(Path("data") / "prompt_packs" / "teacher_requests.jsonl"),
        help="Teacher prompt-pack JSONL path.",
    )
    parser.add_argument("--model", default="gpt-5.3", help="OpenAI model name for the teacher batch.")
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=512,
        help="Maximum output tokens per teacher request.",
    )
    parser.add_argument(
        "--output",
        default=str(Path("data") / "prompt_packs" / "openai_batch_requests.jsonl"),
        help="OpenAI Batch request JSONL output path.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    prompt_rows = load_jsonl(args.prompt_pack)
    requests = build_openai_batch_requests(
        prompt_rows,
        model=args.model,
        max_output_tokens=args.max_output_tokens,
    )
    output_path = export_openai_batch_jsonl(args.output, requests)
    print(f"Batch requests: {len(requests)}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
