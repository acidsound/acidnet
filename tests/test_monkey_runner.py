from collections import Counter

from acidnet.eval import SimulationMonkeyRunner
from acidnet.simulator import Simulation


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


def test_monkey_runner_replays_same_seed_and_role_deterministically() -> None:
    first_simulation = Simulation.create_demo()
    second_simulation = Simulation.create_demo()

    first_report = SimulationMonkeyRunner(first_simulation, seed=13, role="wanderer").run_steps(10)
    second_report = SimulationMonkeyRunner(second_simulation, seed=13, role="wanderer").run_steps(10)

    assert [step.goal for step in first_report.steps] == [step.goal for step in second_report.steps]
    assert [step.command for step in first_report.steps] == [step.command for step in second_report.steps]
    assert first_report.final_player_location == second_report.final_player_location
    assert first_report.final_player_hunger == second_report.final_player_hunger
    assert first_report.final_player_fatigue == second_report.final_player_fatigue
    assert first_report.failure_reasons == second_report.failure_reasons


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


def test_hoarder_monkey_triggers_storage_pressure_when_capacity_is_low() -> None:
    simulation = Simulation.create_demo()
    simulation.player.location_id = "farm"
    simulation.player.carry_capacity = 2.0
    simulation.player.inventory = {"wheat": 2, "tool": 1}
    runner = SimulationMonkeyRunner(simulation, seed=5, role="hoarder")

    report = runner.run_steps(3)

    assert report.storage_pressure_events >= 1
    assert report.peak_load_ratio >= 0.85
    assert "hoarder_never_triggered_storage_pressure" not in report.failure_reasons


def test_exploit_observer_monkey_heads_to_bakery_before_probe() -> None:
    simulation = Simulation.create_demo()
    runner = SimulationMonkeyRunner(simulation, seed=5, role="exploit_observer")

    goal, command = runner.choose_action()

    assert goal == "reach_bakery_vendor"
    assert command == "go bakery"


def test_exploit_observer_monkey_forces_buy_refusal_at_bakery_reserve_floor() -> None:
    simulation = Simulation.create_demo()
    simulation.player.location_id = "bakery"
    hobb = simulation.npcs["npc.hobb"]
    hobb.inventory = {"bread": 4}
    runner = SimulationMonkeyRunner(simulation, seed=5, role="exploit_observer")
    runner.observed_constrained_vendor_ids.add("npc.hobb")

    goal, command = runner.choose_action()

    assert goal == "force_vendor_buy_refusal"
    assert command == "trade Hobb buy bread 1"


def test_exploit_observer_monkey_report_observes_reserved_stock_and_buy_probe() -> None:
    simulation = Simulation.create_demo()
    simulation.player.location_id = "bakery"
    runner = SimulationMonkeyRunner(simulation, seed=5, role="exploit_observer")

    report = runner.run_steps(2)

    assert "npc.hobb" in report.observed_constrained_vendor_ids
    assert report.successful_exchange_modes.get("buy", 0) >= 1
    assert "exploit_observer_never_observed_reserved_stock" not in report.failure_reasons
    assert "exploit_observer_never_probed_vendor" not in report.failure_reasons


def test_exploit_observer_monkey_hits_repeat_request_refusal_when_hungry() -> None:
    simulation = Simulation.create_demo()
    simulation.player.location_id = "square"
    simulation.player.hunger = 78.0
    simulation.player.money = 0
    simulation.player.inventory.clear()
    runner = SimulationMonkeyRunner(simulation, seed=5, role="exploit_observer")
    runner.observed_constrained_vendor_ids.add("npc.hobb")
    runner.successful_exchange_modes["buy"] = 2
    runner.reserve_refusal_npc_ids.add("npc.hobb")

    report = runner.run_steps(2)

    assert report.goal_counts.get("probe_repeat_food_request", 0) == 1
    assert report.goal_counts.get("force_repeat_request_refusal", 0) == 1
    assert report.successful_exchange_modes.get("ask", 0) == 1
    assert "request_cooldown_refusal" in report.observed_exchange_refusal_types


def test_regional_observer_monkey_tracks_market_shift_from_route_pressure() -> None:
    simulation = Simulation.create_demo()
    simulation.world.weather = "storm_front"
    runner = SimulationMonkeyRunner(simulation, seed=5, role="regional_observer")

    report = runner.run_steps(12)

    assert len(report.visited_regions) >= 2
    assert report.observed_route_delay_ids
    assert report.peak_regional_transits >= 1
    assert report.market_price_shift_events >= 1
    assert report.observed_market_price_items
    assert "regional_observer_never_left_home_region" not in report.failure_reasons
    assert "regional_observer_missed_route_delay" not in report.failure_reasons
    assert "regional_observer_never_saw_transit_flow" not in report.failure_reasons
    assert "regional_observer_missed_market_shift" not in report.failure_reasons


def test_downstream_observer_monkey_tracks_regional_stock_and_market_shift() -> None:
    simulation = Simulation.create_demo()
    simulation.world.weather = "storm_front"
    runner = SimulationMonkeyRunner(simulation, seed=5, role="downstream_observer")

    report = runner.run_steps(12)

    assert report.goal_counts.get("inspect_supply_chain", 0) >= 1
    assert report.command_counts.get("regions", 0) >= 1
    assert report.observed_route_delay_ids
    assert report.peak_regional_transits >= 1
    assert report.regional_stock_shift_events >= 1
    assert report.observed_regional_stock_regions
    assert report.observed_regional_stock_items
    assert report.market_price_shift_events >= 1
    assert report.transit_after_route_delay is True
    assert report.regional_stock_shift_after_transit is True
    assert report.market_pressure_after_stock_shift is True
    assert report.downstream_response_chain_complete is True
    assert report.downstream_response_chain_lag_steps is not None
    assert report.downstream_response_chain_lag_steps <= 4
    assert report.downstream_response_items
    assert report.observed_market_flow_items
    assert report.market_flow_after_transit is True
    assert report.downstream_market_flow_step is not None
    assert report.downstream_semantic_items
    assert set(report.downstream_response_items) == (
        set(report.observed_regional_stock_items) & set(report.observed_market_price_items)
    )
    assert set(report.downstream_semantic_items) == (
        set(report.observed_regional_stock_items)
        & set(report.observed_market_flow_items)
    )
    assert "downstream_observer_never_inspected_supply_chain" not in report.failure_reasons
    assert "downstream_observer_missed_route_delay" not in report.failure_reasons
    assert "downstream_observer_never_saw_transit_flow" not in report.failure_reasons
    assert "downstream_observer_missed_regional_stock_shift" not in report.failure_reasons
    assert "downstream_observer_missed_market_shift" not in report.failure_reasons
    assert "downstream_observer_missed_response_chain" not in report.failure_reasons
    assert "downstream_observer_missing_item_overlap" not in report.failure_reasons
    assert "downstream_observer_slow_response_chain" not in report.failure_reasons
    assert "downstream_observer_missing_market_flow_semantics" not in report.failure_reasons


def test_downstream_observer_failure_reason_flags_missing_response_chain() -> None:
    simulation = Simulation.create_demo()
    runner = SimulationMonkeyRunner(simulation, seed=5, role="downstream_observer")
    runner.observed_route_delay_ids.add("route.synthetic")
    runner.route_delay_seen_for_downstream_chain = True
    runner.peak_regional_transits = 1
    runner.regional_stock_shift_events = 1
    runner.market_price_shift_events = 1

    failures = runner._collect_failure_reasons([], Counter(), Counter({"regions": 1}))

    assert "downstream_observer_missed_response_chain" in failures


def test_downstream_observer_failure_reason_flags_missing_item_overlap() -> None:
    simulation = Simulation.create_demo()
    runner = SimulationMonkeyRunner(simulation, seed=5, role="downstream_observer")
    runner.observed_route_delay_ids.add("route.synthetic")
    runner.route_delay_seen_for_downstream_chain = True
    runner.peak_regional_transits = 1
    runner.regional_stock_shift_events = 1
    runner.market_price_shift_events = 1
    runner.transit_after_route_delay = True
    runner.regional_stock_shift_after_transit = True
    runner.market_pressure_after_stock_shift = True
    runner.observed_regional_stock_items.add("bread")
    runner.observed_market_price_items.add("tool")

    failures = runner._collect_failure_reasons([], Counter(), Counter({"regions": 1}))

    assert "downstream_observer_missing_item_overlap" in failures


def test_downstream_observer_failure_reason_flags_slow_response_chain() -> None:
    simulation = Simulation.create_demo()
    runner = SimulationMonkeyRunner(simulation, seed=5, role="downstream_observer")
    runner.observed_route_delay_ids.add("route.synthetic")
    runner.route_delay_seen_for_downstream_chain = True
    runner.downstream_route_delay_step = 0
    runner.peak_regional_transits = 1
    runner.transit_after_route_delay = True
    runner.downstream_transit_step = 1
    runner.regional_stock_shift_events = 1
    runner.regional_stock_shift_after_transit = True
    runner.downstream_regional_stock_step = 2
    runner.market_price_shift_events = 1
    runner.market_pressure_after_stock_shift = True
    runner.downstream_market_pressure_step = 6
    runner.observed_regional_stock_items.add("fish")
    runner.observed_market_price_items.add("fish")

    failures = runner._collect_failure_reasons([], Counter(), Counter({"regions": 1}))

    assert "downstream_observer_slow_response_chain" in failures


def test_downstream_observer_failure_reason_flags_missing_market_flow_semantics() -> None:
    simulation = Simulation.create_demo()
    runner = SimulationMonkeyRunner(simulation, seed=5, role="downstream_observer")
    runner.observed_route_delay_ids.add("route.synthetic")
    runner.route_delay_seen_for_downstream_chain = True
    runner.downstream_route_delay_step = 0
    runner.peak_regional_transits = 1
    runner.transit_after_route_delay = True
    runner.downstream_transit_step = 1
    runner.regional_stock_shift_events = 1
    runner.regional_stock_shift_after_transit = True
    runner.downstream_regional_stock_step = 2
    runner.market_price_shift_events = 1
    runner.market_pressure_after_stock_shift = True
    runner.downstream_market_pressure_step = 3
    runner.observed_regional_stock_items.add("bread")
    runner.observed_market_price_items.add("bread")

    failures = runner._collect_failure_reasons([], Counter(), Counter({"regions": 1}))

    assert "downstream_observer_missing_market_flow_semantics" in failures
