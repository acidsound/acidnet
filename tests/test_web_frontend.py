import json
import threading
from pathlib import Path
from urllib import request

from acidnet.frontend.web_app import AcidNetWebServer, WebSimulationRuntime
from acidnet.llm import DialogueContext, DialogueResult
from acidnet.simulator import Simulation, build_demo_setup


class RecordingDialogueAdapter:
    def __init__(self) -> None:
        self.contexts: list[DialogueContext] = []

    def prepare(self) -> str | None:
        return "ready"

    def generate(self, context: DialogueContext) -> DialogueResult:
        self.contexts.append(context.model_copy(deep=True))
        return DialogueResult(text=f"{context.npc.name} sees: {context.player_prompt}", adapter_name="recording")


def build_recording_runtime(name: str, system_prompt: str) -> tuple[WebSimulationRuntime, RecordingDialogueAdapter]:
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    db_path = artifact_dir / f"{name}.sqlite"
    if db_path.exists():
        db_path.unlink()
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
    runtime = WebSimulationRuntime(
        db_path=db_path,
        persist=False,
        event_log_path=None,
        prepare_dialogue=False,
        simulation=simulation,
    )
    return runtime, adapter


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


def post_json(base_url: str, path: str, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base_url}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(base_url: str, path: str) -> dict[str, object]:
    with request.urlopen(f"{base_url}{path}") as response:
        return json.loads(response.read().decode("utf-8"))


def start_test_server(runtime: WebSimulationRuntime) -> tuple[AcidNetWebServer, threading.Thread, str]:
    server = AcidNetWebServer(("127.0.0.1", 0), runtime)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def stop_test_server(server: AcidNetWebServer, thread: threading.Thread, runtime: WebSimulationRuntime) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
    runtime.close()


def test_scene_payload_exposes_player_view_contract() -> None:
    runtime = build_runtime("web_frontend_scene_payload_test")
    try:
        state = runtime.scene_payload()
    finally:
        runtime.close()

    assert state["world"]["location_id"] == "square"
    assert state["player"]["location_id"] == "square"
    assert "field_stress" in state["world"]
    assert "scarcity_index" in state["world"]
    assert "market_prices" in state["world"]
    assert "bread" in state["world"]["market_prices"]
    assert "active_events" in state["world"]
    assert state["world"]["region_id"] == "region.greenfall"
    assert state["world"]["region_name"] == "Greenfall Village"
    assert any(node["location_id"] == "square" and node["is_player_here"] for node in state["scene"]["map_nodes"])
    assert any(node["location_id"] == "hollowmarket_gate" and node["move_command"] == "travel-region Hollow Market" for node in state["scene"]["map_nodes"])
    assert any(node["is_current_region"] for node in state["scene"]["regional_nodes"])
    assert all("stock_signals" in node for node in state["scene"]["regional_nodes"])
    assert state["scene"]["regional_routes"]
    assert state["scene"]["map_edges"]
    assert state["scene"]["route_preview"]
    assert any(preview["command"] == "go tavern" for preview in state["scene"]["route_preview"])
    assert any(preview["command"] == "travel-region Hollow Market" for preview in state["scene"]["route_preview"])
    assert any(edge["kind"] == "local" for edge in state["scene"]["map_edges"])
    assert any(edge["kind"] == "regional" for edge in state["scene"]["map_edges"])
    assert all("transit_count" in route for route in state["scene"]["regional_routes"])
    assert any(action["command"] == "look" for action in state["actions"]["common"])
    assert any(action["command"] == "meal" for action in state["actions"]["common"])
    assert any(action["command"] == "go tavern" for action in state["actions"]["travel"])
    assert any(action["command"] == "travel-region Hollow Market" for action in state["actions"]["travel"])
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


def test_run_command_forwards_system_prompt_and_player_prompt_for_say() -> None:
    runtime, adapter = build_recording_runtime(
        "web_frontend_recording_say_test",
        "Stay grounded. Reply as exactly one NPC.",
    )
    try:
        result = runtime.run_command("say neri Where did you come from?")
    finally:
        runtime.close()

    assert result["ok"] is True
    assert adapter.contexts
    assert adapter.contexts[-1].system_prompt == "Stay grounded. Reply as exactly one NPC."
    assert adapter.contexts[-1].interaction_mode == "direct_say"
    assert adapter.contexts[-1].player_prompt == "Where did you come from?"


def test_run_command_forwards_system_prompt_and_player_prompt_for_ask_rumor() -> None:
    runtime, adapter = build_recording_runtime(
        "web_frontend_recording_rumor_test",
        "Stay grounded. Reply as exactly one NPC.",
    )
    try:
        result = runtime.run_command("ask neri rumor")
    finally:
        runtime.close()

    assert result["ok"] is True
    assert adapter.contexts
    assert adapter.contexts[-1].system_prompt == "Stay grounded. Reply as exactly one NPC."
    assert adapter.contexts[-1].interaction_mode == "rumor_request"
    assert adapter.contexts[-1].player_prompt == "Have you heard any useful rumors?"


def test_api_command_forwards_system_prompt_and_player_prompt_for_say() -> None:
    runtime, adapter = build_recording_runtime(
        "web_frontend_http_recording_say_test",
        "Stay grounded. Reply as exactly one NPC.",
    )
    server, thread, base_url = start_test_server(runtime)
    try:
        result = post_json(base_url, "/api/command", {"command": "say neri Where did you come from?"})
        prompt_payload = get_json(base_url, "/api/dialogue-prompt")
    finally:
        stop_test_server(server, thread, runtime)

    assert result["ok"] is True
    assert adapter.contexts
    assert adapter.contexts[-1].system_prompt == "Stay grounded. Reply as exactly one NPC."
    assert adapter.contexts[-1].interaction_mode == "direct_say"
    assert adapter.contexts[-1].player_prompt == "Where did you come from?"
    assert prompt_payload["current_prompt"] == "Stay grounded. Reply as exactly one NPC."


def test_api_command_forwards_system_prompt_and_player_prompt_for_ask_rumor() -> None:
    runtime, adapter = build_recording_runtime(
        "web_frontend_http_recording_rumor_test",
        "Stay grounded. Reply as exactly one NPC.",
    )
    server, thread, base_url = start_test_server(runtime)
    try:
        result = post_json(base_url, "/api/command", {"command": "ask neri rumor"})
    finally:
        stop_test_server(server, thread, runtime)

    assert result["ok"] is True
    assert adapter.contexts
    assert adapter.contexts[-1].system_prompt == "Stay grounded. Reply as exactly one NPC."
    assert adapter.contexts[-1].interaction_mode == "rumor_request"
    assert adapter.contexts[-1].player_prompt == "Have you heard any useful rumors?"


def test_api_command_accepts_share_shortcut_for_social_transfer() -> None:
    runtime = build_runtime("web_frontend_share_command_test")
    server, thread, base_url = start_test_server(runtime)
    try:
        runtime.simulation.player.inventory["bread"] = 2
        result = post_json(base_url, "/api/command", {"command": "share mara bread 1"})
    finally:
        stop_test_server(server, thread, runtime)

    assert result["ok"] is True
    assert any("give 1 bread to Mara".lower() in entry["text"].lower() for entry in result["entries"])
    assert any(
        item["item"] == "bread" and item["quantity"] == 1
        for item in result["state"]["player"]["inventory"]
    )


def test_api_command_accepts_barter_on_shared_exchange_path() -> None:
    runtime = build_runtime("web_frontend_barter_command_test")
    server, thread, base_url = start_test_server(runtime)
    try:
        runtime.simulation.player.inventory["bread"] = 2
        result = post_json(base_url, "/api/command", {"command": "trade mara barter bread 1 for fish 1"})
    finally:
        stop_test_server(server, thread, runtime)

    assert result["ok"] is True
    assert any("barter 1 bread with Mara for 1 fish".lower() in entry["text"].lower() for entry in result["entries"])
    assert any(
        item["item"] == "fish" and item["quantity"] >= 1
        for item in result["state"]["player"]["inventory"]
    )


def test_api_command_accepts_debt_and_returns_player_debt_summary() -> None:
    runtime = build_runtime("web_frontend_debt_command_test")
    server, thread, base_url = start_test_server(runtime)
    try:
        runtime.simulation.player.hunger = 78.0
        runtime.simulation.player.money = 0
        runtime.simulation.player.inventory.clear()
        result = post_json(base_url, "/api/command", {"command": "trade mara debt bread 1"})
    finally:
        stop_test_server(server, thread, runtime)

    assert result["ok"] is True
    assert any("take 1 bread on debt for 6 gold" in entry["text"].lower() for entry in result["entries"])
    assert any(
        debt["npc_id"] == "npc.mara" and debt["amount"] == 6
        for debt in result["state"]["player"]["debts"]
    )


def test_scene_payload_exposes_debt_options_when_credit_is_available() -> None:
    runtime = build_runtime("web_frontend_debt_options_test")
    try:
        runtime.simulation.player.hunger = 78.0
        runtime.simulation.player.money = 0
        runtime.simulation.player.inventory.clear()
        state = runtime.scene_payload()
    finally:
        runtime.close()

    mara = next(person for person in state["scene"]["people"] if person["npc_id"] == "npc.mara")
    assert any(
        option["item"] == "bread" and option["quantity"] >= 1 and option["price"] == 6
        for option in mara["debt_options"]
    )


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
    assert state["scene"]["route_preview"] == []
    assert state["actions"]["travel"] == []
    assert "On the road to" in state["world"]["location_name"]


def test_scene_payload_marks_blocked_local_route_in_route_preview_and_action_catalog() -> None:
    runtime = build_runtime("web_frontend_route_preview_blocked_test")
    try:
        runtime.simulation.player.location_id = "farm"
        runtime.simulation.world.weather = "storm_front"
        state = runtime.scene_payload()
    finally:
        runtime.close()

    riverside_preview = next(preview for preview in state["scene"]["route_preview"] if preview["destination_location_id"] == "riverside")
    riverside_action = next(action for action in state["actions"]["travel"] if action["command"] == "go riverside")

    assert riverside_preview["enabled"] is False
    assert "unsafe" in riverside_preview["blocked_reason"].lower()
    assert riverside_action["enabled"] is False
    assert "unsafe" in riverside_action["blocked_reason"].lower()


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


def test_scene_payload_exposes_route_delay_status() -> None:
    runtime = build_runtime("web_frontend_route_delay_test")
    try:
        runtime.simulation.world.weather = "storm_front"
        runtime.simulation.advance_turn(1)
        state = runtime.scene_payload()
    finally:
        runtime.close()

    assert any(event["event_type"] == "route_delay" for event in state["world"]["active_events"])
    assert any(route["status"] == "delayed" for route in state["scene"]["regional_routes"])
    assert all("status_summary" in route for route in state["scene"]["regional_routes"])


def test_scene_payload_regional_nodes_reflect_dynamic_risk_level_changes() -> None:
    runtime = build_runtime("web_frontend_regional_risk_test")
    try:
        initial_state = runtime.scene_payload()
        initial_hollow_risk = next(
            node["risk_level"] for node in initial_state["scene"]["regional_nodes"] if node["region_id"] == "region.hollowmarket"
        )
        runtime.simulation.world.weather = "storm_front"
        runtime.simulation.advance_turn(4)
        stressed_state = runtime.scene_payload()
    finally:
        runtime.close()

    stressed_hollow_risk = next(
        node["risk_level"] for node in stressed_state["scene"]["regional_nodes"] if node["region_id"] == "region.hollowmarket"
    )
    assert stressed_hollow_risk > initial_hollow_risk


def test_scene_payload_hides_remote_route_delay_after_region_travel() -> None:
    runtime = build_runtime("web_frontend_remote_route_visibility_test")
    try:
        runtime.simulation.world.weather = "storm_front"
        runtime.run_command("travel-region hollow")
        while runtime.simulation.player.travel_state.is_traveling:
            runtime.run_command("next 1")
        runtime.simulation.advance_turn(1)
        state = runtime.scene_payload()
    finally:
        runtime.close()

    route_statuses = {route["route_id"]: route["status"] for route in state["scene"]["regional_routes"]}

    assert route_statuses["route.greenfall.hollowmarket"] in {"stable", "delayed"}
    assert route_statuses["route.greenfall.stonewatch"] == "unknown"


def test_scene_payload_exposes_regional_transit_counts() -> None:
    runtime = build_runtime("web_frontend_regional_transit_test")
    try:
        runtime.simulation.world.regions["region.greenfall"].stock_signals["wheat"] = 18
        runtime.simulation.world.regions["region.hollowmarket"].stock_signals["wheat"] = 2
        runtime.simulation.advance_turn(10)
        state = runtime.scene_payload()
    finally:
        runtime.close()

    assert any(route["transit_count"] > 0 for route in state["scene"]["regional_routes"])


def test_scene_payload_exposes_market_pressure_from_regional_supply_and_route_weather() -> None:
    clear_runtime = build_runtime("web_frontend_market_pressure_clear_test")
    storm_runtime = build_runtime("web_frontend_market_pressure_storm_test")
    try:
        for runtime in (clear_runtime, storm_runtime):
            runtime.simulation.player.inventory.clear()
            for npc in runtime.simulation.npcs.values():
                npc.inventory.clear()
                npc.production_queue.clear()
            runtime.simulation.world.regions["region.greenfall"].stock_signals["bread"] = 0
            runtime.simulation.world.regions["region.stonewatch"].stock_signals["bread"] = 0
            runtime.simulation.world.regions["region.hollowmarket"].stock_signals["bread"] = 20

        clear_runtime.simulation.world.weather = "clear"
        clear_state = clear_runtime.scene_payload()

        storm_runtime.simulation.world.weather = "storm_front"
        storm_state = storm_runtime.scene_payload()
    finally:
        clear_runtime.close()
        storm_runtime.close()

    assert clear_state["world"]["scarcity_index"] < storm_state["world"]["scarcity_index"]
    assert clear_state["world"]["market_prices"]["bread"] < storm_state["world"]["market_prices"]["bread"]


def test_scene_payload_exposes_market_support_event_from_regional_transit() -> None:
    runtime = build_runtime("web_frontend_market_support_event_test")
    try:
        runtime.simulation.player.inventory.clear()
        for npc in runtime.simulation.npcs.values():
            npc.inventory.clear()
            npc.production_queue.clear()
        runtime.simulation.world.weather = "clear"
        runtime.simulation.world.regions["region.greenfall"].stock_signals["bread"] = 0
        runtime.simulation.world.regions["region.hollowmarket"].stock_signals["bread"] = 20
        runtime.simulation.advance_turn(10)
        state = runtime.scene_payload()
    finally:
        runtime.close()

    assert any(event["event_type"] == "market_support" for event in state["world"]["active_events"])
    assert any("bread" in event["summary"].lower() for event in state["world"]["active_events"])
    assert any("relief" in event["summary"].lower() for event in state["world"]["active_events"])
