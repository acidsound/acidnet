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
