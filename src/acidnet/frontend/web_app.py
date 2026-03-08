from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from acidnet.llm import DEFAULT_OPENAI_COMPAT_MODEL, RUNTIME_DIALOGUE_BACKENDS
from acidnet.simulator.service import SimulatorService

WebSimulationRuntime = SimulatorService


class AcidNetWebHandler(BaseHTTPRequestHandler):
    server: "AcidNetWebServer"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._serve_asset("index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/api/state":
            self._write_json(HTTPStatus.OK, self.server.runtime.scene_payload())
            return
        if parsed.path == "/api/events":
            query = parse_qs(parsed.query)
            after_seq = self._parse_int(query.get("after_seq", ["0"])[0], default=0, minimum=0)
            timeout_s = self._parse_float(query.get("timeout_s", ["15"])[0], default=15.0, minimum=0.0)
            limit = self._parse_int(query.get("limit", ["64"])[0], default=64, minimum=1)
            self._write_json(
                HTTPStatus.OK,
                self.server.runtime.events_payload(after_seq=after_seq, timeout_s=timeout_s, limit=limit),
            )
            return
        if parsed.path == "/api/dialogue-prompt":
            self._write_json(HTTPStatus.OK, self.server.runtime.dialogue_prompt_payload())
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/command", "/api/dialogue-prompt"}:
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        try:
            body = self.rfile.read(content_length) if content_length else b"{}"
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body."})
            return
        if parsed.path == "/api/dialogue-prompt":
            if payload.get("reset_default"):
                result = self.server.runtime.reset_dialogue_system_prompt()
            else:
                result = self.server.runtime.save_dialogue_system_prompt(str(payload.get("prompt", "")))
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            self._write_json(status, result)
            return
        command = str(payload.get("command", "")).strip()
        result = self.server.runtime.run_command(command)
        status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
        self._write_json(status, result)

    def _serve_asset(self, relative_path: str, content_type: str) -> None:
        asset_path = self.server.asset_root / relative_path
        if not asset_path.exists():
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Asset not found."})
            return
        content = asset_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _parse_int(self, raw: str, *, default: int, minimum: int) -> int:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return default
        return max(minimum, value)

    def _parse_float(self, raw: str, *, default: float, minimum: float) -> float:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return default
        return max(minimum, value)


class AcidNetWebServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], runtime: WebSimulationRuntime) -> None:
        super().__init__(server_address, AcidNetWebHandler)
        self.runtime = runtime
        self.asset_root = Path(__file__).resolve().parent / "client"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the acidnet shareable web frontend.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
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
        "--dialogue-backend",
        choices=RUNTIME_DIALOGUE_BACKENDS,
        default="heuristic",
        help="Dialogue backend to use for NPC interactions. Runtime entrypoints promote the OpenAI-compatible GGUF path.",
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
    parser.add_argument(
        "--event-log",
        default=str(Path("data") / "logs" / "acidnet-web-events.log"),
        help="Plain-text event log path for tailing runtime events.",
    )
    parser.add_argument(
        "--no-event-log",
        action="store_true",
        help="Disable plain-text event log file output.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    runtime = WebSimulationRuntime(
        db_path=args.db,
        persist=not args.no_persist,
        player_name=args.player_name,
        dialogue_backend=args.dialogue_backend,
        dialogue_model=args.dialogue_model,
        dialogue_endpoint=args.dialogue_endpoint,
        event_log_path=None if args.no_event_log else args.event_log,
    )
    server = AcidNetWebServer((args.host, args.port), runtime)
    print(f"acidnet web frontend listening on http://{args.host}:{args.port}")
    print("Use --host 0.0.0.0 to share on your local network.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down acidnet web frontend.")
    finally:
        server.shutdown()
        server.server_close()
        runtime.close()
