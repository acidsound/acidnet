import sqlite3
from pathlib import Path

from acidnet.simulator import SQLiteWorldStore, Simulation


def test_sqlite_store_persists_world_snapshot() -> None:
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    db_path = artifact_dir / "acidnet_test.sqlite"
    if db_path.exists():
        db_path.unlink()
    simulation = Simulation.create_demo()
    store = SQLiteWorldStore(db_path)

    store.save_simulation(simulation, kind="test_save", message="saved in test", payload={"source": "pytest"})
    latest = store.latest_snapshot()

    assert latest is not None
    assert latest["player"]["location_id"] == "square"
    assert "fatigue" in latest["player"]
    assert "travel_state" in latest["player"]
    assert latest["world"]["weather"] == "dry_wind"

    connection = sqlite3.connect(db_path)
    try:
        snapshot_count = connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        event_count = connection.execute("SELECT COUNT(*) FROM event_log").fetchone()[0]
        rumor_count = connection.execute("SELECT COUNT(*) FROM rumors").fetchone()[0]
    finally:
        connection.close()
        store.close()

    assert snapshot_count == 1
    assert event_count == 1
    assert rumor_count == len(simulation.rumors)


def test_sqlite_store_round_trips_dialogue_system_prompt_setting() -> None:
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    db_path = artifact_dir / "acidnet_settings_test.sqlite"
    if db_path.exists():
        db_path.unlink()

    store = SQLiteWorldStore(db_path)
    try:
        default_prompt = store.get_default_dialogue_system_prompt()
        assert default_prompt
        assert store.get_dialogue_system_prompt() == default_prompt

        updated_prompt = default_prompt + "\nRespond in a low-key village tone."
        store.set_dialogue_system_prompt(updated_prompt)

        assert store.get_dialogue_system_prompt() == updated_prompt
    finally:
        store.close()


def test_sqlite_store_latest_snapshot_tracks_latest_runtime_state_across_multiple_saves() -> None:
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    db_path = artifact_dir / "acidnet_latest_snapshot_test.sqlite"
    if db_path.exists():
        db_path.unlink()

    simulation = Simulation.create_demo()
    simulation.world.weather = "clear"
    store = SQLiteWorldStore(db_path)
    try:
        store.save_simulation(simulation, kind="session_start", message="start")

        simulation.handle_command("go tavern")
        store.save_simulation(simulation, kind="command", message="go tavern")

        while simulation.player.travel_state.is_traveling:
            simulation.handle_command("next 1")
        store.save_simulation(simulation, kind="command", message="arrive tavern")

        latest = store.latest_snapshot()
        assert latest is not None
        assert latest["player"]["location_id"] == "tavern"
        assert latest["player"]["travel_state"]["is_traveling"] is False
        assert latest["player"]["travel_state"]["ticks_remaining"] == 0
        assert latest["world"]["tick"] == simulation.world.tick
        assert latest["player"]["fatigue"] == simulation.player.fatigue

        with sqlite3.connect(db_path) as connection:
            snapshot_count = connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
            event_count = connection.execute("SELECT COUNT(*) FROM event_log").fetchone()[0]
    finally:
        store.close()

    assert snapshot_count == 3
    assert event_count == 3


def test_prompt_presets_table_is_read_only_for_updates() -> None:
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    db_path = artifact_dir / "acidnet_prompt_presets_test.sqlite"
    if db_path.exists():
        db_path.unlink()

    store = SQLiteWorldStore(db_path)
    try:
        with sqlite3.connect(db_path) as connection:
            try:
                connection.execute("UPDATE prompt_presets SET prompt_text = 'mutated'")
            except sqlite3.IntegrityError:
                pass
            else:
                raise AssertionError("prompt_presets update unexpectedly succeeded")
    finally:
        store.close()


def test_sqlite_store_latest_snapshot_survives_reopen_with_mid_travel_state() -> None:
    artifact_dir = Path("data") / "test_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    db_path = artifact_dir / "acidnet_midtravel_test.sqlite"
    if db_path.exists():
        db_path.unlink()

    simulation = Simulation.create_demo()
    simulation.world.weather = "storm_front"
    simulation._refresh_market_snapshot()
    simulation.handle_command("travel-region hollow")

    store = SQLiteWorldStore(db_path)
    try:
        store.save_simulation(simulation, kind="mid_travel", message="saved while traveling")
    finally:
        store.close()

    reopened = SQLiteWorldStore(db_path)
    try:
        latest = reopened.latest_snapshot()
    finally:
        reopened.close()

    assert latest is not None
    assert latest["player"]["travel_state"]["is_traveling"] is True
    assert latest["player"]["travel_state"]["destination_location_id"] == "hollowmarket_gate"
    assert latest["world"]["market"]["scarcity_index"] == simulation.world.market.scarcity_index
    assert latest["world"]["market"]["items"]["bread"]["current_price"] == simulation.world.market.items["bread"].current_price
