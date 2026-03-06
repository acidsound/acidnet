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


def test_player_can_eat_food() -> None:
    simulation = Simulation.create_demo()
    starting_hunger = simulation.player.hunger

    result = simulation.handle_command("eat bread")

    assert any("You eat bread." in line for line in result.lines)
    assert simulation.player.hunger < starting_hunger


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

    snapshot = simulation.snapshot()

    assert snapshot["world"]["day"] == 1
    assert snapshot["player"]["location_id"] == "square"
    assert "npc.mara" in snapshot["npcs"]
    assert "rumor.shortage.wheat" in snapshot["rumors"]


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

    simulation.advance_turn(1)
    assert serin.inventory.get("bread", 0) == 1
