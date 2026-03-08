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
- `run_bootstrap_qwen4b_pipeline.py`
- `run_export_gguf.py`
- `run_publish_hf_artifacts.py`

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

## Hugging Face Restore Layout

The maintained portability path now uses two Hugging Face repos:

- model repo: `acidsound/acidnet_model`
- dataset repo: `acidsound/acidnet_dataset`

Each published run lives under `runs/<run-name>/` with stable internal names.

Dataset repo layout:

- `runs/<run-name>/prompt_packs/requests.parquet`
- `runs/<run-name>/prompt_packs/teacher_outputs.jsonl`
- `runs/<run-name>/sft/train.jsonl`
- `runs/<run-name>/sft/eval.jsonl`
- `runs/<run-name>/sft/bench_train_1024.jsonl`
- `runs/<run-name>/sft/bench_eval_128.jsonl`
- `runs/<run-name>/preferences/preferences.parquet`
- `runs/<run-name>/preferences/manifest.json`
- `runs/<run-name>/manifests/pipeline.json`
- `runs/<run-name>/manifests/run_spec.json`
- `runs/<run-name>/manifests/gate_report.json`
- `runs/<run-name>/manifests/publish_manifest.json`

Model repo layout:

- `runs/<run-name>/adapter/...`
- `runs/<run-name>/gguf/adapter-f16.gguf`
- `runs/<run-name>/gguf/adapter_manifest.json`
- `runs/<run-name>/manifests/publish_manifest.json`

The Hub repos are a registry only.
Training and runtime still read local files under `data/` and `models/`.

Restore paths on a new machine:

- prompt-pack provenance -> `data/prompt_packs/`
- train/eval and bench split -> `data/sft/`
- optional RL precursor preference bundle -> `data/preferences/`
- pipeline and run metadata -> `data/training/`
- gate reports -> `data/eval/`
- final PEFT adapter -> `data/training/<run-name>_adapter/`
- LoRA GGUF -> `data/gguf/`
- base quantized model -> local `models/` path outside the HF adapter repo

## End-To-End Refresh

The maintained refresh order is:

1. Regenerate the canonical bootstrap data.

```powershell
python run_bootstrap_qwen4b_pipeline.py
```

2. Run the WSL smoke lane.

```powershell
powershell -ExecutionPolicy Bypass -File run_wsl_qwen_training.ps1 -Mode smoke
```

3. Run the full WSL lane.

```powershell
powershell -ExecutionPolicy Bypass -File run_wsl_qwen_training.ps1 -Mode full
```

4. Gate the fresh adapter.

```powershell
python run_model_gate.py `
  --dialogue-backend local_peft `
  --dialogue-model Qwen/Qwen3.5-4B `
  --dialogue-adapter-path data/training/<run-name>_adapter `
  --turns 120 `
  --output data/eval/model_gate_<run-name>_report.json
```

5. Export the adapter GGUF.

```powershell
python run_export_gguf.py `
  --mode adapter `
  --adapter-path data/training/<run-name>_adapter `
  --base-model Qwen/Qwen3.5-4B `
  --llama-cpp-dir data/vendor/llama.cpp `
  --output data/gguf/<run-name>_adapter-f16.gguf `
  --manifest-output data/gguf/<run-name>_adapter_manifest.json
```

6. Publish the run to Hugging Face.

```powershell
python run_publish_hf_artifacts.py `
  --run-name <run-name> `
  --adapter-dir data/training/<run-name>_adapter_publish `
  --gguf-path data/gguf/<run-name>_adapter-f16.gguf `
  --gguf-path data/gguf/<run-name>_adapter_manifest.json `
  --dataset-file data/prompt_packs/bootstrap_teacher_requests.parquet `
  --dataset-file data/prompt_packs/bootstrap_teacher_outputs.jsonl `
  --dataset-file data/sft/train_bootstrap_teacher_sft_dataset.jsonl `
  --dataset-file data/sft/eval_bootstrap_teacher_sft_dataset.jsonl `
  --dataset-file data/sft/bench_train_1024.jsonl `
  --dataset-file data/sft/bench_eval_128.jsonl `
  --dataset-file data/preferences/bootstrap_dialogue_preferences.parquet `
  --dataset-file data/preferences/bootstrap_dialogue_preferences_manifest.json `
  --dataset-file data/training/bootstrap_qwen4b_pipeline.json `
  --dataset-file data/training/<run-name>_run_spec.json `
  --dataset-file data/eval/model_gate_<run-name>_report.json `
  --base-model Qwen/Qwen3.5-4B
```

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
- keep large raw logs outside the default Hugging Face publish set; prefer storing summarized metrics and portable manifests in the Hub repos
- keep the launcher/generator source in git, but treat generated `train_*.py` files as run artifacts rather than canonical source files
