# Bootstrap Teacher To Local Adapter

## Purpose

Close the first real small-model loop without depending on external teacher completions:

1. generate synthetic prompt packs
2. synthesize bootstrap teacher outputs from the same world context
3. build SFT JSONL and Parquet datasets
4. run a LoRA fine-tune
5. serve the resulting adapter behind the existing OpenAI-compatible runtime boundary

## Implemented Entry Points

- `src/acidnet/training/bootstrap_teacher.py`
- `run_bootstrap_qwen4b_pipeline.py`
- `src/acidnet/training/hf_peft_runner.py`
- `run_qwen4b_baseline_train.py`
- `run_local_adapter_server.py`
- `run_local_adapter_dev_loop.ps1`

## Current Default Path

Generate the full bootstrap dataset:

```bash
python run_bootstrap_qwen4b_pipeline.py ^
  --mode synthetic ^
  --scenarios 2048 ^
  --turns 4 ^
  --tasks dialogue ^
  --format both ^
  --train-rows 50000 ^
  --eval-rows 4000 ^
  --trainer-backend hf_peft
```

This currently produces:

- `data/prompt_packs/bootstrap_teacher_requests.jsonl`
- `data/prompt_packs/bootstrap_teacher_requests.parquet`
- `data/prompt_packs/bootstrap_teacher_outputs.jsonl`
- `data/sft/bootstrap_teacher_sft_dataset.jsonl`
- `data/sft/bootstrap_teacher_sft_dataset.parquet`
- `data/sft/train_bootstrap_teacher_sft_dataset.jsonl`
- `data/sft/train_bootstrap_teacher_sft_dataset.parquet`
- `data/sft/eval_bootstrap_teacher_sft_dataset.jsonl`
- `data/sft/eval_bootstrap_teacher_sft_dataset.parquet`
- `data/training/qwen3_5_4b_bootstrap_baseline_run_spec.json`
- `data/training/train_qwen3_5_4b_bootstrap_baseline.py`

## Current Dataset Snapshot

Latest generated bootstrap dataset:

- prompt rows: `73728`
- teacher rows: `73728`
- train rows: `50000`
- eval rows: `4000`
- task focus: `dialogue`
- trainer backend: `hf_peft`

See:

- `data/training/bootstrap_qwen4b_pipeline.json`

## Smoke Fine-Tune Result

A tiny HF/PEFT LoRA smoke run already completed successfully against the bootstrap dataset shape.

Artifacts:

- `data/test_artifacts/train_bootstrap_smoke.jsonl`
- `data/test_artifacts/eval_bootstrap_smoke.jsonl`
- `data/test_artifacts/qwen3_5_4b_bootstrap_smoke_adapter/`

Observed result:

- training completed for 2 epochs
- adapter weights were written successfully
- the adapter can be served through the local runtime server

## Local Adapter Runtime

Serve a fine-tuned adapter:

```bash
python run_local_adapter_server.py ^
  --adapter-path data/test_artifacts/qwen3_5_4b_bootstrap_smoke_adapter ^
  --base-model Qwen/Qwen3.5-4B ^
  --model-alias acidnet-qwen3.5-4b-smoke ^
  --port 8011
```

Then point the existing evaluation/runtime path at it:

```bash
python run_prompt_only_baseline_eval.py ^
  --dialogue-backend openai_compat ^
  --dialogue-model acidnet-qwen3.5-4b-smoke ^
  --dialogue-endpoint http://127.0.0.1:8011/v1/chat/completions
```

```powershell
powershell -ExecutionPolicy Bypass -File run_local_adapter_dev_loop.ps1 `
  -AdapterPath data/test_artifacts/qwen3_5_4b_bootstrap_smoke_adapter `
  -ModelAlias acidnet-qwen3.5-4b-smoke `
  -NoMonkey
```

## Current Read

- the end-to-end technical path is working
- the tiny smoke adapter is not good enough for promotion
- prompt quality is still below the model gate threshold
- world circulation remains stable because the rule-based simulation still owns world mutation

## Immediate Next Work

- run a larger 4B LoRA job from the full bootstrap dataset
- add runtime transcripts back into the dataset mix
- reduce latency on the adapter server path
- only after a 4B checkpoint clears the gate, prepare the GGUF export path
