# WSL2 Unsloth Train Path

## Purpose

Move 4B LoRA training off the Windows fallback path and onto a Linux-first stack that is more likely to use the optimized Qwen3.5 kernels.

This path is for training only.
The Windows GUI and local play loop remain valid.

## Why This Exists

The current Windows HF/PEFT path is technically correct but too slow for a practical promotion run because:

- `torch` is available, but the Qwen3.5 fast path is not
- the log reports a fallback because `flash-linear-attention` and `causal-conv1d` are missing
- the active Windows Python environment also shows invalid distribution warnings

WSL2 gives a cleaner Linux package path for Unsloth and related CUDA kernels.

## Entry Points

- `run_wsl_qwen_training.ps1`
- `scripts/setup_wsl_uv_unsloth.sh`
- `scripts/launch_qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke.sh`
- `scripts/launch_qwen3_5_4b_runtime_dialogue_unsloth_wsl_full.sh`

## Setup

Create the WSL-specific `uv` environment:

```powershell
powershell -ExecutionPolicy Bypass -File run_wsl_qwen_training.ps1 -Mode setup
```

This now creates `.venv-wsl` inside the project root with Python 3.12 by default and installs:

- CUDA `torch`
- `unsloth`
- `datasets`
- `trl`
- `peft`
- `accelerate`
- `bitsandbytes`
- `flash-linear-attention`
- `causal-conv1d`
- project training extras

Use `-PythonVersion 3.11` only when you explicitly need to compare against the older known-good baseline or isolate a version-specific issue.

## Smoke Benchmark

Run the maintained WSL Unsloth benchmark against the standard runtime-dialogue bench split:

```powershell
powershell -ExecutionPolicy Bypass -File run_wsl_qwen_training.ps1 -Mode smoke
```

Default datasets:

- `data/sft/bench_train_1024.jsonl`
- `data/sft/bench_eval_128.jsonl`

The launcher also accepts `ACIDNET_WSL_TRAIN_DATASET` and `ACIDNET_WSL_EVAL_DATASET` overrides when a specialized subset is needed.

Artifacts:

- log: `data/logs/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke.log`
- adapter dir: `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_adapter`
- run spec: `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_run_spec.json`

## Full WSL Run

After the smoke benchmark succeeds, run the full 50k / 4k dataset:

```powershell
powershell -ExecutionPolicy Bypass -File run_wsl_qwen_training.ps1 -Mode full
```

Artifacts:

- log: `data/logs/qwen3_5_4b_runtime_dialogue_unsloth_wsl_full.log`
- adapter dir: `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_full_adapter`
- run spec: `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_full_run_spec.json`

## Current Measured Result

The default WSL smoke path is now revalidated on Python 3.12.

- default setup probe in `.venv-wsl` reports `Python 3.12.10`, `unsloth 2026.3.3`, `fla 0.4.1`, and `causal_conv1d 1.6.0`
- standard smoke artifacts:
  - `data/logs/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke.log`
  - `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_adapter/`
  - `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_run_spec.json`
- current maintained `1024 / 128` bench smoke runtime: `train_runtime = 169 s`
- current maintained `1024 / 128` bench smoke throughput: `train_samples_per_second = 6.06`, `train_steps_per_second = 0.379`
- the standard smoke log shows `Fast Qwen3_5 patching` and `FA [Xformers = 0.0.35. FA2 = False]`
- the launcher-side dependency check now imports `unsloth` before `trl`, so the earlier warning about reversed import order no longer appears during standard launches

The first full WSL candidate is also complete.

- adapter: `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_full_adapter`
- gate report: `data/eval/model_gate_runtime_dialogue_unsloth_wsl_full_report.json`
- full gate result: `PASS`
- full prompt average score: `1.000`
- full prompt average latency: `2994.443 ms`
- full circulation score: `0.925`
- full starving NPCs: `0`
- full train runtime: `6999 s`

The Windows `local_peft` loader now reads adapter metadata so the WSL-trained Unsloth adapter loads without the earlier missing-key warning.

## Notes

- this path is preferred when WSL2 is available and stable
- `uv` improves environment reproducibility, not raw training speed by itself
- WSL2 is expected to help because the Unsloth stack is Linux-first
- for the best I/O behavior, larger future runs should eventually move hot data and caches into the WSL filesystem instead of a mounted Windows drive
