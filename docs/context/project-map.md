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
- `data/` is gitignored on purpose. It is a generated artifact root, not a committed source tree.

## Generated Artifact Roots

- `data/acidnet.sqlite`: default single-user runtime SQLite store
- `data/logs/`: web/runtime logs, event logs, and training logs created on demand
- `data/prompt_packs/`: generated bootstrap prompt-pack inputs and teacher outputs
- `data/sft/`: merged and split SFT datasets used by baseline and WSL training runs
- `data/training/`: generated run specs, exported trainer scripts, LoRA adapter outputs, and local Hugging Face publish manifests
- `data/eval/`: prompt-only, model-gate, and related evaluation reports
- `data/test_artifacts/`: temporary fixtures and small benchmark subsets created by tests and smoke paths
- `models/`: local base GGUF restore point for the promoted runtime; the repo keeps only placeholder guidance such as `models/README.md`, while `models/*.gguf` stays gitignored
- If a tool or editor hides `data/`, check whether it respects `.gitignore`; the directory is usually present or creatable even though it is not tracked.
- The maintained runtime-dialogue training defaults now use `data/prompt_packs/bootstrap_teacher_requests.*`, `data/sft/train_bootstrap_teacher_sft_dataset.*`, `data/sft/eval_bootstrap_teacher_sft_dataset.*`, and the refreshed bench subset `data/sft/bench_{train_1024,eval_128}.jsonl`.

## Main Entrypoints

- `run_acidnet.py`: terminal and raw-command runtime
- `run_acidnet_web.py`: shareable web runtime
- `run_llama_server.ps1`: promoted local GGUF runtime launcher; it now forces `--reasoning-format none` and `--reasoning-budget 0` so Qwen3.5 runtime replies stay in `message.content` instead of falling into hidden-reasoning mode
- `run_publish_hf_artifacts.py`: `.env`-driven Hugging Face publish tool for LoRA/GGUF model artifacts and runtime-dialogue datasets
  - local and uploaded `publish_manifest.json` files are intended to stay portable: they record repo-relative source paths plus Hub `runs/<run-name>/...` targets instead of machine-specific absolute paths
  - the publish step also refreshes the repo-root `README.md` cards in both HF repos so the restore layout is visible from the Hub UI
- `acidnet_qwen3.5_4b_gguf_lora.ipynb`: standalone Google Colab notebook that restores a published AcidNet dataset run from Hugging Face, fine-tunes a fresh Unsloth LoRA adapter, and can optionally export/upload the adapter GGUF back to the Hub
- `acidnet_qwen3.5_4b_unsloth_t4_colab.ipynb`: alternate Google Colab notebook tuned for the official free-T4 Unsloth install matrix; it defaults to a smoke run and is meant as a compatibility probe before attempting longer Colab training
- `run_local_adapter_server.py`: local OpenAI-compatible adapter server for dev/eval, not the promoted deployment runtime
- `run_local_adapter_dev_loop.ps1`: optional Windows helper that now launches the local adapter server, model gate, and web runtime together for dev/eval observation
- `run_*pipeline*.py`, `run_*train*.py`, `run_*eval*.py`: training and evaluation entrypoints
- `run_wsl_qwen_training.ps1`: WSL `uv` wrapper; the default `.venv-wsl` baseline now targets Python 3.12
- `scripts/launch_qwen3_5_4b_runtime_dialogue_unsloth_wsl_*.sh`: preferred WSL Unsloth training launchers for fast dialogue refresh loops; the standard smoke launcher now benchmarks against `data/sft/bench_train_1024.jsonl` and `data/sft/bench_eval_128.jsonl`
- `data/sft/bench_train_1024.jsonl` and `data/sft/bench_eval_128.jsonl`: maintained runtime-dialogue bench split for WSL fast-path smoke checks

## Hugging Face Artifact Registry

- Hugging Face is the portability registry for generated artifacts. AcidNet does not train from or serve from HF directly.
- Training, evaluation, and runtime still read local files under `data/` and `models/`.
- The default dataset repo is `acidsound/acidnet_dataset`.
  - each published run now uses stable subpaths such as `runs/<run-name>/prompt_packs/`, `runs/<run-name>/sft/`, `runs/<run-name>/preferences/`, and `runs/<run-name>/manifests/`
  - restore prompt-pack provenance into `data/prompt_packs/`
  - restore train/eval and bench splits into `data/sft/`
  - restore optional RL precursor preference data into `data/preferences/`
  - restore pipeline manifests and run specs into `data/training/`
  - restore gate reports into `data/eval/`
- The default model repo is `acidsound/acidnet_model`.
  - each published run now uses stable subpaths such as `runs/<run-name>/adapter/`, `runs/<run-name>/gguf/`, and `runs/<run-name>/manifests/`
  - restore the final PEFT adapter bundle into `data/training/<run-name>_adapter/` for `local_peft` dev/eval use
  - restore the LoRA GGUF into `data/gguf/` for `llama-server` deployment
- The base quantized model is still separate.
  - `acidnet_model` stores the fine-tuned adapter and adapter GGUF, not the base `Q4_K_M` model itself
  - the promoted runtime expects the base GGUF at `models/Qwen3.5-4B-Q4_K_M.gguf`
  - if the file is missing on a new machine, restore or download it there before launching `run_llama_server.ps1`, `run_acidnet.py`, or `run_acidnet_web.py` against the promoted runtime path
  - maintained reference source: `https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf`
- If a new machine should reuse an existing run, either:
  - regenerate the canonical dataset locally with `run_bootstrap_qwen4b_pipeline.py`, or
  - restore the published dataset files back into the same repo-relative `data/...` paths before launching WSL training or local evaluation

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
  - exact trade quote/stock/bargain dialogue now routes through simulator adjudication here before the dialogue backend phrases the result
  - the simulator only adjudicates structured trade facts; parser/renderer work stays outside the simulator boundary
  - the built-in parser remains English-canonical for now, but `openai_compat` can add a model-assisted parse attempt before freeform fallback
  - web/runtime debugging now surfaces a dialogue trace so engineers can see whether a turn was freeform, adjudicated, repaired, or fell back
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
  - carries live vendor `buy_options` / `debt_options` into the prompt contract so exact price questions can stay aligned with simulator trade facts
- `src/acidnet/llm/rule_based.py`
- `src/acidnet/llm/openai_compat.py`
  - promoted simulator runtime path against `llama-server` serving the `Q4_K_M` GGUF model line
  - if `llama-server` is left in Qwen thinking mode, replies can arrive as empty `message.content` plus `reasoning_content`, which currently falls through to heuristic fallback
- `src/acidnet/llm/local_peft.py`
  - in-process dev/eval parity backend; not the promoted deployment runtime
- `src/acidnet/training/dataset_builder.py`
- `src/acidnet/training/bootstrap_teacher.py`
- `src/acidnet/training/teacher_prompts.py`
  - prompt-pack generation and bootstrap teacher shaping for runtime dialogue training
  - mirrors live trade-option context into training samples so future dialogue refreshes do not regress back to raw-market price guesses
  - vendor hard-case samples can now also carry server-authored `trade_fact` plus `ask_options`/`debt_options`, so quote/stock/offer/free-help supervision stays aligned with the live adjudication path
- `src/acidnet/training/sft_dataset.py`
  - runtime-aligned SFT export now emits both in-character dialogue examples and strict trade-parser JSON examples from the same fact-grounded prompt rows when a canonical trade intent is present
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
- `src/acidnet/simulator/*` should stay language-neutral; locale-specific token parsing, alias tables, and rendered dialogue strings belong in a parser/renderer layer outside the simulator boundary.
- Until explicit i18n work exists, keep system-coupled trade-dialogue parsing and rendering English-canonical only.
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
