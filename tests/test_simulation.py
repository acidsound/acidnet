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


def test_snapshot_contains_serializable_runtime_state() -> None:
    simulation = Simulation.create_demo()

    snapshot = simulation.snapshot()

    assert snapshot["world"]["day"] == 1
    assert snapshot["player"]["location_id"] == "square"
    assert "npc.mara" in snapshot["npcs"]
    assert "rumor.shortage.wheat" in snapshot["rumors"]
