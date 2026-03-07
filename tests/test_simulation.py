import re

from acidnet.llm import DialogueContext, DialogueResult
from acidnet.simulator import Simulation, build_demo_setup
from acidnet.simulator.models import RegionalTransit, WorldEvent


class RecordingDialogueAdapter:
    def __init__(self) -> None:
        self.contexts: list[DialogueContext] = []

    def prepare(self) -> str | None:
        return "ready"

    def generate(self, context: DialogueContext) -> DialogueResult:
        self.contexts.append(context.model_copy(deep=True))
        return DialogueResult(text=f"{context.npc.name} sees: {context.player_prompt}", adapter_name="recording")


class StaticDialogueAdapter:
    def __init__(self, text: str, *, used_rumor_ids: list[str] | None = None) -> None:
        self.text = text
        self.used_rumor_ids = list(used_rumor_ids or [])

    def prepare(self) -> str | None:
        return "ready"

    def generate(self, context: DialogueContext) -> DialogueResult:
        return DialogueResult(
            text=self.text,
            adapter_name="static",
            used_rumor_ids=list(self.used_rumor_ids),
        )


def build_recording_simulation(system_prompt: str = "Test system prompt.") -> tuple[Simulation, RecordingDialogueAdapter]:
    setup = build_demo_setup()
    adapter = RecordingDialogueAdapter()
    simulation = Simulation(
        world=setup.world,
        player=setup.player,
        npcs=setup.npcs,
        personas=setup.personas,
        rumors=setup.rumors,
        dialogue_adapter=adapter,
        dialogue_system_prompt=system_prompt,
    )
    return simulation, adapter


def build_static_simulation(text: str, *, used_rumor_ids: list[str] | None = None) -> Simulation:
    setup = build_demo_setup()
    adapter = StaticDialogueAdapter(text, used_rumor_ids=used_rumor_ids)
    return Simulation(
        world=setup.world,
        player=setup.player,
        npcs=setup.npcs,
        personas=setup.personas,
        rumors=setup.rumors,
        dialogue_adapter=adapter,
    )


def _sentence_count(text: str) -> int:
    return len([match.group(0) for match in re.finditer(r'[^.!?]+[.!?]["\')\]]*|[^.!?]+$', text) if match.group(0).strip()])


def test_demo_simulation_boots_with_interactable_square() -> None:
    simulation = Simulation.create_demo()

    description = simulation.describe_location()

    assert "Market Square" in description
    assert "Mara" in description
    assert "Neri" in description


def test_talking_to_npc_can_surface_a_rumor() -> None:
    simulation = Simulation.create_demo()

    result = simulation.handle_command("talk neri")

    assert any("dry wind" in line for line in result.lines)
    assert simulation.player.known_rumor_ids
    assert not any("leans closer" in line for line in result.lines)
    assert not any("adds quietly" in line for line in result.lines)


def test_talk_learns_rumor_from_dialogue_text_without_used_rumor_ids() -> None:
    setup = build_demo_setup()
    rumor = setup.rumors[setup.npcs["npc.neri"].known_rumor_ids[0]]
    simulation = build_static_simulation(f"People keep saying this: {rumor.content}")

    result = simulation.handle_command("talk neri")

    assert rumor.rumor_id in simulation.player.known_rumor_ids
    assert any(entry.kind == "system" and "note a rumor" in entry.text.lower() for entry in result.entries)


def test_talk_does_not_learn_rumor_from_generic_nonmatching_reply() -> None:
    simulation = build_static_simulation("I am busy with orders today.")

    result = simulation.handle_command("talk neri")

    assert not simulation.player.known_rumor_ids
    assert not any(entry.kind == "system" and "note a rumor" in entry.text.lower() for entry in result.entries)


def test_player_can_say_freeform_message_to_npc() -> None:
    simulation = Simulation.create_demo()

    result = simulation.handle_command("say neri Have you heard any useful rumors today?")

    assert any("dry wind" in line.lower() for line in result.lines)
    assert simulation.player.known_rumor_ids
    assert result.entries[0].kind == "npc"
    assert result.entries[0].text.startswith("Neri:")
    assert any(entry.kind == "world" for entry in result.entries[1:])


def test_talk_forwards_system_prompt_into_dialogue_context() -> None:
    simulation, adapter = build_recording_simulation("Stay grounded. Never narrate hidden state.")

    simulation.handle_command("talk neri")

    assert adapter.contexts
    assert adapter.contexts[-1].system_prompt == "Stay grounded. Never narrate hidden state."
    assert adapter.contexts[-1].interaction_mode == "talk"
    assert adapter.contexts[-1].player_prompt == "What is going on around here?"


def test_ask_rumor_forwards_system_prompt_into_dialogue_context() -> None:
    simulation, adapter = build_recording_simulation("Answer as exactly one NPC.")

    simulation.handle_command("ask neri rumor")

    assert adapter.contexts
    assert adapter.contexts[-1].system_prompt == "Answer as exactly one NPC."
    assert adapter.contexts[-1].interaction_mode == "rumor_request"
    assert adapter.contexts[-1].player_prompt == "Have you heard any useful rumors?"


def test_direct_say_forwards_exact_player_prompt_into_dialogue_context() -> None:
    simulation, adapter = build_recording_simulation("Keep the reply short.")

    simulation.handle_command("say neri Where did you come from?")

    assert adapter.contexts
    assert adapter.contexts[-1].system_prompt == "Keep the reply short."
    assert adapter.contexts[-1].interaction_mode == "direct_say"
    assert adapter.contexts[-1].player_prompt == "Where did you come from?"


def test_asking_for_rumor_uses_single_npc_line_and_nonverbal_system_note() -> None:
    simulation = Simulation.create_demo(dialogue_backend="heuristic")

    result = simulation.handle_command("ask neri rumor")

    assert not any("leans closer" in line for line in result.lines)
    assert not any("adds quietly" in line for line in result.lines)
    assert sum(1 for entry in result.entries if entry.kind == "npc") == 1
    assert any(entry.kind == "system" and "rumor" in entry.text.lower() for entry in result.entries)


def test_direct_say_first_meeting_question_uses_player_prompt_and_location_context() -> None:
    simulation = Simulation.create_demo(dialogue_backend="heuristic")

    result = simulation.handle_command("say neri Where did you come from?")

    assert result.entries[0].kind == "npc"
    assert "Stories travel faster than thread in this village." not in result.entries[0].text
    assert "You are not entirely new to me anymore." not in result.entries[0].text
    assert "Market Square" in result.entries[0].text


def test_heuristic_default_prompt_keeps_talk_reply_within_two_sentences() -> None:
    simulation = Simulation.create_demo(dialogue_backend="heuristic")

    reply = simulation.probe_npc_dialogue("npc.neri", interaction_mode="talk", player_prompt="What is going on around here?")

    assert "dry wind" in reply.lower()
    assert _sentence_count(reply) <= 2


def test_heuristic_custom_one_sentence_prompt_is_enforced() -> None:
    simulation = Simulation.create_demo(dialogue_backend="heuristic")
    simulation.set_dialogue_system_prompt("Stay grounded in the supplied state. Reply with one short in-character sentence only.")

    reply = simulation.probe_npc_dialogue("npc.neri", interaction_mode="talk", player_prompt="What is going on around here?")

    assert "dry wind" in reply.lower()
    assert _sentence_count(reply) == 1


def test_heuristic_hunger_reply_does_not_offer_non_food_goods() -> None:
    simulation = Simulation.create_demo(dialogue_backend="heuristic")

    reply = simulation.probe_npc_dialogue("npc.doran", interaction_mode="direct_say", player_prompt="I am hungry.")

    assert "tool" not in reply.lower()
    assert "bakery" in reply.lower() or "square" in reply.lower()


def test_heuristic_food_trade_reply_redirects_when_vendor_has_no_edible_stock() -> None:
    simulation = Simulation.create_demo(dialogue_backend="heuristic")

    reply = simulation.probe_npc_dialogue(
        "npc.doran",
        interaction_mode="trade_request",
        player_prompt="I need food. What can you sell me right now?",
    )

    assert "tool" not in reply.lower()
    assert "do not have food" in reply.lower()


def test_demo_world_starts_with_multiple_distinct_rumors() -> None:
    simulation = Simulation.create_demo()

    assert len(simulation.rumors) >= 5
    assert len({rumor.content for rumor in simulation.rumors.values()}) >= 5


def test_player_can_collect_multiple_distinct_rumors_from_different_npcs() -> None:
    simulation = Simulation.create_demo()

    simulation.handle_command("ask neri rumor")
    simulation.handle_command("ask mara rumor")

    known_contents = {
        simulation.rumors[rumor_id].content
        for rumor_id in simulation.player.known_rumor_ids
        if rumor_id in simulation.rumors
    }

    assert len(known_contents) >= 2


def test_baker_keeps_bread_stock_during_early_supply_loop() -> None:
    simulation = Simulation.create_demo()

    simulation.advance_turn(48)

    assert simulation.npcs["npc.hobb"].inventory.get("bread", 0) >= 1


def test_midgame_population_avoids_total_exhaustion_collapse() -> None:
    simulation = Simulation.create_demo()

    simulation.advance_turn(120)

    starving = [npc for npc in simulation.npcs.values() if npc.hunger >= 95]
    exhausted = [npc for npc in simulation.npcs.values() if npc.fatigue >= 95]

    assert len(starving) <= 1
    assert not exhausted
    assert simulation.npcs["npc.hobb"].hunger < 80


def test_blacksmith_output_buffer_prevents_tool_overload_travel_lock() -> None:
    simulation = Simulation.create_demo()

    simulation.advance_turn(120)
    doran = simulation.npcs["npc.doran"]

    assert doran.inventory.get("tool", 0) <= 4
    assert doran.carried_weight <= doran.carry_capacity
    assert doran.hunger < 95


def test_dynamic_rumors_spawn_as_world_conditions_change() -> None:
    simulation = Simulation.create_demo()
    starting_count = len(simulation.rumors)

    simulation.advance_turn(10)

    assert len(simulation.rumors) > starting_count
    assert any(rumor_id.startswith("rumor.dynamic.") for rumor_id in simulation.rumors)


def test_repeated_dynamic_rumor_content_reuses_existing_rumor() -> None:
    simulation = Simulation.create_demo()
    hobb = simulation.npcs["npc.hobb"]
    hobb.inventory["wheat"] = 1

    simulation.advance_turn(6)
    simulation.advance_turn(6)
    simulation.advance_turn(6)

    matching = [
        rumor
        for rumor in simulation.rumors.values()
        if rumor.content == "Hobb is running low on wheat and may need to slow the bakery's next batch."
    ]

    assert len(matching) == 1


def test_player_known_rumors_do_not_duplicate_same_content() -> None:
    simulation = Simulation.create_demo()
    simulation.player.location_id = "bakery"
    simulation._ensure_rumor(
        rumor_id="rumor.dynamic.test.hobb.shortage",
        origin_npc_id="npc.hobb",
        subject_id="bakery",
        content="Hobb is running low on wheat and may need to slow the bakery's next batch.",
        category=simulation.rumors["rumor.shortage.wheat"].category,
        confidence=0.79,
        value=0.71,
        holders=["npc.hobb"],
    )
    simulation.npcs["npc.hobb"].known_rumor_ids = ["rumor.dynamic.test.hobb.shortage"]

    simulation.handle_command("ask hobb rumor")
    simulation.handle_command("ask hobb rumor")

    matching_known = [
        rumor_id
        for rumor_id in simulation.player.known_rumor_ids
        if simulation.rumors.get(rumor_id) is not None
        and simulation.rumors[rumor_id].content == "Hobb is running low on wheat and may need to slow the bakery's next batch."
    ]

    assert len(matching_known) == 1


def test_stale_dynamic_rumors_expire() -> None:
    simulation = Simulation.create_demo()
    simulation._ensure_rumor(
        rumor_id="rumor.dynamic.test.old",
        origin_npc_id="npc.hobb",
        subject_id="bakery",
        content="A stale bakery whisper is losing its edge.",
        category=simulation.rumors["rumor.bakery.night_batch"].category,
        confidence=0.6,
        value=0.5,
        holders=["npc.hobb"],
    )
    simulation.player.known_rumor_ids.append("rumor.dynamic.test.old")
    simulation.rumors["rumor.dynamic.test.old"].last_shared_tick = 0
    simulation.world.tick = 8 * 60

    simulation.advance_turn(1)

    assert "rumor.dynamic.test.old" not in simulation.rumors
    assert "rumor.dynamic.test.old" not in simulation.player.known_rumor_ids


def test_info_and_action_results_are_not_labeled_as_world_by_default() -> None:
    simulation = Simulation.create_demo()

    look_result = simulation.handle_command("look")
    move_result = simulation.handle_command("go tavern")

    assert look_result.entries
    assert all(entry.kind == "system" for entry in look_result.entries)
    assert move_result.entries[0].kind == "system"
    assert any(entry.kind == "world" for entry in move_result.entries[1:])


def test_player_can_buy_from_vendor() -> None:
    simulation = Simulation.create_demo()
    starting_money = simulation.player.money
    starting_bread = simulation.player.inventory.get("bread", 0)

    result = simulation.handle_command("trade mara buy bread 1")

    assert any("buy 1 bread" in line.lower() for line in result.lines)
    assert simulation.player.money < starting_money
    assert simulation.player.inventory.get("bread", 0) == starting_bread + 1


def test_player_can_request_food_as_a_gift_when_need_is_clear() -> None:
    simulation = Simulation.create_demo()
    simulation.player.hunger = 78.0
    simulation.player.money = 0
    starting_bread = simulation.player.inventory.get("bread", 0)

    result = simulation.handle_command("trade mara ask bread 1")

    assert any("gives you 1 bread" in line.lower() for line in result.lines)
    assert simulation.player.money == 0
    assert simulation.player.inventory.get("bread", 0) == starting_bread + 1


def test_player_request_respects_npc_reserve_floor() -> None:
    simulation = Simulation.create_demo()
    simulation.player.hunger = 82.0
    simulation.npcs["npc.mara"].inventory = {"bread": 1}

    result = simulation.handle_command("trade mara ask bread 1")

    assert any("cannot spare" in line.lower() for line in result.lines)
    assert simulation.player.inventory.get("bread", 0) == 1


def test_player_repeat_food_request_hits_recent_help_buffer() -> None:
    simulation = Simulation.create_demo()
    simulation.player.hunger = 78.0
    simulation.player.money = 0
    simulation.player.inventory.clear()

    first = simulation.handle_command("trade mara ask bread 1")
    second = simulation.handle_command("trade mara ask bread 1")

    assert any("gives you 1 bread" in line.lower() for line in first.lines)
    assert any("already helped you recently" in line.lower() for line in second.lines)
    assert simulation.player.inventory.get("bread", 0) == 1


def test_recent_help_buffer_expires_after_cooldown_window() -> None:
    simulation = Simulation.create_demo()
    simulation.player.hunger = 80.0
    simulation.player.money = 0
    simulation.player.inventory.clear()

    first = simulation.handle_command("trade mara ask bread 1")

    assert any("gives you 1 bread" in line.lower() for line in first.lines)
    assert simulation._requestable_quantity(simulation.npcs["npc.mara"], simulation.player, "bread") == 0

    simulation.player.inventory.clear()
    simulation.player.hunger = 84.0
    simulation.world.tick += 36

    assert simulation._requestable_quantity(simulation.npcs["npc.mara"], simulation.player, "bread") >= 1


def test_player_can_give_items_without_payment() -> None:
    simulation = Simulation.create_demo()
    simulation.player.inventory["bread"] = 2
    starting_money = simulation.player.money
    starting_bread = simulation.npcs["npc.mara"].inventory.get("bread", 0)

    result = simulation.handle_command("trade mara give bread 1")

    assert any("give 1 bread to Mara".lower() in line.lower() for line in result.lines)
    assert simulation.player.money == starting_money
    assert simulation.player.inventory.get("bread", 0) == 1
    assert simulation.npcs["npc.mara"].inventory.get("bread", 0) == starting_bread + 1


def test_food_spoilage_reduces_player_inventory_over_time() -> None:
    simulation = Simulation.create_demo()
    simulation.world.market.items["fish"].spoilage_ticks = 24
    simulation.player.inventory["fish"] = 2

    result = simulation.advance_turn(2)

    assert simulation.player.inventory.get("fish", 0) == 1
    assert any("fish spoils in your pack" in line for line in result.lines)


def test_tool_wear_breaks_player_tool_after_repeated_field_work() -> None:
    simulation = Simulation.create_demo()
    simulation.player.location_id = "farm"
    simulation.player.inventory["tool"] = 1

    for _ in range(4):
        simulation.handle_command("work")

    assert simulation.player.inventory.get("tool", 0) == 0


def test_work_without_tool_reduces_farm_yield() -> None:
    simulation = Simulation.create_demo()
    simulation.player.location_id = "farm"
    simulation.world.weather = "clear"
    simulation.player.inventory.pop("tool", None)

    result = simulation.handle_command("work")

    assert any("gather 1 wheat" in line.lower() for line in result.lines)


def test_storage_pressure_leaves_part_of_field_yield_behind() -> None:
    simulation = Simulation.create_demo()
    simulation.player.location_id = "farm"
    simulation.world.weather = "clear"
    simulation.world.field_stress = 0.0
    simulation.player.carry_capacity = 2.0
    simulation.player.inventory = {"wheat": 2, "tool": 1}

    result = simulation.handle_command("work")

    assert any("gather 0 wheat" in line.lower() or "gather 1 wheat" in line.lower() for line in result.lines)
    assert any("leave" in line.lower() and "behind" in line.lower() for line in result.lines)


def test_baker_production_finishes_one_turn_after_batch_starts() -> None:
    simulation = Simulation.create_demo()
    hobb = simulation.npcs["npc.hobb"]
    starting_bread = hobb.inventory.get("bread", 0)
    hobb.current_intent = None

    event = simulation._perform_work(hobb)

    assert event == "Hobb starts a fresh bread batch."
    assert hobb.inventory.get("bread", 0) == starting_bread
    assert hobb.production_queue.get("bread", 0) == 2

    turn_result = simulation.advance_turn(1)

    assert any("Hobb finishes bread x2." in line for line in turn_result.lines)
    assert hobb.inventory.get("bread", 0) == starting_bread + 2
    assert hobb.production_queue.get("bread", 0) >= 0


def test_cook_production_finishes_one_turn_after_batch_starts() -> None:
    simulation = Simulation.create_demo()
    bina = simulation.npcs["npc.bina"]
    starting_stew = bina.inventory.get("stew", 0)
    bina.inventory["fish"] = 1

    event = simulation._perform_work(bina)

    assert event == "Bina starts a pot of stew."
    assert bina.inventory.get("stew", 0) == starting_stew
    assert bina.production_queue.get("stew", 0) == 1

    turn_result = simulation.advance_turn(1)

    assert any("Bina finishes stew x1." in line for line in turn_result.lines)
    assert bina.inventory.get("stew", 0) == starting_stew + 1
    assert bina.production_queue.get("stew", 0) >= 0


def test_talk_without_target_is_rejected_when_multiple_npcs_are_present() -> None:
    simulation = Simulation.create_demo()

    result = simulation.handle_command("talk")

    assert any("Choose who to talk to" in line for line in result.lines)


def test_focus_enables_targetless_follow_up_actions() -> None:
    simulation = Simulation.create_demo()
    simulation.player.location_id = "bakery"

    focus_result = simulation.handle_command("focus hobb")
    trade_result = simulation.handle_command("trade buy bread 1")

    assert any("Interaction target set to Hobb." in line for line in focus_result.lines)
    assert simulation.player.focused_npc_id == "npc.hobb"
    assert any("buy 1 bread from Hobb".lower() in line.lower() for line in trade_result.lines)


def test_trade_without_target_uses_unique_matching_stock_holder() -> None:
    simulation = Simulation.create_demo()
    simulation.player.location_id = "farm"
    simulation.npcs["npc.hobb"].location_id = "farm"

    result = simulation.handle_command("trade buy bread 1")

    assert any("buy 1 bread from Hobb".lower() in line.lower() for line in result.lines)


def test_look_at_npc_shows_tradeable_inventory() -> None:
    simulation = Simulation.create_demo()
    simulation.player.location_id = "riverside"

    result = simulation.handle_command("look toma")

    assert any("Target: Toma (fisher)" in line for line in result.lines)
    assert any("Buy (cash): fish x1" in line for line in result.lines)


def test_player_can_eat_food() -> None:
    simulation = Simulation.create_demo()
    starting_hunger = simulation.player.hunger

    result = simulation.handle_command("eat bread")

    assert any("You eat bread." in line for line in result.lines)
    assert simulation.player.hunger < starting_hunger


def test_player_can_take_best_meal_without_naming_food() -> None:
    simulation = Simulation.create_demo()
    simulation.player.inventory = {"fish": 1, "bread": 1}

    result = simulation.handle_command("meal")

    assert any("You eat bread." in line for line in result.lines)
    assert simulation.player.inventory.get("bread", 0) == 0
    assert simulation.player.inventory.get("fish", 0) == 1


def test_default_eat_command_uses_best_meal_when_item_is_omitted() -> None:
    simulation = Simulation.create_demo()
    simulation.player.inventory = {"fish": 1, "bread": 1}

    result = simulation.handle_command("eat")

    assert any("You eat bread." in line for line in result.lines)


def test_go_starts_multi_turn_travel_instead_of_teleporting() -> None:
    simulation = Simulation.create_demo()
    simulation.world.weather = "clear"

    result = simulation.handle_command("go tavern")

    assert any("You set out for Copper Cup Tavern." in line for line in result.lines)
    assert simulation.player.location_id == "square"
    assert simulation.player.travel_state.is_traveling is True
    assert simulation.player.travel_state.destination_location_id == "tavern"
    assert simulation.player.travel_state.ticks_remaining > 0


def test_heavier_load_increases_travel_eta_and_risk_budget() -> None:
    light_simulation = Simulation.create_demo()
    light_simulation.world.weather = "clear"

    heavy_simulation = Simulation.create_demo()
    heavy_simulation.world.weather = "clear"
    heavy_simulation.player.inventory["tool"] = 4
    heavy_simulation._refresh_actor_loads()

    light_simulation.handle_command("go tavern")
    heavy_simulation.handle_command("go tavern")

    assert heavy_simulation.player.travel_state.ticks_remaining > light_simulation.player.travel_state.ticks_remaining
    assert heavy_simulation.player.travel_state.risk_budget > light_simulation.player.travel_state.risk_budget


def test_next_completes_travel_and_arrives_after_eta() -> None:
    simulation = Simulation.create_demo()
    simulation.world.weather = "clear"

    simulation.handle_command("go tavern")
    result = simulation.handle_command("next 1")

    assert simulation.player.location_id == "tavern"
    assert simulation.player.travel_state.is_traveling is False
    assert any("You arrive at Copper Cup Tavern." in line for line in result.lines)



def test_storm_front_blocks_riverside_route() -> None:
    simulation = Simulation.create_demo()
    simulation.player.location_id = "farm"
    simulation.world.weather = "storm_front"

    result = simulation.handle_command("go riverside")

    assert any("unsafe" in line.lower() for line in result.lines)
    assert simulation.player.travel_state.is_traveling is False


def test_dry_wind_builds_field_stress_and_starts_harvest_shortfall_event() -> None:
    simulation = Simulation.create_demo()
    simulation.world.weather = "dry_wind"

    result = simulation.advance_turn(4)

    assert simulation.world.field_stress >= 0.55
    assert any(event.event_id == "event.farm.harvest_shortfall" for event in simulation.world.active_events)
    assert any("harvest shortfall" in line.lower() for line in result.lines)


def test_cool_rain_recovers_field_stress_and_clears_harvest_shortfall_event() -> None:
    simulation = Simulation.create_demo()
    simulation.world.weather = "dry_wind"
    simulation.advance_turn(4)
    simulation.world.weather = "cool_rain"

    result = simulation.advance_turn(2)

    assert simulation.world.field_stress <= 0.24
    assert not any(event.event_id == "event.farm.harvest_shortfall" for event in simulation.world.active_events)
    assert any("steadier yield" in line.lower() for line in result.lines)


def test_traveling_blocks_location_bound_interactions() -> None:
    simulation = Simulation.create_demo()
    simulation.world.weather = "clear"

    simulation.handle_command("go tavern")
    result = simulation.handle_command("talk neri")

    assert any("already on the road" in line.lower() for line in result.lines)


def test_sleep_recovers_more_fatigue_than_rest_when_shelter_is_better() -> None:
    square_simulation = Simulation.create_demo()
    square_simulation.player.fatigue = 60.0
    square_simulation.player.location_id = "square"
    square_simulation.handle_command("rest 1")

    shrine_simulation = Simulation.create_demo()
    shrine_simulation.player.fatigue = 60.0
    shrine_simulation.player.location_id = "shrine"
    shrine_simulation.handle_command("sleep 1")

    assert square_simulation.player.fatigue < 60.0
    assert shrine_simulation.player.fatigue < square_simulation.player.fatigue


def test_poor_shelter_sleep_stays_shallow_until_better_cover_is_found() -> None:
    farm_simulation = Simulation.create_demo()
    farm_simulation.player.fatigue = 84.0
    farm_simulation.player.location_id = "farm"

    shrine_simulation = Simulation.create_demo()
    shrine_simulation.player.fatigue = 84.0
    shrine_simulation.player.location_id = "shrine"

    farm_result = farm_simulation.handle_command("sleep 6")
    shrine_simulation.handle_command("sleep 6")

    assert any("too exposed for deep sleep" in line.lower() for line in farm_result.lines)
    assert farm_simulation.player.fatigue >= 38.0
    assert shrine_simulation.player.fatigue < farm_simulation.player.fatigue


def test_field_stress_reduces_player_farm_work_yield() -> None:
    simulation = Simulation.create_demo()
    simulation.player.location_id = "farm"
    simulation.world.field_stress = 0.72
    simulation.world.weather = "dry_wind"
    starting_wheat = simulation.player.inventory.get("wheat", 0)

    result = simulation.handle_command("work")

    assert any("gather 1 wheat" in line.lower() for line in result.lines)
    assert simulation.player.inventory.get("wheat", 0) == starting_wheat + 1


def test_player_can_work_for_gold_and_resources() -> None:
    simulation = Simulation.create_demo()

    square_money = simulation.player.money
    square_result = simulation.handle_command("work")

    assert any("earn 4 gold" in line for line in square_result.lines)
    assert simulation.player.money == square_money + 4

    simulation.player.location_id = "farm"
    simulation.world.weather = "clear"
    simulation.world.field_stress = 0.0
    simulation.player.inventory["tool"] = 1
    farm_wheat = simulation.player.inventory.get("wheat", 0)
    farm_result = simulation.handle_command("work")

    assert any("gather 2 wheat" in line for line in farm_result.lines)
    assert simulation.player.inventory.get("wheat", 0) == farm_wheat + 2


def test_snapshot_contains_serializable_runtime_state() -> None:
    simulation = Simulation.create_demo()
    simulation.set_dialogue_system_prompt("Custom system prompt for tests.")

    snapshot = simulation.snapshot()

    assert snapshot["world"]["day"] == 1
    assert snapshot["player"]["location_id"] == "square"
    assert "fatigue" in snapshot["player"]
    assert "carried_weight" in snapshot["player"]
    assert "travel_state" in snapshot["player"]
    assert "fatigue" in snapshot["npcs"]["npc.mara"]
    assert "travel_state" in snapshot["npcs"]["npc.mara"]
    assert "npc.mara" in snapshot["npcs"]
    assert "rumor.shortage.wheat" in snapshot["rumors"]
    assert "region.greenfall" in snapshot["world"]["regions"]
    assert snapshot["world"]["locations"]["square"]["region_id"] == "region.greenfall"
    assert snapshot["dialogue_system_prompt"] == "Custom system prompt for tests."


def test_player_status_surfaces_fatigue_and_load() -> None:
    simulation = Simulation.create_demo()

    status = simulation.player_status()

    assert "Fatigue:" in status
    assert "Shelter:" in status
    assert "Load:" in status
    assert "Region:" in status


def test_offscreen_regional_summaries_drift_over_time() -> None:
    simulation = Simulation.create_demo()
    before = dict(simulation.world.regions["region.hollowmarket"].stock_signals)

    simulation.advance_turn(5)

    after = simulation.world.regions["region.hollowmarket"].stock_signals
    assert after != before


def test_regional_transit_spawns_from_summary_stock_imbalance() -> None:
    simulation = Simulation.create_demo()
    simulation.world.regions["region.greenfall"].stock_signals["wheat"] = 18
    simulation.world.regions["region.hollowmarket"].stock_signals["wheat"] = 2

    simulation.advance_turn(10)

    assert any(transit.route_id == "route.greenfall.hollowmarket" for transit in simulation.world.regional_transits)


def test_regional_transit_delivery_moves_stock_between_regions() -> None:
    simulation = Simulation.create_demo()
    simulation.world.weather = "clear"
    simulation.world.regions["region.greenfall"].stock_signals["bread"] = 12
    simulation.world.regions["region.hollowmarket"].stock_signals["bread"] = 4
    simulation.world.regional_transits.append(
        RegionalTransit(
            transit_id="transit.test.delivery",
            route_id="route.greenfall.hollowmarket",
            from_region_id="region.greenfall",
            to_region_id="region.hollowmarket",
            cargo_item="bread",
            quantity=2,
            ticks_remaining=1,
        )
    )

    simulation.advance_turn(1)

    assert simulation.world.regions["region.greenfall"].stock_signals["bread"] == 10
    assert simulation.world.regions["region.hollowmarket"].stock_signals["bread"] == 6


def test_remote_regional_supply_support_lowers_local_market_price_when_routes_are_clear() -> None:
    clear_simulation = Simulation.create_demo()
    storm_simulation = Simulation.create_demo()

    for simulation in (clear_simulation, storm_simulation):
        simulation.player.inventory.clear()
        for npc in simulation.npcs.values():
            npc.inventory.clear()
            npc.production_queue.clear()
        simulation.world.regions["region.greenfall"].stock_signals["bread"] = 0
        simulation.world.regions["region.stonewatch"].stock_signals["bread"] = 0
        simulation.world.regions["region.hollowmarket"].stock_signals["bread"] = 20

    clear_simulation.world.weather = "clear"
    clear_simulation._refresh_market_snapshot()
    storm_simulation.world.weather = "storm_front"
    storm_simulation._refresh_market_snapshot()

    assert clear_simulation.world.market.items["bread"].stock > storm_simulation.world.market.items["bread"].stock
    assert clear_simulation.world.market.items["bread"].current_price < storm_simulation.world.market.items["bread"].current_price


def test_regional_transit_delivery_into_anchor_region_reduces_market_bread_price() -> None:
    simulation = Simulation.create_demo()
    simulation.player.inventory.clear()
    for npc in simulation.npcs.values():
        npc.inventory.clear()
        npc.production_queue.clear()
    simulation.world.weather = "clear"
    simulation.world.regions["region.greenfall"].stock_signals["bread"] = 0
    simulation.world.regions["region.hollowmarket"].stock_signals["bread"] = 3

    simulation._refresh_market_snapshot()
    price_before = simulation.world.market.items["bread"].current_price
    stock_before = simulation.world.market.items["bread"].stock

    simulation._deliver_regional_transit(
        RegionalTransit(
            transit_id="transit.test.anchor_delivery",
            route_id="route.greenfall.hollowmarket",
            from_region_id="region.hollowmarket",
            to_region_id="region.greenfall",
            cargo_item="bread",
            quantity=3,
            ticks_remaining=0,
        )
    )
    simulation._refresh_market_snapshot()

    assert simulation.world.market.items["bread"].stock > stock_before
    assert simulation.world.market.items["bread"].current_price < price_before


def test_route_pressure_slows_regional_transit_progress() -> None:
    clear_simulation = Simulation.create_demo()
    clear_simulation.world.regional_transits.append(
        RegionalTransit(
            transit_id="transit.clear",
            route_id="route.greenfall.hollowmarket",
            from_region_id="region.greenfall",
            to_region_id="region.hollowmarket",
            cargo_item="bread",
            quantity=1,
            ticks_remaining=96,
        )
    )
    clear_simulation.world.weather = "clear"
    clear_simulation.advance_turn(1)
    clear_remaining = clear_simulation.world.regional_transits[0].ticks_remaining

    storm_simulation = Simulation.create_demo()
    storm_simulation.world.regional_transits.append(
        RegionalTransit(
            transit_id="transit.storm",
            route_id="route.greenfall.hollowmarket",
            from_region_id="region.greenfall",
            to_region_id="region.hollowmarket",
            cargo_item="bread",
            quantity=1,
            ticks_remaining=96,
        )
    )
    storm_simulation.world.weather = "storm_front"
    storm_simulation.advance_turn(1)
    storm_remaining = storm_simulation.world.regional_transits[0].ticks_remaining

    assert storm_remaining > clear_remaining


def test_regional_route_delay_event_appears_under_storm_front() -> None:
    simulation = Simulation.create_demo()
    simulation.world.weather = "storm_front"

    simulation.advance_turn(1)
    result = simulation.handle_command("regions")

    assert any(event.event_type == "route_delay" for event in simulation.world.active_events)
    assert any("caravans are arriving late" in line for line in result.lines)


def test_regional_travel_eta_rises_when_route_pressure_is_high() -> None:
    clear_simulation = Simulation.create_demo()
    clear_simulation.world.weather = "clear"
    clear_simulation.handle_command("travel-region hollow")
    clear_eta = clear_simulation.player.travel_state.ticks_remaining

    storm_simulation = Simulation.create_demo()
    storm_simulation.world.weather = "storm_front"
    storm_simulation.handle_command("travel-region hollow")
    storm_eta = storm_simulation.player.travel_state.ticks_remaining

    assert storm_eta > clear_eta


def test_regional_travel_progress_applies_hunger_and_fatigue_before_arrival() -> None:
    simulation = Simulation.create_demo()
    simulation.world.weather = "clear"
    simulation.player.hunger = 18.0
    simulation.player.fatigue = 12.0

    simulation.handle_command("travel-region hollow")
    start_ticks = simulation.player.travel_state.ticks_remaining
    result = simulation.handle_command("next 1")

    assert simulation.player.location_id == "square"
    assert simulation.player.travel_state.is_traveling is True
    assert simulation.player.travel_state.ticks_remaining < start_ticks
    assert simulation.player.hunger > 18.0
    assert simulation.player.fatigue > 12.0
    assert any("keep moving toward" in line.lower() for line in result.lines)


def test_low_offscreen_food_stock_spawns_regional_summary_rumor() -> None:
    simulation = Simulation.create_demo()
    stonewatch = simulation.world.regions["region.stonewatch"]
    stonewatch.stock_signals["bread"] = 1
    stonewatch.stock_signals["wheat"] = 1
    stonewatch.stock_signals["fish"] = 0

    simulation.advance_turn(12)

    assert any("Stonewatch Outpost" in rumor.content for rumor in simulation.rumors.values())


def test_route_delay_spawns_regional_delay_rumor() -> None:
    simulation = Simulation.create_demo()
    simulation.world.weather = "storm_front"

    simulation.advance_turn(6)

    assert any("road toward" in rumor.content and "dragging under the storm front" in rumor.content for rumor in simulation.rumors.values())


def test_visible_world_events_hide_remote_route_delay_after_region_travel() -> None:
    simulation = Simulation.create_demo()
    simulation.world.weather = "storm_front"

    simulation.handle_command("travel-region hollow")
    while simulation.player.travel_state.is_traveling:
        simulation.handle_command("next 1")
    simulation.advance_turn(1)

    visible_route_ids = {event.route_id for event in simulation._visible_world_events_for_player() if event.route_id is not None}

    assert "route.greenfall.hollowmarket" in visible_route_ids
    assert "route.greenfall.stonewatch" not in visible_route_ids


def test_visible_world_events_hide_remote_local_region_events() -> None:
    simulation = Simulation.create_demo()
    simulation.world.active_events.append(
        WorldEvent(
            event_id="event.test.remote",
            event_type="test_remote",
            summary="Remote test event.",
            start_tick=simulation.world.tick,
            region_id="region.greenfall",
            location_id="farm",
        )
    )

    simulation.handle_command("travel-region hollow")
    while simulation.player.travel_state.is_traveling:
        simulation.handle_command("next 1")

    visible_event_ids = {event.event_id for event in simulation._visible_world_events_for_player()}

    assert "event.test.remote" not in visible_event_ids


def test_regions_command_lists_current_region_and_routes() -> None:
    simulation = Simulation.create_demo()

    result = simulation.handle_command("regions")

    assert any("Greenfall Village [current]" in line for line in result.lines)
    assert any("Hollow Market" in line for line in result.lines)
    assert any("Routes:" in line for line in result.lines)


def test_player_can_travel_between_regions_via_anchor_locations() -> None:
    simulation = Simulation.create_demo()
    simulation.world.weather = "clear"

    start = simulation.handle_command("travel-region hollow")
    while simulation.player.travel_state.is_traveling:
        simulation.handle_command("next 1")

    assert any("You set out for Hollow Market." in line for line in start.lines)
    assert simulation.player.location_id == "hollowmarket_gate"
    assert simulation.current_region() is not None
    assert simulation.current_region().region_id == "region.hollowmarket"


def test_vendor_with_food_eats_instead_of_trying_to_trade_with_self() -> None:
    simulation = Simulation.create_demo()
    hobb = simulation.npcs["npc.hobb"]
    hobb.location_id = "farm"
    hobb.hunger = 54.0
    hobb.inventory = {"bread": 4}

    simulation.advance_turn(1)

    assert hobb.current_intent is not None
    assert hobb.current_intent.intent_type.value == "eat"
    assert hobb.inventory.get("bread", 0) == 3


def test_hungry_npc_buys_affordable_food_instead_of_failing_on_unaffordable_best_item() -> None:
    simulation = Simulation.create_demo()
    iva = simulation.npcs["npc.iva"]
    iva.inventory.clear()
    iva.hunger = 70.0
    iva.money = 6

    simulation.advance_turn(1)

    assert iva.current_intent is not None
    assert iva.current_intent.intent_type.value == "trade"
    assert sum(iva.inventory.get(item, 0) for item in ("stew", "bread", "fish", "wheat")) == 1
    assert iva.money <= 6


def test_broke_service_npc_can_work_back_into_food_loop() -> None:
    simulation = Simulation.create_demo()
    serin = simulation.npcs["npc.serin"]
    serin.inventory.clear()
    serin.hunger = 70.0
    serin.money = 0

    simulation.advance_turn(1)
    assert serin.current_intent is not None
    assert serin.current_intent.intent_type.value == "move"

    for _ in range(5):
        simulation.advance_turn(1)
        if sum(serin.inventory.get(item, 0) for item in ("stew", "bread", "fish", "wheat")) >= 1:
            break

    assert sum(serin.inventory.get(item, 0) for item in ("stew", "bread", "fish", "wheat")) >= 1


def test_cash_buy_respects_vendor_reserve_floor() -> None:
    simulation = Simulation.create_demo()
    simulation.player.location_id = "bakery"
    hobb = simulation.npcs["npc.hobb"]
    hobb.inventory = {"bread": 4}

    result = simulation.handle_command("trade hobb buy bread 1")

    assert any("does not have enough bread" in line.lower() for line in result.lines)
    assert hobb.inventory.get("bread", 0) == 4
