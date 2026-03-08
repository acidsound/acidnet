from __future__ import annotations

import threading
from collections import deque
from pathlib import Path
from time import monotonic
from typing import Any

from acidnet.simulator.runtime import CONSUMPTION_VALUE, TurnEvent
from acidnet.simulator.simulation import Simulation
from acidnet.simulator.storage import EventLogFile, SQLiteWorldStore


class SimulatorService:
    def __init__(
        self,
        *,
        db_path: str | Path = Path("data") / "acidnet.sqlite",
        persist: bool = True,
        player_name: str | None = None,
        dialogue_backend: str = "heuristic",
        dialogue_model: str | None = None,
        dialogue_endpoint: str | None = None,
        dialogue_adapter_path: str | None = None,
        simulation: Simulation | None = None,
        event_log_path: str | Path | None = Path("data") / "logs" / "acidnet-web-events.log",
        prepare_dialogue: bool = True,
    ) -> None:
        self.lock = threading.RLock()
        self._event_condition = threading.Condition(self.lock)
        self._state_version = 0
        self._latest_event_seq = 0
        self._next_command_id = 1
        self.recent_events: deque[dict[str, Any]] = deque(maxlen=96)
        self._event_stream: deque[dict[str, Any]] = deque(maxlen=512)

        self.config_store = SQLiteWorldStore(db_path)
        if player_name is not None:
            self.config_store.set_player_name(player_name)
        provided_simulation = simulation is not None
        self.simulation = simulation or Simulation.create_demo(
            player_name=self.config_store.get_player_name(),
            dialogue_backend=dialogue_backend,
            dialogue_model=dialogue_model,
            dialogue_endpoint=dialogue_endpoint,
            dialogue_adapter_path=dialogue_adapter_path,
        )
        self.store = self.config_store if persist else None
        self.event_log = EventLogFile(event_log_path) if event_log_path is not None else None
        if provided_simulation and player_name is not None:
            self.simulation.player.name = self.config_store.get_player_name()
        if not provided_simulation:
            self.simulation.set_dialogue_system_prompt(self.config_store.get_dialogue_system_prompt())
        self.dialogue_ready = False
        self.dialogue_loading = False
        self.dialogue_message = f"Loading {dialogue_backend} dialogue model..."

        self._record_system(
            "session_start",
            "Web session started.",
            payload={"entrypoint": "web", "dialogue_backend": dialogue_backend},
            save_snapshot=True,
        )
        with self.lock:
            self._publish_events([("system", "acidnet web frontend ready.")], save_snapshot=False)

            if prepare_dialogue:
                self._publish_events([("system", self.dialogue_message)], save_snapshot=False)
                self._start_dialogue_prepare()
            else:
                if dialogue_backend == "heuristic":
                    self.dialogue_ready = True
                    self.dialogue_message = f"{type(self.simulation.dialogue_adapter).__name__} ready."
                else:
                    self.dialogue_message = "Dialogue preparation skipped for this runtime."
                self._publish_events([("system", self.dialogue_message)], save_snapshot=False)

    @property
    def state_version(self) -> int:
        return self._state_version

    @property
    def latest_event_seq(self) -> int:
        return self._latest_event_seq

    def _is_dialogue_command(self, command: str) -> bool:
        lowered = command.strip().lower()
        return lowered.startswith("talk") or lowered.startswith("say ") or lowered.startswith("tell ") or lowered.startswith("ask ")

    def _format_dialogue_trace_text(self, trace: dict[str, Any]) -> str:
        parts = [f"path={trace.get('path', 'unknown')}"]
        if trace.get("interaction_mode"):
            parts.append(f"mode={trace['interaction_mode']}")
        if trace.get("trade_parser_source"):
            parts.append(f"parser={trace['trade_parser_source']}")
        if trace.get("trade_intent"):
            parts.append(f"intent={trace['trade_intent']}")
        if trace.get("trade_fact_kind"):
            parts.append(f"fact={trace['trade_fact_kind']}")
        if trace.get("response_guard"):
            parts.append(f"guard={trace['response_guard']}")
        if trace.get("validation_reason"):
            parts.append(f"validation={trace['validation_reason']}")
        if trace.get("reason"):
            parts.append(f"reason={trace['reason']}")
        if trace.get("adapter_name"):
            parts.append(f"adapter={trace['adapter_name']}")
        return "dialogue trace | " + " | ".join(parts)

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

    def _publish_events(
        self,
        events: list[tuple[str, str]],
        *,
        save_snapshot: bool,
        snapshot_kind: str | None = None,
        snapshot_message: str | None = None,
        snapshot_payload: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self._state_version += 1
        published: list[dict[str, Any]] = []
        for kind, text in events:
            self._latest_event_seq += 1
            event = {
                "seq": self._latest_event_seq,
                "kind": kind,
                "text": text,
                "day": self.simulation.world.day,
                "tick": self.simulation.world.tick,
            }
            self.recent_events.append(event)
            self._event_stream.append(event)
            published.append(event)

        if save_snapshot and snapshot_kind is not None and snapshot_message is not None:
            self._record_system(
                snapshot_kind,
                snapshot_message,
                payload=snapshot_payload,
                save_snapshot=True,
            )
        self._event_condition.notify_all()
        return published

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
            self._publish_events([("system", message)], save_snapshot=False)

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
                    "debt_options": [
                        {"item": option.item, "quantity": option.quantity, "price": option.price}
                        for option in self.simulation.player_trade_options(npc.npc_id, mode="debt")
                    ],
                }
            )
        return people

    def _map_nodes(self) -> list[dict[str, Any]]:
        current_id = self.simulation.player.location_id
        current = self.simulation.world.locations[current_id]
        current_region = self.simulation.current_region()
        nodes: list[dict[str, Any]] = []
        for location_id, location in self.simulation.world.locations.items():
            occupant_count = sum(1 for npc in self.simulation.npcs.values() if npc.location_id == location_id)
            move_command: str | None = None
            connection_kind = "local"
            is_reachable = False
            if location_id == current_id:
                move_command = "look"
                is_reachable = True
            elif location.region_id == current.region_id and location_id in current.neighbors:
                move_command = f"go {location_id}"
                is_reachable = True
            elif current_region is not None and location.location_id == self.simulation.world.regions.get(location.region_id, current_region).anchor_location_id:
                route = self.simulation._regional_route_between(current.region_id, location.region_id)
                if route is not None and not self.simulation.player.travel_state.is_traveling:
                    target_region = self.simulation.world.regions.get(location.region_id)
                    if target_region is not None:
                        move_command = f"travel-region {target_region.name}"
                        is_reachable = True
                        connection_kind = "regional"
            nodes.append(
                {
                    "location_id": location_id,
                    "name": location.name,
                    "kind": location.kind,
                    "row": location.map_row,
                    "column": location.map_column,
                    "glyph": location.map_glyph,
                    "is_player_here": location_id == current_id,
                    "is_adjacent": location_id in current.neighbors,
                    "is_reachable": is_reachable,
                    "move_command": move_command,
                    "connection_kind": connection_kind,
                    "occupant_count": occupant_count,
                }
            )
        return nodes

    def _map_edges(self) -> list[dict[str, Any]]:
        current_region = self.simulation.current_region()
        current_location = self.simulation.world.locations[self.simulation.player.location_id]
        seen: set[tuple[str, str, str]] = set()
        edges: list[dict[str, Any]] = []

        for location in self.simulation.world.locations.values():
            if location.region_id != current_location.region_id:
                continue
            for neighbor_id in location.neighbors:
                neighbor = self.simulation.world.locations.get(neighbor_id)
                if neighbor is None or neighbor.region_id != current_location.region_id:
                    continue
                key = tuple(sorted((location.location_id, neighbor.location_id))) + ("local",)
                if key in seen:
                    continue
                seen.add(key)
                edges.append(
                    {
                        "from_location_id": location.location_id,
                        "to_location_id": neighbor.location_id,
                        "kind": "local",
                        "route_id": None,
                        "is_delayed": False,
                    }
                )

        if current_region is None or current_region.anchor_location_id is None:
            return edges

        for route in self.simulation.world.regional_routes:
            other_region_id: str | None = None
            if route.from_region_id == current_region.region_id:
                other_region_id = route.to_region_id
            elif route.to_region_id == current_region.region_id:
                other_region_id = route.from_region_id
            if other_region_id is None:
                continue
            other_region = self.simulation.world.regions.get(other_region_id)
            if other_region is None or other_region.anchor_location_id is None:
                continue
            key = tuple(sorted((current_region.anchor_location_id, other_region.anchor_location_id))) + ("regional",)
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "from_location_id": current_region.anchor_location_id,
                    "to_location_id": other_region.anchor_location_id,
                    "kind": "regional",
                    "route_id": route.route_id,
                    "is_delayed": self.simulation._visible_route_delay_event_for_player(route.route_id) is not None,
                }
            )
        return edges

    def _route_preview(self) -> list[dict[str, Any]]:
        if self.simulation.player.travel_state.is_traveling:
            return []
        previews: list[dict[str, Any]] = []
        current = self.simulation.world.locations[self.simulation.player.location_id]
        for neighbor_id in current.neighbors:
            preview = self.simulation._preview_local_route(neighbor_id)
            if preview is not None:
                previews.append(preview)
        for region in self.simulation.world.regions.values():
            preview = self.simulation._preview_regional_route(region.region_id)
            if preview is not None:
                previews.append(preview)
        return previews

    def _action_catalog(self) -> dict[str, list[dict[str, Any]]]:
        focused_npc = self.simulation._focused_npc_here()
        best_food = self.simulation._best_food_in_inventory(self.simulation.player.inventory)
        route_preview = self._route_preview()
        common = [
            {"label": "Look", "command": "look"},
            {"label": "Work", "command": "work"},
            {"label": "Meal", "command": "meal", "enabled": best_food is not None, "item": best_food},
            {"label": "Rest", "command": "rest 1"},
            {"label": "Sleep", "command": "sleep 3"},
            {"label": "Next", "command": "next 1"},
        ]
        consume = [
            {"label": f"Eat {item.title()}", "command": f"eat {item}", "item": item, "quantity": qty}
            for item, qty in sorted(self.simulation.player.inventory.items())
            if qty > 0 and item in CONSUMPTION_VALUE
        ]
        target = [
            {"label": "Inspect", "command": "inspect", "requires_target": True, "enabled": focused_npc is not None},
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
        travel = [
            {
                "label": ("Go " if preview["connection_kind"] == "local" else "Travel to ") + str(preview["destination_name"]),
                "command": preview["command"],
                "enabled": preview["enabled"],
                "kind": preview["connection_kind"],
                "destination_location_id": preview["destination_location_id"],
                "destination_region_id": preview["destination_region_id"],
                "travel_ticks": preview["travel_ticks"],
                "travel_turns": preview["travel_turns"],
                "blocked_reason": preview["blocked_reason"],
                "route_id": preview["route_id"],
            }
            for preview in route_preview
        ]
        return {"common": common, "consume": consume, "target": target, "travel": travel}

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
            return {
                "ok": False,
                "error": "The dialogue system prompt cannot be empty.",
                "state_version": self.state_version,
                "latest_event_seq": self.latest_event_seq,
            }
        with self.lock:
            self.config_store.set_dialogue_system_prompt(cleaned)
            self.simulation.set_dialogue_system_prompt(cleaned)
            self._publish_events(
                [("system", "Dialogue system prompt updated.")],
                save_snapshot=True,
                snapshot_kind="settings",
                snapshot_message="Updated dialogue system prompt.",
                snapshot_payload={"prompt_lines": len(cleaned.splitlines()), "prompt_chars": len(cleaned)},
            )
            return {
                "ok": True,
                "message": "Dialogue system prompt updated.",
                "prompt": self.dialogue_prompt_payload(),
                "state_version": self.state_version,
                "latest_event_seq": self.latest_event_seq,
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
            self.simulation._refresh_market_snapshot()
            focused_npc = self.simulation._focused_npc_here()
            location = self.simulation.world.locations[self.simulation.player.location_id]
            region = self.simulation.current_region()
            location_name = location.name
            if self.simulation.player.travel_state.is_traveling:
                destination_id = self.simulation.player.travel_state.destination_location_id or self.simulation.player.location_id
                location_name = f"On the road to {self.simulation.world.locations[destination_id].name}"
            return {
                "state_version": self.state_version,
                "latest_event_seq": self.latest_event_seq,
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
                    "scarcity_index": round(self.simulation.world.market.scarcity_index, 2),
                    "market_prices": {
                        item_id: state.current_price for item_id, state in sorted(self.simulation.world.market.items.items())
                    },
                    "location_id": location.location_id,
                    "location_name": location_name,
                    "region_id": location.region_id,
                    "region_name": region.name if region is not None else None,
                    "active_events": [
                        {"event_id": event.event_id, "event_type": event.event_type, "summary": event.summary}
                        for event in self.simulation._visible_world_events_for_player()
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
                    "debts": [
                        {
                            "npc_id": npc_id,
                            "name": self.simulation.npcs[npc_id].name if npc_id in self.simulation.npcs else npc_id,
                            "amount": amount,
                        }
                        for npc_id, amount in sorted(self.simulation.player.debts.items())
                        if amount > 0
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
                    "route_preview": self._route_preview(),
                    "map_nodes": self._map_nodes(),
                    "map_edges": self._map_edges(),
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
                            "transit_count": sum(
                                1
                                for transit in self.simulation.world.regional_transits
                                if transit.route_id == route.route_id
                            ),
                            "status": "unknown"
                            if not self.simulation._is_route_visible_to_player(route)
                            else "delayed"
                            if self.simulation._visible_route_delay_event_for_player(route.route_id) is not None
                            else "stable",
                            "status_summary": None
                            if self.simulation._visible_route_delay_event_for_player(route.route_id) is None
                            else self.simulation._visible_route_delay_event_for_player(route.route_id).summary,
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

    def events_payload(self, *, after_seq: int, timeout_s: float = 15.0, limit: int = 64) -> dict[str, Any]:
        safe_after_seq = max(0, after_seq)
        safe_limit = max(1, min(limit, 256))
        safe_timeout = max(0.0, min(timeout_s, 30.0))
        deadline = monotonic() + safe_timeout
        with self.lock:
            while True:
                earliest_seq = self._event_stream[0]["seq"] if self._event_stream else self.latest_event_seq + 1
                reset_required = safe_after_seq < earliest_seq - 1
                if reset_required or self.latest_event_seq > safe_after_seq:
                    events = [event for event in self._event_stream if event["seq"] > safe_after_seq][:safe_limit]
                    return {
                        "ok": True,
                        "after_seq": safe_after_seq,
                        "latest_event_seq": self.latest_event_seq,
                        "state_version": self.state_version,
                        "timed_out": False,
                        "reset_required": reset_required,
                        "events": events,
                    }
                remaining = deadline - monotonic()
                if remaining <= 0:
                    return {
                        "ok": True,
                        "after_seq": safe_after_seq,
                        "latest_event_seq": self.latest_event_seq,
                        "state_version": self.state_version,
                        "timed_out": True,
                        "reset_required": False,
                        "events": [],
                    }
                self._event_condition.wait(timeout=remaining)

    def run_command(self, command: str) -> dict[str, Any]:
        cleaned = " ".join(command.split())
        if not cleaned:
            return {
                "ok": False,
                "error": "Command is empty.",
                "command_id": None,
                "state_version": self.state_version,
                "latest_event_seq": self.latest_event_seq,
                "state": self.scene_payload(),
                "entries": [],
            }

        with self.lock:
            if self._is_dialogue_command(cleaned) and not self.dialogue_ready:
                message = "Dialogue model is still loading. Wait for the ready message."
                self._publish_events([("system", message)], save_snapshot=False)
                return {
                    "ok": False,
                    "error": message,
                    "command_id": None,
                    "state_version": self.state_version,
                    "latest_event_seq": self.latest_event_seq,
                    "state": self.scene_payload(),
                    "entries": [],
                }

            command_id = f"cmd-{self._next_command_id}"
            self._next_command_id += 1
            result = self.simulation.handle_command(cleaned)
            entries = [entry if isinstance(entry, TurnEvent) else TurnEvent(kind="world", text=str(entry)) for entry in result.entries]
            dialogue_trace = dict(self.simulation.last_dialogue_trace or {}) or None

            event_batch = [("input", f"> {cleaned}")]
            event_batch.extend((entry.kind, entry.text) for entry in entries)
            if dialogue_trace is not None:
                event_batch.append(("debug", self._format_dialogue_trace_text(dialogue_trace)))

            payload = {"command_id": command_id, "result_lines": result.lines, "result_entries": result.payload()}
            if dialogue_trace is not None:
                payload["dialogue_trace"] = dialogue_trace

            self._publish_events(
                event_batch,
                save_snapshot=self.store is not None,
                snapshot_kind="web_command",
                snapshot_message=cleaned,
                snapshot_payload=payload,
            )
            if self.event_log is not None:
                self.event_log.write(
                    kind="web_command",
                    message=cleaned,
                    day=self.simulation.world.day,
                    tick=self.simulation.world.tick,
                    payload=payload,
                )

            response = {
                "ok": True,
                "command": cleaned,
                "command_id": command_id,
                "state_version": self.state_version,
                "latest_event_seq": self.latest_event_seq,
                "entries": result.payload(),
                "state": self.scene_payload(),
            }
            if dialogue_trace is not None:
                response["debug"] = {"dialogue_trace": dialogue_trace}
            return response

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
