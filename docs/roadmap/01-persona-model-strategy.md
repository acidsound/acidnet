# Persona Model Strategy

## Decision Summary

- Primary training baseline on 24GB VRAM: `Qwen/Qwen3.5-4B-Base`
- Challenger for comparison: `Qwen3.5-9B` class checkpoint, exported at runtime as `unsloth/Qwen3.5-9B-GGUF`
- Preferred training method: bf16 LoRA
- Preferred runtime quant: `Q4_K_M GGUF`
- Scope: NPC persona, dialogue tone, rumor framing, and social biasing
- Non-scope: inventory mutation, pathfinding, economy settlement, physics

## Priority Rule

- A smaller model that behaves as a believable independent NPC inside the live world is better than a larger model that only looks better in isolated samples.
- Model upgrades are secondary to maintaining a circulating, entropy-driven world state.
- The preferred model is the smallest, simplest, most precise model that survives real gameplay.

## Why 4B Is The Baseline

- It is the safer fit on a 24GB GPU.
- It leaves more room for sequence length, evaluation runs, and iteration speed.
- It is more likely to be cost-efficient for a tightly scoped NPC persona model.

## Why 9B Still Matters

- It may deliver better dialogue nuance, deception handling, and style consistency.
- It should be treated as a challenger run, not the default assumption.
- It only becomes the primary path if evaluation wins are large enough to justify the cost and latency.

## Training And Runtime Split

- Train from a fine-tuning checkpoint.
- Validate the tuned checkpoint before export.
- Export the validated result to `GGUF q4_k_m`.
- Do not attempt to fine-tune the `GGUF` deployment artifact directly.

## Current Engineering Judgment

- Use 4B first.
- Run 9B second if the baseline data pipeline and evaluation harness are stable.
- Keep the planner heuristic until the persona/dialogue model is proven useful.

## Data Contract

The persona model should consume:

- NPC profile
- relationship summary
- salient beliefs
- active rumors
- player interaction context
- local world pressure such as hunger and scarcity

The persona model should produce:

- short NPC dialogue
- rumor phrasing or withholding
- socially consistent responses

It should not produce:

- raw world writes
- economy mutations
- pathfinding decisions that bypass the rule engine

## Dataset Plan

- source 1: GPT-5.3 teacher prompt packs generated from synthetic village rollouts
- source 2: runtime interaction transcripts from terminal and GUI sessions
- source 3: future human review sets for preference and style correction

## Selection Criteria

- persona consistency
- world consistency
- responsiveness under local runtime constraints
- memory fit on the target machine
- improvement over the 4B baseline, not just absolute quality
- controllability and prompt stability over long sessions

## Operational Risks

- training on the wrong artifact type
- template mismatch between training and runtime
- overfitting on flavor while losing utility
- choosing 9B before the evaluation loop is stable

## Sources

- [Unsloth Qwen3.5 fine-tuning guide](https://unsloth.ai/docs/models/qwen3.5/fine-tune)
- [Qwen3.5-9B GGUF runtime repo](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF)
- [Qwen3.5-9B `Q4_K_M` runtime file](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-Q4_K_M.gguf)
- [Qwen3.5-4B GGUF runtime repo](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF)
