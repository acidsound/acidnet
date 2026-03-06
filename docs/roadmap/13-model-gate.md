# Model Gate

## Purpose

Before spending time on dataset generation, fine-tuning, or a larger model, the backend should clear a single combined gate:

- dialogue quality is acceptable
- world circulation remains stable

This keeps the project honest about the "small, simple, precise" rule.

## Entry Points

- `src/acidnet/eval/model_gate.py`
- `run_model_gate.py`

## Gate Inputs

- prompt-only dialogue evaluation
- circulation evaluation over a fixed number of turns

## Current Pass Rules

- `prompt_average_score >= 0.85`
- `prompt_rows_with_failures <= 2`
- `average_active_locations >= 4.0`
- `starving_npc_count <= 1`
- no `hard_clustering` flag

## Example Commands

Heuristic control:

```bash
python run_model_gate.py --dialogue-backend heuristic --turns 60
```

OpenAI-compatible local backend:

```bash
python run_model_gate.py ^
  --dialogue-backend openai_compat ^
  --dialogue-model qwen3.5-4b ^
  --dialogue-endpoint http://127.0.0.1:8000/v1/chat/completions ^
  --turns 120
```

Observe the GUI after running the same gate:

```powershell
powershell -ExecutionPolicy Bypass -File run_dev_world.ps1 `
  -DialogueBackend openai_compat `
  -DialogueModel qwen3.5-4b `
  -DialogueEndpoint http://127.0.0.1:8000/v1/chat/completions `
  -RunModelGate `
  -Detached
```

## Output

```text
data/eval/model_gate_report.json
```

## Why This Matters

- it gives one repeatable report shape for heuristic, prompt-only 4B, and future fine-tuned 4B runs
- it blocks model changes that sound good in dialogue samples but damage the live world
- it keeps 9B out of the loop unless the smaller model clearly fails

## Next Work

- store model-gate reports per backend/model instead of a single default file
- add latency and timeout measurements for the local backend
- compare fine-tuned checkpoints against the same gate after SFT
