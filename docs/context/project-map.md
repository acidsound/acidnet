# Project Map

## Purpose

This is the short system map for new conversations.
Read it after `docs/context/current-state.md`.

The goal is not to restate every roadmap file.
The goal is to show where the live contracts actually sit in code and tests.

## Canonical Docs

- `AGENTS.md`: project rules and read order
- `docs/context/current-state.md`: rolling current priorities and risks
- `docs/roadmap/00-execution-checklist.md`: top-level goal and promotion baseline
- `docs/roadmap/20-spatial-time-exchange-model.md`: world-model direction
- `docs/roadmap/23-web-client-api-spec.md`: browser-facing contract
- `docs/roadmap/24-execution-roadmap.md`: current implementation sequence

## Repo Reality

- The package layout is broader than the live implementation.
- Some directories such as `src/acidnet/actions`, `src/acidnet/api`, `src/acidnet/economy`, `src/acidnet/memory`, `src/acidnet/npc`, and `src/acidnet/social` are placeholders or future boundaries.
- Do not infer runtime ownership from directory names alone.
- Confirm the active code path before editing.

## Main Entrypoints

- `run_acidnet.py`: terminal and raw-command runtime
- `run_acidnet_web.py`: shareable web runtime
- `run_acidnet_gui.py`: legacy exploratory GUI path, not a parity target
- `run_local_adapter_server.py`: local OpenAI-compatible adapter server
- `run_*pipeline*.py`, `run_*train*.py`, `run_*eval*.py`: training and evaluation entrypoints

## Core Runtime Files

- `src/acidnet/engine/simulation.py`
  - dominant simulation loop and command handling
  - travel, recovery, exchange, rumor flow, NPC turns, and many derived rules currently live here
- `src/acidnet/models/core.py`
  - shared world, player, NPC, rumor, intent, and travel schemas
- `src/acidnet/world/demo.py`
  - seeded map, personas, NPC setup, and initial rumor state
- `src/acidnet/frontend/web_app.py`
  - canonical HTTP surface and derived player-view payload
- `src/acidnet/llm/prompt_builder.py`
  - shared dialogue prompt and interaction-mode shaping
- `src/acidnet/llm/rule_based.py`
- `src/acidnet/llm/openai_compat.py`
- `src/acidnet/llm/local_peft.py`
  - dialogue backend implementations that must obey the same runtime contract
- `src/acidnet/storage/sqlite_store.py`
  - snapshot persistence and runtime dialogue prompt storage

## Core Test Anchors

- `tests/test_simulation.py`: simulation behavior and command regressions
- `tests/test_web_frontend.py`: browser-facing payload and command contract
- `tests/test_model_gate.py`: combined dialogue/circulation promotion checks
- `tests/test_prompt_only_eval.py`: prompt-only eval path
- `tests/test_circulation_eval.py`: circulation harness
- `tests/test_local_peft.py`: local dialogue adapter path
- `tests/test_storage.py`: SQLite snapshot and settings behavior

## Working Boundaries

- Simulation truth belongs in the simulation runtime and shared models, not in the web client.
- The browser renders derived scene state from `src/acidnet/frontend/web_app.py`.
- Dialogue backends share one runtime contract through `system_prompt`.
- Training and evaluation code can produce artifacts and scores, but they do not define world rules.

## Change Audit

- If you change world-state fields or command meaning, audit `src/acidnet/frontend/web_app.py`, `tests/test_web_frontend.py`, and `docs/roadmap/23-web-client-api-spec.md`.
- If you change travel, fatigue, recovery, or exchange rules, audit `docs/roadmap/20-spatial-time-exchange-model.md`, `docs/roadmap/24-execution-roadmap.md`, and player-visible web state.
- If you change dialogue prompt behavior, audit `rule_based`, `openai_compat`, and `local_peft` parity together with `src/acidnet/storage/sqlite_store.py`.
- If you move logic out of `src/acidnet/engine/simulation.py`, remove dead paths and update this file instead of assuming the old ownership map still holds.
