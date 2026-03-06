# Midpoint Checkpoint

## Where The Project Stands

The project is no longer blocked on core world simulation.

What already exists:

- a playable village loop in terminal
- a keyboard-driven GUI frontend
- deterministic NPC movement, trade, hunger, and rumor flow
- SQLite persistence
- synthetic GPT-5.3 teacher prompt export
- 4B vs 9B experiment manifest generation

This means the remaining work is not "build the world from scratch".
The remaining work is "turn the prototype into a model-backed game loop without losing determinism".

## Priority Restatement

The two most important finish conditions are:

1. NPCs must function as independent actors that interact with the world while using a small local language model.
2. The world must keep circulating through entropy and recovery instead of freezing into a dead or solved state.

Large frontend growth and 9B escalation are both secondary to those two conditions.

The default bias should stay:

- smaller over larger
- simpler over more complex
- precise and controllable over impressive but noisy

## Critical Path To Finish

1. Freeze the first training/eval dataset split.
2. Attach GPT-5.3 teacher completions to the exported prompt packs.
3. Run the first `Qwen3.5-4B` baseline fine-tune.
4. Build an evaluation harness for persona consistency, world consistency, latency, and cost.
5. Only then run the `Qwen3.5-9B` challenger.
6. Choose the winner and export the validated runtime artifact to `GGUF q4_k_m`.
7. Attach the local dialogue/persona adapter to the live simulation.
8. Improve memory retrieval enough that NPC dialogue can reference stable relationship and rumor history.
9. Add save/load and a clearer world presentation pass for the frontend.

## What Is Still Missing Before We Can Call It Finished

- real teacher outputs, not only teacher prompt packs
- fine-tuning runner scripts
- checkpoint evaluation and comparison
- local model inference wired into `talk` and `ask rumor`
- memory retrieval that goes beyond the current lightweight hooks
- frontend pass for "world readability" and progression feel

## Plan A

The main plan should stay narrow:

- choose `Qwen3.5-4B` as the first real training target
- generate a large but curated synthetic dataset
- run one clean baseline
- measure it inside the real simulator
- only expand to 9B if the measured gains justify the cost

This is the safest route because the current prototype already proves that the world loop works without the model.

Plan A success condition:

- the 4B-class model is good enough to make NPC interaction feel alive inside the running simulation
- the world economy and rumor loop continue to circulate without manual resets

## Plan B

If local fine-tuning slips or quality is weak:

- keep the heuristic planner
- restrict the model to dialogue/persona only
- use a smaller, tighter 4B dialogue adapter with stronger prompt conditioning
- keep memory and rumor retrieval external and deterministic
- postpone 9B entirely

This still ships a playable world with believable NPC dialogue and avoids blocking the whole project on model quality.

## Plan C If Needed

If training cost, latency, or toolchain friction becomes unacceptable:

- ship the game loop with the current heuristic core
- use templated persona dialogue plus selective local generation only for important interactions
- treat the fine-tuned model as a post-MVP upgrade path

This is not the preferred outcome, but it protects the project from stalling.

## Main Risks

- dataset quality drift
- prompt-template mismatch between teacher data and runtime
- spending too much time on 9B before 4B is proven
- trying to solve memory retrieval and local generation at the same time
- frontend ambitions growing faster than model/runtime stability

## Recommended Finish Order

1. Dataset split and teacher completion pipeline
2. 4B baseline fine-tune
3. Evaluation harness
4. Runtime local-model integration
5. Memory retrieval upgrade
6. 9B challenger only if justified
7. Frontend polish and save/load

## Definition Of Done For This Phase

This phase is done when the player can:

- walk the village in the GUI
- build relationships through repeated interactions
- see rumors and trade pressure affect conversations
- interact with NPCs whose dialogue is actually driven by a validated local model
- save and resume the world without losing core social state
