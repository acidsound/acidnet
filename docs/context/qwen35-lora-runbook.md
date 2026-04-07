# Qwen3.5-4B LoRA Runbook

Linux-first one-page guide for refreshing the AcidNet dialogue LoRA on a new machine.

## Target Shape

- GPU: single 24 GB class card such as RTX 4090
- OS: native Linux
- base model: `Qwen/Qwen3.5-4B`
- source registry: GitHub
- artifact registry:
  - dataset repo: `acidsound/acidnet_dataset`
  - model repo: `acidsound/acidnet_model`

## Non-Negotiables

- Train from a native Linux filesystem, not a mounted network or host path.
- Regenerate the canonical dataset locally; do not train directly from Hugging Face files in place.
- Use one clean git commit as the source snapshot for each training run.
- Treat gate as the promotion boundary.
- Upload every run to Hugging Face if it is useful for comparison, but refresh `promoted/latest` only after gate passes.

## Local Layout

Keep these repo-relative paths stable:

- `data/prompt_packs/`: prompt-pack inputs and teacher outputs
- `data/sft/`: train/eval and bench splits
- `data/training/`: run specs, adapters, publish manifests
- `data/eval/`: gate reports
- `data/gguf/`: exported adapter GGUF
- `models/Qwen3.5-4B-Q4_K_M.gguf`: local base GGUF for runtime serving

## Environment

Build an isolated Python 3.12 environment and install a Linux-native Unsloth stack that can reach the fast Qwen path.
The healthy target is:

- CUDA torch installed
- `unsloth`, `trl`, `peft`, `datasets`, `accelerate`, `bitsandbytes`
- `flash-attn`, `flash-linear-attention`, `causal-conv1d`
- startup banner shows `Fast Qwen3_5 patching`
- startup banner shows `FA2 = True`

If `FA2 = False` or the runtime falls back to a degraded path, fix the environment before trusting long runs.

## Data Refresh

Before every real training cycle:

1. regenerate the canonical bootstrap prompt-pack
2. regenerate the merged runtime-dialogue SFT dataset
3. regenerate the maintained bench split

The canonical outputs to refresh are:

- `data/prompt_packs/bootstrap_teacher_requests.parquet`
- `data/prompt_packs/bootstrap_teacher_outputs.jsonl`
- `data/sft/train_bootstrap_teacher_sft_dataset.jsonl`
- `data/sft/eval_bootstrap_teacher_sft_dataset.jsonl`
- `data/sft/bench_train_1024.jsonl`
- `data/sft/bench_eval_128.jsonl`
- `data/training/bootstrap_qwen4b_pipeline.json`

## Training Loop

Run the loop in this order:

1. smoke
2. full
3. gate
4. export GGUF only if gate passes
5. publish model and dataset artifacts

### Smoke

Use the maintained bench split:

- train: `data/sft/bench_train_1024.jsonl`
- eval: `data/sft/bench_eval_128.jsonl`

Smoke exists to verify:

- the environment is still accelerated
- the dataset shape is still valid
- the trainer starts and saves correctly

### Full

Use the maintained full split:

- train rows: `50000`
- eval rows: `4000`

Keep checkpoint cadence reasonably tight. `save_steps = 250` is the maintained baseline for long runs because it reduces restart cost without creating unmanageable churn.

## Gate Rule

A run is only promotable if the fresh adapter clears the combined gate.
The gate report under `data/eval/` is the source of truth.

- gate fail:
  - keep the run for analysis
  - upload as `candidate` or `failed_gate`
  - do not refresh `promoted/latest`
- gate pass:
  - export GGUF
  - upload model and dataset artifacts
  - refresh `promoted/latest`

## Publish Rule

Publish both dataset and model artifacts so another machine can reproduce or inspect the run.

Dataset side should include:

- prompt-pack provenance
- train/eval split
- bench split
- optional preference bundle if present
- pipeline manifest
- run spec
- gate report
- publish manifest

Model side should include:

- final adapter bundle
- adapter GGUF
- GGUF manifest
- publish manifest

## Checkpoints

`checkpoint-*` directories are resume-only trainer state.

- keep them during an active run
- keep them if you may resume
- once a run is definitively finished and no longer needs resume support, they can be deleted locally

Do not publish raw checkpoint trees as the portable model artifact.
The portable upload should contain only the clean adapter bundle.

## Runtime Notes

For local serving with `llama-server`, keep Qwen thinking disabled.
On this small-model path, hidden reasoning is treated as a deployment error because it can move output out of `message.content` and silently trigger fallback behavior.

## Working Memory

If you only remember one thing, remember this loop:

`clean commit -> regenerate dataset -> smoke -> full -> gate -> export/publish only on pass`
