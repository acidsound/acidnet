from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acidnet.eval.prompt_only import export_prompt_only_eval_json, run_prompt_only_baseline_eval, summarize_scores
from acidnet.llm import DEFAULT_OPENAI_COMPAT_MODEL, EVAL_DIALOGUE_BACKENDS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate prompt-only dialogue behavior before fine-tuning.")
    parser.add_argument(
        "--dialogue-backend",
        choices=EVAL_DIALOGUE_BACKENDS,
        default="heuristic",
        help="Dialogue backend to evaluate. local_peft stays available here for in-process dev/eval parity.",
    )
    parser.add_argument(
        "--dialogue-model",
        default=None,
        help=f"Model identifier for the dialogue backend. openai_compat usually targets the llama-server alias (default: {DEFAULT_OPENAI_COMPAT_MODEL}).",
    )
    parser.add_argument(
        "--dialogue-endpoint",
        default=None,
        help="OpenAI-compatible endpoint for dialogue generation, typically llama-server for the promoted GGUF runtime.",
    )
    parser.add_argument(
        "--dialogue-adapter-path",
        default=None,
        help="Local LoRA adapter path for the local_peft dev/eval backend.",
    )
    parser.add_argument(
        "--output",
        default=str(Path("data") / "eval" / "prompt_only_baseline_report.json"),
        help="Output report path.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows = run_prompt_only_baseline_eval(
        dialogue_backend=args.dialogue_backend,
        dialogue_model=args.dialogue_model,
        dialogue_endpoint=args.dialogue_endpoint,
        dialogue_adapter_path=args.dialogue_adapter_path,
    )
    output_path = export_prompt_only_eval_json(args.output, rows)
    print(summarize_scores(rows))
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
