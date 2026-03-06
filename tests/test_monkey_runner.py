from acidnet.engine import Simulation
from acidnet.eval import SimulationMonkeyRunner


def test_monkey_runner_executes_deterministic_steps_without_breaking_invariants() -> None:
    simulation = Simulation.create_demo()
    runner = SimulationMonkeyRunner(simulation, seed=13)

    report = runner.run_steps(25)

    assert report.steps_executed == 25
    assert report.role == "wanderer"
    assert report.final_player_location in simulation.world.locations
    assert 0.0 <= report.final_player_hunger <= 100.0
    assert 0.0 <= report.final_player_fatigue <= 100.0
    assert 0.0 <= report.score <= 1.0
    assert isinstance(report.goal_counts, dict)
    assert isinstance(report.command_counts, dict)
    assert isinstance(report.failure_reasons, list)
    assert report.steps
    assert all(step.goal for step in report.steps)
    assert all(step.command for step in report.steps)
    assert all(step.entries for step in report.steps)


def test_survivor_monkey_prefers_food_when_hungry() -> None:
    simulation = Simulation.create_demo()
    simulation.player.hunger = 80.0
    simulation.player.inventory["bread"] = 1
    runner = SimulationMonkeyRunner(simulation, seed=5, role="survivor")

    goal, command = runner.choose_action()

    assert goal == "eat_available_food"
    assert command == "meal"


def test_altruist_monkey_prefers_gifting_food_to_hungry_npc() -> None:
    simulation = Simulation.create_demo()
    simulation.player.inventory["bread"] = 2
    simulation.player.hunger = 10.0
    simulation.npcs["npc.mara"].hunger = 80.0
    runner = SimulationMonkeyRunner(simulation, seed=5, role="altruist")

    goal, command = runner.choose_action()

    assert goal == "share_food"
    assert command == "trade Mara give bread 1"


def test_rumor_verifier_monkey_targets_unasked_npc_rumors_first() -> None:
    simulation = Simulation.create_demo()
    runner = SimulationMonkeyRunner(simulation, seed=5, role="rumor_verifier")

    goal, command = runner.choose_action()

    assert goal == "collect_rumor"
    assert command.startswith("ask ")
    assert command.endswith(" rumor")


def test_survivor_monkey_report_records_goal_counts_and_successful_score() -> None:
    simulation = Simulation.create_demo()
    simulation.player.hunger = 80.0
    simulation.player.inventory["bread"] = 1
    runner = SimulationMonkeyRunner(simulation, seed=5, role="survivor")

    report = runner.run_steps(1)

    assert report.goal_counts.get("eat_available_food") == 1
    assert report.command_counts.get("meal") == 1
    assert report.score > 0.5
    assert "survivor_failed_to_stabilize_hunger" not in report.failure_reasons


def test_shock_observer_monkey_tracks_field_stress_and_events() -> None:
    simulation = Simulation.create_demo()
    simulation.world.weather = "dry_wind"
    runner = SimulationMonkeyRunner(simulation, seed=5, role="shock_observer")

    report = runner.run_steps(12)

    assert report.peak_field_stress >= 0.45
    assert "harvest_shortfall" in report.observed_event_types
    assert report.goal_counts.get("reach_shock_site", 0) >= 1
    assert "shock_observer_missed_world_event" not in report.failure_reasons
