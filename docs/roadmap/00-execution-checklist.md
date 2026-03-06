# Execution Checklist

## Goal

Build a simulation-first village RPG where the player can move through the world, talk with NPCs, trade, collect rumors, and eventually run a tightly tuned local persona/dialogue model.

## Primary Priorities

1. Finish NPCs that can act as independent agents inside the world while using a small local language model for persona/dialogue.
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
- [ ] Step 13: Add Qwen3.5 4B vs 9B fine-tuning experiment harness.
- [ ] Step 14: Export validated persona checkpoints to GGUF `q4_k_m`.
- [ ] Step 15: Add local persona/dialogue runtime adapter.
- [ ] Step 16: Add evaluation harness and model selection report.
- [ ] Step 17: Add optional RL for dialogue/persona consistency only.

## Current Focus

Current implementation focus is Step 13:

- define the first 4B baseline run
- define the 9B challenger run
- generate large GPT-5.3 teacher prompt packs in JSONL and Parquet
- prepare OpenAI batch request artifacts for teacher completion generation
- normalize OpenAI batch outputs into `teacher_outputs.jsonl`
- split merged SFT data into deterministic train/eval artifacts
- prepare the first Unsloth training script for the 4B baseline
- keep a runnable 4B baseline launcher ready before touching 9B
- validate prompt-only base-model behavior before any long fine-tuning run starts
- prepare selection criteria before any long fine-tuning run starts

In practical terms, this means:

- the small-model NPC loop matters more than model-size escalation
- world circulation and entropy stability matter more than UI scale-up
- player survival and earning loops must stay inside the same rule-based economy

## Prototype Status

There is now a playable prototype in the repo with:

- terminal runtime: `run_acidnet.py`
- keyboard GUI runtime: `run_acidnet_gui.py`
- SQLite persistence path: `data/acidnet.sqlite`
- teacher dataset export path: `run_teacher_prompt_export.py`
- fine-tuning experiment manifest export: `run_finetune_manifest_export.py`

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
- synthetic teacher prompt generation for planner and dialogue tasks
- prompt-only baseline evaluation harness
- world circulation evaluation harness
- combined model gate for dialogue quality plus world circulation
- OpenAI batch request preparation for teacher runs
- OpenAI batch output normalization into teacher-output JSONL
- deterministic train/eval SFT split export
- Unsloth 4B baseline run-spec and training-script export
- Unsloth 4B baseline launcher

## Exit Criteria For The Next Step

- the first fine-tuning run definition must specify 4B baseline vs 9B challenger without ambiguity
- the exported dataset must be reproducible from a fixed seed
- evaluation must include persona consistency, world consistency, latency, and memory fit
