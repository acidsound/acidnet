# Optional Dialogue RL

## Purpose

RL stays optional and dialogue-only.

The project now has the minimum scaffolding needed to refine a good SFT checkpoint with preference optimization without giving the model direct control over world mutation.

## Implemented Entry Points

- `src/acidnet/eval/persona_reward.py`
- `src/acidnet/training/preference_dataset.py`
- `src/acidnet/training/dpo_runner.py`
- `run_dialogue_preference_export.py`
- `run_dialogue_rl_train.py`

## Current Default Flow

Generate preference pairs:

```bash
python run_dialogue_preference_export.py ^
  --prompt-pack data/prompt_packs/bootstrap_teacher_requests.jsonl ^
  --chosen-output data/prompt_packs/bootstrap_teacher_outputs.jsonl ^
  --format both
```

Prepare the optional DPO run:

```bash
python run_dialogue_rl_train.py ^
  --prepare-only ^
  --train-dataset data/preferences/bootstrap_dialogue_preferences.jsonl ^
  --eval-dataset data/preferences/bootstrap_dialogue_preferences.jsonl ^
  --sft-adapter-path data/test_artifacts/qwen3_5_4b_bootstrap_smoke_adapter
```

## Current Preference Dataset Snapshot

- rows: `50700`
- chosen source: bootstrap teacher outputs
- rejected source: bootstrap low-signal dialogue outputs

Artifacts:

- `data/preferences/bootstrap_dialogue_preferences.jsonl`
- `data/preferences/bootstrap_dialogue_preferences.parquet`
- `data/preferences/bootstrap_dialogue_preferences_manifest.json`
- `data/training/qwen3_5_4b_dialogue_dpo_run_spec.json`
- `data/training/train_qwen3_5_4b_dialogue_dpo.py`

## Boundaries

- RL is only for dialogue/persona consistency
- planner/world mutation stays rule-based
- RL is only attempted after SFT produces a checkpoint that is already usable
- if RL hurts latency or stability, it stays disabled
