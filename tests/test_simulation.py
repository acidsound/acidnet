from acidnet.engine import Simulation


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


def test_player_can_say_freeform_message_to_npc() -> None:
    simulation = Simulation.create_demo()

    result = simulation.handle_command("say neri Have you heard any useful rumors today?")

    assert any("dry wind" in line.lower() for line in result.lines)
    assert simulation.player.known_rumor_ids
    assert result.entries[0].kind == "npc"
    assert result.entries[0].text.startswith("Neri:")
    assert any(entry.kind == "world" for entry in result.entries[1:])


def test_heuristic_dialogue_honors_korean_language_request_in_system_prompt() -> None:
    simulation = Simulation.create_demo(dialogue_backend="heuristic")
    simulation.set_dialogue_system_prompt(
        "You are a village NPC. Respond in exactly one language. That language must be Korean. 한국어만 사용해."
    )

    text = simulation.probe_npc_dialogue("npc.neri", interaction_mode="talk", player_prompt="안녕?")

    assert any("\uac00" <= char <= "\ud7a3" for char in text)
    assert "Stories travel faster than thread in this village." not in text


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
    assert any("Buy (cash): fish x3" in line for line in result.lines)


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


def test_player_can_work_for_gold_and_resources() -> None:
    simulation = Simulation.create_demo()

    square_money = simulation.player.money
    square_result = simulation.handle_command("work")

    assert any("earn 4 gold" in line for line in square_result.lines)
    assert simulation.player.money == square_money + 4

    simulation.player.location_id = "farm"
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
    assert snapshot["dialogue_system_prompt"] == "Custom system prompt for tests."


def test_player_status_surfaces_fatigue_and_load() -> None:
    simulation = Simulation.create_demo()

    status = simulation.player_status()

    assert "Fatigue:" in status
    assert "Load:" in status


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
    assert iva.inventory.get("bread", 0) == 1
    assert iva.money == 0


def test_broke_service_npc_can_work_back_into_food_loop() -> None:
    simulation = Simulation.create_demo()
    serin = simulation.npcs["npc.serin"]
    serin.inventory.clear()
    serin.hunger = 70.0
    serin.money = 0

    simulation.advance_turn(1)
    assert serin.current_intent is not None
    assert serin.current_intent.intent_type.value == "work"
    assert serin.money >= 6

    simulation.advance_turn(1)
    assert serin.current_intent is not None
    assert serin.current_intent.intent_type.value in {"move", "trade"}

    for _ in range(4):
        if serin.inventory.get("bread", 0) >= 1:
            break
        simulation.advance_turn(1)

    assert serin.inventory.get("bread", 0) == 1
