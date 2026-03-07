# Current State

## Purpose

This is the short rolling status file for new conversations.
Keep it brief and update it when the active slice changes.

Updated: 2026-03-07

## Priority Rule

When roadmap documents differ, use this priority order:

1. `docs/context/current-state.md` for the live next-slice queue
2. `docs/roadmap/24-execution-roadmap.md` for the active simulation and world-expansion track order
3. `docs/roadmap/21-frontend-world-expansion-checklist.md` for step exit criteria and remaining gaps
4. `docs/roadmap/00-execution-checklist.md` for durable product priorities and model-promotion baseline

This means structural repo-split work and simulation/world-loop work may move in parallel tracks.
If they compete for the next thin slice, this file decides.

## Baseline

- simulation-first
- web client is the primary frontend feedback surface
- frontends are thin clients: they send intents and read state, but do not own time progression
- frontend API handoff lives in `docs/context/frontend-api-handoff.md` and stays limited to queryable and controllable browser contract
- terminal and raw commands are the debugging control surface
- Tk is legacy and should not regain parity scope
- travel is multi-turn and should consume time, fatigue, and load
- exchange should converge on one rule path across cash, gifting, barter, and debt
- `system_prompt` is a live runtime contract across all dialogue backends
- the frontend consumes derived player-view state, not raw persistence snapshots

## Where The Live Center Is Today

- Most gameplay behavior now lives in `src/acidnet/simulator/simulation.py`.
- `src/acidnet/engine/simulation.py` is now a compatibility shim over the simulator runtime.
- Headless split-prep imports now have a stable public boundary in `src/acidnet/simulator/`.
- The browser contract is served by `src/acidnet/frontend/web_app.py` and specified in `docs/roadmap/23-web-client-api-spec.md`.
- The current village, personas, and seeded rumors live in `src/acidnet/simulator/demo.py`.
- Runtime prompt persistence lives in `src/acidnet/simulator/sqlite_store.py`.

## What Already Landed

- derived web player-view state over HTTP
- dialogue readiness and prompt editing in the web runtime
- shared fatigue, load, carry-capacity, and `travel_state` fields in the core models
- first multi-turn travel baseline with route progress
- seeded rumors plus dynamic rumor dedupe and stale-rumor decay
- direct `local_peft` dev/eval path and model-gate harness
- HTTP-level prompt propagation tests for `say` and `ask rumor` through the web API
- reserve floors now apply to cash buys as well as gifts and asks, so vendor stock is not drained below survival buffers
- blacksmith tool output is now buffered so smiths do not self-trap under load and miss the food loop
- the default runtime `system_prompt` now explicitly prioritizes direct answers to the player's latest words
- bootstrap dialogue data now includes hard `direct_say` cases for origin, identity, and hunger
- bootstrap dialogue data now always includes a hunger-direct case and adds extra no-food hunger prompts for actors without edible goods
- prompt-only evaluation now scores `origin_direct`, `identity_direct`, and `hunger_direct` separately
- a WSL Unsloth hungerfix smoke run is complete at `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_hungerfix_smoke_adapter`
- current prompt-refresh reports are:
  - `data/eval/prompt_only_runtime_dialogue_unsloth_wsl_hungerfix_smoke_report.json`
  - `data/eval/model_gate_runtime_dialogue_unsloth_wsl_hungerfix_smoke_report.json`
- the latest in-process `local_peft` hungerfix smoke rerun now confirms `prompt_avg=1.000`, `prompt_fail_rows=0`, `prompt_fallback_rows=0`, `prompt_latency_ms=2304.7`, and `circulation=0.806`
- the promoted simulator runtime path is now `openai_compat` against `llama-server` with the `Q4_K_M` GGUF base model and optional GGUF LoRA adapter; `local_peft` stays available only for in-process dev/eval parity
- HTTP `/api/command` was rechecked in-process with the hungerfix adapter: Hobb answers origin and rumor requests correctly and Doran now redirects hunger cleanly instead of inventing edible stock
- bootstrap teacher trade guidance now handles food-buy requests to no-food vendors by refusing plainly and redirecting instead of naming unrelated stock
- shared dialogue output cleanup and sentence-limit enforcement now run through one post-processing path across `heuristic`, `openai_compat`, and `local_peft`
- shared dialogue cleanup now also unwraps common code-fenced or JSON-wrapped replies before sentence limiting, reducing backend-specific formatting drift from runtime and eval servers
- prompt-only evaluation now reaches wrapped `openai_compat` and `local_peft` adapters with `temperature=0.0`, and model-gate fallback accounting now treats `local_peft` the same way as `openai_compat`
- runtime and eval parser policy now consistently limits promoted entrypoints to `heuristic` and `openai_compat`, while keeping `local_peft` on the dev/eval path only
- player rumor notes can now be inferred from dialogue text during ordinary `talk` turns when a backend mentions a known rumor without populating `used_rumor_ids`
- goal monkeys now include an `exploit_observer` role that reaches the bakery, verifies reserve-constrained vendor exposure, and probes buy-floor guardrails from the player side
- summarized regional stock and route pressure now feed into the live market snapshot, so offscreen supply and delays can move local scarcity and prices instead of only changing summary nodes
- `regional_observer` now fast-forwards long route completion during deterministic monkey runs and can clear actual cross-settlement observation inside short regression windows
- `downstream_observer` now records summarized regional stock shifts together with downstream market-price reactions from the player side
- the web player-view contract now exposes `scarcity_index` and `market_prices`, so browser-side observation can track market pressure without reading raw persistence
- simulator-only split readiness now explicitly locks load-sensitive travel ETA/risk, deterministic monkey replay, and multi-save latest-snapshot persistence
- headless CLI, eval, and simulator-only tests now import the rehome surface through `acidnet.simulator` instead of reaching directly into `engine` and `storage`
- the web runtime and runtime-adjacent backend tests now also import through `acidnet.simulator`, shrinking the remaining split-facing direct imports
- the concrete simulation, shared model definitions, demo world fixture, and SQLite/event-log persistence implementations now live under `src/acidnet/simulator/`, with `engine`, `models`, `world`, and `storage` left as compatibility shims
- the pure browser asset bundle now lives under `src/acidnet/frontend/client/`, separating static client resources more cleanly from the Python web runtime

## Immediate Queue

### Track A: Structural Boundary

1. Continue repo split prep by rehoming simulator packages behind `acidnet.simulator` without mixing in new simulation semantics.
2. Queue the realtime-transition refactor after the split work: separate command resolution from world time progression so the simulator owns the clock and frontends remain request/response clients only.

### Track B: Live Simulation and World Loop

1. Complete `20G` with one more economy sink or buffer rule plus exploit-oriented validation.
2. Extend goal-driven monkey evaluation toward richer downstream-economy scoring beyond current route, transit, stock-shift, and price-shift observation.
3. Continue toward stronger summarized regional scaling and downstream transit effects beyond price/scarcity pressure alone.

### Still Open Milestones, But Not The Current Thin-Slice Queue

- continue the travel and recovery slice so fatigue stays meaningfully tied to `rest`, `sleep`, shelter, and route cost
- continue exchange unification instead of letting vendor trade and gifting drift into separate rule systems

## Current Risks

- `src/acidnet/simulator/simulation.py` is the de facto source of truth and already large, so contract drift is easy if docs and tests are not updated in the same slice.
- The `acidnet.simulator` boundary now owns the core runtime implementations, but compatibility shims still have to stay aligned until the split is complete.
- current command handlers still advance time directly, so future realtime/2D integration will need a server-authoritative clock refactor before automatic time can be enabled safely
- Some package directories are placeholders, so refactors can accidentally target non-live paths.
- Web payloads and raw-command behavior can drift if command semantics change without updating the browser contract.
- Dialogue backends can silently diverge if one path stops honoring the shared `system_prompt` rules.
- Dialogue backend parity is no longer the active next-slice queue item, but it still needs to stay locked through the regression suite whenever prompt shaping, sanitization, or runtime parser policy changes.
- Runtime entrypoints can drift away from the promoted GGUF deployment path if `openai_compat` defaults, llama-server aliasing, and docs are not kept aligned together.
- Windows `local_peft` still falls back to the slow torch path because the fast linear-attention kernels are not present on the Windows runtime.
- The live market still uses one shared snapshot anchored to the current high-resolution economy, so multi-settlement pricing is still an approximation until more than one region runs at full local resolution.

## Simulator-Only Split Gate

- Keep `tests/test_simulation.py`, `tests/test_monkey_runner.py`, `tests/test_storage.py`, and `tests/test_event_log_file.py` green together before and through any repo split.
- Treat the repo split as structure-only on top of a green simulator gate; do not mix new simulation semantics into the same refactor slice.
- The minimum internal guarantees to preserve are travel progression cost, recovery behavior, exchange reserve floors, regional pressure observation, and persisted mid-travel snapshots.

## Default Read Path For New Work

- `AGENTS.md`
- `docs/context/current-state.md`
- `docs/context/project-map.md`
- `docs/context/frontend-api-handoff.md`
- `docs/roadmap/00-execution-checklist.md`
- `docs/roadmap/20-spatial-time-exchange-model.md`
- `docs/roadmap/23-web-client-api-spec.md`
- `docs/roadmap/24-execution-roadmap.md`

Inspect the live code path before editing.
Do not assume the directory layout matches runtime ownership.
