# World Persistence

## Current Status

Implemented:

- JSON-serializable `Simulation.snapshot()`
- SQLite snapshot store
- event log persistence from CLI and GUI sessions

Code entrypoints:

- `src/acidnet/engine/simulation.py`
- `src/acidnet/storage/sqlite_store.py`
- `src/acidnet/cli.py`
- `src/acidnet/frontend/tk_app.py`

## What Is Stored

- world snapshot payload
- player state
- NPC states
- rumors
- episodic memories
- event log records from user commands and sessions

SQLite tables:

- `snapshots`
- `memories`
- `rumors`
- `event_log`

## Default Path

```text
data/acidnet.sqlite
```

## Why SQLite First

- zero extra infrastructure
- fast enough for current prototype scale
- simple to inspect during debugging and dataset curation
- works well on Windows

## Vector Search Boundary

- `zvec` remains optional
- current code keeps Windows on SQLite-only mode
- treat `zvec` as a future Linux/macOS deployment option for memory retrieval

Reference:

- [zvec repository](https://github.com/alibaba/zvec)

## Next Work

- add retrieval-oriented memory indexes
- decide whether long-term memory retrieval needs SQLite FTS, zvec, or both
- define the retention policy for runtime transcripts vs curated training data
