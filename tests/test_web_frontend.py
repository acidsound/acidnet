from pathlib import Path

from acidnet.frontend.web_app import WebSimulationRuntime


def build_runtime(name: str) -> WebSimulationRuntime:
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    db_path = artifact_dir / f"{name}.sqlite"
    if db_path.exists():
        db_path.unlink()
    return WebSimulationRuntime(
        db_path=db_path,
        persist=False,
        event_log_path=None,
        prepare_dialogue=False,
    )


def test_scene_payload_exposes_player_view_contract() -> None:
    runtime = build_runtime("web_frontend_scene_payload_test")
    try:
        state = runtime.scene_payload()
    finally:
        runtime.close()

    assert state["world"]["location_id"] == "square"
    assert state["player"]["location_id"] == "square"
    assert "field_stress" in state["world"]
    assert "active_events" in state["world"]
    assert state["world"]["region_id"] == "region.greenfall"
    assert state["world"]["region_name"] == "Greenfall Village"
    assert any(node["location_id"] == "square" and node["is_player_here"] for node in state["scene"]["map_nodes"])
    assert any(node["is_current_region"] for node in state["scene"]["regional_nodes"])
    assert all("stock_signals" in node for node in state["scene"]["regional_nodes"])
    assert state["scene"]["regional_routes"]
    assert any(action["command"] == "look" for action in state["actions"]["common"])
    assert any(action["command"] == "meal" for action in state["actions"]["common"])
    assert "people" in state["scene"]
    assert all("ask_options" in person and "give_options" in person for person in state["scene"]["people"])
    assert isinstance(state["help"], list)


def test_run_command_updates_target_and_recent_events() -> None:
    runtime = build_runtime("web_frontend_target_test")
    try:
        result = runtime.run_command("focus mara")
    finally:
        runtime.close()

    assert result["ok"] is True
    assert result["state"]["player"]["focused_npc_id"] == "npc.mara"
    assert result["state"]["target"]["name"] == "Mara"
    assert any(event["kind"] == "input" and "focus mara" in event["text"] for event in result["state"]["recent_events"])


def test_run_command_returns_turn_entries() -> None:
    runtime = build_runtime("web_frontend_command_test")
    try:
        result = runtime.run_command("look")
    finally:
        runtime.close()

    assert result["ok"] is True
    assert result["entries"]
    assert any(entry["text"].startswith("You are at") for entry in result["entries"])


def test_prompt_settings_round_trip_through_runtime() -> None:
    runtime = build_runtime("web_frontend_prompt_test")
    try:
        original = runtime.dialogue_prompt_payload()
        saved = runtime.save_dialogue_system_prompt("You are terse.\nStay grounded in the village.")
        reset = runtime.reset_dialogue_system_prompt()
    finally:
        runtime.close()

    assert original["current_prompt"]
    assert saved["ok"] is True
    assert saved["prompt"]["current_prompt"] == "You are terse.\nStay grounded in the village."
    assert reset["ok"] is True
    assert reset["prompt"]["current_prompt"] == reset["prompt"]["default_prompt"]


def test_scene_payload_hides_people_during_travel() -> None:
    runtime = build_runtime("web_frontend_travel_state_test")
    try:
        runtime.simulation.world.weather = "clear"
        runtime.run_command("go tavern")
        state = runtime.scene_payload()
    finally:
        runtime.close()

    assert state["player"]["travel_state"]["is_traveling"] is True
    assert state["scene"]["people"] == []
    assert "On the road to" in state["world"]["location_name"]


def test_scene_payload_exposes_active_shock_state() -> None:
    runtime = build_runtime("web_frontend_shock_state_test")
    try:
        runtime.simulation.world.weather = "dry_wind"
        runtime.simulation.advance_turn(4)
        state = runtime.scene_payload()
    finally:
        runtime.close()

    assert state["world"]["field_stress"] >= 0.55
    assert any(event["event_type"] == "harvest_shortfall" for event in state["world"]["active_events"])


def test_scene_payload_updates_region_after_inter_region_travel() -> None:
    runtime = build_runtime("web_frontend_region_travel_test")
    try:
        runtime.simulation.world.weather = "clear"
        runtime.run_command("travel-region hollow")
        while runtime.simulation.player.travel_state.is_traveling:
            runtime.run_command("next 1")
        state = runtime.scene_payload()
    finally:
        runtime.close()

    assert state["world"]["region_id"] == "region.hollowmarket"
    assert state["world"]["region_name"] == "Hollow Market"
