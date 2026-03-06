# Fine-Tuning Experiment Harness

## Current Status

Implemented:

- baseline/challenger experiment manifest generator
- fixed dataset path contract
- fixed training row and eval row targets
- export script for reproducible experiment JSON

Code entrypoints:

- `src/acidnet/training/finetune_manifest.py`
- `run_finetune_manifest_export.py`

## Manifest Purpose

The manifest exists to lock down:

- which model is the baseline
- which model is the challenger
- which dataset artifacts each run should consume
- which LoRA and batch settings are assumed before any long run starts

## Current Default Plan

Baseline:

- `Qwen3.5-4B`
- `bf16 LoRA`
- `max_seq_length = 4096`
- `batch_size = 2`
- `grad_accum = 8`

Challenger:

- `Qwen3.5-9B`
- `bf16 LoRA`
- `max_seq_length = 3072`
- `batch_size = 1`
- `grad_accum = 16`

## Export Command

```bash
python run_finetune_manifest_export.py --vram 24 --train-rows 50000 --eval-rows 4000
```

## Output

```text
data/training/finetune_manifest.json
```

## What This Does Not Do Yet

- run Unsloth training directly
- launch distributed jobs
- evaluate checkpoints automatically

Those belong to the next concrete implementation step.
