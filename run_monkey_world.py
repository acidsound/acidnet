from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acidnet.engine import Simulation
from acidnet.eval.monkey import SimulationMonkeyRunner, export_monkey_report_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a headless monkey test over the village simulation.")
    parser.add_argument("--steps", type=int, default=120, help="Number of monkey steps to execute.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed.")
    parser.add_argument(
        "--dialogue-backend",
        choices=("heuristic", "openai_compat"),
        default="heuristic",
        help="Dialogue backend to exercise during monkey testing.",
    )
    parser.add_argument("--dialogue-model", default=None, help="Model identifier for the dialogue backend.")
    parser.add_argument("--dialogue-endpoint", default=None, help="OpenAI-compatible endpoint for dialogue generation.")
    parser.add_argument(
        "--output",
        default=str(Path("data") / "eval" / "monkey_report.json"),
        help="Output report path.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    simulation = Simulation.create_demo(
        dialogue_backend=args.dialogue_backend,
        dialogue_model=args.dialogue_model,
        dialogue_endpoint=args.dialogue_endpoint,
    )
    runner = SimulationMonkeyRunner(simulation, seed=args.seed)
    report = runner.run_steps(args.steps)
    output_path = export_monkey_report_json(args.output, report)
    print(
        f"steps={report.steps_executed} day={report.final_day} tick={report.final_tick} "
        f"location={report.final_player_location} rumors={report.known_rumors}"
    )
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
