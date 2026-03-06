# Prompt-Only Baseline Evaluation

## Why This Step Exists

Before fine-tuning, the project now validates whether a base small model can already function inside the live ecosystem with prompt engineering alone.

This matters because:

- it shows whether fine-tuning is actually necessary
- it narrows the supervision target if fine-tuning is needed
- it protects the project from over-training a model that prompt control could already handle

## Current Implementation

Implemented:

- runtime dialogue adapter boundary
- deterministic rule-based fallback
- openai-compatible backend hook for local model servers
- prompt-only evaluation harness with fixed demo cases

Entry points:

- `src/acidnet/llm/`
- `run_prompt_only_baseline_eval.py`
- `src/acidnet/eval/prompt_only.py`

## Recommended Validation Order

1. Run the heuristic backend as a control.
2. Run the base `Qwen3.5-4B` backend through an openai-compatible local server.
3. Compare prompt-only behavior before generating any training run.

## Example Commands

Heuristic control:

```bash
python run_prompt_only_baseline_eval.py --dialogue-backend heuristic
```

Prompt-only local model check:

```bash
python run_prompt_only_baseline_eval.py ^
  --dialogue-backend openai_compat ^
  --dialogue-model qwen3.5-4b ^
  --dialogue-endpoint http://127.0.0.1:8000/v1/chat/completions
```

Run the live CLI against the same backend:

```bash
python run_acidnet.py ^
  --dialogue-backend openai_compat ^
  --dialogue-model qwen3.5-4b ^
  --dialogue-endpoint http://127.0.0.1:8000/v1/chat/completions
```

Run the GUI against the same backend:

```bash
python run_acidnet_gui.py ^
  --dialogue-backend openai_compat ^
  --dialogue-model qwen3.5-4b ^
  --dialogue-endpoint http://127.0.0.1:8000/v1/chat/completions
```

## What The Harness Checks

- non-empty reply
- reasonable reply length
- no obvious meta leakage
- rumor mention on rumor-request cases
- stock mention on trade-request cases

## Decision Rule

- if prompt-only 4B is already strong on dialogue/persona, keep fine-tuning narrow
- if prompt-only 4B fails mainly on consistency, fine-tune dialogue/persona only
- if prompt-only 4B fails badly on intent quality, keep planner heuristic and avoid forcing the model into world control

## Next Work

- log real prompt-only eval runs against a served base `Qwen3.5-4B`
- add human review for subjective persona quality
- keep fine-tuning scope as small as the evaluation allows
