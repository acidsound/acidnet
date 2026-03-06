from __future__ import annotations

import argparse
from pathlib import Path

from acidnet.engine import Simulation
from acidnet.storage import SQLiteWorldStore

INTRO = """acidnet playable village MVP

You can move through the village, talk to NPCs, trade with vendors, wait for the world to advance,
and collect rumors as the NPC simulation runs around you.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the acidnet terminal village simulation.")
    parser.add_argument(
        "--db",
        default=str(Path("data") / "acidnet.sqlite"),
        help="SQLite database path for world snapshots.",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Disable SQLite snapshot persistence for this session.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    simulation = Simulation.create_demo()
    store = None if args.no_persist else SQLiteWorldStore(args.db)

    if store is not None:
        store.save_simulation(
            simulation,
            kind="session_start",
            message="CLI session started.",
            payload={"entrypoint": "cli"},
        )

    print(INTRO)
    if store is not None:
        print(f"Persistence: {Path(args.db)}")
    print(simulation.help_text())
    print()
    print(simulation.describe_location())

    try:
        while True:
            try:
                raw = input("\nacidnet> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting acidnet.")
                break

            if not raw:
                continue
            if raw.lower() in {"quit", "exit"}:
                print("Exiting acidnet.")
                break

            result = simulation.handle_command(raw)
            if store is not None:
                store.save_simulation(
                    simulation,
                    kind="command",
                    message=raw,
                    payload={"result_lines": result.lines},
                )
            if result.lines:
                print("\n".join(line for line in result.lines if line))
    finally:
        if store is not None:
            store.save_simulation(
                simulation,
                kind="session_end",
                message="CLI session ended.",
                payload={"entrypoint": "cli"},
            )
            store.close()
