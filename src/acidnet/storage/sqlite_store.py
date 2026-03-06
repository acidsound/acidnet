from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class SQLiteWorldStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                tick INTEGER NOT NULL,
                day INTEGER NOT NULL,
                player_location TEXT NOT NULL,
                player_money INTEGER NOT NULL,
                player_hunger REAL NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                npc_id TEXT NOT NULL,
                tick INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                importance REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rumors (
                rumor_id TEXT PRIMARY KEY,
                origin_npc_id TEXT NOT NULL,
                content TEXT NOT NULL,
                confidence REAL NOT NULL,
                hop_count INTEGER NOT NULL,
                last_shared_tick INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tick INTEGER NOT NULL,
                kind TEXT NOT NULL,
                message TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def save_simulation(self, simulation: Any, kind: str, message: str, payload: dict | None = None) -> None:
        snapshot = simulation.snapshot()
        self.connection.execute(
            """
            INSERT INTO snapshots (tick, day, player_location, player_money, player_hunger, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot["world"]["tick"],
                snapshot["world"]["day"],
                snapshot["player"]["location_id"],
                snapshot["player"]["money"],
                snapshot["player"]["hunger"],
                json.dumps(snapshot, ensure_ascii=False),
            ),
        )

        for rumor in simulation.rumors.values():
            self.connection.execute(
                """
                INSERT INTO rumors (rumor_id, origin_npc_id, content, confidence, hop_count, last_shared_tick)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(rumor_id) DO UPDATE SET
                    confidence=excluded.confidence,
                    hop_count=excluded.hop_count,
                    last_shared_tick=excluded.last_shared_tick
                """,
                (
                    rumor.rumor_id,
                    rumor.origin_npc_id,
                    rumor.content,
                    rumor.confidence,
                    rumor.hop_count,
                    rumor.last_shared_tick,
                ),
            )

        for memory_list in simulation.memories.values():
            for memory in memory_list:
                self.connection.execute(
                    """
                    INSERT OR REPLACE INTO memories (memory_id, npc_id, tick, event_type, summary, importance)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        memory.memory_id,
                        memory.npc_id,
                        memory.timestamp_tick,
                        memory.event_type,
                        memory.summary,
                        memory.importance,
                    ),
                )

        self.connection.execute(
            """
            INSERT INTO event_log (tick, kind, message, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                snapshot["world"]["tick"],
                kind,
                message,
                json.dumps(payload or {}, ensure_ascii=False),
            ),
        )
        self.connection.commit()

    def latest_snapshot(self) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT payload_json
            FROM snapshots
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload_json"])

    def close(self) -> None:
        self.connection.close()
