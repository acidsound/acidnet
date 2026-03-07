from __future__ import annotations

import argparse
from pathlib import Path

from acidnet.eval import export_circulation_report_json, run_circulation_eval
from acidnet.llm import RUNTIME_DIALOGUE_BACKENDS
from acidnet.simulator import Simulation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a headless circulation evaluation for the demo world.")
    parser.add_argument("--turns", type=int, default=120, help="Number of turns to simulate.")
    parser.add_argument(
        "--dialogue-backend",
        choices=RUNTIME_DIALOGUE_BACKENDS,
        default="heuristic",
        help="Dialogue backend to use during the simulation run.",
    )
    parser.add_argument("--dialogue-model", default=None, help="Optional model identifier for the dialogue backend.")
    parser.add_argument("--dialogue-endpoint", default=None, help="OpenAI-compatible endpoint for dialogue generation.")
    parser.add_argument(
        "--output",
        default=str(Path("data") / "eval" / "circulation_report.json"),
        help="Output JSON path.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    simulation = Simulation.create_demo(
        dialogue_backend=args.dialogue_backend,
        dialogue_model=args.dialogue_model,
        dialogue_endpoint=args.dialogue_endpoint,
    )
    report = run_circulation_eval(simulation, turns=args.turns)
    output_path = export_circulation_report_json(args.output, report)
    print(
        f"Saved circulation report to {output_path} | score={report.circulation_score:.3f} "
        f"| starving={report.starving_npc_count} | avg_active_locations={report.average_active_locations:.2f}"
    )


if __name__ == "__main__":
    main()
