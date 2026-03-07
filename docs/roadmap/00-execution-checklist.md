# Execution Checklist

## Goal

Build a simulation-first village RPG where the player can move through the world, talk with NPCs, trade, collect rumors, and run a tightly tuned small local persona/dialogue model.

## Primary Priorities

1. Finish NPCs that behave as independent agents inside the world while using a small local language model for persona/dialogue.
2. Finish a world loop that keeps circulating through entropy, production, trade, hunger, rumor, and recovery instead of collapsing into a static state.

## Model Selection Principle

- Smaller is better if it is sufficient.
- Simpler is better if it is more controllable.
- More precise is better than more expressive but unstable.
- A model only earns the right to grow if the smaller model clearly fails on live-world behavior.

## Explicit Non-Priorities For Now

- large frontend expansion before the simulation and local-model loop are validated
- moving to 9B before the small-model path proves itself inside the real game loop

## Working Rules

- Update `docs/roadmap/` and `docs_kr/roadmap/` whenever a major system or execution path changes.
- Use project-root-relative paths only inside documents. Do not write absolute filesystem paths.
- Keep world mutation rule-based; local models may suggest intent or dialogue, but they do not write physics or economy directly.
- Treat `GGUF q4_k_m` as a deployment artifact, not the primary fine-tuning artifact.
- Keep SQLite as the default persistence layer on Windows; treat `zvec` as an optional Linux/macOS deployment path.
- Treat bootstrap teacher generation as the default dataset path. External teacher completions are optional refinement, not a prerequisite.

## Priority Interpretation

- This document owns the durable product priorities and model-promotion baseline.
- For the live next-slice queue, use `docs/context/current-state.md`.
- For the active simulation and world-expansion track order, use `docs/roadmap/24-execution-roadmap.md`.
- For step exit criteria and remaining gaps, use `docs/roadmap/21-frontend-world-expansion-checklist.md`.
- Promotion quality and simulation/world-loop hardening are parallel concerns; neither should be read as permission to ignore the other.

## Step Checklist

- [x] Step 00: Write architecture and implementation planning docs.
- [x] Step 01: Create project skeleton and core schemas.
- [x] Step 02: Add deterministic tick engine and scheduler.
- [x] Step 03: Add map, locations, and movement rules.
- [x] Step 04: Add hunger, food inventory, and consumption.
- [x] Step 05: Add market price feedback and trade execution.
- [x] Step 06: Add rumor lifecycle and relationship updates.
- [x] Step 07: Add memory retrieval and belief reflection jobs beyond the current lightweight hooks.
- [x] Step 08: Add heuristic planner and intent validation.
- [x] Step 09: Add playable terminal MVP.
- [x] Step 10: Add SQLite world snapshot persistence.
- [x] Step 11: Add keyboard-driven GUI frontend.
- [x] Step 12: Add teacher prompt schema and synthetic dataset export.
- [x] Step 13: Add Qwen3.5 4B vs 9B fine-tuning experiment harness.
- [x] Step 14: Add GGUF runtime export paths for validated persona checkpoints.
- [x] Step 15: Add local persona/dialogue runtime adapter.
- [x] Step 16: Add evaluation harness and model selection report.
- [x] Step 17: Add optional RL for dialogue/persona consistency only.

## Current Focus

Current product-level focus remains promotion quality:

- improve the bootstrap-teacher dataset so the first real 4B run clears the model gate
- keep thinking disabled across runtime and training so small-model dialogue stays terse and game-usable
- keep `Qwen/Qwen3.5-4B` as the primary training checkpoint
- keep `Qwen/Qwen3.5-9B` as a challenger only after the 4B run is stable
- prefer WSL2 + Unsloth for 4B LoRA when WSL2 is available and stable; keep HF/PEFT on Windows as the fallback path
- validate adapters through the local OpenAI-compatible runtime before promotion
- promote only checkpoints that beat the heuristic control on dialogue quality without breaking world circulation

In practical terms, this means:

- the small-model NPC loop matters more than model-size escalation
- bootstrap teacher data matters more than external API dependence
- runtime-aligned dialogue SFT matters more than teacher JSON fidelity for player-facing NPC speech
- world circulation and entropy stability matter more than UI scale-up
- player survival and earning loops must stay inside the same rule-based economy
- before a larger frontend push, lock graph-based travel time, actor movement cost, and unified exchange as core simulation rules
- let the frontend consume derived player-view scene state, not raw persistence snapshots
- use bounded goal-monkey evaluation to stress travel, exchange, and shock handling before expanding world scale
- keep Tk removed; do not reintroduce it as a parity target for new simulation systems
- use the shareable web probe as the main feedback surface for frontend-facing iteration

This section is not the live per-slice queue.
It sets the durable bar the current simulation work still has to serve.

Current measured status:

- the in-process `local_peft` dev/eval path now runs the latest `Qwen/Qwen3.5-4B` LoRA adapter directly without an HTTP bridge
- the promoted simulator runtime path is `openai_compat` against `llama-server` serving the `Q4_K_M` GGUF base model plus optional GGUF LoRA adapter
- the latest runtime-dialogue smoke adapter clears the combined model gate
- current gate result: `prompt_avg=1.000`, `prompt_fail_rows=0`, `prompt_latency_ms=1672.6`, `circulation=0.925`
- the WSL2 + Unsloth smoke path is now validated with fast-path kernels installed
- current WSL smoke gate result: `prompt_avg=1.000`, `prompt_fail_rows=0`, `prompt_latency_ms=2554.396`, `circulation=0.925`
- current WSL smoke `2048 / 256` benchmark train runtime: `335 s`
- the first full WSL2 + Unsloth 4B candidate is complete and clears the combined model gate
- current full WSL gate result: `prompt_avg=1.000`, `prompt_fail_rows=0`, `prompt_latency_ms=2994.443`, `circulation=0.925`
- current full WSL `50000 / 4000` train runtime: `6999 s`
- the shareable web probe is the active frontend surface for dialogue backend validation
- the web probe now shows dialogue-model startup readiness and logs both loading and ready events
- the shared dialogue system prompt is editable through the web probe and stored in SQLite with a read-only preset table plus editable runtime settings
- rumor diversity is no longer anchored to a single wheat-shortage rumor; the demo world now starts with multiple seeded rumors and generates additional dynamic rumors from weather, scarcity, and supply shifts
- repeated rumor content is now deduped by signature and stale dynamic rumors now decay out of the world instead of stacking forever
- the next world-design baseline is now documented in `docs/roadmap/20-spatial-time-exchange-model.md`
- phased follow-up work is now tracked in `docs/roadmap/21-frontend-world-expansion-checklist.md`
- the shareable web-frontend baseline is now documented in `docs/roadmap/22-web-frontend-shareable.md`
- the browser-facing runtime contract is now documented in `docs/roadmap/23-web-client-api-spec.md`
- the current implementation sequence is now documented in `docs/roadmap/24-execution-roadmap.md`
- actor travel-cost baseline fields now exist for fatigue, load, carry capacity, and serialized travel state
- a first stdlib-backed web probe now exposes derived player-view state and raw-command submission through a browser URL

## Prototype Status

There is now a playable prototype in the repo with:

- terminal runtime: `run_acidnet.py`
- shareable web runtime: `run_acidnet_web.py`
- SQLite persistence path: `data/acidnet.sqlite`
- bootstrap teacher data path: `run_bootstrap_qwen4b_pipeline.py`
- baseline launcher: `run_qwen4b_baseline_train.py`
- local adapter dev/eval server path: `run_local_adapter_server.py`
- Windows local adapter dev/eval loop: `run_local_adapter_dev_loop.ps1`
- direct in-process local adapter dev/eval path: `run_model_gate.py --dialogue-backend local_peft --dialogue-adapter-path ...`

Implemented systems:

- village map and movement
- NPC dialogue and rumor sharing
- player work loop for earning gold or gathering food
- vendor trading and food consumption
- deterministic tick progression
- heuristic NPC planner
- memory retrieval scoring and belief refresh
- openai-compatible dialogue adapter boundary with deterministic fallback
- world snapshot persistence
- shareable web probe over derived player-view scene state
- synthetic teacher prompt generation for planner and dialogue tasks
- bootstrap teacher output generation without external completion dependency
- prompt-only baseline evaluation harness with latency and fallback reporting
- world circulation evaluation harness
- combined model gate for dialogue quality plus world circulation
- deterministic train/eval SFT split export
- Unsloth and HF/PEFT 4B baseline run-spec/training-script export
- HF/PEFT LoRA smoke fine-tune run on `Qwen/Qwen3.5-4B`
- local OpenAI-compatible adapter server for fine-tuned checkpoints
- GGUF adapter export for smoke LoRA checkpoints
- dialogue preference dataset export for optional DPO/ORPO refinement
- optional DPO run-spec/training-script export

## Exit Criteria For Promotion

- the first substantial 4B checkpoint must clear the model gate with no heuristic fallback
- the local adapter runtime must stay grounded in world state and persona constraints
- the checkpoint must be exportable into the final GGUF runtime path
- evaluation must continue to include persona consistency, world consistency, latency, and memory fit
