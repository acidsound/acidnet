# Curated Context From Shared Chat

## Scope

This note captures only the parts of the shared conversation that remain useful for the current project direction.

Shared thread reviewed:

- <https://chatgpt.com/share/69aa3ede-21ac-8011-9a9d-05193f800bf3>

## High-Signal Points We Keep

- `Qwen3.5-4B` is feasible on a 24GB VRAM machine when the training path stays in 4-bit LoRA or QLoRA territory.
- NPC systems need explicit state, action, reward, and environment boundaries.
- Memory must be externalized instead of expecting the model to remember the full game history.
- Reward targets like persona consistency, world consistency, and action correctness are meaningful if RL is added later.
- A simulation environment must exist before any RL loop can be trusted.
- Rule-based action execution remains safer than letting the model mutate the world directly.
- `SFT -> RL` is a healthier progression than jumping into RL from the start.

## Medium-Signal Points We Keep With Caution

- Dual-model phrasing can be useful conceptually:
  - trainable policy or persona model
  - external reward or evaluation component
- GRPO may become a practical RL candidate later on smaller hardware.

These stay as future options, not current commitments.

## What We Drop

- RL-only as the main starting path
- hard sample-count promises like `200k RL episodes`
- broad capability comparisons such as "Skyrim level" or "BG3 level"
- any advice that assumes the referenced X post is verified in detail
- using model output as a direct world-state executor

## Concrete Effect On This Repo

- persona fine-tuning stays the primary model track
- planner and action execution remain structured and validated
- RL is moved behind simulator stability, dataset readiness, and SFT validation
- memory summaries become first-class input artifacts for persona prompting

