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

This creates `.venv-wsl` inside the project root with Python 3.11 and installs:

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

## Smoke Benchmark

Run a small WSL Unsloth benchmark against the existing runtime-dialogue smoke dataset:

```powershell
powershell -ExecutionPolicy Bypass -File run_wsl_qwen_training.ps1 -Mode smoke
```

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

The WSL smoke path is now validated.

- adapter: `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_adapter`
- gate report: `data/eval/model_gate_runtime_dialogue_unsloth_wsl_smoke_report.json`
- gate result: `PASS`
- prompt average score: `1.000`
- prompt average latency: `2554.396 ms`
- circulation score: `0.925`
- starving NPCs: `0`

Measured training improvement on the same `2048 / 256` smoke dataset:

- earlier WSL smoke before fast-path installs: `train_runtime = 1204 s`
- current WSL smoke after `flash-linear-attention` and `causal-conv1d`: `train_runtime = 335 s`

## Notes

- this path is preferred when WSL2 is available and stable
- `uv` improves environment reproducibility, not raw training speed by itself
- WSL2 is expected to help because the Unsloth stack is Linux-first
- for the best I/O behavior, larger future runs should eventually move hot data and caches into the WSL filesystem instead of a mounted Windows drive
