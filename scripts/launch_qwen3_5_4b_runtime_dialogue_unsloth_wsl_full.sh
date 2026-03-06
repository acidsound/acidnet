#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$HOME/.local/bin"
export PYTHONNOUSERSITE=1
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True,max_split_size_mb:128"
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export HF_HUB_CACHE="${HF_HUB_CACHE:-$HF_HOME/hub}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/transformers}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
export TOKENIZERS_PARALLELISM=false

cd "$ROOT"

if [[ ! -x .venv-wsl/bin/python ]]; then
  echo "Missing .venv-wsl. Run scripts/setup_wsl_uv_unsloth.sh first." >&2
  exit 1
fi

mkdir -p data/logs
LOG_PATH="data/logs/qwen3_5_4b_runtime_dialogue_unsloth_wsl_full.log"

{
  echo "[$(date '+%F %T')] Starting WSL Unsloth full training..."
  .venv-wsl/bin/python run_qwen4b_baseline_train.py \
    --train-dataset data/sft/train_bootstrap_teacher_sft_dataset.jsonl \
    --eval-dataset data/sft/eval_bootstrap_teacher_sft_dataset.jsonl \
    --output-dir data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_full_adapter \
    --script-output data/training/train_qwen3_5_4b_runtime_dialogue_unsloth_wsl_full.py \
    --spec-output data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_full_run_spec.json \
    --trainer-backend unsloth \
    --epochs 1 \
    --eval-steps 1000 \
    --save-steps 1000 \
    --max-seq-length 1024 \
    --batch-size 2 \
    --grad-accum 8 \
    --lora-rank 16 \
    --lora-alpha 16
  echo "[$(date '+%F %T')] Full training command exited with code $?"
} 2>&1 | tee "$LOG_PATH"
