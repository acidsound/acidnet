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
  --trainer-backend hf_peft ^
  --sft-variant runtime_dialogue
```

Run the full 50k / 4k runtime-dialogue LoRA job and gate it directly through `local_peft`:

```bash
python run_bootstrap_qwen4b_pipeline.py ^
  --mode synthetic ^
  --scenarios 2048 ^
  --turns 4 ^
  --tasks dialogue ^
  --format both ^
  --train-rows 50000 ^
  --eval-rows 4000 ^
  --trainer-backend hf_peft ^
  --sft-variant runtime_dialogue ^
  --training-output-dir data/training/qwen3_5_4b_runtime_dialogue_full_adapter ^
  --run-spec-output data/training/qwen3_5_4b_runtime_dialogue_full_run_spec.json ^
  --training-script-output data/training/train_qwen3_5_4b_runtime_dialogue_full.py ^
  --launch-train ^
  --run-gate ^
  --gate-output data/eval/qwen3_5_4b_runtime_dialogue_full_gate_report.json
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
- sft variant: `runtime_dialogue`

See:

- `data/training/bootstrap_qwen4b_pipeline.json`

## Smoke Fine-Tune Result

A tiny HF/PEFT LoRA smoke run already completed successfully against the bootstrap dataset shape.
A maintained runtime-dialogue smoke benchmark now runs against the standard `1024 train / 128 eval` bench split under `data/sft`.

Artifacts:

- `data/test_artifacts/train_bootstrap_smoke.jsonl`
- `data/test_artifacts/eval_bootstrap_smoke.jsonl`
- `data/test_artifacts/qwen3_5_4b_bootstrap_smoke_adapter/`
- `data/sft/bench_train_1024.jsonl`
- `data/sft/bench_eval_128.jsonl`
- `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_adapter/`

Observed result:

- training completed successfully on the maintained bench split
- adapter weights were written successfully
- the latest standard WSL smoke benchmark on Python 3.12 reports `train_runtime=169 s`, `train_samples_per_second=6.06`, and `train_steps_per_second=0.379`
- fast-path setup is active in WSL with `flash-linear-attention` and `causal-conv1d`
- the runtime-dialogue smoke track has already shown a gate-clearing adapter with `prompt_avg=1.000`, `prompt_fail_rows=0`, `prompt_latency_ms=1672.6`, and `circulation=0.925`

## Local Adapter Runtime

Serve a fine-tuned adapter:

```bash
python run_local_adapter_server.py ^
  --adapter-path data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_adapter ^
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
  -AdapterPath data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_adapter `
  -ModelAlias acidnet-qwen3.5-4b-smoke `
  -TailLog
```

Run the same adapter directly inside the CLI without an HTTP bridge:

```bash
python run_acidnet.py ^
  --no-persist ^
  --dialogue-backend local_peft ^
  --dialogue-model Qwen/Qwen3.5-4B ^
  --dialogue-adapter-path data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_adapter
```

Or launch the web runtime against a locally served adapter:

```powershell
powershell -ExecutionPolicy Bypass -File run_local_adapter_dev_loop.ps1 `
  -AdapterPath data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_full_adapter `
  -ModelAlias acidnet-qwen3.5-4b-full `
  -TailLog
```

## Current Read

- the end-to-end technical path is working
- the first tiny smoke adapter was not good enough for promotion
- the runtime-dialogue smoke adapter is good enough to use as the current local-model baseline
- `thinking` must stay disabled in both training and runtime for the small-model path
- runtime dialogue SFT is now the default promotion path for NPC speech
- runtime dialogue SFT now normalizes old bootstrap interaction labels into the live runtime modes: `talk`, `rumor_request`, `trade_request`, and `direct_say`
- world circulation remains stable because the rule-based simulation still owns world mutation

## Immediate Next Work

- run the larger 4B LoRA job from the full bootstrap dataset and promote the first checkpoint that clears the direct `local_peft` gate
- add runtime transcripts back into the dataset mix
- reduce latency on the direct `local_peft` path
- after the larger checkpoint lands, prepare the GGUF export path
