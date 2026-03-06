from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acidnet.training import (
    TeacherConfig,
    export_prompt_pack_jsonl,
    export_prompt_pack_parquet,
    generate_demo_prompt_pack,
    generate_synthetic_prompt_pack,
)
from acidnet.training.experiment_registry import selection_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export GPT teacher prompt packs for acidnet.")
    parser.add_argument(
        "--mode",
        choices=("demo", "synthetic"),
        default="synthetic",
        help="Prompt-pack generation mode.",
    )
    parser.add_argument(
        "--turns",
        type=int,
        default=4,
        help="Turns per scenario to roll out while collecting teacher prompt rows.",
    )
    parser.add_argument(
        "--scenarios",
        type=int,
        default=128,
        help="Number of synthetic scenarios to generate in synthetic mode.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Random seed for synthetic scenario generation.",
    )
    parser.add_argument(
        "--teacher-model",
        default="gpt-5.3",
        help="Teacher model name recorded in the prompt pack.",
    )
    parser.add_argument(
        "--world-name",
        default="acidnet village",
        help="World name inserted into the teacher system prompt.",
    )
    parser.add_argument(
        "--vram",
        type=int,
        default=24,
        help="Available GPU VRAM in GB for model selection notes.",
    )
    parser.add_argument(
        "--jsonl-output",
        default=str(Path("data") / "prompt_packs" / "teacher_requests.jsonl"),
        help="Output JSONL path.",
    )
    parser.add_argument(
        "--parquet-output",
        default=str(Path("data") / "prompt_packs" / "teacher_requests.parquet"),
        help="Output Parquet path.",
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
    config = TeacherConfig(teacher_model=args.teacher_model, world_name=args.world_name)
    if args.mode == "demo":
        rows = generate_demo_prompt_pack(num_turns=max(1, args.turns), config=config)
    else:
        rows = generate_synthetic_prompt_pack(
            num_scenarios=max(1, args.scenarios),
            turns_per_scenario=max(1, args.turns),
            config=config,
            seed=args.seed,
        )

    print(selection_summary(args.vram))
    print(f"Teacher prompt pack rows: {len(rows)}")

    if args.format in {"jsonl", "both"}:
        jsonl_path = export_prompt_pack_jsonl(args.jsonl_output, rows)
        print(f"JSONL: {jsonl_path}")
    if args.format in {"parquet", "both"}:
        parquet_path = export_prompt_pack_parquet(args.parquet_output, rows)
        print(f"Parquet: {parquet_path}")


if __name__ == "__main__":
    main()
