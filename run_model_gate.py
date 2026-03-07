from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acidnet.eval import export_model_gate_json, run_model_gate, summarize_model_gate
from acidnet.llm import DEFAULT_OPENAI_COMPAT_MODEL, EVAL_DIALOGUE_BACKENDS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a combined dialogue and world-circulation gate for a backend.")
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
    parser.add_argument("--turns", type=int, default=120, help="Number of circulation turns to simulate.")
    parser.add_argument(
        "--output",
        default=str(Path("data") / "eval" / "model_gate_report.json"),
        help="Output report path.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = run_model_gate(
        dialogue_backend=args.dialogue_backend,
        dialogue_model=args.dialogue_model,
        dialogue_endpoint=args.dialogue_endpoint,
        dialogue_adapter_path=args.dialogue_adapter_path,
        circulation_turns=args.turns,
    )
    output_path = export_model_gate_json(args.output, report)
    print(summarize_model_gate(report))
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
