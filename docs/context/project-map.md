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
- `docs/context/frontend-api-handoff.md`: frontend-only summary of queryable and controllable HTTP contract
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
- `run_local_adapter_server.py`: local OpenAI-compatible adapter server for dev/eval, not the promoted deployment runtime
- `run_local_adapter_dev_loop.ps1`: optional Windows helper that now launches the local adapter server, model gate, and web runtime together for dev/eval observation
- `run_*pipeline*.py`, `run_*train*.py`, `run_*eval*.py`: training and evaluation entrypoints
- `run_wsl_qwen_training.ps1`: WSL `uv` wrapper; the default `.venv-wsl` baseline now targets Python 3.12
- `scripts/launch_qwen3_5_4b_runtime_dialogue_unsloth_wsl_*.sh`: preferred WSL Unsloth training launchers for fast dialogue refresh loops; the standard smoke launcher now benchmarks against `data/sft/bench_train_1024.jsonl` and `data/sft/bench_eval_128.jsonl`
- `data/sft/bench_train_1024.jsonl` and `data/sft/bench_eval_128.jsonl`: maintained runtime-dialogue bench split for WSL fast-path smoke checks

## Core Runtime Files

- `src/acidnet/simulator/*.py`
  - stable headless import boundary for repo-split prep
  - active rehome surface for `engine`, `models`, `world`, and `storage`
  - now used by headless CLI, eval, web runtime, and split-gate/runtime-adjacent tests
- `src/acidnet/simulator/runtime.py`, `src/acidnet/simulator/models.py`, `src/acidnet/simulator/world.py`, `src/acidnet/simulator/storage.py`
  - public split-safe sub-surfaces under the simulator package
  - compatibility shims should re-export from these modules rather than from deeper simulator internals
- `src/acidnet/simulator/simulation.py`
  - dominant simulation loop and command handling
  - travel, recovery, exchange, rumor flow, NPC turns, and many derived rules currently live here
- `src/acidnet/engine/simulation.py`
  - compatibility shim over `src/acidnet/simulator/simulation.py`
- `src/acidnet/simulator/core.py`
  - shared world, player, NPC, rumor, intent, and travel schemas
- `src/acidnet/models/core.py`
  - compatibility shim over `src/acidnet/simulator/core.py`
- `src/acidnet/simulator/demo.py`
  - seeded map, personas, NPC setup, and initial rumor state
- `src/acidnet/world/demo.py`
  - compatibility shim over `src/acidnet/simulator/demo.py`
- `src/acidnet/frontend/web_app.py`
  - canonical HTTP surface and derived player-view payload
- `src/acidnet/frontend/client/index.html`
  - current pure static browser client asset bundle
- `src/acidnet/llm/prompt_builder.py`
  - shared dialogue prompt and interaction-mode shaping
- `src/acidnet/llm/rule_based.py`
- `src/acidnet/llm/openai_compat.py`
  - promoted simulator runtime path against `llama-server` serving the `Q4_K_M` GGUF model line
- `src/acidnet/llm/local_peft.py`
  - in-process dev/eval parity backend; not the promoted deployment runtime
- `src/acidnet/training/dataset_builder.py`
- `src/acidnet/training/bootstrap_teacher.py`
- `src/acidnet/training/teacher_prompts.py`
  - prompt-pack generation and bootstrap teacher shaping for runtime dialogue training
- `src/acidnet/eval/prompt_only.py`
- `src/acidnet/eval/model_gate.py`
  - question-focused dialogue scoring and combined promotion checks
- `src/acidnet/simulator/sqlite_store.py`
  - snapshot persistence and runtime dialogue prompt storage
- `src/acidnet/simulator/event_log_file.py`
  - plain-text event log persistence for headless/web runtime
- `src/acidnet/storage/sqlite_store.py`
  - compatibility shim over `src/acidnet/simulator/sqlite_store.py`

## Core Test Anchors

- `tests/test_simulation.py`: simulation behavior and command regressions
- `tests/test_web_frontend.py`: browser-facing payload, command contract, and HTTP prompt-propagation checks
- `tests/test_model_gate.py`: combined dialogue/circulation promotion checks
- `tests/test_monkey_runner.py`: goal-monkey role behavior and observation scoring
- `tests/test_prompt_only_eval.py`: prompt-only eval path
- `tests/test_circulation_eval.py`: circulation harness
- `tests/test_dialogue_backends.py`: backend parity around output cleanup, fallback config forwarding, and fallback accounting
- `tests/test_local_peft.py`: local dialogue adapter path
- `tests/test_storage.py`: SQLite snapshot and settings behavior
- `tests/test_simulator_boundary.py`: split-boundary import/export gate for simulator public sub-surfaces and compatibility shims

For repo-split safety, the minimum simulator-only gate is `tests/test_simulation.py`, `tests/test_monkey_runner.py`, `tests/test_storage.py`, and `tests/test_event_log_file.py`.

## Simulator-Only Split Gate

- Structural repo splits should keep `tests/test_simulation.py`, `tests/test_monkey_runner.py`, `tests/test_storage.py`, and `tests/test_event_log_file.py` green before wider web or model-eval suites.
- Use this subset as the first no-behavior-change gate when rehoming `src/acidnet/engine`, `src/acidnet/models`, `src/acidnet/world`, or `src/acidnet/storage`.
- If a split changes the headless control surface, add or update a terminal-path regression instead of relying on manual smoke only.
- Keep `tests/test_simulator_boundary.py` green so deep simulator internals do not leak back into compatibility shims or live entrypoints.
- Treat direct imports of `acidnet.simulator.simulation`, `acidnet.simulator.core`, `acidnet.simulator.demo`, `acidnet.simulator.sqlite_store`, and `acidnet.simulator.event_log_file` outside the public sub-surfaces as split failures.
- Treat any new import from `src/acidnet/simulator/*.py` back into frontend, eval, training, or legacy shim layers as a split failure.
- Treat `pyproject.toml`, `run_acidnet.py`, and `run_acidnet_web.py` as part of the split gate, because frontend deep testing depends on stable runtime entrypoint targets.

## Working Boundaries

- Simulation truth belongs in the simulation runtime and shared models, not in the web client.
- Headless CLI, eval, and split-gate code should prefer `acidnet.simulator` as the stable import surface when possible.
- Compatibility shims in `engine`, `models`, `world`, and `storage` should import from `acidnet.simulator.runtime`, `acidnet.simulator.models`, `acidnet.simulator.world`, and `acidnet.simulator.storage`, not from deeper simulator modules.
- Frontends should remain thin intent/state clients; future realtime ticking still belongs to the simulator side, not the client.
- The browser renders derived scene state from `src/acidnet/frontend/web_app.py`.
- Dialogue backends share one runtime contract through `system_prompt`.
- Training and evaluation code can produce artifacts and scores, but they do not define world rules.

## Change Audit

- If you change world-state fields or command meaning, audit `src/acidnet/frontend/web_app.py`, `tests/test_web_frontend.py`, `docs/context/frontend-api-handoff.md`, and `docs/roadmap/23-web-client-api-spec.md`.
- If you change travel, fatigue, recovery, or exchange rules, audit `docs/roadmap/20-spatial-time-exchange-model.md`, `docs/roadmap/24-execution-roadmap.md`, and player-visible web state.
- If you change dialogue prompt behavior, audit `rule_based`, `openai_compat`, and `local_peft` parity together with `src/acidnet/storage/sqlite_store.py`.
- If you change dialogue data or teacher logic, audit `src/acidnet/training/dataset_builder.py`, `src/acidnet/training/bootstrap_teacher.py`, `src/acidnet/eval/prompt_only.py`, and the latest smoke gate reports together.
- If you change simulator package boundaries for split work, keep `src/acidnet/simulator/*.py` aligned as the public import surface.
- If you move more logic under `src/acidnet/simulator/`, keep `engine`, `world`, and `storage` compatibility shims aligned until the split is complete.
- Before deeper frontend testing or any realtime-transition design, recheck the split gate first so the browser audit is not run against a moving runtime boundary.
