import sqlite3
from pathlib import Path

from acidnet.engine import Simulation
from acidnet.storage import SQLiteWorldStore


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
