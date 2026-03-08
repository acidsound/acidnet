# Fine-Tuning Experiment Harness

## Current Status

Implemented:

- baseline/challenger experiment manifest generator
- fixed dataset path contract
- fixed training row and eval row targets
- export script for reproducible experiment JSON
- OpenAI teacher batch request export for `/v1/responses`
- OpenAI batch output normalization into `teacher_outputs.jsonl`
- deterministic train/eval SFT split export
- Unsloth 4B baseline run-spec export
- Unsloth 4B baseline training-script export
- optional 4B baseline training launcher with dependency checks

Code entrypoints:

- `src/acidnet/training/finetune_manifest.py`
- `run_finetune_manifest_export.py`
- `src/acidnet/training/openai_batch.py`
- `src/acidnet/training/sft_dataset.py`
- `src/acidnet/training/unsloth_runner.py`
- `run_openai_teacher_batch_prepare.py`
- `run_openai_teacher_batch_normalize.py`
- `run_teacher_sft_split.py`
- `run_qwen4b_baseline_prep.py`
- `run_qwen4b_baseline_train.py`
- `run_qwen4b_baseline_pipeline.py`

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
data/prompt_packs/openai_batch_requests.jsonl
data/prompt_packs/teacher_outputs.jsonl
data/sft/train_bootstrap_teacher_sft_dataset.jsonl
data/sft/eval_bootstrap_teacher_sft_dataset.jsonl
data/training/qwen3_5_4b_baseline_run_spec.json
data/training/train_qwen3_5_4b_baseline.py
data/training/qwen3_5_4b_baseline_pipeline.json
```

## Example Commands

Prepare OpenAI batch requests from the teacher prompt pack:

```bash
python run_openai_teacher_batch_prepare.py --model gpt-5.3
```

Normalize downloaded OpenAI batch output into teacher-output JSONL:

```bash
python run_openai_teacher_batch_normalize.py ^
  --batch-output data/prompt_packs/openai_batch_output.jsonl ^
  --output data/prompt_packs/bootstrap_teacher_outputs.jsonl
```

Split the merged SFT dataset into deterministic train/eval artifacts:

```bash
python run_teacher_sft_split.py --train-rows 50000 --eval-rows 4000 --format both
```

Prepare the first 4B baseline Unsloth runner:

```bash
python run_qwen4b_baseline_prep.py
```

Prepare and launch the 4B baseline run:

```bash
python run_qwen4b_baseline_train.py
```

Prepare merged SFT, split artifacts, and the 4B run in one pass:

```bash
python run_qwen4b_baseline_pipeline.py ^
  --teacher-output data/prompt_packs/bootstrap_teacher_outputs.jsonl ^
  --format both
```

## What This Does Not Do Yet

- submit or poll OpenAI batch jobs directly
- launch distributed jobs
- evaluate checkpoints automatically

Those belong to the next concrete implementation step after the first baseline run is validated.
