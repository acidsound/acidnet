from __future__ import annotations

import argparse
from pathlib import Path

from acidnet.llm import DEFAULT_OPENAI_COMPAT_MODEL, RUNTIME_DIALOGUE_BACKENDS
from acidnet.simulator import EventLogFile, SQLiteWorldStore, Simulation

INTRO = """acidnet playable village MVP

You can move through the village, talk to NPCs, trade with vendors, use next to advance the world,
and collect rumors as the NPC simulation runs around you.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the acidnet terminal village simulation.")
    parser.add_argument(
        "--player-name",
        default=None,
        help="Override and persist the default single-player name used for new demo sessions.",
    )
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
        choices=RUNTIME_DIALOGUE_BACKENDS,
        default="heuristic",
        help="Dialogue backend to use for NPC talk interactions. Runtime entrypoints promote the OpenAI-compatible GGUF path.",
    )
    parser.add_argument(
        "--dialogue-model",
        default=None,
        help=f"Model alias for the dialogue backend. For openai_compat, this should match the llama-server alias (default: {DEFAULT_OPENAI_COMPAT_MODEL}).",
    )
    parser.add_argument(
        "--dialogue-endpoint",
        default=None,
        help="OpenAI-compatible endpoint for runtime dialogue generation, typically llama-server serving the Q4 GGUF runtime.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config_store = SQLiteWorldStore(args.db)
    if args.player_name is not None:
        config_store.set_player_name(args.player_name)
    simulation = Simulation.create_demo(
        player_name=config_store.get_player_name(),
        dialogue_backend=args.dialogue_backend,
        dialogue_model=args.dialogue_model,
        dialogue_endpoint=args.dialogue_endpoint,
    )
    store = None if args.no_persist else config_store
    event_log = None if args.no_event_log else EventLogFile(args.event_log)
    simulation.set_dialogue_system_prompt(config_store.get_dialogue_system_prompt())

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
                    payload={"result_lines": result.lines, "result_entries": result.payload()},
                )
            if event_log is not None:
                event_log.write(
                    kind="command",
                    message=raw,
                    day=simulation.world.day,
                    tick=simulation.world.tick,
                    payload={"result_lines": result.lines, "result_entries": result.payload()},
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
        else:
            config_store.close()
        if event_log is not None:
            event_log.write(
                kind="session_end",
                message="CLI session ended.",
                day=simulation.world.day,
                tick=simulation.world.tick,
                payload={"entrypoint": "cli"},
            )
            event_log.close()
