from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Iterable

from acidnet.llm import DialogueContext, DialogueModelAdapter, DialogueResult, RuleBasedDialogueAdapter, build_dialogue_adapter
from acidnet.llm.prompt_builder import DEFAULT_SYSTEM_PROMPT, infer_interaction_mode
from acidnet.models import (
    Belief,
    EpisodicMemory,
    IntentType,
    NPCState,
    PersonaProfile,
    PlayerState,
    RelationshipState,
    Rumor,
    RumorCategory,
    WorldState,
)
from acidnet.planner import HeuristicPlanner, PlannerContext
from acidnet.world import build_demo_setup

FOOD_ITEMS = ("stew", "bread", "fish", "wheat")
ITEM_VALUES = {"wheat": 2, "bread": 5, "fish": 4, "stew": 7, "tool": 15}
CONSUMPTION_VALUE = {"wheat": 10.0, "bread": 26.0, "fish": 21.0, "stew": 34.0}
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
                "  where                    Show nearby locations.",
                "  map                      List all locations.",
                "  go <location>            Move to a neighboring location.",
                "  talk <npc>               Talk to an NPC at your location.",
                "  say <npc> <message>      Speak to an NPC using your own words.",
                "  ask <npc> rumor          Ask an NPC for their latest rumor.",
                "  work                     Do local work or gather resources here.",
                "  eat <item>               Consume food from your inventory.",
                "  trade <npc> buy <item> <qty>",
                "  trade <npc> sell <item> <qty>",
                "  inventory                Show your inventory and gold.",
                "  status                   Show player and world status.",
                "  rumors                   Show rumors you know.",
                "  npcs                     List NPCs at your location.",
                "  wait [turns]             Advance the world.",
                "  help                     Show this help.",
                "  quit                     Exit the simulation.",
            ]
        )

    def describe_location(self) -> str:
        location = self.world.locations[self.player.location_id]
        npcs = self._npcs_at(location.location_id)
        npc_lines = []
        for npc in npcs:
            mood = self._npc_mood(npc)
            stock = self._vendor_stock_line(npc)
            npc_lines.append(f"- {npc.name} ({npc.profession}, {mood}){stock}")
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

    def player_status(self) -> str:
        lines = [
            f"Day {self.world.day}, tick {self.world.tick}, weather: {self.world.weather}",
            f"{self.player.name} is at {self.world.locations[self.player.location_id].name}.",
            f"Hunger: {self.player.hunger:.1f}/100",
            f"Money: {self.player.money} gold",
            f"Inventory: {self._format_inventory(self.player.inventory)}",
            f"Known rumors: {len(self.player.known_rumor_ids)}",
        ]
        if self.tick_log:
            lines.append("Recent world events:")
            lines.extend(f"- {entry}" for entry in list(self.tick_log)[-5:])
        return "\n".join(lines)

    def known_rumors_text(self) -> str:
        if not self.player.known_rumor_ids:
            return "You do not know any rumors yet."
        lines = ["Rumors you know:"]
        for rumor in self._sorted_known_rumors(self.player.known_rumor_ids):
            lines.append(f"- {rumor.content} (confidence {rumor.confidence:.2f})")
        return "\n".join(lines)

    def npcs_here_text(self) -> str:
        npcs = self._npcs_at(self.player.location_id)
        if not npcs:
            return "There are no NPCs here."
        return "\n".join(f"- {npc.name} ({npc.profession})" for npc in npcs)

    def _events(self, kind: str, lines: Iterable[str]) -> list[TurnEvent]:
        return [TurnEvent(kind=kind, text=line) for line in lines if line]

    def _npc_dialogue_event(self, npc: NPCState, text: str) -> TurnEvent:
        cleaned = " ".join(text.split()) or "..."
        return TurnEvent(kind="npc", text=f"{npc.name}: {cleaned}")

    def move_player(self, location_query: str) -> TurnResult:
        destination = self._resolve_location(location_query)
        if destination is None:
            return TurnResult(self._events("system", [f'Unknown location "{location_query}".']))
        current = self.world.locations[self.player.location_id]
        if destination.location_id not in current.neighbors:
            return TurnResult(self._events("system", [f"You cannot go directly to {destination.name} from here."]))
        self.player.location_id = destination.location_id
        entries = self._events("system", [f"You move to {destination.name}.", self.describe_location()])
        entries.extend(self.advance_turn(1).entries)
        return TurnResult(entries)

    def talk_to_npc(self, npc_query: str) -> TurnResult:
        npc = self._resolve_npc_here(npc_query)
        if npc is None:
            return TurnResult(self._events("system", [f'No NPC named "{npc_query}" is here.']))

        player_prompt = "What is going on around here?"
        entries = [self._npc_dialogue_event(npc, self._generate_dialogue(npc, interaction_mode="talk", player_prompt=player_prompt))]
        self._record_dialogue_exchange(npc, player_prompt=player_prompt)
        self._change_relationship(npc, self.player.player_id, trust_delta=0.02, closeness_delta=0.04)
        rumor_line = self._offer_rumor_to_player(npc, asked=False)
        if rumor_line:
            entries.extend(self._events("npc", [rumor_line]))
        entries.extend(self.advance_turn(1).entries)
        return TurnResult(entries)

    def say_to_npc(self, npc_query: str, player_message: str) -> TurnResult:
        npc = self._resolve_npc_here(npc_query)
        if npc is None:
            return TurnResult(self._events("system", [f'No NPC named "{npc_query}" is here.']))

        player_prompt = " ".join(player_message.split())
        if not player_prompt:
            return TurnResult(self._events("system", ["Say what?"]))

        interaction_mode = infer_interaction_mode(player_prompt)
        entries = [
            self._npc_dialogue_event(
                npc,
                self._generate_dialogue(npc, interaction_mode=interaction_mode, player_prompt=player_prompt),
            )
        ]
        self._record_dialogue_exchange(npc, player_prompt=player_prompt)
        self._change_relationship(npc, self.player.player_id, trust_delta=0.02, closeness_delta=0.05)
        if interaction_mode == "rumor_request":
            rumor_line = self._offer_rumor_to_player(npc, asked=True)
            if rumor_line:
                entries.extend(self._events("npc", [rumor_line]))
        entries.extend(self.advance_turn(1).entries)
        return TurnResult(entries)

    def ask_npc(self, npc_query: str, topic: str) -> TurnResult:
        npc = self._resolve_npc_here(npc_query)
        if npc is None:
            return TurnResult(self._events("system", [f'No NPC named "{npc_query}" is here.']))
        if topic.lower() != "rumor":
            return TurnResult(
                [self._npc_dialogue_event(npc, 'tilts their head. "Ask about rumors if you want local news."')]
            )
        player_prompt = "Have you heard any useful rumors?"
        result = [
            self._npc_dialogue_event(
                npc,
                self._generate_dialogue(npc, interaction_mode="rumor_request", player_prompt=player_prompt),
            )
        ]
        self._record_dialogue_exchange(npc, player_prompt=player_prompt)
        rumor_line = self._offer_rumor_to_player(npc, asked=True)
        if rumor_line is not None:
            result.extend(self._events("npc", [rumor_line]))
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

    def player_work(self) -> TurnResult:
        location = self.world.locations[self.player.location_id]
        lines: list[str] = []
        if location.location_id == "farm":
            self._adjust_item(self.player.inventory, "wheat", 2)
            lines.append("You help in the south field and gather 2 wheat.")
        elif location.location_id == "riverside":
            self._adjust_item(self.player.inventory, "fish", 1)
            lines.append("You spend a shift on the riverside and catch 1 fish.")
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
        entries = self._events("system", lines)
        entries.extend(self.advance_turn(1).entries)
        return TurnResult(entries)

    def trade_with_npc(self, npc_query: str, mode: str, item_query: str, qty: int) -> TurnResult:
        npc = self._resolve_npc_here(npc_query)
        if npc is None:
            return TurnResult(self._events("system", [f'No NPC named "{npc_query}" is here.']))
        if qty <= 0:
            return TurnResult(self._events("system", ["Quantity must be greater than zero."]))
        item = self._resolve_item(item_query)
        if item is None:
            return TurnResult(self._events("system", [f'Unknown item "{item_query}".']))

        mode = mode.lower()
        if mode not in {"buy", "sell"}:
            return TurnResult(self._events("system", ['Trade mode must be "buy" or "sell".']))

        lines: list[str] = []
        if mode == "buy":
            price = self._price_for(npc, item, buy_from_vendor=True)
            if npc.inventory.get(item, 0) < qty:
                return TurnResult(self._events("system", [f"{npc.name} does not have enough {item}."]))
            total = price * qty
            if self.player.money < total:
                return TurnResult(self._events("system", [f"You need {total} gold, but you only have {self.player.money}."]))
            self.player.money -= total
            npc.money += total
            self._adjust_item(self.player.inventory, item, qty)
            self._adjust_item(npc.inventory, item, -qty)
            lines.append(f"You buy {qty} {item} from {npc.name} for {total} gold.")
        else:
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

        self._record_memory(
            npc_id=npc.npc_id,
            event_type="trade",
            summary=f"Traded {item} with {self.player.name}.",
            entities=[self.player.player_id],
            importance=0.65,
        )
        self._record_memory(
            npc_id=self.player.player_id,
            event_type="trade",
            summary=f"Traded {item} with {npc.name}.",
            entities=[npc.npc_id],
            importance=0.65,
        )
        self._change_relationship(npc, self.player.player_id, trust_delta=0.03, closeness_delta=0.02)
        self._refresh_market_snapshot()
        entries = self._events("system", lines)
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
        if command == "help":
            return TurnResult(self._events("system", [self.help_text()]))
        if command in {"look", "where"}:
            return TurnResult(self._events("system", [self.describe_location()]))
        if command == "map":
            return TurnResult(self._events("system", [self.list_map()]))
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
        if command in {"work", "gather", "forage"}:
            return self.player_work()
        if command == "eat" and len(parts) >= 2:
            return self.player_eat(" ".join(parts[1:]))
        if command == "go" and len(parts) >= 2:
            return self.move_player(" ".join(parts[1:]))
        if command == "talk" and len(parts) >= 2:
            return self.talk_to_npc(" ".join(parts[1:]))
        if command in {"say", "tell"} and len(parts) >= 3:
            return self.say_to_npc(parts[1], " ".join(parts[2:]))
        if command == "ask" and len(parts) >= 3:
            return self.ask_npc(parts[1], " ".join(parts[2:]))
        if command == "trade" and len(parts) == 5:
            try:
                qty = int(parts[4])
            except ValueError:
                return TurnResult(self._events("system", ["Trade quantity must be an integer."]))
            return self.trade_with_npc(parts[1], parts[2], parts[3], qty)
        if command == "wait":
            turns = 1
            if len(parts) >= 2:
                try:
                    turns = int(parts[1])
                except ValueError:
                    return TurnResult(self._events("system", ["Wait amount must be an integer."]))
            return self.advance_turn(turns)
        return TurnResult(self._events("system", ['Unknown command. Type "help" to see valid commands.']))

    def _step_turn(self) -> list[str]:
        self.turn_counter += 1
        self.world.tick += self.turn_ticks
        self.world.day = 1 + (self.world.tick // (12 * 60 * 24))
        lines: list[str] = []

        self.player.hunger = min(100.0, self.player.hunger + 1.2)
        self._advance_weather()
        self._refresh_dynamic_rumors()
        for npc in self.npcs.values():
            npc.hunger = min(100.0, npc.hunger + 1.6)
            self._refresh_beliefs_for_npc(npc)

        self._refresh_market_snapshot()
        for npc_id in sorted(self.npcs):
            npc = self.npcs[npc_id]
            context = self._build_planner_context(npc)
            npc.current_intent = self.planner.plan(context).intent
            event = self._execute_npc_intent(npc)
            if event:
                lines.append(event)
                self.tick_log.append(event)
        self._refresh_market_snapshot()
        return lines

    def _build_planner_context(self, npc: NPCState) -> PlannerContext:
        top_goals: list[str] = []
        food_item = self._best_food_in_inventory(npc.inventory)
        if npc.hunger >= 45 and food_item is not None:
            top_goals.append(f"eat:{food_item}")
        elif npc.hunger >= 45:
            vendor = self._nearest_food_vendor(npc, affordable_only=True)
            if vendor is not None:
                if npc.location_id == vendor.location_id:
                    top_goals.append(f"trade_food:{vendor.npc_id}")
                else:
                    top_goals.append(f"move:{vendor.location_id}")
            else:
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
                npc.location_id = next_hop
                return f"{npc.name} moves to {self.world.locations[next_hop].name}."
            return None
        if intent.intent_type is IntentType.EAT and intent.target_id:
            if npc.inventory.get(intent.target_id, 0) > 0:
                self._consume_food(npc.inventory, intent.target_id, npc)
                return f"{npc.name} eats {intent.target_id}."
            return None
        if intent.intent_type is IntentType.TRADE and intent.target_id:
            vendor = self.npcs.get(intent.target_id)
            if vendor is not None:
                return self._npc_buy_food(npc, vendor)
            return None
        if intent.intent_type is IntentType.SHARE_RUMOR and intent.target_id:
            target = self.npcs.get(intent.target_id)
            if target is not None:
                return self._share_rumor(npc, target)
            return None
        if intent.intent_type is IntentType.WORK:
            return self._perform_work(npc)
        return None

    def _perform_work(self, npc: NPCState) -> str | None:
        if npc.profession in WORK_OUTPUT:
            item, amount = self._work_output_for(npc.profession)
            self._adjust_item(npc.inventory, item, amount)
            income = self._work_income(npc)
            if income > 0:
                npc.money += income
            self._record_memory(
                npc_id=npc.npc_id,
                event_type="work",
                summary=(
                    f"Produced {amount} {item} and earned {income} gold."
                    if income > 0
                    else f"Produced {amount} {item}."
                ),
                importance=0.4,
            )
            if income > 0:
                return f"{npc.name} works and produces {amount} {item}, earning {income} gold."
            return f"{npc.name} works and produces {amount} {item}."
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
                    npc.location_id = destination
                    return f"{npc.name} heads toward the farm for wheat."
                return None
            self._adjust_item(npc.inventory, "wheat", -1)
            self._adjust_item(npc.inventory, "bread", 2)
            return f"{npc.name} bakes fresh bread."
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
                    npc.location_id = destination
                    return f"{npc.name} heads toward the riverside for fish."
                return None
            self._adjust_item(npc.inventory, "fish", -1)
            self._adjust_item(npc.inventory, "stew", 1)
            return f"{npc.name} cooks a pot of stew."
        income = self._work_income(npc)
        if income > 0:
            npc.money += income
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
            return f"{npc.name} forages {fallback_item} to stay fed."
        return None

    def _npc_buy_food(self, npc: NPCState, vendor: NPCState) -> str | None:
        if npc.npc_id == vendor.npc_id:
            return None
        food = self._best_food_to_buy(npc, vendor, affordable_only=True)
        if food is None or npc.money <= 0:
            return None
        return self._npc_buy_specific_item(npc, vendor, food, 1)

    def _npc_buy_specific_item(self, buyer: NPCState, vendor: NPCState, item: str, qty: int) -> str | None:
        if vendor.inventory.get(item, 0) < qty:
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

    def _share_rumor(self, speaker: NPCState, listener: NPCState) -> str | None:
        rumor = self._preferred_rumor_to_share(speaker, listener)
        if rumor is None:
            return None
        if rumor.rumor_id not in listener.known_rumor_ids:
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

    def _offer_rumor_to_player(self, npc: NPCState, asked: bool) -> str | None:
        rumor = self._preferred_rumor_to_share_to_player(npc)
        if rumor is None:
            return None
        if rumor.rumor_id not in self.player.known_rumor_ids:
            self.player.known_rumor_ids.append(rumor.rumor_id)
        prefix = "leans closer" if asked else "adds quietly"
        return f'{npc.name} {prefix}: "{rumor.content}"'

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
        visible_rumors = [self.rumors[rumor_id] for rumor_id in npc.known_rumor_ids if rumor_id in self.rumors]
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
        if rumor_id in self.rumors:
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

    def _sorted_known_rumors(self, rumor_ids: Iterable[str]) -> list[Rumor]:
        available = [self.rumors[rumor_id] for rumor_id in rumor_ids if rumor_id in self.rumors]
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

    def _work_output_for(self, profession: str) -> tuple[str, int]:
        item, amount = WORK_OUTPUT[profession]
        if profession == "farmer":
            if self.world.weather in {"cool_rain", "market_day"}:
                amount += 1
            elif self.world.weather in {"dry_wind", "dusty_heat"}:
                amount = max(1, amount - 1)
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
        if npc.workplace_id is None:
            return None
        if npc.location_id != npc.workplace_id:
            return f"move:{npc.workplace_id}"
        return f"work:{npc.workplace_id}"

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
        unknown = [
            rumor
            for rumor in self._sorted_known_rumors(speaker.known_rumor_ids)
            if rumor.rumor_id not in listener.known_rumor_ids
        ]
        return unknown[0] if unknown else None

    def _preferred_rumor_to_share_to_player(self, speaker: NPCState) -> Rumor | None:
        ranked = self._sorted_known_rumors(speaker.known_rumor_ids)
        unknown = [rumor for rumor in ranked if rumor.rumor_id not in self.player.known_rumor_ids]
        if unknown:
            return unknown[0]
        return ranked[0] if ranked else None

    def _nearest_food_vendor(self, npc: NPCState, *, affordable_only: bool = False) -> NPCState | None:
        candidates: list[tuple[int, int, float, NPCState]] = []
        for other in self.npcs.values():
            if other.npc_id == npc.npc_id or not other.is_vendor:
                continue
            food = self._best_food_to_buy(npc, other, affordable_only=affordable_only)
            if food is None:
                if affordable_only:
                    continue
                food = self._best_food_in_inventory(other.inventory)
                if food is None:
                    continue
            price = self._price_for(other, food, buy_from_vendor=True)
            candidates.append(
                (self._path_length(npc.location_id, other.location_id), price, -CONSUMPTION_VALUE[food], other)
            )
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3].npc_id))
        return candidates[0][3]

    def _best_food_to_buy(self, buyer: NPCState, vendor: NPCState, *, affordable_only: bool) -> str | None:
        best_item: str | None = None
        best_score: tuple[float, int] | None = None
        for item in FOOD_ITEMS:
            if vendor.inventory.get(item, 0) <= 0:
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

    def _work_income(self, npc: NPCState) -> int:
        return WORK_WAGES.get(npc.profession, 0)

    def _consume_food(self, inventory: dict[str, int], item: str, actor: NPCState | PlayerState) -> None:
        self._adjust_item(inventory, item, -1)
        actor.hunger = max(0.0, actor.hunger - CONSUMPTION_VALUE[item])

    def _refresh_market_snapshot(self) -> None:
        totals = {item: 0 for item in ITEM_VALUES}
        for npc in self.npcs.values():
            for item, qty in npc.inventory.items():
                totals[item] = totals.get(item, 0) + qty
        for item, qty in self.player.inventory.items():
            totals[item] = totals.get(item, 0) + qty
        for item, state in self.world.market.items.items():
            state.stock = max(0, totals.get(item, 0))
            scarcity = max(0, 10 - state.stock)
            state.current_price = max(state.base_price, state.base_price + scarcity // 2)
        self.world.market.scarcity_index = max(
            0.0,
            sum(max(0, 6 - self.world.market.items[item].stock) for item in ("bread", "stew", "fish")) / 10.0,
        )

    def _price_for(self, vendor: NPCState, item: str, *, buy_from_vendor: bool) -> int:
        base = self.world.market.items.get(item)
        base_price = base.current_price if base is not None else ITEM_VALUES[item]
        persona = self.personas[vendor.persona_id]
        modifier = 1.0 + max(0.0, persona.trade_bias) * 0.25 if buy_from_vendor else 0.55 + max(0.0, persona.trade_bias) * 0.1
        return max(1, round(base_price * modifier))

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
        return [npc for npc in self.npcs.values() if npc.location_id == location_id]

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

    def _adjust_item(self, inventory: dict[str, int], item: str, delta: int) -> None:
        inventory[item] = inventory.get(item, 0) + delta
        if inventory[item] <= 0:
            inventory.pop(item, None)
