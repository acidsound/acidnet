from __future__ import annotations

import argparse
import json
import threading
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from acidnet.engine import Simulation
from acidnet.engine.simulation import CONSUMPTION_VALUE, TurnEvent
from acidnet.storage import EventLogFile, SQLiteWorldStore

MAP_GRID = {
    "shrine": {"row": 1, "column": 2, "glyph": "^"},
    "bakery": {"row": 1, "column": 4, "glyph": "B"},
    "tavern": {"row": 2, "column": 1, "glyph": "T"},
    "square": {"row": 2, "column": 3, "glyph": "+"},
    "smithy": {"row": 2, "column": 5, "glyph": "S"},
    "riverside": {"row": 3, "column": 1, "glyph": "~"},
    "farm": {"row": 3, "column": 3, "glyph": '"'},
}


class WebSimulationRuntime:
    def __init__(
        self,
        *,
        db_path: str | Path = Path("data") / "acidnet.sqlite",
        persist: bool = True,
        dialogue_backend: str = "heuristic",
        dialogue_model: str | None = None,
        dialogue_endpoint: str | None = None,
        dialogue_adapter_path: str | None = None,
        event_log_path: str | Path | None = Path("data") / "logs" / "acidnet-web-events.log",
        prepare_dialogue: bool = True,
    ) -> None:
        self.lock = threading.RLock()
        self.simulation = Simulation.create_demo(
            dialogue_backend=dialogue_backend,
            dialogue_model=dialogue_model,
            dialogue_endpoint=dialogue_endpoint,
            dialogue_adapter_path=dialogue_adapter_path,
        )
        self.config_store = SQLiteWorldStore(db_path)
        self.store = self.config_store if persist else None
        self.event_log = EventLogFile(event_log_path) if event_log_path is not None else None
        self.simulation.set_dialogue_system_prompt(self.config_store.get_dialogue_system_prompt())
        self.dialogue_ready = False
        self.dialogue_loading = False
        self.dialogue_message = f"Loading {dialogue_backend} dialogue model..."
        self.recent_events: deque[dict[str, Any]] = deque(maxlen=96)
        self._asset_root = Path(__file__).resolve().parent / "web"

        self._record_system(
            "session_start",
            "Web session started.",
            payload={"entrypoint": "web", "dialogue_backend": dialogue_backend},
            save_snapshot=True,
        )
        self._append_event("system", "acidnet web frontend ready.")
        self._append_event("system", "Share this URL to get feedback on the simulation state and interaction loop.")

        if prepare_dialogue:
            self._append_event("system", self.dialogue_message)
            self._start_dialogue_prepare()
        else:
            if dialogue_backend == "heuristic":
                self.dialogue_ready = True
                self.dialogue_message = f"{type(self.simulation.dialogue_adapter).__name__} ready."
            else:
                self.dialogue_message = "Dialogue preparation skipped for this runtime."
            self._append_event("system", self.dialogue_message)

    @property
    def asset_root(self) -> Path:
        return self._asset_root

    def _append_event(self, kind: str, text: str) -> None:
        self.recent_events.append(
            {
                "kind": kind,
                "text": text,
                "day": self.simulation.world.day,
                "tick": self.simulation.world.tick,
            }
        )

    def _record_system(
        self,
        kind: str,
        message: str,
        *,
        payload: dict[str, Any] | None = None,
        save_snapshot: bool = False,
    ) -> None:
        if save_snapshot and self.store is not None:
            self.store.save_simulation(self.simulation, kind=kind, message=message, payload=payload)
        if self.event_log is not None:
            self.event_log.write(
                kind=kind,
                message=message,
                day=self.simulation.world.day,
                tick=self.simulation.world.tick,
                payload=payload,
            )

    def _start_dialogue_prepare(self) -> None:
        if self.dialogue_loading or self.dialogue_ready:
            return
        self.dialogue_loading = True
        thread = threading.Thread(target=self._prepare_dialogue_worker, name="acidnet-web-dialogue-prepare", daemon=True)
        thread.start()

    def _prepare_dialogue_worker(self) -> None:
        try:
            message = self.simulation.prepare_dialogue_adapter()
        except Exception as exc:
            success = False
            message = f"Dialogue model failed to load: {exc}"
        else:
            success = True
        with self.lock:
            self.dialogue_loading = False
            self.dialogue_ready = success
            self.dialogue_message = message
            self._append_event("system", message)

    def _is_dialogue_command(self, command: str) -> bool:
        lowered = command.strip().lower()
        return lowered.startswith("talk") or lowered.startswith("say ") or lowered.startswith("tell ") or lowered.startswith("ask ")

    def _scene_people(self) -> list[dict[str, Any]]:
        if self.simulation.player.travel_state.is_traveling:
            return []
        people: list[dict[str, Any]] = []
        focused_npc = self.simulation.player.focused_npc_id
        for npc in self.simulation._npcs_at(self.simulation.player.location_id):
            people.append(
                {
                    "npc_id": npc.npc_id,
                    "name": npc.name,
                    "profession": npc.profession,
                    "mood": self.simulation._npc_mood(npc),
                    "is_vendor": npc.is_vendor,
                    "is_target": npc.npc_id == focused_npc,
                    "stock": [
                        {"item": item, "quantity": qty}
                        for item, qty in npc.inventory.items()
                        if qty > 0
                    ],
                    "buy_options": [
                        {"item": option.item, "quantity": option.quantity, "price": option.price}
                        for option in self.simulation.player_trade_options(npc.npc_id, mode="buy")
                    ],
                    "sell_options": [
                        {"item": option.item, "quantity": option.quantity, "price": option.price}
                        for option in self.simulation.player_trade_options(npc.npc_id, mode="sell")
                    ],
                    "ask_options": [
                        {"item": option.item, "quantity": option.quantity, "price": option.price}
                        for option in self.simulation.player_trade_options(npc.npc_id, mode="ask")
                    ],
                    "give_options": [
                        {"item": option.item, "quantity": option.quantity, "price": option.price}
                        for option in self.simulation.player_trade_options(npc.npc_id, mode="give")
                    ],
                }
            )
        return people

    def _map_nodes(self) -> list[dict[str, Any]]:
        current_id = self.simulation.player.location_id
        current = self.simulation.world.locations[current_id]
        nodes: list[dict[str, Any]] = []
        for location_id, location in self.simulation.world.locations.items():
            layout = MAP_GRID.get(location_id, {"row": 1, "column": 1, "glyph": "?"})
            occupant_count = sum(1 for npc in self.simulation.npcs.values() if npc.location_id == location_id)
            nodes.append(
                {
                    "location_id": location_id,
                    "name": location.name,
                    "kind": location.kind,
                    "row": layout["row"],
                    "column": layout["column"],
                    "glyph": layout["glyph"],
                    "is_player_here": location_id == current_id,
                    "is_adjacent": location_id in current.neighbors,
                    "occupant_count": occupant_count,
                }
            )
        return nodes

    def _action_catalog(self) -> dict[str, list[dict[str, Any]]]:
        focused_npc = self.simulation._focused_npc_here()
        best_food = self.simulation._best_food_in_inventory(self.simulation.player.inventory)
        common = [
            {"label": "Look", "command": "look"},
            {"label": "Work", "command": "work"},
            {
                "label": "Meal",
                "command": "meal",
                "enabled": best_food is not None,
                "item": best_food,
            },
            {"label": "Rest", "command": "rest 1"},
            {"label": "Sleep", "command": "sleep 3"},
            {"label": "Next", "command": "next 1"},
        ]
        consume = [
            {
                "label": f"Eat {item.title()}",
                "command": f"eat {item}",
                "item": item,
                "quantity": qty,
            }
            for item, qty in sorted(self.simulation.player.inventory.items())
            if qty > 0 and item in CONSUMPTION_VALUE
        ]
        target = [
            {
                "label": "Inspect",
                "command": "inspect",
                "requires_target": True,
                "enabled": focused_npc is not None,
            },
            {
                "label": "Talk",
                "command": "talk",
                "requires_target": True,
                "enabled": focused_npc is not None and self.dialogue_ready,
            },
            {
                "label": "Ask Rumor",
                "command": "ask rumor",
                "requires_target": True,
                "enabled": focused_npc is not None and self.dialogue_ready,
            },
        ]
        return {"common": common, "consume": consume, "target": target}

    def dialogue_prompt_payload(self) -> dict[str, Any]:
        with self.lock:
            current_prompt = self.simulation.dialogue_system_prompt.strip()
            default_prompt = self.config_store.get_default_dialogue_system_prompt().strip()
            return {
                "current_prompt": current_prompt,
                "default_prompt": default_prompt,
                "current_lines": len(current_prompt.splitlines()),
                "current_chars": len(current_prompt),
            }

    def save_dialogue_system_prompt(self, prompt: str) -> dict[str, Any]:
        cleaned = prompt.strip()
        if not cleaned:
            return {"ok": False, "error": "The dialogue system prompt cannot be empty."}
        with self.lock:
            self.config_store.set_dialogue_system_prompt(cleaned)
            self.simulation.set_dialogue_system_prompt(cleaned)
            self._append_event("system", "Dialogue system prompt updated.")
            self._record_system(
                "settings",
                "Updated dialogue system prompt.",
                payload={"prompt_lines": len(cleaned.splitlines()), "prompt_chars": len(cleaned)},
                save_snapshot=True,
            )
            return {
                "ok": True,
                "message": "Dialogue system prompt updated.",
                "prompt": self.dialogue_prompt_payload(),
            }

    def reset_dialogue_system_prompt(self) -> dict[str, Any]:
        default_prompt = self.config_store.get_default_dialogue_system_prompt().strip()
        result = self.save_dialogue_system_prompt(default_prompt)
        if result.get("ok"):
            result["message"] = "Dialogue system prompt reset to default."
        return result

    def scene_payload(self) -> dict[str, Any]:
        with self.lock:
            self.simulation._refresh_actor_loads()
            focused_npc = self.simulation._focused_npc_here()
            location = self.simulation.world.locations[self.simulation.player.location_id]
            region = self.simulation.current_region()
            location_name = location.name
            if self.simulation.player.travel_state.is_traveling:
                destination_id = self.simulation.player.travel_state.destination_location_id or self.simulation.player.location_id
                location_name = f"On the road to {self.simulation.world.locations[destination_id].name}"
            return {
                "dialogue": {
                    "ready": self.dialogue_ready,
                    "loading": self.dialogue_loading,
                    "message": self.dialogue_message,
                    "backend": type(self.simulation.dialogue_adapter).__name__,
                },
                "world": {
                    "day": self.simulation.world.day,
                    "tick": self.simulation.world.tick,
                    "weather": self.simulation.world.weather,
                    "field_stress": round(self.simulation.world.field_stress, 2),
                    "location_id": location.location_id,
                    "location_name": location_name,
                    "region_id": location.region_id,
                    "region_name": region.name if region is not None else None,
                    "active_events": [
                        {
                            "event_id": event.event_id,
                            "event_type": event.event_type,
                            "summary": event.summary,
                        }
                        for event in self.simulation.world.active_events
                    ],
                },
                "player": {
                    "name": self.simulation.player.name,
                    "location_id": self.simulation.player.location_id,
                    "money": self.simulation.player.money,
                    "hunger": round(self.simulation.player.hunger, 1),
                    "fatigue": round(self.simulation.player.fatigue, 1),
                    "carried_weight": round(self.simulation.player.carried_weight, 1),
                    "carry_capacity": round(self.simulation.player.carry_capacity, 1),
                    "focused_npc_id": self.simulation.player.focused_npc_id,
                    "inventory": [
                        {"item": item, "quantity": qty}
                        for item, qty in self.simulation.player.inventory.items()
                        if qty > 0
                    ],
                    "travel_state": self.simulation.player.travel_state.model_dump(mode="json"),
                },
                "actions": self._action_catalog(),
                "scene": {
                    "description": self.simulation.describe_location(),
                    "people": self._scene_people(),
                    "rumors": [
                        {"content": rumor.content, "confidence": round(rumor.confidence, 2)}
                        for rumor in self.simulation._sorted_known_rumors(
                            self.simulation.player.known_rumor_ids,
                            dedupe_by_signature=True,
                        )
                    ],
                    "map_nodes": self._map_nodes(),
                    "regional_nodes": [
                        {
                            "region_id": node.region_id,
                            "name": node.name,
                            "kind": node.kind,
                            "summary": node.summary,
                            "risk_level": round(node.risk_level, 2),
                            "is_current_region": node.region_id == location.region_id,
                            "known_local_locations": list(node.local_location_ids),
                            "stock_signals": dict(node.stock_signals),
                        }
                        for node in self.simulation.world.regions.values()
                    ],
                    "regional_routes": [
                        {
                            "route_id": route.route_id,
                            "from_region_id": route.from_region_id,
                            "to_region_id": route.to_region_id,
                            "travel_ticks": route.travel_ticks,
                            "cargo_risk": round(route.cargo_risk, 2),
                            "weather_sensitivity": round(route.weather_sensitivity, 2),
                            "seasonal_capacity": round(route.seasonal_capacity, 2),
                            "status": "delayed"
                            if self.simulation._route_delay_event(route.route_id) is not None
                            else "stable",
                            "status_summary": None
                            if self.simulation._route_delay_event(route.route_id) is None
                            else self.simulation._route_delay_event(route.route_id).summary,
                        }
                        for route in self.simulation.world.regional_routes
                    ],
                },
                "target": None
                if focused_npc is None
                else {
                    "npc_id": focused_npc.npc_id,
                    "name": focused_npc.name,
                    "detail_text": self.simulation.npc_detail_text(focused_npc.npc_id),
                },
                "recent_events": list(self.recent_events),
                "help": self.simulation.help_text().splitlines(),
            }

    def run_command(self, command: str) -> dict[str, Any]:
        cleaned = " ".join(command.split())
        if not cleaned:
            return {"ok": False, "error": "Command is empty.", "state": self.scene_payload(), "entries": []}

        with self.lock:
            if self._is_dialogue_command(cleaned) and not self.dialogue_ready:
                message = "Dialogue model is still loading. Wait for the ready message."
                self._append_event("system", message)
                return {"ok": False, "error": message, "state": self.scene_payload(), "entries": []}

            self._append_event("input", f"> {cleaned}")
            result = self.simulation.handle_command(cleaned)
            entries = [entry if isinstance(entry, TurnEvent) else TurnEvent(kind="world", text=str(entry)) for entry in result.entries]
            for entry in entries:
                self._append_event(entry.kind, entry.text)

            if self.store is not None:
                self.store.save_simulation(
                    self.simulation,
                    kind="web_command",
                    message=cleaned,
                    payload={"result_lines": result.lines, "result_entries": result.payload()},
                )
            if self.event_log is not None:
                self.event_log.write(
                    kind="web_command",
                    message=cleaned,
                    day=self.simulation.world.day,
                    tick=self.simulation.world.tick,
                    payload={"result_lines": result.lines, "result_entries": result.payload()},
                )

            return {
                "ok": True,
                "command": cleaned,
                "entries": result.payload(),
                "state": self.scene_payload(),
            }

    def close(self) -> None:
        with self.lock:
            self._record_system("session_end", "Web session ended.", payload={"entrypoint": "web"}, save_snapshot=True)
            store = self.store
            config_store = self.config_store
            self.store = None
            self.config_store = None
            if store is not None:
                store.close()
            elif config_store is not None:
                config_store.close()
            if self.event_log is not None:
                self.event_log.close()
                self.event_log = None


class AcidNetWebHandler(BaseHTTPRequestHandler):
    server: "AcidNetWebServer"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self._serve_asset("index.html", "text/html; charset=utf-8")
            return
        if self.path == "/api/state":
            self._write_json(HTTPStatus.OK, self.server.runtime.scene_payload())
            return
        if self.path == "/api/dialogue-prompt":
            self._write_json(HTTPStatus.OK, self.server.runtime.dialogue_prompt_payload())
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_POST(self) -> None:
        if self.path not in {"/api/command", "/api/dialogue-prompt"}:
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        try:
            body = self.rfile.read(content_length) if content_length else b"{}"
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body."})
            return
        if self.path == "/api/dialogue-prompt":
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
        asset_path = self.server.runtime.asset_root / relative_path
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
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class AcidNetWebServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], runtime: WebSimulationRuntime) -> None:
        super().__init__(server_address, AcidNetWebHandler)
        self.runtime = runtime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the acidnet shareable web frontend.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
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
        choices=("heuristic", "openai_compat", "local_peft"),
        default="heuristic",
        help="Dialogue backend to use for NPC interactions.",
    )
    parser.add_argument("--dialogue-model", default=None, help="Model identifier for the dialogue backend.")
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
        dialogue_backend=args.dialogue_backend,
        dialogue_model=args.dialogue_model,
        dialogue_endpoint=args.dialogue_endpoint,
        dialogue_adapter_path=args.dialogue_adapter_path,
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
