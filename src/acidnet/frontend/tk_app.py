from __future__ import annotations

import argparse
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path

from acidnet.engine import Simulation
from acidnet.eval import SimulationMonkeyRunner
from acidnet.engine.simulation import TurnEvent
from acidnet.storage import EventLogFile, SQLiteWorldStore

FONT_BODY = ("Consolas", 11)
FONT_TITLE = ("Consolas", 12, "bold")
BG_ROOT = "#111315"
BG_PANEL = "#1A1E22"
BG_CANVAS = "#0E141B"
FG_TEXT = "#E6D7A6"
FG_MUTED = "#98A7B3"
ACCENT = "#D9A441"
ACCENT_ALT = "#4AA3A2"
PLAYER_COLOR = "#C96E4A"
LOG_COLORS = {
    "input": "#C96E4A",
    "npc": "#6ED3B8",
    "world": "#E6D7A6",
    "system": "#90C0FF",
    "ui": "#D9A441",
}


@dataclass(frozen=True, slots=True)
class MapNode:
    x: int
    y: int


MAP_LAYOUT: dict[str, MapNode] = {
    "square": MapNode(300, 170),
    "tavern": MapNode(115, 170),
    "bakery": MapNode(470, 75),
    "smithy": MapNode(470, 260),
    "farm": MapNode(275, 335),
    "riverside": MapNode(95, 335),
    "shrine": MapNode(305, 60),
}


class AcidNetApp(tk.Tk):
    def __init__(
        self,
        *,
        db_path: str | Path = Path("data") / "acidnet.sqlite",
        persist: bool = True,
        dialogue_backend: str = "heuristic",
        dialogue_model: str | None = None,
        dialogue_endpoint: str | None = None,
        dialogue_adapter_path: str | None = None,
        monkey: bool = False,
        monkey_steps: int = 160,
        monkey_delay_ms: int = 350,
        monkey_seed: int = 7,
        event_log_path: str | Path | None = Path("data") / "logs" / "acidnet-events.log",
    ) -> None:
        super().__init__()
        self.title("acidnet village")
        self.geometry("1180x760")
        self.minsize(1020, 700)
        self.configure(bg=BG_ROOT)

        self.simulation = Simulation.create_demo(
            dialogue_backend=dialogue_backend,
            dialogue_model=dialogue_model,
            dialogue_endpoint=dialogue_endpoint,
            dialogue_adapter_path=dialogue_adapter_path,
        )
        self.store = SQLiteWorldStore(db_path) if persist else None
        self.event_log = EventLogFile(event_log_path) if event_log_path is not None else None
        self.selected_location_id = self.simulation.player.location_id
        self.status_var = tk.StringVar()
        self.dialogue_var = tk.StringVar()
        self.footer_var = tk.StringVar()
        self.monkey_button_var = tk.StringVar()
        self._location_items: dict[str, tuple[int, int]] = {}
        self._npc_name_by_index: list[str] = []
        self.monkey_enabled = monkey
        self.monkey_default_steps = monkey_steps
        self.monkey_steps_remaining = monkey_steps
        self.monkey_delay_ms = monkey_delay_ms
        self.monkey_seed = monkey_seed
        self.monkey_runner = SimulationMonkeyRunner(self.simulation, seed=monkey_seed)
        self.dialogue_ready = False
        self.dialogue_loading = False
        self._monkey_waiting_for_dialogue = monkey
        self.dialogue_var.set(f"Loading {dialogue_backend} dialogue model...")

        self._build_ui()
        self._refresh_monkey_button()
        self._bind_shortcuts()
        self._render_world()
        self._refresh_panels()
        self._append_log(
            [
                "acidnet GUI loaded.",
                "Use arrow keys or WASD to move. Click an adjacent location on the map to travel there.",
                "T to talk, Y to focus direct speech, R for rumor, X to work, B to buy bread, E to eat, Space to wait.",
                f"Dialogue backend: {dialogue_backend}",
            ],
            kind="system",
        )
        if self.monkey_enabled:
            self._append_log(
                [f"Monkey mode enabled: {self.monkey_steps_remaining} steps, {self.monkey_delay_ms}ms delay."],
                kind="system",
            )
        self._append_log([self.dialogue_var.get()], kind="system")

        if self.store is not None:
            self._save_snapshot("session_start", "GUI session started.", {"entrypoint": "gui"})
        if self.event_log is not None:
            self.event_log.write(
                kind="session_start",
                message="GUI session started.",
                day=self.simulation.world.day,
                tick=self.simulation.world.tick,
                payload={"entrypoint": "gui", "dialogue_backend": dialogue_backend},
            )

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(50, self._start_dialogue_prepare)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        map_frame = tk.Frame(self, bg=BG_ROOT, padx=14, pady=14)
        map_frame.grid(row=0, column=0, sticky="nsew")
        map_frame.rowconfigure(1, weight=3)
        map_frame.rowconfigure(5, weight=2)
        map_frame.columnconfigure(0, weight=1)

        tk.Label(
            map_frame,
            text="ACIDNET VILLAGE",
            font=("Consolas", 18, "bold"),
            fg=FG_TEXT,
            bg=BG_ROOT,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.canvas = tk.Canvas(
            map_frame,
            bg=BG_CANVAS,
            highlightthickness=0,
            relief="flat",
        )
        self.canvas.grid(row=1, column=0, sticky="nsew")

        tk.Label(
            map_frame,
            text="Rumors",
            font=FONT_TITLE,
            fg=FG_TEXT,
            bg=BG_ROOT,
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self.rumor_text = self._make_text(map_frame, height=5)
        self.rumor_text.grid(row=3, column=0, sticky="ew", pady=(4, 10))

        tk.Label(
            map_frame,
            text="Event Log",
            font=FONT_TITLE,
            fg=FG_TEXT,
            bg=BG_ROOT,
            anchor="w",
        ).grid(row=4, column=0, sticky="ew")
        self.log_text = self._make_text(map_frame, height=16)
        self.log_text.grid(row=5, column=0, sticky="nsew", pady=(4, 0))
        for kind, color in LOG_COLORS.items():
            self.log_text.tag_configure(kind, foreground=color)

        sidebar = tk.Frame(self, bg=BG_PANEL, padx=14, pady=14)
        sidebar.grid(row=0, column=1, sticky="nsew")
        sidebar.columnconfigure(0, weight=1)

        tk.Label(sidebar, text="Status", font=FONT_TITLE, fg=FG_TEXT, bg=BG_PANEL, anchor="w").grid(
            row=0, column=0, sticky="ew"
        )
        self.status_label = tk.Label(
            sidebar,
            textvariable=self.status_var,
            font=FONT_BODY,
            justify="left",
            anchor="nw",
            fg=FG_TEXT,
            bg=BG_PANEL,
            wraplength=380,
        )
        self.status_label.grid(row=1, column=0, sticky="ew", pady=(4, 12))

        tk.Label(sidebar, text="Dialogue", font=FONT_TITLE, fg=FG_TEXT, bg=BG_PANEL, anchor="w").grid(
            row=2, column=0, sticky="ew"
        )
        self.dialogue_label = tk.Label(
            sidebar,
            textvariable=self.dialogue_var,
            font=("Consolas", 10),
            justify="left",
            anchor="nw",
            fg=ACCENT_ALT,
            bg=BG_PANEL,
            wraplength=380,
        )
        self.dialogue_label.grid(row=3, column=0, sticky="ew", pady=(4, 12))

        info_frame = tk.Frame(sidebar, bg=BG_PANEL)
        info_frame.grid(row=4, column=0, sticky="nsew")
        info_frame.columnconfigure(0, weight=1)
        info_frame.rowconfigure(1, weight=1)
        info_frame.rowconfigure(3, weight=1)

        tk.Label(info_frame, text="Location", font=FONT_TITLE, fg=FG_TEXT, bg=BG_PANEL, anchor="w").grid(
            row=0, column=0, sticky="ew"
        )
        self.location_text = self._make_text(info_frame, height=9)
        self.location_text.grid(row=1, column=0, sticky="nsew", pady=(4, 10))

        tk.Label(info_frame, text="NPCs Here", font=FONT_TITLE, fg=FG_TEXT, bg=BG_PANEL, anchor="w").grid(
            row=2, column=0, sticky="ew"
        )
        self.npc_list = tk.Listbox(
            info_frame,
            height=6,
            bg="#13171B",
            fg=FG_TEXT,
            selectbackground=ACCENT,
            selectforeground="#1A1308",
            relief="flat",
            highlightthickness=0,
            font=FONT_BODY,
        )
        self.npc_list.grid(row=3, column=0, sticky="nsew", pady=(4, 10))

        action_frame = tk.Frame(sidebar, bg=BG_PANEL)
        action_frame.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        for idx in range(3):
            action_frame.columnconfigure(idx, weight=1)

        self._make_button(action_frame, "Talk (T)", self._talk_selected).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._make_button(action_frame, "Rumor (R)", self._ask_rumor_selected).grid(row=0, column=1, sticky="ew", padx=3)
        self._make_button(action_frame, "Buy Bread (B)", self._buy_bread_selected).grid(
            row=0, column=2, sticky="ew", padx=(6, 0)
        )
        self._make_button(action_frame, "Work (X)", self._player_work).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(6, 0))
        self._make_button(action_frame, "Eat (E)", self._eat_best_food).grid(row=1, column=1, sticky="ew", padx=3, pady=(6, 0))
        self._make_button(action_frame, "Wait (Space)", self._wait_one_turn).grid(row=1, column=2, sticky="ew", padx=(6, 0), pady=(6, 0))
        self._make_button(action_frame, "Look (L)", self._look).grid(row=2, column=0, sticky="ew", padx=(0, 6), pady=(6, 0))
        tk.Button(
            action_frame,
            textvariable=self.monkey_button_var,
            command=self._toggle_monkey,
            bg=ACCENT_ALT,
            fg="#081615",
            activebackground="#6AC7C4",
            activeforeground="#081615",
            relief="flat",
            font=FONT_BODY,
            padx=10,
            pady=6,
        ).grid(row=2, column=1, columnspan=2, sticky="ew", padx=(3, 0), pady=(6, 0))

        tk.Label(sidebar, text="Direct Speech", font=FONT_TITLE, fg=FG_TEXT, bg=BG_PANEL, anchor="w").grid(
            row=6, column=0, sticky="ew"
        )
        speak_frame = tk.Frame(sidebar, bg=BG_PANEL)
        speak_frame.grid(row=7, column=0, sticky="ew", pady=(4, 10))
        speak_frame.columnconfigure(0, weight=1)
        self.say_entry = tk.Entry(
            speak_frame,
            bg="#13171B",
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
            font=FONT_BODY,
        )
        self.say_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.say_entry.bind("<Return>", self._submit_say_selected)
        self._make_button(speak_frame, "Say", self._submit_say_selected).grid(row=0, column=1, sticky="ew")

        tk.Label(sidebar, text="Raw Command", font=FONT_TITLE, fg=FG_TEXT, bg=BG_PANEL, anchor="w").grid(
            row=8, column=0, sticky="ew"
        )
        command_frame = tk.Frame(sidebar, bg=BG_PANEL)
        command_frame.grid(row=9, column=0, sticky="ew", pady=(4, 0))
        command_frame.columnconfigure(0, weight=1)
        self.command_entry = tk.Entry(
            command_frame,
            bg="#13171B",
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
            font=FONT_BODY,
        )
        self.command_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.command_entry.bind("<Return>", self._submit_entry_command)
        self._make_button(command_frame, "Run (Enter)", self._submit_entry_command).grid(row=0, column=1, sticky="ew")

        footer = tk.Label(
            sidebar,
            textvariable=self.footer_var,
            justify="left",
            anchor="w",
            fg=FG_MUTED,
            bg=BG_PANEL,
            font=("Consolas", 10),
        )
        footer.grid(row=10, column=0, sticky="ew", pady=(12, 0))

    def _make_text(self, parent: tk.Widget, *, height: int) -> tk.Text:
        widget = tk.Text(
            parent,
            height=height,
            bg="#13171B",
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
            highlightthickness=0,
            font=FONT_BODY,
            wrap="word",
            padx=8,
            pady=8,
        )
        widget.configure(state="disabled")
        return widget

    def _make_button(self, parent: tk.Widget, label: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=label,
            command=command,
            bg=ACCENT,
            fg="#1A1308",
            activebackground="#F0C86B",
            activeforeground="#1A1308",
            relief="flat",
            font=FONT_BODY,
            padx=10,
            pady=6,
        )

    def _bind_shortcuts(self) -> None:
        self.bind("<Up>", lambda _event: self._run_shortcut(lambda: self._move_direction(0, -1)))
        self.bind("<Down>", lambda _event: self._run_shortcut(lambda: self._move_direction(0, 1)))
        self.bind("<Left>", lambda _event: self._run_shortcut(lambda: self._move_direction(-1, 0)))
        self.bind("<Right>", lambda _event: self._run_shortcut(lambda: self._move_direction(1, 0)))
        self.bind("w", lambda _event: self._run_shortcut(lambda: self._move_direction(0, -1)))
        self.bind("s", lambda _event: self._run_shortcut(lambda: self._move_direction(0, 1)))
        self.bind("a", lambda _event: self._run_shortcut(lambda: self._move_direction(-1, 0)))
        self.bind("d", lambda _event: self._run_shortcut(lambda: self._move_direction(1, 0)))
        self.bind("t", lambda _event: self._run_shortcut(self._talk_selected))
        self.bind("y", lambda _event: self._focus_say_entry())
        self.bind("r", lambda _event: self._run_shortcut(self._ask_rumor_selected))
        self.bind("b", lambda _event: self._run_shortcut(self._buy_bread_selected))
        self.bind("x", lambda _event: self._run_shortcut(self._player_work))
        self.bind("e", lambda _event: self._run_shortcut(self._eat_best_food))
        self.bind("l", lambda _event: self._run_shortcut(self._look))
        self.bind("m", lambda _event: self._run_shortcut(self._toggle_monkey))
        self.bind("<space>", lambda _event: self._run_shortcut(self._wait_one_turn))

    def _render_world(self) -> None:
        self.canvas.delete("all")
        drawn_edges: set[tuple[str, str]] = set()
        for location_id, location in self.simulation.world.locations.items():
            node = MAP_LAYOUT[location_id]
            for neighbor_id in location.neighbors:
                edge = tuple(sorted((location_id, neighbor_id)))
                if edge in drawn_edges:
                    continue
                drawn_edges.add(edge)
                neighbor = MAP_LAYOUT[neighbor_id]
                self.canvas.create_line(
                    node.x,
                    node.y,
                    neighbor.x,
                    neighbor.y,
                    fill="#2D4555",
                    width=4,
                )

        self._location_items.clear()
        for location_id, location in self.simulation.world.locations.items():
            node = MAP_LAYOUT[location_id]
            half_w = 72
            half_h = 34
            fill = ACCENT_ALT if location_id == self.simulation.player.location_id else "#233645"
            outline = ACCENT if location_id == self.selected_location_id else "#5E7C8D"
            rect = self.canvas.create_rectangle(
                node.x - half_w,
                node.y - half_h,
                node.x + half_w,
                node.y + half_h,
                fill=fill,
                outline=outline,
                width=3,
            )
            label = self.canvas.create_text(
                node.x,
                node.y - 8,
                text=location.name,
                fill=FG_TEXT,
                font=FONT_TITLE,
                width=132,
            )
            npc_names = ", ".join(npc.name for npc in self.simulation.npcs.values() if npc.location_id == location_id)
            occupants = self.canvas.create_text(
                node.x,
                node.y + 18,
                text=npc_names or "empty",
                fill=FG_MUTED,
                font=("Consolas", 9),
                width=130,
            )
            for item in (rect, label, occupants):
                self.canvas.tag_bind(item, "<Button-1>", lambda _event, loc=location_id: self._click_location(loc))
            self._location_items[location_id] = (rect, label)

        player_node = MAP_LAYOUT[self.simulation.player.location_id]
        self.canvas.create_oval(
            player_node.x - 10,
            player_node.y - 56,
            player_node.x + 10,
            player_node.y - 36,
            fill=PLAYER_COLOR,
            outline="",
        )
        self.canvas.create_text(
            player_node.x,
            player_node.y - 72,
            text=self.simulation.player.name,
            fill=PLAYER_COLOR,
            font=("Consolas", 10, "bold"),
        )

    def _refresh_panels(self) -> None:
        selected_npc_name = self._selected_npc_name()
        self.selected_location_id = self.simulation.player.location_id
        self.status_var.set(self.simulation.player_status())
        self.footer_var.set(
            "Controls: arrows/WASD move | click adjacent node | T talk | Y direct speech | R rumor | X work | B buy bread | E eat | M monkey | Space wait | L look"
        )
        self._set_text(self.location_text, self.simulation.describe_location())
        self._set_text(self.rumor_text, self.simulation.known_rumors_text())

        npcs_here = [npc for npc in self.simulation.npcs.values() if npc.location_id == self.simulation.player.location_id]
        self.npc_list.delete(0, tk.END)
        self._npc_name_by_index = []
        for npc in npcs_here:
            entry = f"{npc.name} ({npc.profession})"
            self.npc_list.insert(tk.END, entry)
            self._npc_name_by_index.append(npc.name)
        if npcs_here:
            try:
                selected_index = self._npc_name_by_index.index(selected_npc_name) if selected_npc_name else 0
            except ValueError:
                selected_index = 0
            self.npc_list.selection_set(selected_index)

        self._render_world()

    def _set_text(self, widget: tk.Text, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _append_log(self, lines: list[str], *, kind: str) -> None:
        if not lines:
            return
        prefix = f"[day {self.simulation.world.day:02d} tick {self.simulation.world.tick:04d} | {kind}] "
        self.log_text.configure(state="normal")
        for line in lines:
            self.log_text.insert(tk.END, prefix + line + "\n", (kind,))
            if self.event_log is not None:
                self.event_log.write(
                    kind=kind,
                    message=line,
                    day=self.simulation.world.day,
                    tick=self.simulation.world.tick,
                )
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _append_entries(self, entries: list[TurnEvent]) -> None:
        if not entries:
            self._append_log(["No visible effect."], kind="system")
            return
        for entry in entries:
            self._append_log([entry.text], kind=entry.kind)

    def _click_location(self, location_id: str) -> None:
        current_id = self.simulation.player.location_id
        if location_id == current_id:
            self._select_location(location_id)
            return
        if location_id in self.simulation.world.locations[current_id].neighbors:
            self.selected_location_id = location_id
            self._render_world()
            self._run_command(f"go {location_id}")
            return
        self._select_location(location_id)
        location = self.simulation.world.locations[location_id]
        self._append_log(
            [f"{location.name} is not directly connected. Move through a neighboring node first."],
            kind="ui",
        )

    def _select_location(self, location_id: str) -> None:
        self.selected_location_id = location_id
        self._render_world()
        location = self.simulation.world.locations[location_id]
        self._append_log([f"Selected {location.name}."], kind="ui")

    def _selected_npc_name(self) -> str | None:
        selection = self.npc_list.curselection()
        if selection:
            return self._npc_name_by_index[selection[0]]
        return self._npc_name_by_index[0] if self._npc_name_by_index else None

    def _text_input_has_focus(self) -> bool:
        return self.focus_get() in {self.command_entry, self.say_entry}

    def _run_shortcut(self, callback) -> None:
        if self._text_input_has_focus():
            return
        callback()

    def _focus_say_entry(self) -> None:
        if self.focus_get() is self.command_entry:
            return
        self.say_entry.focus_set()
        self.say_entry.icursor(tk.END)

    def _run_command(self, command: str, *, kind: str = "gui_command") -> None:
        if self._is_dialogue_command(command) and not self.dialogue_ready:
            self._append_log(["Dialogue model is still loading. Wait for the ready message."], kind="system")
            return
        self._append_log([f"> {command}"], kind="input")
        result = self.simulation.handle_command(command)
        self._append_entries(result.entries)
        self._refresh_panels()
        self.command_entry.delete(0, tk.END)
        self.focus_set()
        self._save_snapshot(kind, command, {"result_lines": result.lines, "result_entries": result.payload()})

    def _save_snapshot(self, kind: str, message: str, payload: dict) -> None:
        if self.store is None:
            return
        self.store.save_simulation(self.simulation, kind=kind, message=message, payload=payload)

    def _submit_entry_command(self, _event=None) -> None:
        command = self.command_entry.get().strip()
        if command:
            self._run_command(command)

    def _submit_say_selected(self, _event=None) -> None:
        npc_name = self._selected_npc_name()
        if npc_name is None:
            self._append_log(["No NPC is available here."], kind="ui")
            return
        message = self.say_entry.get().strip()
        if not message:
            self._append_log(["Type something to say first."], kind="ui")
            self.say_entry.focus_set()
            return
        self.say_entry.delete(0, tk.END)
        self._run_command(f"say {npc_name} {message}")

    def _talk_selected(self) -> None:
        npc_name = self._selected_npc_name()
        if npc_name is None:
            self._append_log(["No NPC is available here."], kind="ui")
            return
        self._run_command(f"talk {npc_name}")

    def _ask_rumor_selected(self) -> None:
        npc_name = self._selected_npc_name()
        if npc_name is None:
            self._append_log(["No NPC is available here."], kind="ui")
            return
        self._run_command(f"ask {npc_name} rumor")

    def _buy_bread_selected(self) -> None:
        npc_name = self._selected_npc_name()
        if npc_name is None:
            self._append_log(["No vendor is available here."], kind="ui")
            return
        self._run_command(f"trade {npc_name} buy bread 1")

    def _player_work(self) -> None:
        self._run_command("work")

    def _eat_best_food(self) -> None:
        for item in ("stew", "bread", "fish", "wheat"):
            if self.simulation.player.inventory.get(item, 0) > 0:
                self._run_command(f"eat {item}")
                return
        self._append_log(["You have no food to eat."], kind="ui")

    def _wait_one_turn(self) -> None:
        self._run_command("wait 1")

    def _look(self) -> None:
        self._run_command("look")

    def _refresh_monkey_button(self) -> None:
        state = "On" if self.monkey_enabled else "Off"
        self.monkey_button_var.set(f"Monkey ({state})")

    def _toggle_monkey(self) -> None:
        if self.monkey_enabled:
            self.monkey_enabled = False
            self._monkey_waiting_for_dialogue = False
            self._refresh_monkey_button()
            self._append_log(["Monkey mode disabled."], kind="system")
            return
        if self.monkey_steps_remaining <= 0:
            self.monkey_steps_remaining = self.monkey_default_steps
            self.monkey_runner = SimulationMonkeyRunner(self.simulation, seed=self.monkey_seed)
        self.monkey_enabled = True
        self._monkey_waiting_for_dialogue = not self.dialogue_ready
        self._refresh_monkey_button()
        self._append_log(
            [f"Monkey mode enabled: {self.monkey_steps_remaining} steps, {self.monkey_delay_ms}ms delay."],
            kind="system",
        )
        if self.dialogue_ready:
            self.after(self.monkey_delay_ms, self._run_monkey_step)

    def _move_direction(self, x_dir: int, y_dir: int) -> None:
        if self._text_input_has_focus():
            return
        current_id = self.simulation.player.location_id
        current_node = MAP_LAYOUT[current_id]
        best_neighbor = None
        best_score = 0.18
        for neighbor_id in self.simulation.world.locations[current_id].neighbors:
            node = MAP_LAYOUT[neighbor_id]
            delta_x = node.x - current_node.x
            delta_y = node.y - current_node.y
            length = max((delta_x**2 + delta_y**2) ** 0.5, 1.0)
            score = ((delta_x / length) * x_dir) + ((delta_y / length) * y_dir)
            if score > best_score:
                best_neighbor = neighbor_id
                best_score = score
        if best_neighbor is None:
            self._append_log(["No path in that direction."], kind="ui")
            return
        self._run_command(f"go {best_neighbor}")

    def _on_close(self) -> None:
        if self.store is not None:
            self._save_snapshot("session_end", "GUI session ended.", {"entrypoint": "gui"})
            self.store.close()
            self.store = None
        if self.event_log is not None:
            self.event_log.write(
                kind="session_end",
                message="GUI session ended.",
                day=self.simulation.world.day,
                tick=self.simulation.world.tick,
                payload={"entrypoint": "gui"},
            )
            self.event_log.close()
            self.event_log = None
        self.destroy()

    def _run_monkey_step(self) -> None:
        if not self.monkey_enabled or self.monkey_runner is None or self.monkey_steps_remaining <= 0:
            return
        step = self.monkey_runner.run_one_step()
        self._append_log([f"[monkey] > {step.command}"], kind="input")
        self._append_entries(step.entries)
        self._refresh_panels()
        self._save_snapshot(
            "monkey_command",
            step.command,
            {
                "result_lines": step.lines,
                "result_entries": [{"kind": entry.kind, "text": entry.text} for entry in step.entries],
                "step_index": step.index,
            },
        )
        self.monkey_steps_remaining -= 1
        if self.monkey_steps_remaining > 0:
            self.after(self.monkey_delay_ms, self._run_monkey_step)
        else:
            self.monkey_enabled = False
            self._monkey_waiting_for_dialogue = False
            self._refresh_monkey_button()
            self._append_log(["Monkey run completed."], kind="system")

    def _is_dialogue_command(self, command: str) -> bool:
        lowered = command.strip().lower()
        return lowered.startswith("talk ") or lowered.startswith("say ") or lowered.startswith("tell ") or lowered.startswith("ask ")

    def _start_dialogue_prepare(self) -> None:
        if self.dialogue_loading or self.dialogue_ready:
            return
        self.dialogue_loading = True
        thread = threading.Thread(target=self._prepare_dialogue_worker, name="acidnet-dialogue-prepare", daemon=True)
        thread.start()

    def _prepare_dialogue_worker(self) -> None:
        try:
            message = self.simulation.prepare_dialogue_adapter()
        except Exception as exc:
            message = f"Dialogue model failed to load: {exc}"
            success = False
        else:
            success = True
        try:
            self.after(0, lambda: self._finish_dialogue_prepare(success=success, message=message))
        except tk.TclError:
            return

    def _finish_dialogue_prepare(self, *, success: bool, message: str) -> None:
        self.dialogue_loading = False
        if not self.winfo_exists():
            return
        self.dialogue_ready = success
        self.dialogue_var.set(message)
        self._append_log([message], kind="system")
        if self.monkey_enabled and self._monkey_waiting_for_dialogue and self.dialogue_ready:
            self._monkey_waiting_for_dialogue = False
            self.after(self.monkey_delay_ms, self._run_monkey_step)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the acidnet keyboard GUI.")
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
        "--monkey",
        action="store_true",
        help="Enable automated GUI monkey actions for observation.",
    )
    parser.add_argument(
        "--monkey-steps",
        type=int,
        default=160,
        help="Number of monkey steps to execute when monkey mode is enabled.",
    )
    parser.add_argument(
        "--monkey-delay-ms",
        type=int,
        default=350,
        help="Delay in milliseconds between monkey actions.",
    )
    parser.add_argument(
        "--monkey-seed",
        type=int,
        default=7,
        help="Random seed for monkey mode.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    app = AcidNetApp(
        db_path=args.db,
        persist=not args.no_persist,
        dialogue_backend=args.dialogue_backend,
        dialogue_model=args.dialogue_model,
        dialogue_endpoint=args.dialogue_endpoint,
        dialogue_adapter_path=args.dialogue_adapter_path,
        event_log_path=None if args.no_event_log else args.event_log,
        monkey=args.monkey,
        monkey_steps=args.monkey_steps,
        monkey_delay_ms=args.monkey_delay_ms,
        monkey_seed=args.monkey_seed,
    )
    app.mainloop()
