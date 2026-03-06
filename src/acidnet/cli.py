from __future__ import annotations

import argparse
from pathlib import Path

from acidnet.engine import Simulation
from acidnet.storage import EventLogFile, SQLiteWorldStore

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
    parser.add_argument(
        "--event-log",
        default=str(Path("data") / "logs" / "acidnet-events.log"),
        help="Plain-text event log path for tailing runtime events.",
    )
    parser.add_argument(
        "--no-event-log",
        action="store_true",
        help="Disable plain-text event log file output.",
    )
    parser.add_argument(
        "--dialogue-backend",
        choices=("heuristic", "openai_compat", "local_peft"),
        default="heuristic",
        help="Dialogue backend to use for NPC talk interactions.",
    )
    parser.add_argument(
        "--dialogue-model",
        default=None,
        help="Model identifier for the dialogue backend.",
    )
    parser.add_argument(
        "--dialogue-endpoint",
        default=None,
        help="OpenAI-compatible endpoint for runtime dialogue generation.",
    )
    parser.add_argument(
        "--dialogue-adapter-path",
        default=None,
        help="Local LoRA adapter path for the local_peft backend.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    simulation = Simulation.create_demo(
        dialogue_backend=args.dialogue_backend,
        dialogue_model=args.dialogue_model,
        dialogue_endpoint=args.dialogue_endpoint,
        dialogue_adapter_path=args.dialogue_adapter_path,
    )
    store = None if args.no_persist else SQLiteWorldStore(args.db)
    event_log = None if args.no_event_log else EventLogFile(args.event_log)

    if store is not None:
        store.save_simulation(
            simulation,
            kind="session_start",
            message="CLI session started.",
            payload={"entrypoint": "cli"},
        )
    if event_log is not None:
        event_log.write(
            kind="session_start",
            message="CLI session started.",
            day=simulation.world.day,
            tick=simulation.world.tick,
            payload={"entrypoint": "cli", "dialogue_backend": args.dialogue_backend},
        )

    print(INTRO)
    if store is not None:
        print(f"Persistence: {Path(args.db)}")
    if event_log is not None:
        print(f"Event log: {Path(args.event_log)}")
    print(f"Dialogue backend: {args.dialogue_backend}")
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
            if event_log is not None:
                event_log.write(
                    kind="command",
                    message=raw,
                    day=simulation.world.day,
                    tick=simulation.world.tick,
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
        if event_log is not None:
            event_log.write(
                kind="session_end",
                message="CLI session ended.",
                day=simulation.world.day,
                tick=simulation.world.tick,
                payload={"entrypoint": "cli"},
            )
            event_log.close()
