# Current State

## Purpose

This is the short rolling status file for new conversations.
Keep it brief and update it when the active slice changes.

Updated: 2026-03-07

## Baseline

- simulation-first
- web client is the primary frontend feedback surface
- terminal and raw commands are the debugging control surface
- Tk is legacy and should not regain parity scope
- travel is multi-turn and should consume time, fatigue, and load
- exchange should converge on one rule path across cash, gifting, barter, and debt
- `system_prompt` is a live runtime contract across all dialogue backends
- the frontend consumes derived player-view state, not raw persistence snapshots

## Where The Live Center Is Today

- Most gameplay behavior still lives in `src/acidnet/engine/simulation.py`.
- The browser contract is served by `src/acidnet/frontend/web_app.py` and specified in `docs/roadmap/23-web-client-api-spec.md`.
- The current village, personas, and seeded rumors live in `src/acidnet/world/demo.py`.
- Runtime prompt persistence lives in `src/acidnet/storage/sqlite_store.py`.

## What Already Landed

- derived web player-view state over HTTP
- dialogue readiness and prompt editing in the web runtime
- shared fatigue, load, carry-capacity, and `travel_state` fields in the core models
- first multi-turn travel baseline with route progress
- seeded rumors plus dynamic rumor dedupe and stale-rumor decay
- direct `local_peft` runtime path and model-gate harness

## Immediate Queue

1. Keep backend parity on the dialogue contract across `heuristic`, `openai_compat`, and `local_peft`.
2. Continue the travel and recovery slice so fatigue stays meaningfully tied to `rest`, `sleep`, shelter, and route cost.
3. Continue exchange unification instead of letting vendor trade and gifting drift into separate rule systems.
4. Use goal-driven monkey evaluation as the observation harness for travel, exchange, and shock behavior.
5. Add state-dependent shocks with explicit recovery loops before any larger frontend expansion.

## Current Risks

- `src/acidnet/engine/simulation.py` is the de facto source of truth and already large, so contract drift is easy if docs and tests are not updated in the same slice.
- Some package directories are placeholders, so refactors can accidentally target non-live paths.
- Web payloads and raw-command behavior can drift if command semantics change without updating the browser contract.
- Dialogue backends can silently diverge if one path stops honoring the shared `system_prompt` rules.

## Default Read Path For New Work

- `AGENTS.md`
- `docs/context/current-state.md`
- `docs/context/project-map.md`
- `docs/roadmap/00-execution-checklist.md`
- `docs/roadmap/20-spatial-time-exchange-model.md`
- `docs/roadmap/23-web-client-api-spec.md`
- `docs/roadmap/24-execution-roadmap.md`

Inspect the live code path before editing.
Do not assume the directory layout matches runtime ownership.
