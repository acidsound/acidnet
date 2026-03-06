from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acidnet.training.preference_dataset import (
    build_bootstrap_rejected_outputs,
    build_dialogue_preference_examples,
    export_preference_jsonl,
    export_preference_parquet,
)
from acidnet.training.sft_dataset import load_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export a dialogue preference dataset for optional DPO/ORPO refinement.")
    parser.add_argument(
        "--prompt-pack",
        default=str(Path("data") / "prompt_packs" / "bootstrap_teacher_requests.jsonl"),
        help="Prompt-pack JSONL path.",
    )
    parser.add_argument(
        "--chosen-output",
        default=str(Path("data") / "prompt_packs" / "bootstrap_teacher_outputs.jsonl"),
        help="Chosen teacher-output JSONL path.",
    )
    parser.add_argument(
        "--rejected-output",
        default=None,
        help="Rejected output JSONL path. If omitted, bootstrap rejected responses are synthesized automatically.",
    )
    parser.add_argument(
        "--output-jsonl",
        default=str(Path("data") / "preferences" / "bootstrap_dialogue_preferences.jsonl"),
        help="Preference JSONL output path.",
    )
    parser.add_argument(
        "--output-parquet",
        default=str(Path("data") / "preferences" / "bootstrap_dialogue_preferences.parquet"),
        help="Preference Parquet output path.",
    )
    parser.add_argument(
        "--manifest-output",
        default=str(Path("data") / "preferences" / "bootstrap_dialogue_preferences_manifest.json"),
        help="Manifest JSON output path.",
    )
    parser.add_argument("--format", choices=("jsonl", "parquet", "both"), default="both", help="Export format.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    prompt_rows = load_jsonl(args.prompt_pack)
    chosen_rows = load_jsonl(args.chosen_output)
    rejected_rows = load_jsonl(args.rejected_output) if args.rejected_output else build_bootstrap_rejected_outputs(prompt_rows)

    examples = build_dialogue_preference_examples(prompt_rows, chosen_rows, rejected_rows)
    jsonl_output = export_preference_jsonl(args.output_jsonl, examples)
    parquet_output = None
    if args.format in {"parquet", "both"}:
        parquet_output = export_preference_parquet(args.output_parquet, examples)

    manifest = {
        "rows": len(examples),
        "prompt_pack": args.prompt_pack,
        "chosen_output": args.chosen_output,
        "rejected_output": args.rejected_output or "bootstrap_rejected",
        "output_jsonl": str(jsonl_output),
        "output_parquet": str(parquet_output) if parquet_output else None,
    }
    manifest_path = Path(args.manifest_output)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Preference rows: {len(examples)}")
    print(f"JSONL: {jsonl_output}")
    if parquet_output:
        print(f"Parquet: {parquet_output}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
