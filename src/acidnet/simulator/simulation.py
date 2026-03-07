from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import re
from typing import Any, Iterable

from acidnet.llm import DialogueContext, DialogueModelAdapter, DialogueResult, RuleBasedDialogueAdapter, build_dialogue_adapter
from acidnet.llm.prompt_builder import DEFAULT_SYSTEM_PROMPT, infer_interaction_mode
from acidnet.simulator.models import (
    Belief,
    EpisodicMemory,
    IntentType,
    NPCState,
    PersonaProfile,
    PlayerState,
    RelationshipState,
    Rumor,
    RumorCategory,
    RegionalTransit,
    TravelState,
    WorldEvent,
    WorldState,
)
from acidnet.planner import HeuristicPlanner, PlannerContext
from acidnet.simulator.world import build_demo_setup

FOOD_ITEMS = ("stew", "bread", "fish", "wheat")
ITEM_VALUES = {"wheat": 2, "bread": 5, "fish": 4, "stew": 7, "tool": 15}
CONSUMPTION_VALUE = {"wheat": 10.0, "bread": 26.0, "fish": 21.0, "stew": 34.0}
ITEM_WEIGHTS = {"wheat": 0.6, "bread": 0.5, "fish": 0.8, "stew": 1.1, "tool": 3.0}
PROFESSION_ITEM_RESERVE_FLOORS = {
    ("baker", "bread"): 4,
    ("cook", "stew"): 2,
    ("fisher", "fish"): 2,
}
PROFESSION_INPUT_EMERGENCY_EAT_HUNGER = {
    ("baker", "wheat"): 90.0,
    ("cook", "fish"): 88.0,
}
PROFESSION_OUTPUT_BUFFER_CAPS = {
    ("blacksmith", "tool"): 4,
}
RUMOR_DECAY_PER_TURN = 0.003
RUMOR_VALUE_DECAY_PER_TURN = 0.002
RUMOR_DYNAMIC_STALE_TICKS = 8 * 60
RUMOR_MATCH_STOPWORDS = {"the", "and", "with", "this", "that", "have", "from", "will", "into", "your", "about"}
LOCAL_REGION_MARKET_SUPPORT_FACTORS = {
    "wheat": 0.5,
    "bread": 0.6,
    "fish": 0.55,
    "stew": 0.0,
    "tool": 0.35,
}
REMOTE_REGION_MARKET_SUPPORT_FACTORS = {
    "wheat": 0.32,
    "bread": 0.35,
    "fish": 0.3,
    "stew": 0.0,
    "tool": 0.22,
}
MARKET_SUPPORT_CAPS = {
    "wheat": 6,
    "bread": 6,
    "fish": 5,
    "stew": 0,
    "tool": 3,
}
WORK_OUTPUT = {
    "farmer": ("wheat", 2),
    "fisher": ("fish", 2),
    "blacksmith": ("tool", 1),
}
WORK_WAGES = {
    "blacksmith": 6,
    "guard": 6,
    "priest": 6,
    "tailor": 6,
}
TRAVEL_EDGE_BASE_TICKS = {
    frozenset(("square", "tavern")): 24,
    frozenset(("square", "bakery")): 18,
    frozenset(("square", "smithy")): 18,
    frozenset(("square", "farm")): 28,
    frozenset(("square", "shrine")): 16,
    frozenset(("tavern", "riverside")): 26,
    frozenset(("farm", "riverside")): 24,
}
WEATHER_TRAVEL_MULTIPLIERS = {
    "clear": 1.0,
    "cool_rain": 1.1,
    "dry_wind": 1.08,
    "market_day": 1.0,
    "dusty_heat": 1.15,
    "storm_front": 1.35,
}
STORM_BLOCKED_EDGES = {
    frozenset(("tavern", "riverside")),
    frozenset(("farm", "riverside")),
}
SHELTER_RATINGS = {
    "rest": 0.95,
    "social": 0.82,
    "workshop": 0.62,
    "market": 0.55,
    "resource": 0.34,
    "route": 0.28,
}
FIELD_STRESS_WEATHER_DELTA = {
    "cool_rain": -0.26,
    "clear": -0.12,
    "market_day": -0.05,
    "dry_wind": 0.18,
    "dusty_heat": 0.24,
    "storm_front": 0.08,
}
HARVEST_SHORTFALL_EVENT_ID = "event.farm.harvest_shortfall"
ROUTE_DELAY_EVENT_PREFIX = "event.route."
ROUTE_WEATHER_PRESSURE = {
    "clear": 0.0,
    "cool_rain": 0.06,
    "market_day": 0.08,
    "dry_wind": 0.32,
    "dusty_heat": 0.46,
    "storm_front": 0.68,
}
DEFAULT_SPOILAGE_TICKS = {
    "fish": 24,
    "stew": 36,
    "bread": 72,
    "wheat": 144,
}
RECENT_REQUEST_BUFFER_TICKS = 36
RECENT_REQUEST_BUFFER_EMERGENCY_HUNGER = 88.0
TOOL_RELEVANT_LOCATIONS = {"farm", "riverside"}
TOOL_RELEVANT_PROFESSIONS = {"farmer", "fisher"}
TOOL_WEAR_INTERVAL = 4
PLAYER_PASSIVE_HUNGER_PER_TURN = 1.2
PLAYER_PASSIVE_FATIGUE_PER_TURN = 0.45
NPC_PASSIVE_HUNGER_PER_TURN = 1.4
NPC_PASSIVE_FATIGUE_PER_TURN = 0.35
PLAYER_TRAVEL_HUNGER_PER_TURN = 0.8
PLAYER_TRAVEL_FATIGUE_PER_TURN = 5.0
NPC_TRAVEL_HUNGER_PER_TURN = 0.5
NPC_TRAVEL_FATIGUE_PER_TURN = 2.4


@dataclass(slots=True, frozen=True)
class TurnEvent:
    kind: str
    text: str


@dataclass(slots=True)
class TurnResult:
    entries: list[TurnEvent | str]

    def __post_init__(self) -> None:
        normalized: list[TurnEvent] = []
        for entry in self.entries:
            if isinstance(entry, TurnEvent):
                normalized.append(entry)
            else:
                normalized.append(TurnEvent(kind="world", text=entry))
        self.entries = normalized

    @property
    def lines(self) -> list[str]:
        return [entry.text for entry in self.entries]

    def payload(self) -> list[dict[str, str]]:
        return [{"kind": entry.kind, "text": entry.text} for entry in self.entries]


@dataclass(slots=True, frozen=True)
class TradeOption:
    item: str
    quantity: int
    price: int | None = None


class Simulation:
    def __init__(
        self,
        world: WorldState,
        player: PlayerState,
        npcs: dict[str, NPCState],
        personas: dict[str, PersonaProfile],
        rumors: dict[str, Rumor],
        dialogue_adapter: DialogueModelAdapter | None = None,
        dialogue_system_prompt: str | None = None,
    ) -> None:
        self.world = world
        self.player = player
        self.npcs = npcs
        self.personas = personas
        self.rumors = rumors
        self.memories: dict[str, list[EpisodicMemory]] = defaultdict(list)
        self.tick_log: deque[str] = deque(maxlen=16)
        self.planner = HeuristicPlanner()
        self.dialogue_adapter = dialogue_adapter or RuleBasedDialogueAdapter()
        self.dialogue_system_prompt = dialogue_system_prompt or DEFAULT_SYSTEM_PROMPT
        self.turn_ticks = 12
        self.turn_counter = 0
        self._normalize_rumor_state()
        self._refresh_actor_loads()

    @classmethod
    def create_demo(
        cls,
        *,
        dialogue_backend: str = "heuristic",
        dialogue_model: str | None = None,
        dialogue_endpoint: str | None = None,
        dialogue_adapter_path: str | None = None,
        dialogue_system_prompt: str | None = None,
    ) -> "Simulation":
        setup = build_demo_setup()
        return cls(
            world=setup.world,
            player=setup.player,
            npcs=setup.npcs,
            personas=setup.personas,
            rumors=setup.rumors,
            dialogue_adapter=build_dialogue_adapter(
                dialogue_backend,
                model=dialogue_model,
                endpoint=dialogue_endpoint,
                adapter_path=dialogue_adapter_path,
            ),
            dialogue_system_prompt=dialogue_system_prompt,
        )

    def snapshot(self) -> dict[str, Any]:
        self._refresh_actor_loads()
        return {
            "world": self.world.model_dump(mode="json"),
            "player": self.player.model_dump(mode="json"),
            "npcs": {npc_id: self.npcs[npc_id].model_dump(mode="json") for npc_id in sorted(self.npcs)},
            "personas": {
                persona_id: self.personas[persona_id].model_dump(mode="json")
                for persona_id in sorted(self.personas)
            },
            "rumors": {rumor_id: self.rumors[rumor_id].model_dump(mode="json") for rumor_id in sorted(self.rumors)},
            "memories": {
                actor_id: [memory.model_dump(mode="json") for memory in memories]
                for actor_id, memories in sorted(self.memories.items())
            },
            "dialogue_backend": type(self.dialogue_adapter).__name__,
            "dialogue_system_prompt": self.dialogue_system_prompt,
            "tick_log": list(self.tick_log),
            "turn_counter": self.turn_counter,
        }

    def prepare_dialogue_adapter(self) -> str:
        return self.dialogue_adapter.prepare() or f"{type(self.dialogue_adapter).__name__} ready."

    def set_dialogue_system_prompt(self, prompt: str) -> None:
        self.dialogue_system_prompt = prompt or DEFAULT_SYSTEM_PROMPT

    def help_text(self) -> str:
        return "\n".join(
            [
                "Commands:",
                "  look                     Show the current location.",
                "  look <npc>               Inspect a person at your location.",
                "  inspect [npc]            Inspect the focused or named NPC.",
                "  where                    Show nearby locations.",
                "  map                      List all locations.",
                "  go <location>            Move to a neighboring location.",
                "  regions                  List summarized regions and routes.",
                "  travel-region <region>   Travel along a regional route to another region anchor.",
                "  focus <npc>              Set the current interaction target.",
                "  focus clear              Clear the current interaction target.",
                "  talk [npc]               Talk to the focused or named NPC.",
                "  say <npc> <message>      Speak to an NPC using your own words.",
                "  ask [npc] rumor          Ask the focused or named NPC for their latest rumor.",
                "  work                     Do local work or gather resources here.",
                "  eat [item]               Consume a named food, or the best meal if omitted.",
                "  meal                     Consume the best available food.",
                "  rest [turns]             Recover a little fatigue in place.",
                "  sleep [turns]            Recover more fatigue, affected by shelter quality.",
                "  trade [npc] buy <item> <qty>",
                "  trade [npc] sell <item> <qty>",
                "  trade [npc] ask <item> <qty>",
                "  trade [npc] give <item> <qty>",
                "  trade [npc] barter <give_item> <give_qty> for <get_item> <get_qty>",
                "  share [npc] <item> <qty> Default social transfer: give if you have it, otherwise ask.",
                "  inventory                Show your inventory and gold.",
                "  status                   Show player and world status.",
                "  rumors                   Show rumors you know.",
                "  npcs                     List NPCs at your location.",
                "  next [turns]             Advance the world.",
                "  help                     Show this help.",
                "  quit                     Exit the simulation.",
            ]
        )

    def describe_location(self) -> str:
        if self.player.travel_state.is_traveling:
            return self._player_travel_text()
        location = self.world.locations[self.player.location_id]
        npcs = self._npcs_at(location.location_id)
        focused_npc = self._focused_npc_here()
        npc_lines = []
        for npc in npcs:
            mood = self._npc_mood(npc)
            stock = self._vendor_stock_line(npc)
            marker = " [target]" if focused_npc is not None and focused_npc.npc_id == npc.npc_id else ""
            npc_lines.append(f"- {npc.name}{marker} ({npc.profession}, {mood}){stock}")
        exits = ", ".join(self.world.locations[loc_id].name for loc_id in location.neighbors)
        return "\n".join(
            [
                f"You are at {location.name} [{location.kind}].",
                f"Exits: {exits}",
                "People here:" if npc_lines else "No one is here right now.",
                *npc_lines,
            ]
        )

    def list_map(self) -> str:
        lines = ["Village map:"]
        for location in self.world.locations.values():
            exits = ", ".join(self.world.locations[node].name for node in location.neighbors)
            lines.append(f"- {location.name}: {exits}")
        return "\n".join(lines)

    def list_regions(self) -> str:
        current_region = self.current_region()
        current_region_id = current_region.region_id if current_region is not None else None
        lines = ["Regional overview:"]
        for region in self.world.regions.values():
            marker = " [current]" if region.region_id == current_region_id else ""
            stocks = ", ".join(f"{item}:{qty}" for item, qty in sorted(region.stock_signals.items()))
            lines.append(f"- {region.name}{marker} ({region.kind}) | risk {region.risk_level:.2f} | {stocks}")
        if self.world.regional_routes:
            lines.append("Routes:")
            for route in self.world.regional_routes:
                left = self.world.regions[route.from_region_id].name
                right = self.world.regions[route.to_region_id].name
                route_event = self._visible_route_delay_event_for_player(route.route_id)
                route_status = f" | {route_event.summary}" if route_event is not None else ""
                transit_count = sum(1 for transit in self.world.regional_transits if transit.route_id == route.route_id)
                transit_suffix = f" | transit {transit_count}" if transit_count > 0 else ""
                lines.append(
                    f"- {left} <-> {right}: {self._travel_eta_turns(route.travel_ticks)} turns, risk {route.cargo_risk:.2f}{transit_suffix}{route_status}"
                )
        return "\n".join(lines)

    def player_status(self) -> str:
        self._refresh_actor_loads()
        focused_npc = self._focused_npc_here()
        current_region = self.current_region()
        location_line = f"{self.player.name} is at {self.world.locations[self.player.location_id].name}."
        shelter_line = "Shelter: none while traveling"
        if self.player.travel_state.is_traveling:
            origin_name = self.world.locations[self.player.travel_state.origin_location_id or self.player.location_id].name
            destination_id = self.player.travel_state.destination_location_id or self.player.location_id
            destination_name = self.world.locations[destination_id].name
            location_line = f"{self.player.name} is traveling from {origin_name} to {destination_name}."
        else:
            shelter = self._shelter_rating(self.player.location_id)
            shelter_line = f"Shelter: {self._shelter_label(shelter)} ({shelter:.2f})"
        lines = [
            f"Day {self.world.day}, tick {self.world.tick}, weather: {self.world.weather}",
            location_line,
            f"Region: {current_region.name if current_region is not None else 'unknown'}",
            f"Target: {focused_npc.name if focused_npc is not None else 'none'}",
            f"Hunger: {self.player.hunger:.1f}/100",
            f"Fatigue: {self.player.fatigue:.1f}/100",
            shelter_line,
            f"Field stress: {self.world.field_stress:.2f}",
            f"Load: {self.player.carried_weight:.1f}/{self.player.carry_capacity:.1f}",
            f"Money: {self.player.money} gold",
            f"Inventory: {self._format_inventory(self.player.inventory)}",
            f"Known rumors: {len(self.player.known_rumor_ids)}",
        ]
        if self.player.travel_state.is_traveling:
            destination = self.player.travel_state.destination_location_id or "unknown"
            lines.append(f"Travel: en route to {destination} ({self.player.travel_state.ticks_remaining} ticks remaining)")
        visible_events = self._visible_world_events_for_player()
        if visible_events:
            lines.append("Active world events:")
            lines.extend(f"- {event.summary}" for event in visible_events)
        if self.tick_log:
            lines.append("Recent world events:")
            lines.extend(f"- {entry}" for entry in list(self.tick_log)[-5:])
        return "\n".join(lines)

    def current_region(self):
        location = self.world.locations.get(self.player.location_id)
        if location is None:
            return None
        return self.world.regions.get(location.region_id)

    def known_rumors_text(self) -> str:
        if not self.player.known_rumor_ids:
            return "You do not know any rumors yet."
        lines = ["Rumors you know:"]
        for rumor in self._sorted_known_rumors(self.player.known_rumor_ids, dedupe_by_signature=True):
            lines.append(f"- {rumor.content} (confidence {rumor.confidence:.2f})")
        return "\n".join(lines)

    def npcs_here_text(self) -> str:
        if self.player.travel_state.is_traveling:
            return "You are on the road right now and cannot interact with anyone."
        npcs = self._npcs_at(self.player.location_id)
        if not npcs:
            return "There are no NPCs here."
        focused_npc = self._focused_npc_here()
        lines = []
        for npc in npcs:
            marker = " [target]" if focused_npc is not None and focused_npc.npc_id == npc.npc_id else ""
            lines.append(f"- {npc.name}{marker} ({npc.profession})")
        return "\n".join(lines)

    def player_trade_options(self, npc_query: str | None = None, *, mode: str = "buy") -> list[TradeOption]:
        npc = self._resolve_npc_here(npc_query) if npc_query else self._focused_npc_here()
        if npc is None:
            return []

        mode = self._normalize_trade_mode(mode)
        if mode == "buy":
            inventory = npc.inventory
            buy_from_vendor = True
        elif mode == "sell":
            if not npc.is_vendor:
                return []
            inventory = self.player.inventory
            buy_from_vendor = False
        elif mode == "ask":
            options: list[TradeOption] = []
            for item in ITEM_VALUES:
                quantity = self._requestable_quantity(npc, self.player, item)
                if quantity > 0:
                    options.append(TradeOption(item=item, quantity=quantity))
            return options
        elif mode == "give":
            options = []
            for item in ITEM_VALUES:
                quantity = self._giftable_quantity(self.player, item)
                if quantity > 0:
                    options.append(TradeOption(item=item, quantity=quantity))
            return options
        else:
            return []

        options: list[TradeOption] = []
        for item in ITEM_VALUES:
            quantity = self._sellable_quantity(npc, item) if mode == "buy" else inventory.get(item, 0)
            if quantity <= 0:
                continue
            options.append(
                TradeOption(
                    item=item,
                    quantity=quantity,
                    price=self._price_for(npc, item, buy_from_vendor=buy_from_vendor),
                )
            )
        return options

    def npc_detail_text(self, npc_query: str | None = None) -> str:
        self._refresh_actor_loads()
        npc = self._resolve_npc_here(npc_query) if npc_query else self._focused_npc_here()
        if npc is None:
            return "No interaction target selected."

        location = self.world.locations[npc.location_id].name
        buy_options = self.player_trade_options(npc.npc_id, mode="buy")
        sell_options = self.player_trade_options(npc.npc_id, mode="sell")
        ask_options = self.player_trade_options(npc.npc_id, mode="ask")
        give_options = self.player_trade_options(npc.npc_id, mode="give")
        lines = [
            f"Target: {npc.name} ({npc.profession})",
            f"Location: {location}",
            f"Mood: {self._npc_mood(npc)} | Money: {npc.money} gold",
            f"Fatigue: {npc.fatigue:.1f}/100 | Load: {npc.carried_weight:.1f}/{npc.carry_capacity:.1f}",
            f"Inventory: {self._format_inventory(npc.inventory)}",
            "Buy (cash): "
            + (", ".join(f"{option.item} x{option.quantity} ({option.price}g)" for option in buy_options) if buy_options else "nothing available."),
            "Ask (gift): " + (", ".join(f"{option.item} x{option.quantity}" for option in ask_options) if ask_options else "nothing they can spare right now."),
            "Give (gift): " + (", ".join(f"{option.item} x{option.quantity}" for option in give_options) if give_options else "nothing you can spare right now."),
        ]
        if npc.is_vendor:
            sell_line = (
                ", ".join(f"{option.item} x{option.quantity} ({option.price}g)" for option in sell_options)
                if sell_options
                else "nothing from your inventory."
            )
            lines.append(f"Sell (cash): {sell_line}")
        else:
            lines.append("Sell (cash): this NPC is not buying goods.")
        if npc.known_rumor_ids:
            lines.append(f"Rumors known: {len(npc.known_rumor_ids)}")
        return "\n".join(lines)

    def _events(self, kind: str, lines: Iterable[str]) -> list[TurnEvent]:
        return [TurnEvent(kind=kind, text=line) for line in lines if line]

    def _npc_dialogue_event(self, npc: NPCState, text: str) -> TurnEvent:
        cleaned = " ".join(text.split()) or "..."
        return TurnEvent(kind="npc", text=f"{npc.name}: {cleaned}")

    def move_player(self, location_query: str) -> TurnResult:
        if self.player.travel_state.is_traveling:
            return TurnResult(self._events("system", [self._travel_command_block_message()]))
        destination = self._resolve_location(location_query)
        if destination is None:
            return TurnResult(self._events("system", [f'Unknown location "{location_query}".']))
        current = self.world.locations[self.player.location_id]
        if destination.location_id not in current.neighbors:
            return TurnResult(self._events("system", [f"You cannot go directly to {destination.name} from here."]))
        blocked_reason = self._travel_block_reason(current.location_id, destination.location_id, self.player)
        if blocked_reason:
            return TurnResult(self._events("system", [blocked_reason]))
        total_ticks = self._begin_travel(self.player, destination.location_id)
        self.player.focused_npc_id = None
        entries = self._events(
            "system",
            [f"You set out for {destination.name}. ETA {self._travel_eta_turns(total_ticks)} turns ({total_ticks} ticks)."],
        )
        entries.extend(self.advance_turn(1).entries)
        return TurnResult(entries)

    def move_player_to_region(self, region_query: str) -> TurnResult:
        if self.player.travel_state.is_traveling:
            return TurnResult(self._events("system", [self._travel_command_block_message()]))
        destination_region = self._resolve_region(region_query)
        if destination_region is None:
            return TurnResult(self._events("system", [f'Unknown region "{region_query}".']))
        current_region = self.current_region()
        if current_region is None:
            return TurnResult(self._events("system", ["Your current region is unknown."]))
        if destination_region.region_id == current_region.region_id:
            return TurnResult(self._events("system", [f"You are already in {destination_region.name}."]))
        route = self._regional_route_between(current_region.region_id, destination_region.region_id)
        if route is None:
            return TurnResult(self._events("system", [f"There is no known regional route to {destination_region.name}."]))
        if destination_region.anchor_location_id is None or destination_region.anchor_location_id not in self.world.locations:
            return TurnResult(self._events("system", [f"{destination_region.name} does not yet have a travel anchor."]))
        total_ticks = self._begin_regional_travel(self.player, route, destination_region.anchor_location_id)
        self.player.focused_npc_id = None
        entries = self._events(
            "system",
            [f"You set out for {destination_region.name}. ETA {self._travel_eta_turns(total_ticks)} turns ({total_ticks} ticks)."],
        )
        entries.extend(self.advance_turn(1).entries)
        return TurnResult(entries)

    def set_player_focus(self, npc_query: str | None) -> TurnResult:
        if npc_query is None:
            focused_npc = self._focused_npc_here()
            if focused_npc is None:
                return TurnResult(self._events("system", ["No interaction target is selected."]))
            return TurnResult(self._events("system", [f"Current target: {focused_npc.name}."]))
        lowered = npc_query.strip().lower()
        if lowered in {"clear", "none"}:
            self.player.focused_npc_id = None
            return TurnResult(self._events("system", ["Interaction target cleared."]))
        npc = self._resolve_npc_here(npc_query)
        if npc is None:
            return TurnResult(self._events("system", [f'No NPC named "{npc_query}" is here.']))
        self.player.focused_npc_id = npc.npc_id
        return TurnResult(self._events("system", [f"Interaction target set to {npc.name}.", self.npc_detail_text(npc.npc_id)]))

    def inspect_npc(self, npc_query: str | None = None) -> TurnResult:
        npc, error = self._resolve_interaction_npc(npc_query, action="inspect")
        if npc is None:
            return TurnResult(self._events("system", [error]))
        return TurnResult(self._events("system", [self.npc_detail_text(npc.npc_id)]))

    def talk_to_npc(self, npc_query: str | None = None) -> TurnResult:
        npc, error = self._resolve_interaction_npc(npc_query, action="talk to")
        if npc is None:
            return TurnResult(self._events("system", [error]))

        player_prompt = "What is going on around here?"
        dialogue = self._generate_dialogue_result(npc, interaction_mode="talk", player_prompt=player_prompt)
        entries = [self._npc_dialogue_event(npc, dialogue.text)]
        self._record_dialogue_exchange(npc, player_prompt=player_prompt)
        self._change_relationship(npc, self.player.player_id, trust_delta=0.02, closeness_delta=0.04)
        rumor_notice = self._offer_rumor_to_player(npc, dialogue_result=dialogue, asked=False)
        if rumor_notice:
            entries.extend(self._events("system", [rumor_notice]))
        entries.extend(self.advance_turn(1).entries)
        return TurnResult(entries)

    def say_to_npc(self, npc_query: str, player_message: str) -> TurnResult:
        npc, error = self._resolve_interaction_npc(npc_query, action="talk to")
        if npc is None:
            return TurnResult(self._events("system", [error]))

        player_prompt = " ".join(player_message.split())
        if not player_prompt:
            return TurnResult(self._events("system", ["Say what?"]))

        interaction_mode = infer_interaction_mode(player_prompt)
        dialogue = self._generate_dialogue_result(npc, interaction_mode=interaction_mode, player_prompt=player_prompt)
        entries = [
            self._npc_dialogue_event(npc, dialogue.text)
        ]
        self._record_dialogue_exchange(npc, player_prompt=player_prompt)
        self._change_relationship(npc, self.player.player_id, trust_delta=0.02, closeness_delta=0.05)
        if interaction_mode == "rumor_request":
            rumor_notice = self._offer_rumor_to_player(npc, dialogue_result=dialogue, asked=True)
            if rumor_notice:
                entries.extend(self._events("system", [rumor_notice]))
        entries.extend(self.advance_turn(1).entries)
        return TurnResult(entries)

    def ask_npc(self, npc_query: str | None, topic: str) -> TurnResult:
        npc, error = self._resolve_interaction_npc(npc_query, action="ask")
        if npc is None:
            return TurnResult(self._events("system", [error]))
        if topic.lower() != "rumor":
            player_prompt = f"What do you know about {topic}?"
            dialogue = self._generate_dialogue_result(npc, interaction_mode="direct_say", player_prompt=player_prompt)
            self._record_dialogue_exchange(npc, player_prompt=player_prompt)
            result = [self._npc_dialogue_event(npc, dialogue.text)]
            result.extend(self.advance_turn(1).entries)
            return TurnResult(result)
        player_prompt = "Have you heard any useful rumors?"
        dialogue = self._generate_dialogue_result(npc, interaction_mode="rumor_request", player_prompt=player_prompt)
        result = [self._npc_dialogue_event(npc, dialogue.text)]
        self._record_dialogue_exchange(npc, player_prompt=player_prompt)
        rumor_notice = self._offer_rumor_to_player(npc, dialogue_result=dialogue, asked=True)
        if rumor_notice is not None:
            result.extend(self._events("system", [rumor_notice]))
        result.extend(self.advance_turn(1).entries)
        return TurnResult(result)

    def probe_npc_dialogue(self, npc_id: str, *, interaction_mode: str, player_prompt: str) -> str:
        return self.probe_npc_dialogue_result(
            npc_id,
            interaction_mode=interaction_mode,
            player_prompt=player_prompt,
        ).text

    def probe_npc_dialogue_result(
        self,
        npc_id: str,
        *,
        interaction_mode: str,
        player_prompt: str,
    ) -> DialogueResult:
        npc = self.npcs[npc_id]
        return self._generate_dialogue_result(npc, interaction_mode=interaction_mode, player_prompt=player_prompt)

    def player_eat(self, item_query: str) -> TurnResult:
        item = self._resolve_item(item_query)
        if item is None or item not in FOOD_ITEMS:
            return TurnResult(self._events("system", [f'"{item_query}" is not edible here.']))
        if self.player.inventory.get(item, 0) <= 0:
            return TurnResult(self._events("system", [f"You do not have any {item}."]))
        self._consume_food(self.player.inventory, item, self.player)
        self._record_memory(
            npc_id=self.player.player_id,
            event_type="eat",
            summary=f"Ate {item}.",
            importance=0.35,
        )
        entries = self._events("system", [f"You eat {item}. Hunger drops to {self.player.hunger:.1f}."])
        entries.extend(self.advance_turn(1).entries)
        return TurnResult(entries)

    def player_meal(self) -> TurnResult:
        best_item = self._best_food_in_inventory(self.player.inventory)
        if best_item is None:
            return TurnResult(self._events("system", ["You have no food to eat."]))
        return self.player_eat(best_item)

    def player_rest(self, turns: int = 1, *, sleep: bool = False) -> TurnResult:
        if self.player.travel_state.is_traveling:
            return TurnResult(self._events("system", [self._travel_command_block_message()]))
        turns = max(1, turns)
        shelter = self._shelter_rating(self.player.location_id)
        quality = self._shelter_label(shelter)
        sleep_floor = self._sleep_recovery_floor(shelter) if sleep else None
        intro = (
            f"You settle in for sleep at {self.world.locations[self.player.location_id].name}. Shelter is {quality} ({shelter:.2f})."
            if sleep
            else f"You stop to rest at {self.world.locations[self.player.location_id].name}. Shelter is {quality} ({shelter:.2f})."
        )
        entries = self._events("system", [intro])
        if sleep_floor is not None and sleep_floor > 0.0:
            if shelter >= 0.45:
                entries.extend(
                    self._events(
                        "system",
                        [f"The shelter here only supports light sleep, so fatigue will not settle much below {sleep_floor:.1f}."],
                    )
                )
            else:
                entries.extend(
                    self._events(
                        "system",
                        [f"This spot is too exposed for deep sleep, so fatigue will not settle much below {sleep_floor:.1f}."],
                    )
                )
        for _ in range(turns):
            entries.extend(self.advance_turn(1).entries)
            self._apply_recovery(self.player, location_id=self.player.location_id, sleep=sleep)
        action_name = "sleep" if sleep else "rest"
        entries.extend(
            self._events(
                "system",
                [f"After {action_name}, hunger is {self.player.hunger:.1f} and fatigue is {self.player.fatigue:.1f}."],
            )
        )
        return TurnResult(entries)

    def player_work(self) -> TurnResult:
        if self.player.travel_state.is_traveling:
            return TurnResult(self._events("system", [self._travel_command_block_message()]))
        if self.player.fatigue >= 85:
            return TurnResult(self._events("system", ["You are too exhausted to work. Rest or sleep first."]))
        self._refresh_actor_loads()
        location = self.world.locations[self.player.location_id]
        lines: list[str] = []
        if location.location_id == "farm":
            wheat_yield = self._effective_work_amount(
                self.player,
                base_amount=self._farm_yield_amount(),
                location_id=location.location_id,
            )
            kept_yield, lost_yield = self._apply_storage_pressure_to_gain(self.player, "wheat", wheat_yield)
            if kept_yield > 0:
                self._adjust_item(self.player.inventory, "wheat", kept_yield)
            lines.append(f"You help in the south field and gather {kept_yield} wheat.")
            if lost_yield > 0:
                lines.append(f"You leave {lost_yield} wheat behind because your load is already too heavy.")
        elif location.location_id == "riverside":
            fish_yield = self._effective_work_amount(self.player, base_amount=1, location_id=location.location_id)
            kept_yield, lost_yield = self._apply_storage_pressure_to_gain(self.player, "fish", fish_yield)
            if kept_yield > 0:
                self._adjust_item(self.player.inventory, "fish", kept_yield)
            lines.append(f"You spend a shift on the riverside and catch {kept_yield} fish.")
            if lost_yield > 0:
                lines.append(f"You leave {lost_yield} fish behind because your load is already too heavy.")
        elif location.location_id == "square":
            self.player.money += 4
            lines.append("You run market errands and earn 4 gold.")
        elif location.location_id == "bakery":
            self.player.money += 5
            lines.append("You help with bakery deliveries and earn 5 gold.")
        elif location.location_id == "tavern":
            self.player.money += 5
            lines.append("You serve at the tavern for a while and earn 5 gold.")
        elif location.location_id == "smithy":
            self.player.money += 5
            lines.append("You haul ore and coal at the smithy and earn 5 gold.")
        elif location.location_id == "shrine":
            self.player.money += 3
            lines.append("You help maintain the shrine and receive 3 gold in offerings.")
        else:
            return TurnResult(self._events("system", ["There is no useful work available here right now."]))

        self._record_memory(
            npc_id=self.player.player_id,
            event_type="work",
            summary=f"Worked at {location.name}.",
            importance=0.4,
        )
        tool_wear_line = self._apply_tool_wear_if_due(self.player, location_id=location.location_id)
        if tool_wear_line:
            lines.append(tool_wear_line)
        self.player.fatigue = min(100.0, self.player.fatigue + 8.0)
        entries = self._events("system", lines)
        entries.extend(self.advance_turn(1).entries)
        return TurnResult(entries)

    def trade_with_npc(self, npc_query: str | None, mode: str, item_query: str, qty: int) -> TurnResult:
        item = self._resolve_item(item_query)
        if item is None:
            return TurnResult(self._events("system", [f'Unknown item "{item_query}".']))
        if qty <= 0:
            return TurnResult(self._events("system", ["Quantity must be greater than zero."]))

        mode = self._normalize_trade_mode(mode)
        if mode not in {"buy", "sell", "ask", "give"}:
            return TurnResult(self._events("system", ['Trade mode must be "buy", "sell", "ask", or "give".']))
        candidates = self._trade_candidates(mode, item, qty)
        action = f"{mode} {item}"
        npc, error = self._resolve_interaction_npc(npc_query, action=action, candidates=candidates)
        if npc is None:
            return TurnResult(self._events("system", [error]))

        lines: list[str] = []
        if mode == "buy":
            price = self._price_for(npc, item, buy_from_vendor=True)
            if self._sellable_quantity(npc, item) < qty:
                return TurnResult(self._events("system", [f"{npc.name} does not have enough {item}."]))
            total = price * qty
            if self.player.money < total:
                return TurnResult(self._events("system", [f"You need {total} gold, but you only have {self.player.money}."]))
            self.player.money -= total
            npc.money += total
            self._adjust_item(self.player.inventory, item, qty)
            self._adjust_item(npc.inventory, item, -qty)
            lines.append(f"You buy {qty} {item} from {npc.name} for {total} gold.")
        elif mode == "sell":
            if self.player.inventory.get(item, 0) < qty:
                return TurnResult(self._events("system", [f"You do not have enough {item}."]))
            if not npc.is_vendor:
                return TurnResult(self._events("system", [f"{npc.name} is not interested in trading right now."]))
            price = self._price_for(npc, item, buy_from_vendor=False)
            total = price * qty
            if npc.money < total:
                return TurnResult(self._events("system", [f"{npc.name} cannot afford that deal."]))
            self.player.money += total
            npc.money -= total
            self._adjust_item(self.player.inventory, item, -qty)
            self._adjust_item(npc.inventory, item, qty)
            lines.append(f"You sell {qty} {item} to {npc.name} for {total} gold.")
        elif mode == "ask":
            giftable = self._giftable_quantity(npc, item)
            if giftable < qty:
                return TurnResult(self._events("system", [f"{npc.name} cannot spare that much {item} right now."]))
            recent_request_buffer = self._recent_request_buffer_active(npc, self.player, item)
            requestable = self._requestable_quantity(npc, self.player, item)
            if requestable < qty:
                if recent_request_buffer:
                    return TurnResult(self._events("system", [f"{npc.name} already helped you recently and asks you to make do for now."]))
                return TurnResult(self._events("system", [f"{npc.name} is not willing to give you that much {item} right now."]))
            self._adjust_item(self.player.inventory, item, qty)
            self._adjust_item(npc.inventory, item, -qty)
            lines.append(f"{npc.name} gives you {qty} {item}.")
        else:
            giftable = self._giftable_quantity(self.player, item)
            if self.player.inventory.get(item, 0) < qty:
                return TurnResult(self._events("system", [f"You do not have enough {item}."]))
            if giftable < qty:
                return TurnResult(self._events("system", [f"You cannot spare that much {item} without cutting into your reserve."]))
            self._adjust_item(self.player.inventory, item, -qty)
            self._adjust_item(npc.inventory, item, qty)
            lines.append(f"You give {qty} {item} to {npc.name}.")

        memory_summary = {
            "buy": f"Bought {item} from {self.player.name}.",
            "sell": f"Sold {item} to {self.player.name}.",
            "ask": f"Gave {item} to {self.player.name}.",
            "give": f"Received {item} from {self.player.name}.",
        }[mode]
        player_summary = {
            "buy": f"Bought {item} from {npc.name}.",
            "sell": f"Sold {item} to {npc.name}.",
            "ask": f"Received {item} from {npc.name}.",
            "give": f"Gave {item} to {npc.name}.",
        }[mode]

        self._record_memory(
            npc_id=npc.npc_id,
            event_type="exchange" if mode in {"ask", "give"} else "trade",
            summary=memory_summary,
            entities=[self.player.player_id],
            importance=0.65,
        )
        self._record_memory(
            npc_id=self.player.player_id,
            event_type="exchange" if mode in {"ask", "give"} else "trade",
            summary=player_summary,
            entities=[npc.npc_id],
            importance=0.65,
        )
        if mode == "give":
            self._change_relationship(npc, self.player.player_id, trust_delta=0.08, closeness_delta=0.06)
        elif mode == "ask":
            self._change_relationship(npc, self.player.player_id, trust_delta=0.05, closeness_delta=0.05)
        else:
            self._change_relationship(npc, self.player.player_id, trust_delta=0.03, closeness_delta=0.02)
        self._refresh_market_snapshot()
        entries = self._events("system", lines)
        entries.extend(self.advance_turn(1).entries)
        return TurnResult(entries)

    def share_with_npc(self, npc_query: str | None, item_query: str, qty: int) -> TurnResult:
        item = self._resolve_item(item_query)
        if item is None:
            return TurnResult(self._events("system", [f'Unknown item "{item_query}".']))
        if qty <= 0:
            return TurnResult(self._events("system", ["Quantity must be greater than zero."]))
        mode = "give" if self.player.inventory.get(item, 0) > 0 else "ask"
        return self.trade_with_npc(npc_query, mode, item, qty)

    def barter_with_npc(
        self,
        npc_query: str | None,
        give_item_query: str,
        give_qty: int,
        get_item_query: str,
        get_qty: int,
    ) -> TurnResult:
        give_item = self._resolve_item(give_item_query)
        get_item = self._resolve_item(get_item_query)
        if give_item is None:
            return TurnResult(self._events("system", [f'Unknown item "{give_item_query}".']))
        if get_item is None:
            return TurnResult(self._events("system", [f'Unknown item "{get_item_query}".']))
        if give_item == get_item:
            return TurnResult(self._events("system", ["Barter needs different offered and requested items."]))
        if give_qty <= 0 or get_qty <= 0:
            return TurnResult(self._events("system", ["Barter quantities must be greater than zero."]))

        candidates = self._barter_candidates(give_item, give_qty, get_item, get_qty)
        action = f"barter {give_item} for {get_item}"
        npc, error = self._resolve_interaction_npc(npc_query, action=action, candidates=candidates)
        if npc is None:
            return TurnResult(self._events("system", [error]))

        if self.player.inventory.get(give_item, 0) < give_qty:
            return TurnResult(self._events("system", [f"You do not have enough {give_item}."]))
        if self._giftable_quantity(self.player, give_item) < give_qty:
            return TurnResult(self._events("system", [f"You cannot spare that much {give_item} without cutting into your reserve."]))
        if self._sellable_quantity(npc, get_item) < get_qty:
            return TurnResult(self._events("system", [f"{npc.name} cannot spare that much {get_item} right now."]))

        offered_value = self._exchange_value(give_item, give_qty)
        requested_value = self._exchange_value(get_item, get_qty)
        if offered_value < self._barter_required_value(npc, offered_item=give_item, requested_item=get_item, requested_value=requested_value):
            return TurnResult(
                self._events(
                    "system",
                    [f"{npc.name} does not think {give_qty} {give_item} is enough for {get_qty} {get_item}."],
                )
            )

        self._adjust_item(self.player.inventory, give_item, -give_qty)
        self._adjust_item(npc.inventory, give_item, give_qty)
        self._adjust_item(self.player.inventory, get_item, get_qty)
        self._adjust_item(npc.inventory, get_item, -get_qty)
        self._record_memory(
            npc_id=npc.npc_id,
            event_type="trade",
            summary=f"Bartered {get_item} for {give_item} with {self.player.name}.",
            entities=[self.player.player_id],
            importance=0.67,
        )
        self._record_memory(
            npc_id=self.player.player_id,
            event_type="trade",
            summary=f"Bartered {give_item} for {get_item} with {npc.name}.",
            entities=[npc.npc_id],
            importance=0.67,
        )
        self._change_relationship(npc, self.player.player_id, trust_delta=0.04, closeness_delta=0.03)
        self._refresh_market_snapshot()
        entries = self._events("system", [f"You barter {give_qty} {give_item} with {npc.name} for {get_qty} {get_item}."])
        entries.extend(self.advance_turn(1).entries)
        return TurnResult(entries)

    def advance_turn(self, turns: int) -> TurnResult:
        turns = max(1, turns)
        lines: list[str] = []
        for _ in range(turns):
            lines.extend(self._step_turn())
        return TurnResult(lines)

    def handle_command(self, raw_command: str) -> TurnResult:
        parts = raw_command.strip().split()
        if not parts:
            return TurnResult([])
        command = parts[0].lower()
        if self.player.travel_state.is_traveling and command in {"go", "focus", "target", "inspect", "talk", "say", "tell", "ask", "trade", "share", "work"}:
            return TurnResult(self._events("system", [self._travel_command_block_message()]))
        if command == "help":
            return TurnResult(self._events("system", [self.help_text()]))
        if command == "where":
            return TurnResult(self._events("system", [self.describe_location()]))
        if command == "look":
            if len(parts) == 1:
                return TurnResult(self._events("system", [self.describe_location()]))
            if parts[1].lower() == "at" and len(parts) >= 3:
                return self.inspect_npc(" ".join(parts[2:]))
            return self.inspect_npc(" ".join(parts[1:]))
        if command == "inspect":
            return self.inspect_npc(" ".join(parts[1:]) if len(parts) >= 2 else None)
        if command == "map":
            return TurnResult(self._events("system", [self.list_map()]))
        if command == "regions":
            return TurnResult(self._events("system", [self.list_regions()]))
        if command == "inventory":
            return TurnResult(
                self._events("system", [f"Inventory: {self._format_inventory(self.player.inventory)} | Gold: {self.player.money}"])
            )
        if command == "status":
            return TurnResult(self._events("system", [self.player_status()]))
        if command == "rumors":
            return TurnResult(self._events("system", [self.known_rumors_text()]))
        if command == "npcs":
            return TurnResult(self._events("system", [self.npcs_here_text()]))
        if command in {"focus", "target"}:
            return self.set_player_focus(" ".join(parts[1:]) if len(parts) >= 2 else None)
        if command in {"work", "gather", "forage"}:
            return self.player_work()
        if command == "eat":
            if len(parts) >= 2:
                return self.player_eat(" ".join(parts[1:]))
            return self.player_meal()
        if command == "meal":
            return self.player_meal()
        if command == "rest":
            turns = 1
            if len(parts) >= 2:
                try:
                    turns = int(parts[1])
                except ValueError:
                    return TurnResult(self._events("system", ["Rest amount must be an integer."]))
            return self.player_rest(turns, sleep=False)
        if command == "sleep":
            turns = 3
            if len(parts) >= 2:
                try:
                    turns = int(parts[1])
                except ValueError:
                    return TurnResult(self._events("system", ["Sleep amount must be an integer."]))
            return self.player_rest(turns, sleep=True)
        if command == "go" and len(parts) >= 2:
            return self.move_player(" ".join(parts[1:]))
        if command == "travel-region" and len(parts) >= 2:
            return self.move_player_to_region(" ".join(parts[1:]))
        if command == "talk":
            return self.talk_to_npc(" ".join(parts[1:]) if len(parts) >= 2 else None)
        if command in {"say", "tell"} and len(parts) >= 3:
            return self.say_to_npc(parts[1], " ".join(parts[2:]))
        if command == "ask" and len(parts) >= 2:
            return self.ask_npc(" ".join(parts[1:-1]) if len(parts) >= 3 else None, parts[-1])
        if command == "trade" and len(parts) >= 4:
            lowered_parts = [part.lower() for part in parts]
            if "barter" in lowered_parts[1:]:
                barter_index = lowered_parts.index("barter")
                if len(parts) - barter_index != 6 or lowered_parts[barter_index + 3] != "for":
                    return TurnResult(
                        self._events(
                            "system",
                            ['Barter usage is `trade [npc] barter <give_item> <give_qty> for <get_item> <get_qty>`.'],
                        )
                    )
                try:
                    give_qty = int(parts[barter_index + 2])
                    get_qty = int(parts[barter_index + 5])
                except ValueError:
                    return TurnResult(self._events("system", ["Barter quantities must be integers."]))
                npc_query = " ".join(parts[1:barter_index]) if barter_index > 1 else None
                return self.barter_with_npc(npc_query, parts[barter_index + 1], give_qty, parts[barter_index + 4], get_qty)
            try:
                qty = int(parts[-1])
            except ValueError:
                return TurnResult(self._events("system", ["Trade quantity must be an integer."]))
            return self.trade_with_npc(" ".join(parts[1:-3]) if len(parts) > 4 else None, parts[-3], parts[-2], qty)
        if command == "share" and len(parts) >= 3:
            try:
                qty = int(parts[-1])
            except ValueError:
                return TurnResult(self._events("system", ["Share quantity must be an integer."]))
            return self.share_with_npc(" ".join(parts[1:-2]) if len(parts) > 3 else None, parts[-2], qty)
        if command == "next":
            turns = 1
            if len(parts) >= 2:
                try:
                    turns = int(parts[1])
                except ValueError:
                    return TurnResult(self._events("system", ["Next amount must be an integer."]))
            return self.advance_turn(turns)
        return TurnResult(self._events("system", ['Unknown command. Type "help" to see valid commands.']))

    def _step_turn(self) -> list[str]:
        self.turn_counter += 1
        self.world.tick += self.turn_ticks
        self.world.day = 1 + (self.world.tick // (12 * 60 * 24))
        lines: list[str] = []

        completed_production = self._resolve_pending_production()
        lines.extend(completed_production)
        self.tick_log.extend(completed_production)

        self.player.hunger = min(100.0, self.player.hunger + PLAYER_PASSIVE_HUNGER_PER_TURN)
        self.player.fatigue = min(100.0, self.player.fatigue + PLAYER_PASSIVE_FATIGUE_PER_TURN)
        lines.extend(self._advance_player_travel())
        self._advance_weather()
        self._advance_regional_summaries()
        route_events = self._advance_regional_route_events()
        lines.extend(route_events)
        self.tick_log.extend(route_events)
        transit_events = self._advance_regional_transits()
        lines.extend(transit_events)
        self.tick_log.extend(transit_events)
        shock_events = self._advance_world_shocks()
        lines.extend(shock_events)
        self.tick_log.extend(shock_events)
        spoilage_events = self._apply_spoilage()
        lines.extend(spoilage_events)
        self.tick_log.extend(spoilage_events)
        self._refresh_dynamic_rumors()
        self._decay_rumors()
        for npc in self.npcs.values():
            npc.hunger = min(100.0, npc.hunger + NPC_PASSIVE_HUNGER_PER_TURN)
            npc.fatigue = min(100.0, npc.fatigue + NPC_PASSIVE_FATIGUE_PER_TURN)
            self._refresh_beliefs_for_npc(npc)

        self._refresh_market_snapshot()
        for npc_id in sorted(self.npcs):
            npc = self.npcs[npc_id]
            if npc.travel_state.is_traveling:
                event = self._advance_npc_travel(npc)
                if event:
                    lines.append(event)
                    self.tick_log.append(event)
                continue
            context = self._build_planner_context(npc)
            npc.current_intent = self.planner.plan(context).intent
            event = self._execute_npc_intent(npc)
            if event:
                lines.append(event)
                self.tick_log.append(event)
        self._refresh_market_snapshot()
        return lines

    def _advance_regional_summaries(self) -> None:
        current_region = self.current_region()
        current_region_id = current_region.region_id if current_region is not None else None
        weather_pressure = {
            "clear": 0,
            "cool_rain": 1,
            "market_day": 0,
            "dry_wind": -1,
            "dusty_heat": -1,
            "storm_front": -2,
        }.get(self.world.weather, 0)
        route_capacity: dict[str, float] = {}
        for route in self.world.regional_routes:
            effective_capacity = max(0.2, route.seasonal_capacity - self._regional_route_pressure(route))
            route_capacity[route.from_region_id] = route_capacity.get(route.from_region_id, 0.0) + effective_capacity
            route_capacity[route.to_region_id] = route_capacity.get(route.to_region_id, 0.0) + effective_capacity

        for region in self.world.regions.values():
            if region.region_id == current_region_id:
                continue
            throughput = route_capacity.get(region.region_id, 0.0)
            drift = 1 if throughput >= 0.9 and self.turn_counter % 3 == 0 else 0
            grain_delta = weather_pressure + drift
            tool_delta = 1 if self.turn_counter % 5 == 0 and throughput >= 0.8 else 0
            fish_delta = 1 if self.world.weather in {"cool_rain", "clear"} and self.turn_counter % 4 == 0 else 0

            if "wheat" in region.stock_signals:
                region.stock_signals["wheat"] = max(0, min(24, region.stock_signals["wheat"] + grain_delta))
            if "bread" in region.stock_signals:
                bread_shift = 1 if region.stock_signals.get("wheat", 0) >= 8 and self.turn_counter % 4 == 0 else -1 if grain_delta < 0 else 0
                region.stock_signals["bread"] = max(0, min(24, region.stock_signals["bread"] + bread_shift))
            if "fish" in region.stock_signals:
                region.stock_signals["fish"] = max(0, min(18, region.stock_signals["fish"] + fish_delta))
            if "tool" in region.stock_signals:
                region.stock_signals["tool"] = max(0, min(18, region.stock_signals["tool"] + tool_delta))

    def _advance_regional_route_events(self) -> list[str]:
        events: list[str] = []
        for route in self.world.regional_routes:
            pressure = self._regional_route_pressure(route)
            event_id = self._route_delay_event_id(route.route_id)
            active_event = self._world_event(event_id)
            if pressure >= 0.32:
                summary = self._route_delay_summary(route)
                if active_event is None:
                    self.world.active_events.append(
                        WorldEvent(
                            event_id=event_id,
                            event_type="route_delay",
                            summary=summary,
                            start_tick=self.world.tick,
                            route_id=route.route_id,
                        )
                    )
                    events.append(summary)
                else:
                    active_event.summary = summary
            elif active_event is not None and pressure <= 0.14:
                self.world.active_events = [event for event in self.world.active_events if event.event_id != event_id]
                events.append(self._route_recovery_summary(route))
        return events

    def _advance_regional_transits(self) -> list[str]:
        events: list[str] = []
        active_transits: list[RegionalTransit] = []
        for transit in self.world.regional_transits:
            route = next((candidate for candidate in self.world.regional_routes if candidate.route_id == transit.route_id), None)
            if route is None:
                continue
            progress_ticks = max(1, int(round(self.turn_ticks * (1.0 - self._regional_route_pressure(route) * 0.6))))
            transit.ticks_remaining = max(0, transit.ticks_remaining - progress_ticks)
            if transit.ticks_remaining > 0:
                active_transits.append(transit)
                continue
            delivery_event = self._deliver_regional_transit(transit)
            if delivery_event is not None:
                events.append(delivery_event)
        self.world.regional_transits = active_transits
        if self.turn_counter % 10 == 0:
            events.extend(self._spawn_regional_transits())
        return events

    def _spawn_regional_transits(self) -> list[str]:
        events: list[str] = []
        active_route_ids = {transit.route_id for transit in self.world.regional_transits}
        for route in self.world.regional_routes:
            if route.route_id in active_route_ids:
                continue
            planned = self._plan_regional_transit(route)
            if planned is None:
                continue
            self.world.regional_transits.append(planned)
            if self._is_route_visible_to_player(route):
                events.append(self._regional_transit_departure_summary(planned))
        return events

    def _plan_regional_transit(self, route) -> RegionalTransit | None:
        left = self.world.regions[route.from_region_id]
        right = self.world.regions[route.to_region_id]
        best_item = None
        best_diff = 0
        source = left
        destination = right
        for item in ("bread", "wheat", "fish", "tool"):
            left_qty = left.stock_signals.get(item, 0)
            right_qty = right.stock_signals.get(item, 0)
            diff = abs(left_qty - right_qty)
            if diff <= best_diff:
                continue
            if left_qty > right_qty:
                source = left
                destination = right
            else:
                source = right
                destination = left
            best_item = item
            best_diff = diff
        if best_item is None or best_diff < 4:
            return None
        source_qty = source.stock_signals.get(best_item, 0)
        quantity = min(3, max(1, best_diff // 4))
        if source_qty - quantity < 2:
            return None
        return RegionalTransit(
            transit_id=f"transit.{route.route_id}.{best_item}.day{self.world.day}.turn{self.turn_counter}",
            route_id=route.route_id,
            from_region_id=source.region_id,
            to_region_id=destination.region_id,
            cargo_item=best_item,
            quantity=quantity,
            ticks_remaining=route.travel_ticks,
        )

    def _deliver_regional_transit(self, transit: RegionalTransit) -> str | None:
        from_region = self.world.regions.get(transit.from_region_id)
        to_region = self.world.regions.get(transit.to_region_id)
        if from_region is None or to_region is None:
            return None
        max_signal = 18 if transit.cargo_item in {"fish", "tool"} else 24
        transferable = min(transit.quantity, max(0, from_region.stock_signals.get(transit.cargo_item, 0)))
        if transferable <= 0:
            return None
        from_region.stock_signals[transit.cargo_item] = max(0, from_region.stock_signals.get(transit.cargo_item, 0) - transferable)
        to_region.stock_signals[transit.cargo_item] = min(max_signal, to_region.stock_signals.get(transit.cargo_item, 0) + transferable)
        route = next((candidate for candidate in self.world.regional_routes if candidate.route_id == transit.route_id), None)
        if route is None or not self._is_route_visible_to_player(route):
            return None
        return self._regional_transit_arrival_summary(transit)

    def _build_planner_context(self, npc: NPCState) -> PlannerContext:
        top_goals: list[str] = []
        food_item = self._best_food_for_npc(npc)
        if npc.hunger >= 70 and food_item is not None:
            top_goals.append(f"eat:{food_item}")

        critical_hunger_without_food = npc.hunger >= 80 and food_item is None

        if npc.fatigue >= 90 and not critical_hunger_without_food:
            if npc.home_location_id == npc.location_id or self._shelter_rating(npc.location_id) >= 0.65:
                top_goals.append("sleep")
            else:
                top_goals.append("rest")
        elif npc.fatigue >= 78 and not critical_hunger_without_food:
            if npc.home_location_id and npc.location_id != npc.home_location_id:
                top_goals.append(f"move:{npc.home_location_id}")
            elif npc.home_location_id == npc.location_id or self._shelter_rating(npc.location_id) >= 0.65:
                top_goals.append("sleep")
            else:
                top_goals.append("rest")
        elif npc.fatigue >= 58 and not critical_hunger_without_food:
            top_goals.append("rest")

        if npc.hunger >= 45:
            if food_item is not None:
                top_goals.append(f"eat:{food_item}")
            else:
                if not self._should_return_to_work_with_inputs(npc):
                    source = self._nearest_food_source(npc, affordable_only=True)
                    if source is not None:
                        if npc.location_id == source.location_id:
                            top_goals.append(f"trade_food:{source.npc_id}")
                        elif npc.fatigue < 82 or npc.hunger >= 72:
                            top_goals.append(f"move:{source.location_id}")
                if not top_goals or not top_goals[-1].startswith(("trade_food:", "move:")):
                    work_goal = self._food_emergency_work_goal(npc)
                    if work_goal is not None:
                        top_goals.append(work_goal)
                    else:
                        fallback_location = self._wild_food_fallback_location(npc)
                        if fallback_location == npc.location_id:
                            top_goals.append(f"work:{fallback_location}")
                        elif fallback_location is not None:
                            top_goals.append(f"move:{fallback_location}")

        rumor_target = self._rumor_share_target(npc)
        if rumor_target is not None:
            top_goals.append(f"share_rumor:{rumor_target.npc_id}")

        supply_goal = self._profession_supply_goal(npc)
        if supply_goal is not None:
            top_goals.append(supply_goal)
        elif npc.workplace_id is not None and npc.location_id != npc.workplace_id:
            top_goals.append(f"move:{npc.workplace_id}")
        else:
            top_goals.append(f"work:{npc.workplace_id or npc.location_id}")

        visible_rumors = [self.rumors[rumor_id] for rumor_id in npc.known_rumor_ids if rumor_id in self.rumors]
        return PlannerContext(
            npc=npc,
            persona=self.personas[npc.persona_id],
            top_goals=top_goals,
            salient_beliefs=self._derive_beliefs(npc),
            visible_rumors=visible_rumors,
            nearby_entity_ids=[other.npc_id for other in self._npcs_at(npc.location_id) if other.npc_id != npc.npc_id],
            allowed_intents=[intent.value for intent in IntentType],
        )

    def _execute_npc_intent(self, npc: NPCState) -> str | None:
        if npc.current_intent is None:
            return None
        intent = npc.current_intent
        if intent.intent_type is IntentType.MOVE and intent.target_location:
            next_hop = self._next_hop(npc.location_id, intent.target_location)
            if next_hop and next_hop != npc.location_id:
                blocked_reason = self._travel_block_reason(npc.location_id, next_hop, npc)
                if blocked_reason:
                    if "carrying too much" in blocked_reason:
                        return f"{npc.name} delays travel because their pack is too heavy."
                    return f"{npc.name} delays travel because the route is unsafe."
                travel_ticks = self._begin_travel(npc, next_hop)
                return f"{npc.name} sets out toward {self.world.locations[next_hop].name} ({self._travel_eta_turns(travel_ticks)} turns)."
            return None
        if intent.intent_type is IntentType.EAT and intent.target_id:
            if npc.inventory.get(intent.target_id, 0) > 0:
                self._consume_food(npc.inventory, intent.target_id, npc)
                return f"{npc.name} eats {intent.target_id}."
            return None
        if intent.intent_type is IntentType.TRADE and intent.target_id:
            source = self.npcs.get(intent.target_id)
            if source is not None:
                return self._npc_acquire_food(npc, source)
            return None
        if intent.intent_type is IntentType.SHARE_RUMOR and intent.target_id:
            target = self.npcs.get(intent.target_id)
            if target is not None:
                return self._share_rumor(npc, target)
            return None
        if intent.intent_type is IntentType.REST:
            return self._recover_npc(npc)
        if intent.intent_type is IntentType.WORK:
            return self._perform_work(npc)
        return None

    def _perform_work(self, npc: NPCState) -> str | None:
        if npc.fatigue >= 88:
            return f"{npc.name} is too worn down to work and slows to a stop."
        if npc.profession in WORK_OUTPUT:
            item, amount = self._work_output_for(npc.profession)
            amount = self._effective_work_amount(
                npc,
                base_amount=amount,
                location_id=npc.location_id,
                profession=npc.profession,
            )
            produced_amount = amount
            buffer_cap = PROFESSION_OUTPUT_BUFFER_CAPS.get((npc.profession, item))
            if buffer_cap is not None:
                available_buffer = max(0, buffer_cap - npc.inventory.get(item, 0))
                produced_amount = min(amount, available_buffer)
            if produced_amount > 0:
                self._adjust_item(npc.inventory, item, produced_amount)
            income = self._work_income(npc)
            if income > 0:
                npc.money += income
            npc.fatigue = min(100.0, npc.fatigue + 7.0)
            self._record_memory(
                npc_id=npc.npc_id,
                event_type="work",
                summary=(
                    f"Produced {produced_amount} {item} and earned {income} gold."
                    if produced_amount > 0 and income > 0
                    else f"Produced {produced_amount} {item}."
                    if produced_amount > 0
                    else f"Handled {npc.profession} demand and earned {income} gold."
                    if income > 0
                    else f"Handled {npc.profession} demand."
                ),
                importance=0.4,
            )
            tool_wear_line = self._apply_tool_wear_if_due(npc, location_id=npc.location_id, profession=npc.profession)
            if produced_amount > 0 and income > 0:
                line = f"{npc.name} works and produces {produced_amount} {item}, earning {income} gold."
            elif produced_amount > 0:
                line = f"{npc.name} works and produces {produced_amount} {item}."
            elif income > 0:
                line = f"{npc.name} keeps {npc.profession} demand moving and earns {income} gold."
            else:
                line = f"{npc.name} keeps {npc.profession} demand moving."
            if tool_wear_line:
                return f"{line} {tool_wear_line}"
            return line
        if npc.profession == "merchant":
            return self._merchant_restock(npc)
        if npc.profession == "baker":
            if npc.inventory.get("wheat", 0) <= 0:
                farmer = self.npcs["npc.anik"]
                if npc.location_id == farmer.location_id:
                    bought = self._npc_buy_specific_item(npc, farmer, "wheat", 3)
                    if bought is not None:
                        return f"{npc.name} buys wheat from {farmer.name}."
                    self._adjust_item(npc.inventory, "wheat", 2)
                    return f"{npc.name} gathers emergency wheat stores."
                destination = self._next_hop(npc.location_id, farmer.location_id)
                if destination and destination != npc.location_id:
                    travel_ticks = self._begin_travel(npc, destination)
                    return f"{npc.name} heads toward the farm for wheat ({self._travel_eta_turns(travel_ticks)} turns)."
                return None
            self._adjust_item(npc.inventory, "wheat", -1)
            npc.production_queue["bread"] = npc.production_queue.get("bread", 0) + 2
            npc.fatigue = min(100.0, npc.fatigue + 7.0)
            return f"{npc.name} starts a fresh bread batch."
        if npc.profession == "cook":
            if npc.inventory.get("fish", 0) <= 0:
                fisher = self.npcs["npc.toma"]
                if npc.location_id == fisher.location_id:
                    bought = self._npc_buy_specific_item(npc, fisher, "fish", 2)
                    if bought is not None:
                        return f"{npc.name} buys fish from {fisher.name}."
                    self._adjust_item(npc.inventory, "fish", 1)
                    return f"{npc.name} secures a small backup fish stock."
                destination = self._next_hop(npc.location_id, fisher.location_id)
                if destination and destination != npc.location_id:
                    travel_ticks = self._begin_travel(npc, destination)
                    return f"{npc.name} heads toward the riverside for fish ({self._travel_eta_turns(travel_ticks)} turns)."
                return None
            self._adjust_item(npc.inventory, "fish", -1)
            npc.production_queue["stew"] = npc.production_queue.get("stew", 0) + 1
            npc.fatigue = min(100.0, npc.fatigue + 7.0)
            return f"{npc.name} starts a pot of stew."
        income = self._work_income(npc)
        if income > 0:
            npc.money += income
            npc.fatigue = min(100.0, npc.fatigue + 6.0)
            self._record_memory(
                npc_id=npc.npc_id,
                event_type="work",
                summary=f"Completed {npc.profession} duties and earned {income} gold.",
                importance=0.35,
            )
            return f"{npc.name} completes {npc.profession} duties and earns {income} gold."
        fallback_item = self._wild_food_item_at_location(npc.location_id)
        if fallback_item is not None and npc.hunger >= 60:
            self._adjust_item(npc.inventory, fallback_item, 1)
            npc.fatigue = min(100.0, npc.fatigue + 5.0)
            return f"{npc.name} forages {fallback_item} to stay fed."
        return None

    def _npc_acquire_food(self, npc: NPCState, source: NPCState) -> str | None:
        if npc.npc_id == source.npc_id:
            return None
        food = self._best_requestable_food(source, npc)
        if food is not None:
            return self._npc_request_food(npc, source, food, 1)
        food = self._best_food_to_buy(npc, source, affordable_only=True)
        if food is None or npc.money <= 0:
            return None
        return self._npc_buy_specific_item(npc, source, food, 1)

    def _npc_buy_specific_item(self, buyer: NPCState, vendor: NPCState, item: str, qty: int) -> str | None:
        if self._sellable_quantity(vendor, item) < qty:
            return None
        price = self._price_for(vendor, item, buy_from_vendor=True)
        total = price * qty
        if buyer.money < total:
            return None
        buyer.money -= total
        vendor.money += total
        self._adjust_item(buyer.inventory, item, qty)
        self._adjust_item(vendor.inventory, item, -qty)
        self._record_memory(
            npc_id=buyer.npc_id,
            event_type="trade",
            summary=f"Bought {item} from {vendor.name}.",
            entities=[vendor.npc_id],
            importance=0.5,
        )
        return f"{buyer.name} buys {item} from {vendor.name}."

    def _npc_request_food(self, receiver: NPCState, giver: NPCState, item: str, qty: int) -> str | None:
        quantity = min(qty, self._requestable_quantity(giver, receiver, item))
        if quantity <= 0:
            return None
        self._adjust_item(receiver.inventory, item, quantity)
        self._adjust_item(giver.inventory, item, -quantity)
        self._record_memory(
            npc_id=giver.npc_id,
            event_type="exchange",
            summary=f"Gave {item} to {receiver.name}.",
            entities=[receiver.npc_id],
            importance=0.46,
        )
        self._record_memory(
            npc_id=receiver.npc_id,
            event_type="trade",
            summary=f"Received {item} from {giver.name}.",
            entities=[giver.npc_id],
            importance=0.54,
        )
        self._change_relationship(receiver, giver.npc_id, trust_delta=0.03, closeness_delta=0.02)
        self._change_relationship(giver, receiver.npc_id, trust_delta=0.01, closeness_delta=0.01)
        return f"{giver.name} shares {item} with {receiver.name}."

    def _share_rumor(self, speaker: NPCState, listener: NPCState) -> str | None:
        rumor = self._preferred_rumor_to_share(speaker, listener)
        if rumor is None:
            return None
        if not self._knows_rumor(listener.known_rumor_ids, rumor):
            listener.known_rumor_ids.append(rumor.rumor_id)
        rumor.hop_count += 1
        rumor.last_shared_tick = self.world.tick
        rumor.confidence = max(0.15, rumor.confidence - 0.03)
        self._record_memory(
            npc_id=listener.npc_id,
            event_type="heard_rumor",
            summary=f"Heard from {speaker.name}: {rumor.content}",
            entities=[speaker.npc_id],
            importance=0.7,
        )
        self._change_relationship(listener, speaker.npc_id, trust_delta=0.02, closeness_delta=0.01)
        return f"{speaker.name} shares a rumor with {listener.name}."

    def _offer_rumor_to_player(self, npc: NPCState, *, dialogue_result: DialogueResult | None, asked: bool) -> str | None:
        candidates: list[Rumor] = []
        seen_signatures: set[tuple[str | None, str, str]] = set()
        for rumor_id in dialogue_result.used_rumor_ids if dialogue_result is not None else []:
            rumor = self.rumors.get(rumor_id)
            if rumor is None:
                continue
            signature = self._rumor_signature(rumor)
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            candidates.append(rumor)
        if not candidates and dialogue_result is not None:
            for rumor in self._rumors_referenced_in_dialogue(npc, dialogue_result.text):
                signature = self._rumor_signature(rumor)
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
                candidates.append(rumor)
        if not candidates and asked:
            rumor = self._preferred_rumor_to_share_to_player(npc)
            if rumor is not None:
                candidates.append(rumor)

        learned = 0
        repeated = 0
        for rumor in candidates:
            if self._knows_rumor(self.player.known_rumor_ids, rumor):
                repeated += 1
            else:
                self.player.known_rumor_ids.append(rumor.rumor_id)
                learned += 1
            rumor.hop_count += 1
            rumor.last_shared_tick = self.world.tick
            rumor.confidence = max(0.15, rumor.confidence - 0.02)
        return self._format_player_rumor_notice(npc, asked=asked, learned=learned, repeated=repeated)

    def _format_player_rumor_notice(self, npc: NPCState, *, asked: bool, learned: int, repeated: int) -> str | None:
        if learned <= 0 and repeated <= 0:
            return None
        if learned > 0:
            return f"You note a rumor from {npc.name}."
        if asked:
            return f"{npc.name}'s answer matches notes you already have."
        return f"{npc.name}'s aside matches a rumor already in your notes."

    def _rumors_referenced_in_dialogue(self, npc: NPCState, text: str) -> list[Rumor]:
        normalized = " ".join(str(text or "").lower().split())
        if not normalized:
            return []
        matches: list[Rumor] = []
        for rumor in self._sorted_known_rumors(npc.known_rumor_ids, dedupe_by_signature=True):
            tokens = self._meaningful_rumor_tokens(rumor.content)
            if len(tokens) < 2:
                continue
            overlap = sum(1 for token in tokens if token in normalized)
            if overlap >= 2:
                matches.append(rumor)
        return matches

    def _meaningful_rumor_tokens(self, text: str) -> list[str]:
        tokens = [
            token
            for token in re.findall(r"[a-zA-Z_]+", text.lower())
            if len(token) >= 4 and token not in RUMOR_MATCH_STOPWORDS
        ]
        return tokens[:6]

    def _generate_dialogue(self, npc: NPCState, *, interaction_mode: str, player_prompt: str) -> str:
        return self._generate_dialogue_result(
            npc,
            interaction_mode=interaction_mode,
            player_prompt=player_prompt,
        ).text

    def _generate_dialogue_result(self, npc: NPCState, *, interaction_mode: str, player_prompt: str) -> DialogueResult:
        context = self._build_dialogue_context(npc, interaction_mode=interaction_mode, player_prompt=player_prompt)
        return self.dialogue_adapter.generate(context)

    def _derive_beliefs(self, npc: NPCState) -> list[Belief]:
        self._refresh_beliefs_for_npc(npc)
        return list(npc.beliefs)

    def _build_dialogue_context(self, npc: NPCState, *, interaction_mode: str, player_prompt: str) -> DialogueContext:
        related_entities = [self.player.player_id]
        salient_memories = self._retrieve_salient_memories(
            npc.npc_id,
            related_entity_ids=related_entities,
            location_id=npc.location_id,
            limit=4,
        )
        visible_rumors = self._sorted_known_rumors(npc.known_rumor_ids, dedupe_by_signature=True)
        return DialogueContext(
            npc=npc,
            persona=self.personas[npc.persona_id],
            player=self.player,
            world=self.world,
            location=self.world.locations[npc.location_id],
            interaction_mode=interaction_mode,
            player_prompt=player_prompt,
            system_prompt=self.dialogue_system_prompt,
            relationship_score=self._relationship_score(npc, self.player.player_id),
            salient_beliefs=self._derive_beliefs(npc),
            salient_memories=salient_memories,
            visible_rumors=visible_rumors,
        )

    def _retrieve_salient_memories(
        self,
        actor_id: str,
        *,
        related_entity_ids: list[str] | None = None,
        location_id: str | None = None,
        limit: int = 4,
    ) -> list[EpisodicMemory]:
        memories = self.memories.get(actor_id, [])
        if not memories:
            return []
        related_entity_ids = related_entity_ids or []
        scored: list[tuple[float, EpisodicMemory]] = []
        for memory in memories:
            age = max(0, self.world.tick - memory.timestamp_tick)
            recency = 1.0 / (1.0 + (age / 96.0))
            relevance = 0.0
            if location_id is not None and memory.location_id == location_id:
                relevance += 0.25
            if any(entity_id in memory.entities for entity_id in related_entity_ids):
                relevance += 0.45
            if memory.event_type in {"trade", "heard_rumor", "npc_talk", "player_talk"}:
                relevance += 0.15
            score = recency + memory.importance + relevance
            scored.append((score, memory))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [memory for _, memory in scored[:limit]]

    def _refresh_beliefs_for_npc(self, npc: NPCState) -> None:
        belief_map: dict[tuple[str, str], Belief] = {}
        for belief in npc.beliefs:
            belief_map[(belief.subject_id, belief.predicate)] = belief

        if npc.hunger >= 60:
            belief_map[("self", "needs_food_soon")] = Belief(
                subject_id="self",
                predicate="needs_food_soon",
                confidence=min(0.95, npc.hunger / 100.0),
                evidence_memory_ids=[],
            )
        if self.world.market.scarcity_index >= 1.0:
            belief_map[("market", "food_is_tight")] = Belief(
                subject_id="market",
                predicate="food_is_tight",
                confidence=min(0.9, 0.4 + self.world.market.scarcity_index / 3.0),
                evidence_memory_ids=[],
            )
        if "rumor.shortage.wheat" in npc.known_rumor_ids:
            belief_map[("farm", "expects_grain_shortage")] = Belief(
                subject_id="farm",
                predicate="expects_grain_shortage",
                confidence=0.72,
                evidence_memory_ids=[],
            )

        player_memories = self._retrieve_salient_memories(
            npc.npc_id,
            related_entity_ids=[self.player.player_id],
            location_id=npc.location_id,
            limit=3,
        )
        if len(player_memories) >= 2:
            belief_map[("player", "is_familiar")] = Belief(
                subject_id="player",
                predicate="is_familiar",
                confidence=min(0.85, 0.35 + len(player_memories) * 0.15),
                evidence_memory_ids=[memory.memory_id for memory in player_memories[:2]],
            )

        npc.beliefs = sorted(belief_map.values(), key=lambda belief: (belief.subject_id, belief.predicate))

    def _refresh_dynamic_rumors(self) -> None:
        phase_index = self.turn_counter // 8
        if self.turn_counter % 8 == 0:
            self._spawn_weather_rumor(phase_index)
        if self.turn_counter % 10 == 0:
            self._spawn_market_rumor()
        if self.turn_counter % 6 == 0:
            self._spawn_supply_rumor()
            self._spawn_route_delay_rumor()
        if self.turn_counter % 12 == 0:
            self._spawn_regional_summary_rumor()

    def _spawn_weather_rumor(self, phase_index: int) -> None:
        weather_templates = {
            "cool_rain": (
                "npc.anik",
                RumorCategory.EVENT,
                0.63,
                "Anik says the cool rain may steady the fields if it lingers into tomorrow.",
            ),
            "dry_wind": (
                "npc.anik",
                RumorCategory.SHORTAGE,
                0.77,
                "People at the farm say the dry wind is scraping another layer of moisture out of the soil.",
            ),
            "market_day": (
                "npc.mara",
                RumorCategory.ECONOMY,
                0.61,
                "Mara expects sharper bargaining today because market-day crowds always push prices around.",
            ),
            "storm_front": (
                "npc.toma",
                RumorCategory.DANGER,
                0.72,
                "Toma swears a storm front is turning the riverside meaner by the hour.",
            ),
            "dusty_heat": (
                "npc.hobb",
                RumorCategory.EVENT,
                0.66,
                "Hobb has started talking about dusty heat settling into every oven and store room in town.",
            ),
            "clear": (
                "npc.serin",
                RumorCategory.SOCIAL,
                0.52,
                "Serin says the village feels briefly calmer whenever the sky clears and people breathe again.",
            ),
        }
        template = weather_templates.get(self.world.weather)
        if template is None:
            return
        origin_npc_id, category, value, content = template
        rumor_id = f"rumor.dynamic.weather.{self.world.weather}.{phase_index}"
        self._ensure_rumor(
            rumor_id=rumor_id,
            origin_npc_id=origin_npc_id,
            subject_id=self.npcs[origin_npc_id].location_id,
            content=content,
            category=category,
            confidence=0.74,
            value=value,
            holders=[origin_npc_id, "npc.neri"],
        )

    def _spawn_market_rumor(self) -> None:
        scarcity = self.world.market.scarcity_index
        if scarcity < 0.5:
            return
        severity = "tight" if scarcity < 1.2 else "strained"
        rumor_id = f"rumor.dynamic.market.{severity}.day{self.world.day}.slot{self.turn_counter // 10}"
        content = (
            "Mara says traders are quietly tightening food prices because the market feels unusually thin."
            if severity == "tight"
            else "Mara says the square is straining under thin food stocks and impatient buyers."
        )
        self._ensure_rumor(
            rumor_id=rumor_id,
            origin_npc_id="npc.mara",
            subject_id="square",
            content=content,
            category=RumorCategory.ECONOMY,
            confidence=min(0.88, 0.58 + scarcity * 0.16),
            value=min(0.92, 0.55 + scarcity * 0.18),
            holders=["npc.mara", "npc.neri", "npc.iva"],
        )

    def _spawn_supply_rumor(self) -> None:
        hobb = self.npcs["npc.hobb"]
        if hobb.inventory.get("wheat", 0) <= 1:
            rumor_id = f"rumor.dynamic.bakery.wheat.day{self.world.day}.slot{self.turn_counter // 6}"
            self._ensure_rumor(
                rumor_id=rumor_id,
                origin_npc_id="npc.hobb",
                subject_id="bakery",
                content="Hobb is running low on wheat and may need to slow the bakery's next batch.",
                category=RumorCategory.SHORTAGE,
                confidence=0.79,
                value=0.71,
                holders=["npc.hobb", "npc.mara", "npc.neri"],
            )
        toma = self.npcs["npc.toma"]
        if toma.inventory.get("fish", 0) <= 1:
            rumor_id = f"rumor.dynamic.riverside.fish.day{self.world.day}.slot{self.turn_counter // 6}"
            self._ensure_rumor(
                rumor_id=rumor_id,
                origin_npc_id="npc.toma",
                subject_id="riverside",
                content="Toma says the fish baskets are coming in lighter than usual along the riverside.",
                category=RumorCategory.SHORTAGE,
                confidence=0.76,
                value=0.66,
                holders=["npc.toma", "npc.bina", "npc.neri"],
            )

    def _spawn_route_delay_rumor(self) -> None:
        active_routes = [route for route in self.world.regional_routes if self._route_delay_event(route.route_id) is not None]
        if not active_routes:
            return
        route = sorted(active_routes, key=self._regional_route_pressure, reverse=True)[0]
        destination = self.world.regions[route.to_region_id]
        weather_label = self.world.weather.replace("_", " ")
        self._ensure_rumor(
            rumor_id=f"rumor.dynamic.route.delay.{route.route_id}.day{self.world.day}.slot{self.turn_counter // 6}",
            origin_npc_id="npc.mara",
            subject_id=route.route_id,
            content=f"Mara says the road toward {destination.name} is dragging under the {weather_label}, so outside grain may arrive late.",
            category=RumorCategory.ECONOMY,
            confidence=min(0.9, 0.6 + self._regional_route_pressure(route) * 0.25),
            value=min(0.88, 0.58 + self._regional_route_pressure(route) * 0.2),
            holders=["npc.mara", "npc.neri", "npc.iva"],
        )

    def _spawn_regional_summary_rumor(self) -> None:
        current_region = self.current_region()
        current_region_id = current_region.region_id if current_region is not None else None
        candidates: list[tuple[float, Any]] = []
        for region in self.world.regions.values():
            if region.region_id == current_region_id:
                continue
            food_total = sum(region.stock_signals.get(item, 0) for item in ("bread", "wheat", "fish"))
            route = self._regional_route_between(current_region_id, region.region_id) if current_region_id is not None else None
            route_pressure = self._regional_route_pressure(route) if route is not None else 0.0
            signal_score = max(0.0, 14 - food_total) + route_pressure * 8.0
            if signal_score > 2.0:
                candidates.append((signal_score, region))
        if not candidates:
            return
        _, region = sorted(candidates, key=lambda item: item[0], reverse=True)[0]
        weakest_item = min(("bread", "wheat", "fish"), key=lambda item: region.stock_signals.get(item, 0))
        item_label = {"bread": "bread", "wheat": "grain", "fish": "fish"}[weakest_item]
        self._ensure_rumor(
            rumor_id=f"rumor.dynamic.region.{region.region_id}.day{self.world.day}.slot{self.turn_counter // 12}",
            origin_npc_id="npc.neri",
            subject_id=region.region_id,
            content=f"Neri hears that {region.name} is bargaining hard for food because {item_label} stocks look thin beyond the road.",
            category=RumorCategory.SHORTAGE,
            confidence=0.72,
            value=0.67,
            holders=["npc.neri", "npc.mara", "npc.iva"],
        )

    def _ensure_rumor(
        self,
        *,
        rumor_id: str,
        origin_npc_id: str,
        subject_id: str,
        content: str,
        category: RumorCategory,
        confidence: float,
        value: float,
        holders: list[str],
    ) -> None:
        existing = self.rumors.get(rumor_id) or self._find_matching_rumor(
            origin_npc_id=origin_npc_id,
            subject_id=subject_id,
            content=content,
            category=category,
        )
        if existing is not None:
            existing.confidence = max(existing.confidence, confidence)
            existing.value = max(existing.value, value)
            existing.last_shared_tick = self.world.tick
            for holder_id in holders:
                holder = self.npcs.get(holder_id)
                if holder is not None and not self._knows_rumor(holder.known_rumor_ids, existing):
                    holder.known_rumor_ids.append(existing.rumor_id)
            return
        rumor = Rumor(
            rumor_id=rumor_id,
            origin_npc_id=origin_npc_id,
            subject_id=subject_id,
            content=content,
            category=category,
            confidence=confidence,
            value=value,
            distortion=0.0,
            hop_count=0,
            created_tick=self.world.tick,
            last_shared_tick=self.world.tick,
        )
        self.rumors[rumor_id] = rumor
        for holder_id in holders:
            holder = self.npcs.get(holder_id)
            if holder is not None and rumor_id not in holder.known_rumor_ids:
                holder.known_rumor_ids.append(rumor_id)

    def _sorted_known_rumors(self, rumor_ids: Iterable[str], *, dedupe_by_signature: bool = False) -> list[Rumor]:
        available = [self.rumors[rumor_id] for rumor_id in rumor_ids if rumor_id in self.rumors]
        if dedupe_by_signature:
            available = list(self._dedupe_rumors(available).values())
        return sorted(available, key=self._rumor_sort_key, reverse=True)

    def _rumor_sort_key(self, rumor: Rumor) -> tuple[float, int, float, int]:
        return (rumor.value, rumor.created_tick, rumor.confidence, -rumor.hop_count)

    def _advance_weather(self) -> None:
        if self.turn_counter % 8 != 0:
            return
        cycle = ("clear", "cool_rain", "dry_wind", "market_day", "storm_front", "clear", "dusty_heat")
        if self.world.market.scarcity_index >= 1.4:
            self.world.weather = "dry_wind"
        else:
            self.world.weather = cycle[(self.turn_counter // 8) % len(cycle)]

    def _advance_world_shocks(self) -> list[str]:
        events: list[str] = []
        delta = FIELD_STRESS_WEATHER_DELTA.get(self.world.weather, 0.0)
        self.world.field_stress = max(0.0, min(1.0, round(self.world.field_stress + delta, 3)))

        active_shortfall = self._world_event(HARVEST_SHORTFALL_EVENT_ID)
        if self.world.field_stress >= 0.55:
            summary = "The south field is slipping into a harvest shortfall after repeated drying weather."
            if active_shortfall is None:
                self.world.active_events.append(
                    WorldEvent(
                        event_id=HARVEST_SHORTFALL_EVENT_ID,
                        event_type="harvest_shortfall",
                        summary=summary,
                        start_tick=self.world.tick,
                        region_id="region.greenfall",
                        location_id="farm",
                    )
                )
                events.append(summary)
                self._ensure_rumor(
                    rumor_id=f"rumor.dynamic.shock.harvest_shortfall.day{self.world.day}.slot{self.turn_counter // 4}",
                    origin_npc_id="npc.anik",
                    subject_id="farm",
                    content="Anik says the south field is slipping into a real harvest shortfall after too many drying days.",
                    category=RumorCategory.SHORTAGE,
                    confidence=min(0.92, 0.62 + self.world.field_stress * 0.22),
                    value=min(0.94, 0.6 + self.world.field_stress * 0.2),
                    holders=["npc.anik", "npc.mara", "npc.neri"],
                )
            else:
                active_shortfall.summary = summary
        elif active_shortfall is not None and self.world.field_stress <= 0.24:
            self.world.active_events = [
                event for event in self.world.active_events if event.event_id != HARVEST_SHORTFALL_EVENT_ID
            ]
            recovery_summary = "Cool moisture is easing the south field back toward a steadier yield."
            events.append(recovery_summary)
            self._ensure_rumor(
                rumor_id=f"rumor.dynamic.shock.harvest_recovery.day{self.world.day}.slot{self.turn_counter // 4}",
                origin_npc_id="npc.anik",
                subject_id="farm",
                content="Anik says the south field is drinking again and the next yield may recover if the rain holds.",
                category=RumorCategory.EVENT,
                confidence=0.71,
                value=0.62,
                holders=["npc.anik", "npc.serin", "npc.neri"],
            )
        return events

    def _world_event(self, event_id: str) -> WorldEvent | None:
        for event in self.world.active_events:
            if event.event_id == event_id:
                return event
        return None

    def _visible_world_events_for_player(self) -> list[WorldEvent]:
        current_region = self.current_region()
        current_region_id = current_region.region_id if current_region is not None else None
        visible: list[WorldEvent] = []
        for event in self.world.active_events:
            if event.route_id is not None:
                route = next((candidate for candidate in self.world.regional_routes if candidate.route_id == event.route_id), None)
                if route is not None and self._is_route_visible_to_player(route):
                    visible.append(event)
                continue
            if event.region_id is not None and event.region_id == current_region_id:
                visible.append(event)
                continue
            if event.location_id is not None:
                location = self.world.locations.get(event.location_id)
                if location is not None and location.region_id == current_region_id:
                    visible.append(event)
                continue
            if event.region_id is None and event.route_id is None and event.location_id is None:
                visible.append(event)
        return visible

    def _route_delay_event_id(self, route_id: str) -> str:
        return f"{ROUTE_DELAY_EVENT_PREFIX}{route_id}.delay"

    def _route_delay_event(self, route_id: str) -> WorldEvent | None:
        return self._world_event(self._route_delay_event_id(route_id))

    def _visible_route_delay_event_for_player(self, route_id: str) -> WorldEvent | None:
        for event in self._visible_world_events_for_player():
            if event.route_id == route_id and event.event_type == "route_delay":
                return event
        return None

    def _is_route_visible_to_player(self, route) -> bool:
        if self.player.travel_state.is_traveling and self.player.travel_state.route_id == route.route_id:
            return True
        current_region = self.current_region()
        current_region_id = current_region.region_id if current_region is not None else None
        return current_region_id in {route.from_region_id, route.to_region_id}

    def _regional_route_pressure(self, route) -> float:
        weather_pressure = ROUTE_WEATHER_PRESSURE.get(self.world.weather, 0.0)
        from_region = self.world.regions[route.from_region_id]
        to_region = self.world.regions[route.to_region_id]
        endpoint_risk = max(from_region.risk_level, to_region.risk_level) * 0.18
        return min(1.0, route.weather_sensitivity * weather_pressure + route.cargo_risk * 0.35 + endpoint_risk)

    def _route_delay_summary(self, route) -> str:
        destination = self.world.regions[route.to_region_id].name
        weather_label = self.world.weather.replace("_", " ")
        return f"The road toward {destination} is slowing under the {weather_label}, and caravans are arriving late."

    def _route_recovery_summary(self, route) -> str:
        destination = self.world.regions[route.to_region_id].name
        return f"The road toward {destination} is moving more cleanly again."

    def _regional_transit_departure_summary(self, transit: RegionalTransit) -> str:
        source = self.world.regions[transit.from_region_id].name
        destination = self.world.regions[transit.to_region_id].name
        return f"A small caravan leaves {source} for {destination} carrying {transit.cargo_item} x{transit.quantity}."

    def _regional_transit_arrival_summary(self, transit: RegionalTransit) -> str:
        destination = self.world.regions[transit.to_region_id].name
        return f"A caravan reaches {destination} with {transit.cargo_item} x{transit.quantity}."

    def _farm_yield_amount(self) -> int:
        amount = 2
        if self.world.weather in {"cool_rain", "market_day"}:
            amount += 1
        elif self.world.weather in {"dry_wind", "dusty_heat"}:
            amount = max(1, amount - 1)
        if self.world.field_stress >= 0.55:
            amount = max(1, amount - 1)
        return amount

    def _work_output_for(self, profession: str) -> tuple[str, int]:
        item, amount = WORK_OUTPUT[profession]
        if profession == "farmer":
            amount = self._farm_yield_amount()
        if profession == "fisher" and self.world.weather == "storm_front":
            amount = max(1, amount - 1)
        return item, amount

    def _merchant_restock(self, npc: NPCState) -> str | None:
        stocked_food = sum(npc.inventory.get(item, 0) for item in ("bread", "stew", "fish"))
        if stocked_food >= 5:
            return None
        for supplier in self._merchant_suppliers():
            if supplier.location_id != npc.location_id:
                continue
            item = self._best_food_in_inventory(supplier.inventory)
            if item is None:
                continue
            result = self._npc_buy_specific_item(npc, supplier, item, 2)
            if result is not None:
                return result
        return None

    def _profession_supply_goal(self, npc: NPCState) -> str | None:
        if npc.profession == "baker" and npc.inventory.get("wheat", 0) <= 0:
            supplier = self.npcs["npc.anik"]
            if npc.location_id == supplier.location_id:
                return f"work:{npc.location_id}"
            return f"move:{supplier.location_id}"
        if npc.profession == "cook" and npc.inventory.get("fish", 0) <= 0:
            supplier = self.npcs["npc.toma"]
            if npc.location_id == supplier.location_id:
                return f"work:{npc.location_id}"
            return f"move:{supplier.location_id}"
        return None

    def _merchant_suppliers(self) -> list[NPCState]:
        suppliers = [self.npcs["npc.hobb"], self.npcs["npc.bina"], self.npcs["npc.toma"]]
        return [supplier for supplier in suppliers if self._best_food_in_inventory(supplier.inventory) is not None]

    def _food_emergency_work_goal(self, npc: NPCState) -> str | None:
        if npc.profession in {"farmer", "fisher"} and npc.workplace_id is not None:
            if npc.location_id != npc.workplace_id:
                return f"move:{npc.workplace_id}"
            return f"work:{npc.workplace_id}"
        if npc.profession == "baker" and npc.inventory.get("wheat", 0) > 0 and npc.workplace_id is not None:
            if npc.location_id != npc.workplace_id:
                return f"move:{npc.workplace_id}"
            return f"work:{npc.workplace_id}"
        if npc.profession == "cook" and npc.inventory.get("fish", 0) > 0 and npc.workplace_id is not None:
            if npc.location_id != npc.workplace_id:
                return f"move:{npc.workplace_id}"
            return f"work:{npc.workplace_id}"
        return None

    def _should_return_to_work_with_inputs(self, npc: NPCState) -> bool:
        if npc.workplace_id is None or npc.location_id == npc.workplace_id:
            return False
        if npc.profession == "baker" and npc.inventory.get("wheat", 0) >= 2 and npc.hunger < 82:
            return True
        if npc.profession == "cook" and npc.inventory.get("fish", 0) >= 1 and npc.hunger < 82:
            return True
        return False

    def _wild_food_fallback_location(self, npc: NPCState) -> str | None:
        for location_id in (npc.location_id, "farm", "riverside"):
            if self._wild_food_item_at_location(location_id) is not None:
                return location_id
        return None

    def _wild_food_item_at_location(self, location_id: str) -> str | None:
        location = self.world.locations.get(location_id)
        if location is None:
            return None
        if location.kind == "resource" and location.location_id == "farm":
            return "wheat"
        if location.kind == "resource" and location.location_id == "riverside":
            return "fish"
        return None

    def _rumor_share_target(self, npc: NPCState) -> NPCState | None:
        if npc.hunger >= 35 or npc.fatigue >= 55:
            return None
        if not npc.known_rumor_ids:
            return None
        nearby = [other for other in self._npcs_at(npc.location_id) if other.npc_id != npc.npc_id]
        if not nearby:
            return None
        nearby.sort(key=lambda other: self._relationship_score(npc, other.npc_id), reverse=True)
        for other in nearby:
            if self._preferred_rumor_to_share(npc, other) is not None:
                return other
        return None

    def _preferred_rumor_to_share(self, speaker: NPCState, listener: NPCState) -> Rumor | None:
        known_signatures = self._known_rumor_signatures(listener.known_rumor_ids)
        unknown = [
            rumor
            for rumor in self._sorted_known_rumors(speaker.known_rumor_ids, dedupe_by_signature=True)
            if self._rumor_signature(rumor) not in known_signatures
        ]
        return unknown[0] if unknown else None

    def _preferred_rumor_to_share_to_player(self, speaker: NPCState) -> Rumor | None:
        ranked = self._sorted_known_rumors(speaker.known_rumor_ids, dedupe_by_signature=True)
        known_signatures = self._known_rumor_signatures(self.player.known_rumor_ids)
        unknown = [rumor for rumor in ranked if self._rumor_signature(rumor) not in known_signatures]
        if unknown:
            return unknown[0]
        return ranked[0] if ranked else None

    def _nearest_food_source(self, npc: NPCState, *, affordable_only: bool = False) -> NPCState | None:
        candidates: list[tuple[int, int, int, float, NPCState]] = []
        for other in self.npcs.values():
            if other.npc_id == npc.npc_id or other.travel_state.is_traveling:
                continue
            request_food = self._best_requestable_food(other, npc)
            if request_food is not None:
                candidates.append(
                    (self._path_length(npc.location_id, other.location_id), 0, 0, -CONSUMPTION_VALUE[request_food], other)
                )
            if other.is_vendor:
                buy_food = self._best_food_to_buy(npc, other, affordable_only=affordable_only)
                if buy_food is not None:
                    price = self._price_for(other, buy_food, buy_from_vendor=True)
                    candidates.append(
                        (self._path_length(npc.location_id, other.location_id), 1, price, -CONSUMPTION_VALUE[buy_food], other)
                    )
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4].npc_id))
        return candidates[0][4]

    def _best_requestable_food(self, giver: NPCState, receiver: NPCState | PlayerState) -> str | None:
        best_item: str | None = None
        best_score = -1.0
        for item in FOOD_ITEMS:
            if self._requestable_quantity(giver, receiver, item) <= 0:
                continue
            score = CONSUMPTION_VALUE[item]
            if score > best_score:
                best_item = item
                best_score = score
        return best_item

    def _best_food_to_buy(self, buyer: NPCState, vendor: NPCState, *, affordable_only: bool) -> str | None:
        best_item: str | None = None
        best_score: tuple[float, int] | None = None
        for item in FOOD_ITEMS:
            if self._sellable_quantity(vendor, item) <= 0:
                continue
            price = self._price_for(vendor, item, buy_from_vendor=True)
            if affordable_only and buyer.money < price:
                continue
            score = (CONSUMPTION_VALUE[item], -price)
            if best_score is None or score > best_score:
                best_item = item
                best_score = score
        return best_item

    def _best_food_in_inventory(self, inventory: dict[str, int]) -> str | None:
        best = None
        best_value = -1.0
        for item in FOOD_ITEMS:
            if inventory.get(item, 0) > 0 and CONSUMPTION_VALUE[item] > best_value:
                best = item
                best_value = CONSUMPTION_VALUE[item]
        return best

    def _best_food_for_npc(self, npc: NPCState) -> str | None:
        best = self._best_food_in_inventory(npc.inventory)
        threshold = PROFESSION_INPUT_EMERGENCY_EAT_HUNGER.get((npc.profession, best or ""))
        if threshold is not None and npc.hunger < threshold:
            return None
        return best

    def _work_income(self, npc: NPCState) -> int:
        return WORK_WAGES.get(npc.profession, 0)

    def _consume_food(self, inventory: dict[str, int], item: str, actor: NPCState | PlayerState) -> None:
        self._adjust_item(inventory, item, -1)
        actor.hunger = max(0.0, actor.hunger - CONSUMPTION_VALUE[item])

    def _apply_storage_pressure_to_gain(
        self,
        actor: NPCState | PlayerState,
        item: str,
        amount: int,
    ) -> tuple[int, int]:
        if amount <= 0:
            return 0, 0
        item_weight = ITEM_WEIGHTS.get(item, 1.0)
        if item_weight <= 0:
            return amount, 0
        max_safe_weight = actor.carry_capacity * 0.95
        remaining_weight = max(0.0, max_safe_weight - actor.carried_weight)
        keepable = int(remaining_weight // item_weight)
        kept = max(0, min(amount, keepable))
        lost = max(0, amount - kept)
        return kept, lost

    def _effective_work_amount(
        self,
        actor: NPCState | PlayerState,
        *,
        base_amount: int,
        location_id: str,
        profession: str | None = None,
    ) -> int:
        if isinstance(actor, NPCState):
            return base_amount
        if self._needs_tool_for_work(location_id=location_id, profession=profession) and actor.inventory.get("tool", 0) <= 0:
            return max(1, base_amount - 1)
        return base_amount

    def _needs_tool_for_work(self, *, location_id: str, profession: str | None = None) -> bool:
        if location_id in TOOL_RELEVANT_LOCATIONS:
            return True
        if profession in TOOL_RELEVANT_PROFESSIONS:
            return True
        return False

    def _apply_tool_wear_if_due(
        self,
        actor: NPCState | PlayerState,
        *,
        location_id: str,
        profession: str | None = None,
    ) -> str | None:
        if isinstance(actor, NPCState):
            return None
        if not self._needs_tool_for_work(location_id=location_id, profession=profession):
            return None
        if actor.inventory.get("tool", 0) <= 0:
            return None
        actor_id = self._actor_identifier(actor)
        completed_work_cycles = sum(1 for memory in self.memories[actor_id] if memory.event_type == "work")
        if completed_work_cycles <= 0 or completed_work_cycles % TOOL_WEAR_INTERVAL != 0:
            return None
        self._adjust_item(actor.inventory, "tool", -1)
        if isinstance(actor, NPCState):
            return f"{actor.name}'s worn tool finally gives out."
        return "One of your worn tools finally gives out."

    def _apply_spoilage(self) -> list[str]:
        events: list[str] = []
        for item, market_state in self.world.market.items.items():
            spoilage_ticks = market_state.spoilage_ticks or DEFAULT_SPOILAGE_TICKS.get(item)
            if spoilage_ticks is None or spoilage_ticks <= 0:
                continue
            if self.world.tick % spoilage_ticks != 0:
                continue
            if self.player.inventory.get(item, 0) > self._reserve_floor(self.player, item) + 1:
                self._adjust_item(self.player.inventory, item, -1)
                events.append(f"1 {item} spoils in your pack.")
        return events

    def _resolve_pending_production(self) -> list[str]:
        lines: list[str] = []
        for npc in self.npcs.values():
            if not npc.production_queue:
                continue
            completed = [f"{item} x{qty}" for item, qty in npc.production_queue.items() if qty > 0]
            if not completed:
                npc.production_queue.clear()
                continue
            for item, qty in list(npc.production_queue.items()):
                if qty <= 0:
                    continue
                self._adjust_item(npc.inventory, item, qty)
            npc.production_queue.clear()
            lines.append(f"{npc.name} finishes {', '.join(completed)}.")
        return lines

    def _refresh_market_snapshot(self) -> None:
        totals = {item: 0 for item in ITEM_VALUES}
        for npc in self.npcs.values():
            for item, qty in npc.inventory.items():
                totals[item] = totals.get(item, 0) + qty
        for item, qty in self.player.inventory.items():
            totals[item] = totals.get(item, 0) + qty
        regional_support = self._regional_market_support(totals)
        for item, state in self.world.market.items.items():
            effective_stock = max(0, totals.get(item, 0) + regional_support.get(item, 0))
            state.stock = effective_stock
            scarcity = max(0, 10 - state.stock)
            state.current_price = max(state.base_price, state.base_price + scarcity // 2)
        self.world.market.scarcity_index = max(
            0.0,
            sum(max(0, 6 - self.world.market.items[item].stock) for item in ("bread", "stew", "fish")) / 10.0,
        )

    def _regional_market_support(self, local_totals: dict[str, int]) -> dict[str, int]:
        support = {item: 0 for item in self.world.market.items}
        anchor_region_id = self._market_anchor_region_id()
        if anchor_region_id is None:
            return support

        anchor_region = self.world.regions.get(anchor_region_id)
        if anchor_region is None:
            return support

        for item in support:
            signal = anchor_region.stock_signals.get(item, 0)
            deficit = max(0, signal - local_totals.get(item, 0))
            factor = LOCAL_REGION_MARKET_SUPPORT_FACTORS.get(item, 0.0)
            cap = MARKET_SUPPORT_CAPS.get(item, 0)
            support[item] += min(cap, int(round(deficit * factor)))

        for route in self.world.regional_routes:
            if anchor_region_id not in {route.from_region_id, route.to_region_id}:
                continue
            remote_region_id = route.to_region_id if route.from_region_id == anchor_region_id else route.from_region_id
            remote_region = self.world.regions.get(remote_region_id)
            if remote_region is None:
                continue
            throughput = max(0.0, min(1.0, route.seasonal_capacity - self._regional_route_pressure(route)))
            if throughput <= 0.0:
                continue
            for item in support:
                signal = remote_region.stock_signals.get(item, 0)
                if signal <= 0:
                    continue
                factor = REMOTE_REGION_MARKET_SUPPORT_FACTORS.get(item, 0.0)
                if factor <= 0.0:
                    continue
                cap = MARKET_SUPPORT_CAPS.get(item, 0)
                support[item] = min(cap, support[item] + int(round(signal * throughput * factor)))
        return support

    def _market_anchor_region_id(self) -> str | None:
        region_counts: dict[str, int] = defaultdict(int)
        for npc in self.npcs.values():
            location = self.world.locations.get(npc.location_id)
            if location is None:
                continue
            region_counts[location.region_id] += 1
        if not region_counts:
            current_region = self.current_region()
            if current_region is not None:
                return current_region.region_id
            return next(iter(self.world.regions), None)
        return sorted(region_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]

    def _price_for(self, vendor: NPCState, item: str, *, buy_from_vendor: bool) -> int:
        base = self.world.market.items.get(item)
        base_price = base.current_price if base is not None else ITEM_VALUES[item]
        persona = self.personas[vendor.persona_id]
        modifier = 1.0 + max(0.0, persona.trade_bias) * 0.25 if buy_from_vendor else 0.55 + max(0.0, persona.trade_bias) * 0.1
        return max(1, round(base_price * modifier))

    def _actor_identifier(self, actor: NPCState | PlayerState) -> str:
        return actor.npc_id if isinstance(actor, NPCState) else actor.player_id

    def _reserve_floor(self, actor: NPCState | PlayerState, item: str) -> int:
        reserve = 0
        stock = actor.inventory.get(item, 0)
        if stock <= 0:
            return 0
        if item in FOOD_ITEMS:
            other_food = sum(actor.inventory.get(food, 0) for food in FOOD_ITEMS if food != item)
            meals_to_keep = 2 if actor.hunger >= 45 else 1
            reserve = max(reserve, max(0, meals_to_keep - other_food))
        if isinstance(actor, NPCState):
            if item == "wheat" and actor.profession in {"baker", "farmer"}:
                reserve = max(reserve, 2)
            if item == "tool" and actor.profession == "smith":
                reserve = max(reserve, 1)
            reserve = max(reserve, PROFESSION_ITEM_RESERVE_FLOORS.get((actor.profession, item), 0))
        return min(stock, reserve)

    def _sellable_quantity(self, seller: NPCState | PlayerState, item: str) -> int:
        stock = seller.inventory.get(item, 0)
        if stock <= 0:
            return 0
        return max(0, stock - self._reserve_floor(seller, item))

    def _giftable_quantity(self, giver: NPCState | PlayerState, item: str) -> int:
        return self._sellable_quantity(giver, item)

    def _exchange_value(self, item: str, qty: int) -> int:
        market_item = self.world.market.items.get(item)
        unit_value = market_item.current_price if market_item is not None else ITEM_VALUES[item]
        return max(1, unit_value * qty)

    def _barter_required_value(self, npc: NPCState, *, offered_item: str, requested_item: str, requested_value: int) -> float:
        relationship = max(0.0, self._relationship_score(npc, self.player.player_id))
        discount = min(0.18, relationship * 0.12)
        urgency_discount = 0.0
        if offered_item in FOOD_ITEMS and npc.hunger >= 55:
            urgency_discount += 0.08
        if offered_item == "wheat" and npc.profession == "baker":
            urgency_discount += 0.12
        if offered_item == "fish" and npc.profession == "cook":
            urgency_discount += 0.12
        if requested_item in FOOD_ITEMS and npc.hunger >= 45:
            urgency_discount = max(0.0, urgency_discount - 0.05)
        return max(1.0, requested_value * max(0.7, 1.0 - discount - urgency_discount))

    def _requestable_quantity(self, giver: NPCState, receiver: NPCState | PlayerState, item: str) -> int:
        giftable = self._giftable_quantity(giver, item)
        if giftable <= 0:
            return 0
        if self._recent_request_buffer_active(giver, receiver, item):
            return 0
        relationship = self._relationship_score(giver, self._actor_identifier(receiver))
        urgency = 0.0
        if item in FOOD_ITEMS:
            if receiver.hunger >= 75:
                urgency += 0.45
            elif receiver.hunger >= 55:
                urgency += 0.28
            if sum(receiver.inventory.get(food, 0) for food in FOOD_ITEMS) == 0:
                urgency += 0.12
        if isinstance(receiver, NPCState):
            if item == "wheat" and receiver.profession == "baker":
                urgency += 0.24
            if item == "fish" and receiver.profession == "cook":
                urgency += 0.24
        if giver.profession == "priest":
            urgency += 0.18
        willingness = relationship + urgency
        threshold = 0.18 if item in FOOD_ITEMS else 0.42
        if willingness < threshold:
            return 0
        request_cap = 1
        if isinstance(receiver, NPCState) and ((item == "wheat" and receiver.profession == "baker") or (item == "fish" and receiver.profession == "cook")):
            request_cap += 2
        if willingness >= threshold + 0.28:
            request_cap += 1
        if willingness >= threshold + 0.62:
            request_cap += 1
        return min(giftable, request_cap)

    def _recent_request_buffer_active(self, giver: NPCState, receiver: NPCState | PlayerState, item: str) -> bool:
        if item not in FOOD_ITEMS:
            return False
        if receiver.hunger >= RECENT_REQUEST_BUFFER_EMERGENCY_HUNGER:
            return False
        receiver_id = self._actor_identifier(receiver)
        cutoff_tick = self.world.tick - RECENT_REQUEST_BUFFER_TICKS
        for memory in reversed(self.memories[giver.npc_id]):
            if memory.timestamp_tick < cutoff_tick:
                break
            if memory.event_type != "exchange":
                continue
            if receiver_id not in memory.entities:
                continue
            if not memory.summary.lower().startswith(f"gave {item} "):
                continue
            return True
        return False

    def _relationship_score(self, npc: NPCState, other_npc_id: str) -> float:
        relation = npc.relationships.get(other_npc_id)
        if relation is None:
            return 0.0
        return relation.trust + relation.closeness

    def _change_relationship(self, npc: NPCState, other_npc_id: str, trust_delta: float, closeness_delta: float) -> None:
        relation = npc.relationships.get(other_npc_id)
        if relation is None:
            relation = RelationshipState(other_npc_id=other_npc_id)
            npc.relationships[other_npc_id] = relation
        relation.trust = max(-1.0, min(1.0, relation.trust + trust_delta))
        relation.closeness = max(-1.0, min(1.0, relation.closeness + closeness_delta))

    def _record_memory(
        self,
        *,
        npc_id: str,
        event_type: str,
        summary: str,
        entities: Iterable[str] | None = None,
        importance: float,
    ) -> None:
        entity_ids = list(entities or [])
        location_id = self.player.location_id if npc_id == self.player.player_id else self.npcs[npc_id].location_id
        memory = EpisodicMemory(
            memory_id=f"memory.{npc_id}.{len(self.memories[npc_id]) + 1}",
            npc_id=npc_id,
            timestamp_tick=self.world.tick,
            event_type=event_type,
            summary=summary,
            entities=entity_ids,
            location_id=location_id,
            importance=importance,
            tags=[event_type],
        )
        self.memories[npc_id].append(memory)

    def _record_dialogue_exchange(self, npc: NPCState, *, player_prompt: str) -> None:
        prompt_summary = self._summarize_player_prompt(player_prompt)
        self._record_memory(
            npc_id=npc.npc_id,
            event_type="player_talk",
            summary=f'Spoke with {self.player.name} about "{prompt_summary}" at {self.player.location_id}.',
            entities=[self.player.player_id],
            importance=0.48,
        )
        self._record_memory(
            npc_id=self.player.player_id,
            event_type="npc_talk",
            summary=f'Spoke with {npc.name} about "{prompt_summary}" at {self.player.location_id}.',
            entities=[npc.npc_id],
            importance=0.48,
        )

    def _summarize_player_prompt(self, player_prompt: str, *, limit: int = 72) -> str:
        compact = " ".join(player_prompt.split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 3].rstrip() + "..."

    def _normalize_rumor_state(self) -> None:
        canonical_by_signature: dict[tuple[str | None, str, str], Rumor] = {}
        replacements: dict[str, str] = {}
        for rumor in self.rumors.values():
            signature = self._rumor_signature(rumor)
            current = canonical_by_signature.get(signature)
            if current is None:
                canonical_by_signature[signature] = rumor
                continue
            replacement = self._merge_rumors(current, rumor)
            canonical_by_signature[signature] = replacement
            if replacement is current:
                replacements[rumor.rumor_id] = current.rumor_id
            else:
                replacements[current.rumor_id] = rumor.rumor_id
        for rumor_id in replacements:
            self.rumors.pop(rumor_id, None)
        for npc in self.npcs.values():
            npc.known_rumor_ids = self._normalize_rumor_ids(npc.known_rumor_ids, replacements=replacements)
        self.player.known_rumor_ids = self._normalize_rumor_ids(self.player.known_rumor_ids, replacements=replacements)

    def _normalize_rumor_ids(self, rumor_ids: Iterable[str], *, replacements: dict[str, str] | None = None) -> list[str]:
        normalized: list[str] = []
        seen_signatures: set[tuple[str | None, str, str]] = set()
        for rumor_id in rumor_ids:
            canonical_rumor_id = replacements.get(rumor_id, rumor_id) if replacements is not None else rumor_id
            rumor = self.rumors.get(canonical_rumor_id)
            if rumor is None:
                continue
            signature = self._rumor_signature(rumor)
            if signature in seen_signatures:
                continue
            normalized.append(canonical_rumor_id)
            seen_signatures.add(signature)
        return normalized

    def _merge_rumors(self, left: Rumor, right: Rumor) -> Rumor:
        if self._rumor_sort_key(right) > self._rumor_sort_key(left):
            winner = right
            loser = left
        else:
            winner = left
            loser = right
        winner.confidence = max(winner.confidence, loser.confidence)
        winner.value = max(winner.value, loser.value)
        winner.hop_count = min(winner.hop_count, loser.hop_count)
        winner.created_tick = min(winner.created_tick, loser.created_tick)
        winner.last_shared_tick = max(winner.last_shared_tick, loser.last_shared_tick)
        return winner

    def _rumor_signature(self, rumor: Rumor) -> tuple[str | None, str, str]:
        content_key = " ".join(rumor.content.lower().split())
        return (rumor.subject_id, rumor.category.value, content_key)

    def _find_matching_rumor(
        self,
        *,
        origin_npc_id: str,
        subject_id: str | None,
        content: str,
        category: RumorCategory,
    ) -> Rumor | None:
        target_signature = (subject_id, category.value, " ".join(content.lower().split()))
        for rumor in self.rumors.values():
            if rumor.origin_npc_id != origin_npc_id:
                continue
            if self._rumor_signature(rumor) == target_signature:
                return rumor
        return None

    def _dedupe_rumors(self, rumors: Iterable[Rumor]) -> dict[tuple[str | None, str, str], Rumor]:
        deduped: dict[tuple[str | None, str, str], Rumor] = {}
        for rumor in rumors:
            signature = self._rumor_signature(rumor)
            existing = deduped.get(signature)
            if existing is None or self._rumor_sort_key(rumor) > self._rumor_sort_key(existing):
                deduped[signature] = rumor
        return deduped

    def _known_rumor_signatures(self, rumor_ids: Iterable[str]) -> set[tuple[str | None, str, str]]:
        return {self._rumor_signature(rumor) for rumor_id in rumor_ids if (rumor := self.rumors.get(rumor_id)) is not None}

    def _knows_rumor(self, rumor_ids: Iterable[str], rumor: Rumor) -> bool:
        signature = self._rumor_signature(rumor)
        for known_rumor_id in rumor_ids:
            known_rumor = self.rumors.get(known_rumor_id)
            if known_rumor is not None and self._rumor_signature(known_rumor) == signature:
                return True
        return False

    def _decay_rumors(self) -> None:
        expired_rumor_ids: list[str] = []
        for rumor in self.rumors.values():
            rumor.confidence = max(0.15, rumor.confidence - RUMOR_DECAY_PER_TURN)
            rumor.value = max(0.1, rumor.value - RUMOR_VALUE_DECAY_PER_TURN)
            if not rumor.rumor_id.startswith("rumor.dynamic."):
                continue
            if self.world.tick - rumor.last_shared_tick >= RUMOR_DYNAMIC_STALE_TICKS:
                expired_rumor_ids.append(rumor.rumor_id)
        for rumor_id in expired_rumor_ids:
            self._forget_rumor(rumor_id)
        if expired_rumor_ids:
            self._normalize_rumor_state()

    def _forget_rumor(self, rumor_id: str) -> None:
        self.rumors.pop(rumor_id, None)
        for npc in self.npcs.values():
            if rumor_id in npc.known_rumor_ids:
                npc.known_rumor_ids = [known_rumor_id for known_rumor_id in npc.known_rumor_ids if known_rumor_id != rumor_id]
        if rumor_id in self.player.known_rumor_ids:
            self.player.known_rumor_ids = [
                known_rumor_id for known_rumor_id in self.player.known_rumor_ids if known_rumor_id != rumor_id
            ]

    def _travel_command_block_message(self) -> str:
        state = self.player.travel_state
        destination_id = state.destination_location_id or self.player.location_id
        destination_name = self.world.locations[destination_id].name
        return (
            f"You are already on the road to {destination_name}. "
            "Use next, look, check status, eat, rest later, or sleep after you arrive."
        )

    def _player_travel_text(self) -> str:
        state = self.player.travel_state
        origin_id = state.origin_location_id or self.player.location_id
        destination_id = state.destination_location_id or self.player.location_id
        origin_name = self.world.locations[origin_id].name
        destination_name = self.world.locations[destination_id].name
        return "\n".join(
            [
                f"You are traveling from {origin_name} to {destination_name}.",
                f"ETA: {self._travel_eta_turns(state.ticks_remaining)} turns ({state.ticks_remaining} ticks remaining).",
                "You cannot talk, trade, or work until you arrive.",
            ]
        )

    def _route_base_ticks(self, start: str, destination: str) -> int:
        return TRAVEL_EDGE_BASE_TICKS.get(frozenset((start, destination)), self.turn_ticks * 2)

    def _travel_eta_turns(self, ticks_remaining: int) -> int:
        return max(1, (max(0, ticks_remaining) + self.turn_ticks - 1) // self.turn_ticks)

    def _resolve_region(self, query: str):
        lowered = query.lower()
        for region in self.world.regions.values():
            if region.region_id.lower() == lowered or region.name.lower() == lowered or region.name.lower().startswith(lowered):
                return region
        return None

    def _regional_route_between(self, left_region_id: str, right_region_id: str):
        for route in self.world.regional_routes:
            route_pair = {route.from_region_id, route.to_region_id}
            if route_pair == {left_region_id, right_region_id}:
                return route
        return None

    def _actor_load_ratio(self, actor: NPCState | PlayerState) -> float:
        if actor.carry_capacity <= 0:
            return 0.0
        return actor.carried_weight / actor.carry_capacity

    def _travel_block_reason(self, start: str, destination: str, actor: NPCState | PlayerState) -> str:
        edge = frozenset((start, destination))
        if self.world.weather == "storm_front" and edge in STORM_BLOCKED_EDGES:
            return f"The route to {self.world.locations[destination].name} is unsafe while the storm front is rolling through."
        if self._actor_load_ratio(actor) > 1.02:
            return "You are carrying too much to travel safely. Drop weight or trade first."
        return ""

    def _begin_travel(self, actor: NPCState | PlayerState, destination_id: str) -> int:
        self._refresh_actor_loads()
        start = actor.location_id
        load_ratio = max(0.0, self._actor_load_ratio(actor))
        weather_multiplier = WEATHER_TRAVEL_MULTIPLIERS.get(self.world.weather, 1.0)
        load_multiplier = 1.0 + (load_ratio * 0.45)
        fatigue_multiplier = 1.0 + (actor.fatigue / 180.0)
        total_ticks = max(
            self.turn_ticks,
            int(round(self._route_base_ticks(start, destination_id) * weather_multiplier * load_multiplier * fatigue_multiplier)),
        )
        actor.travel_state = TravelState(
            is_traveling=True,
            route_id=f"{start}->{destination_id}",
            origin_location_id=start,
            destination_location_id=destination_id,
            ticks_remaining=total_ticks,
            risk_budget=min(1.0, 0.1 + (weather_multiplier - 1.0) * 0.6 + load_ratio * 0.2),
        )
        return total_ticks

    def _begin_regional_travel(self, actor: NPCState | PlayerState, route, destination_id: str) -> int:
        self._refresh_actor_loads()
        load_ratio = max(0.0, self._actor_load_ratio(actor))
        weather_multiplier = WEATHER_TRAVEL_MULTIPLIERS.get(self.world.weather, 1.0)
        route_multiplier = 1.0 + self._regional_route_pressure(route) * 0.9
        total_ticks = max(
            self.turn_ticks * 2,
            int(
                round(
                    route.travel_ticks
                    * weather_multiplier
                    * route_multiplier
                    * (1.0 + load_ratio * 0.35)
                    * (1.0 + actor.fatigue / 200.0)
                )
            ),
        )
        actor.travel_state = TravelState(
            is_traveling=True,
            route_id=route.route_id,
            origin_location_id=actor.location_id,
            destination_location_id=destination_id,
            ticks_remaining=total_ticks,
            risk_budget=min(1.0, route.cargo_risk + route.weather_sensitivity * 0.3 + load_ratio * 0.15),
        )
        return total_ticks

    def _advance_player_travel(self) -> list[str]:
        state = self.player.travel_state
        if not state.is_traveling:
            return []
        destination_id = state.destination_location_id or self.player.location_id
        destination_name = self.world.locations[destination_id].name
        load_ratio = max(0.0, self._actor_load_ratio(self.player))
        self.player.hunger = min(100.0, self.player.hunger + PLAYER_TRAVEL_HUNGER_PER_TURN + load_ratio * 0.6)
        self.player.fatigue = min(100.0, self.player.fatigue + PLAYER_TRAVEL_FATIGUE_PER_TURN + load_ratio * 4.0)
        state.ticks_remaining = max(0, state.ticks_remaining - self.turn_ticks)
        if state.ticks_remaining > 0:
            return [f"You keep moving toward {destination_name}. {state.ticks_remaining} ticks remain."]
        self.player.location_id = destination_id
        self.player.travel_state = TravelState()
        return [f"You arrive at {destination_name}.", self.describe_location()]

    def _advance_npc_travel(self, npc: NPCState) -> str | None:
        state = npc.travel_state
        if not state.is_traveling:
            return None
        destination_id = state.destination_location_id or npc.location_id
        load_ratio = max(0.0, self._actor_load_ratio(npc))
        npc.hunger = min(100.0, npc.hunger + NPC_TRAVEL_HUNGER_PER_TURN + load_ratio * 0.4)
        npc.fatigue = min(100.0, npc.fatigue + NPC_TRAVEL_FATIGUE_PER_TURN + load_ratio * 3.0)
        state.ticks_remaining = max(0, state.ticks_remaining - self.turn_ticks)
        if state.ticks_remaining > 0:
            return None
        npc.location_id = destination_id
        npc.travel_state = TravelState()
        return f"{npc.name} arrives at {self.world.locations[destination_id].name}."

    def _shelter_rating(self, location_id: str) -> float:
        location = self.world.locations[location_id]
        return SHELTER_RATINGS.get(location.kind, 0.5)

    def _shelter_label(self, shelter: float) -> str:
        if shelter >= 0.85:
            return "excellent"
        if shelter >= 0.65:
            return "solid"
        if shelter >= 0.45:
            return "thin"
        return "poor"

    def _sleep_recovery_floor(self, shelter: float) -> float:
        if shelter >= 0.85:
            return 8.0
        if shelter >= 0.65:
            return 14.0
        if shelter >= 0.45:
            return 24.0
        return 38.0

    def _apply_recovery(self, actor: NPCState | PlayerState, *, location_id: str, sleep: bool) -> None:
        shelter = self._shelter_rating(location_id)
        base_recovery = (12.0 if sleep else 5.0) * shelter
        if sleep:
            base_recovery += 2.0
        recovered_fatigue = actor.fatigue - base_recovery
        if sleep:
            recovered_fatigue = max(self._sleep_recovery_floor(shelter), recovered_fatigue)
        actor.fatigue = max(0.0, recovered_fatigue)

    def _recover_npc(self, npc: NPCState) -> str | None:
        sleep = npc.fatigue >= 72 and (
            npc.home_location_id == npc.location_id or self._shelter_rating(npc.location_id) >= 0.65
        )
        before = npc.fatigue
        self._apply_recovery(npc, location_id=npc.location_id, sleep=sleep)
        if npc.fatigue >= before:
            return None
        if sleep:
            return f"{npc.name} gets some proper sleep."
        return f"{npc.name} pauses to recover."

    def _focused_npc_here(self) -> NPCState | None:
        if self.player.travel_state.is_traveling:
            self.player.focused_npc_id = None
            return None
        if self.player.focused_npc_id is None:
            return None
        npc = self.npcs.get(self.player.focused_npc_id)
        if npc is None or npc.location_id != self.player.location_id:
            self.player.focused_npc_id = None
            return None
        return npc

    def _resolve_interaction_npc(
        self,
        npc_query: str | None,
        *,
        action: str,
        candidates: list[NPCState] | None = None,
    ) -> tuple[NPCState | None, str]:
        if npc_query:
            npc = self._resolve_npc_here(npc_query)
            if npc is None:
                return None, f'No NPC named "{npc_query}" is here.'
            self.player.focused_npc_id = npc.npc_id
            return npc, ""

        focused_npc = self._focused_npc_here()
        if focused_npc is not None:
            return focused_npc, ""

        pool = list(candidates) if candidates is not None else self._npcs_at(self.player.location_id)
        if len(pool) == 1:
            npc = pool[0]
            self.player.focused_npc_id = npc.npc_id
            return npc, ""
        if not pool:
            return None, "No one here matches that interaction."
        names = ", ".join(npc.name for npc in pool)
        return None, f"Choose who to {action}: {names}. Use `focus <npc>` or include a name."

    def _trade_candidates(self, mode: str, item: str, qty: int) -> list[NPCState]:
        mode = self._normalize_trade_mode(mode)
        npcs_here = self._npcs_at(self.player.location_id)
        if mode == "buy":
            return [npc for npc in npcs_here if self._sellable_quantity(npc, item) >= qty]
        if mode == "sell":
            return [npc for npc in npcs_here if npc.is_vendor]
        if mode == "ask":
            return [npc for npc in npcs_here if self._requestable_quantity(npc, self.player, item) >= qty]
        if mode == "give" and self._giftable_quantity(self.player, item) >= qty:
            return list(npcs_here)
        return []

    def _barter_candidates(self, give_item: str, give_qty: int, get_item: str, get_qty: int) -> list[NPCState]:
        if self._giftable_quantity(self.player, give_item) < give_qty:
            return []
        return [npc for npc in self._npcs_at(self.player.location_id) if self._sellable_quantity(npc, get_item) >= get_qty]

    def _normalize_trade_mode(self, mode: str) -> str:
        normalized = mode.lower()
        aliases = {"gift": "give", "request": "ask"}
        return aliases.get(normalized, normalized)

    def _resolve_npc_here(self, query: str) -> NPCState | None:
        lowered = query.lower()
        for npc in self._npcs_at(self.player.location_id):
            if npc.npc_id.lower() == lowered or npc.name.lower() == lowered or npc.name.lower().startswith(lowered):
                return npc
        return None

    def _resolve_location(self, query: str):
        lowered = query.lower()
        for location in self.world.locations.values():
            if location.location_id.lower() == lowered or location.name.lower() == lowered or location.name.lower().startswith(lowered):
                return location
        return None

    def _resolve_item(self, query: str) -> str | None:
        lowered = query.lower()
        for item in ITEM_VALUES:
            if item == lowered or item.startswith(lowered):
                return item
        return None

    def _npcs_at(self, location_id: str) -> list[NPCState]:
        return [npc for npc in self.npcs.values() if npc.location_id == location_id and not npc.travel_state.is_traveling]

    def _next_hop(self, start: str, goal: str) -> str | None:
        if start == goal:
            return start
        frontier: deque[tuple[str, list[str]]] = deque([(start, [start])])
        seen = {start}
        while frontier:
            node, path = frontier.popleft()
            for neighbor in self.world.locations[node].neighbors:
                if neighbor in seen:
                    continue
                next_path = path + [neighbor]
                if neighbor == goal:
                    return next_path[1]
                seen.add(neighbor)
                frontier.append((neighbor, next_path))
        return None

    def _path_length(self, start: str, goal: str) -> int:
        if start == goal:
            return 0
        frontier: deque[tuple[str, int]] = deque([(start, 0)])
        seen = {start}
        while frontier:
            node, dist = frontier.popleft()
            for neighbor in self.world.locations[node].neighbors:
                if neighbor in seen:
                    continue
                if neighbor == goal:
                    return dist + 1
                seen.add(neighbor)
                frontier.append((neighbor, dist + 1))
        return 999

    def _npc_mood(self, npc: NPCState) -> str:
        if npc.travel_state.is_traveling:
            return "travel"
        if npc.hunger >= 65:
            return "hungry"
        if npc.current_intent is not None:
            return npc.current_intent.intent_type.value
        return "idle"

    def _vendor_stock_line(self, npc: NPCState) -> str:
        if not npc.is_vendor:
            return ""
        goods = [f"{item} x{qty}" for item, qty in npc.inventory.items() if qty > 0]
        return " | stock: " + (", ".join(goods[:4]) if goods else "empty")

    def _format_inventory(self, inventory: dict[str, int]) -> str:
        goods = [f"{item} x{qty}" for item, qty in inventory.items() if qty > 0]
        return ", ".join(goods) if goods else "empty"

    def _inventory_weight(self, inventory: dict[str, int]) -> float:
        return round(sum(ITEM_WEIGHTS.get(item, 1.0) * qty for item, qty in inventory.items()), 2)

    def _refresh_actor_loads(self) -> None:
        self.player.carried_weight = self._inventory_weight(self.player.inventory)
        for npc in self.npcs.values():
            npc.carried_weight = self._inventory_weight(npc.inventory)

    def _adjust_item(self, inventory: dict[str, int], item: str, delta: int) -> None:
        inventory[item] = inventory.get(item, 0) + delta
        if inventory[item] <= 0:
            inventory.pop(item, None)
