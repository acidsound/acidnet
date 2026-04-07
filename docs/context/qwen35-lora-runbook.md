# Qwen3.5-4B LoRA Runbook

One-page operator guide for refreshing the AcidNet dialogue LoRA on another machine without rediscovering the workflow.

## Scope

- base model: `Qwen/Qwen3.5-4B`
- training path: WSL-native or native Linux
- source registry: GitHub
- artifact registry: Hugging Face
  - dataset repo: `acidsound/acidnet_dataset`
  - model repo: `acidsound/acidnet_model`

## Ground Rules

- Edit and test from the main worktree on Windows or macOS.
- Train only from a WSL-native clone such as `/home/<user>/work/acidnet`.
- Do not run long training loops from `/mnt/...`.
- The canonical dataset is regenerated locally, not trained directly from HF.
- Gate first. Export GGUF and promote only after gate passes.

## Restore Once On A New Machine

1. Clone the repo and create a WSL-native training clone.
2. Restore `.env`.
3. Restore the base GGUF to `models/Qwen3.5-4B-Q4_K_M.gguf`.
4. If you need an older candidate for comparison, restore prior runs from HF back into `data/...`.

## Setup

Use the maintained wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File run_wsl_qwen_training.ps1 -Mode setup
```

This creates `.venv-wsl` and installs the maintained Unsloth stack. The known-good accelerated path is the recovered WSL baseline with `FA2 = True`.

## The Loop

1. Regenerate the canonical bootstrap dataset.

```powershell
python run_bootstrap_qwen4b_pipeline.py
```

2. Run smoke first.

```powershell
powershell -ExecutionPolicy Bypass -File run_wsl_qwen_training.ps1 -Mode smoke
```

3. If smoke is clean, run full.

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

## Promotion Rule

- If gate fails:
  - upload as `candidate` or `failed_gate` under `runs/<run-name>/...`
  - do not refresh `promoted/latest/...`
- If gate passes:
  - export GGUF
  - publish model and dataset artifacts
  - then refresh `promoted/latest/...`

## Export And Publish

```powershell
python run_export_gguf.py `
  --mode adapter `
  --adapter-path data/training/<run-name>_adapter `
  --base-model Qwen/Qwen3.5-4B `
  --llama-cpp-dir data/vendor/llama.cpp `
  --output data/gguf/<run-name>_adapter-f16.gguf `
  --manifest-output data/gguf/<run-name>_adapter_manifest.json
```

```powershell
python run_publish_hf_artifacts.py `
  --run-name <run-name> `
  --adapter-dir data/training/<run-name>_adapter `
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

## Practical Notes

- `checkpoint-*` directories are resume-only state. Once a run is complete and no longer needs resume support, they can be deleted locally.
- The publish tool automatically stages `data/training/<run-name>_adapter_publish/` if the raw adapter directory still contains checkpoints.
- HF dataset cards now point the default viewer at the bench split, not the full artifact payload.
- For runtime serving, keep Qwen thinking disabled on the `llama-server` path.

## When In Doubt

- Read `docs/context/current-state.md`.
- Read `docs/context/project-map.md`.
- Treat the latest gate report as the truth for whether a run is promotable.
