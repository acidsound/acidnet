from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from acidnet.llm.prompt_builder import DEFAULT_SYSTEM_PROMPT

SYSTEM_PROMPT_SETTING_KEY = "dialogue.system_prompt"
SYSTEM_PROMPT_PRESET_ID = "system.default"


class SQLiteWorldStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
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

            CREATE TABLE IF NOT EXISTS runtime_settings (
                key TEXT PRIMARY KEY,
                value_text TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS prompt_presets (
                prompt_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                prompt_text TEXT NOT NULL
            );

            CREATE TRIGGER IF NOT EXISTS prompt_presets_no_update
            BEFORE UPDATE ON prompt_presets
            BEGIN
                SELECT RAISE(ABORT, 'prompt_presets is read-only');
            END;

            CREATE TRIGGER IF NOT EXISTS prompt_presets_no_delete
            BEFORE DELETE ON prompt_presets
            BEGIN
                SELECT RAISE(ABORT, 'prompt_presets is read-only');
            END;
            """
        )
        self.connection.execute(
            """
            INSERT OR IGNORE INTO prompt_presets (prompt_id, name, prompt_text)
            VALUES (?, ?, ?)
            """,
            (SYSTEM_PROMPT_PRESET_ID, "Default NPC Dialogue System Prompt", DEFAULT_SYSTEM_PROMPT),
        )
        self.connection.execute(
            """
            INSERT OR IGNORE INTO runtime_settings (key, value_text)
            VALUES (?, ?)
            """,
            (SYSTEM_PROMPT_SETTING_KEY, DEFAULT_SYSTEM_PROMPT),
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

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.connection.execute(
            """
            SELECT value_text
            FROM runtime_settings
            WHERE key = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            return default
        return str(row["value_text"])

    def set_setting(self, key: str, value: str) -> None:
        self.connection.execute(
            """
            INSERT INTO runtime_settings (key, value_text)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_text = excluded.value_text,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )
        self.connection.commit()

    def get_dialogue_system_prompt(self) -> str:
        return self.get_setting(SYSTEM_PROMPT_SETTING_KEY, DEFAULT_SYSTEM_PROMPT) or DEFAULT_SYSTEM_PROMPT

    def set_dialogue_system_prompt(self, prompt: str) -> None:
        self.set_setting(SYSTEM_PROMPT_SETTING_KEY, prompt)

    def get_default_dialogue_system_prompt(self) -> str:
        return DEFAULT_SYSTEM_PROMPT

    def close(self) -> None:
        self.connection.close()
