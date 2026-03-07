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
ENV_DIR="${ACIDNET_WSL_ENV_DIR:-.venv-wsl}"
RUN_NAME="qwen3_5_4b_runtime_dialogue_unsloth_wsl_hungerfix_smoke${ACIDNET_WSL_RUN_SUFFIX:-}"
TRAIN_DATASET="${ACIDNET_WSL_TRAIN_DATASET:-data/test_artifacts/train_runtime_dialogue_hungerfix_smoke_3072.jsonl}"
EVAL_DATASET="${ACIDNET_WSL_EVAL_DATASET:-data/test_artifacts/eval_runtime_dialogue_hungerfix_smoke_384.jsonl}"

cd "$ROOT"

if [[ ! -x "$ENV_DIR/bin/python" ]]; then
  echo "Missing $ENV_DIR. Run scripts/setup_wsl_uv_unsloth.sh first." >&2
  exit 1
fi
if [[ ! -f "$TRAIN_DATASET" ]]; then
  echo "Missing train dataset $TRAIN_DATASET." >&2
  exit 1
fi
if [[ ! -f "$EVAL_DATASET" ]]; then
  echo "Missing eval dataset $EVAL_DATASET." >&2
  exit 1
fi

mkdir -p data/logs data/training
LOG_PATH="data/logs/${RUN_NAME}.log"

{
  echo "[$(date '+%F %T')] Starting WSL Unsloth hungerfix smoke training..."
  "$ENV_DIR/bin/python" run_qwen4b_baseline_train.py \
    --train-dataset "$TRAIN_DATASET" \
    --eval-dataset "$EVAL_DATASET" \
    --output-dir "data/training/${RUN_NAME}_adapter" \
    --script-output "data/training/train_${RUN_NAME}.py" \
    --spec-output "data/training/${RUN_NAME}_run_spec.json" \
    --trainer-backend unsloth \
    --epochs 1 \
    --eval-steps 128 \
    --save-steps 128 \
    --max-seq-length 1024 \
    --batch-size 2 \
    --grad-accum 8 \
    --lora-rank 16 \
    --lora-alpha 16
  echo "[$(date '+%F %T')] Hungerfix smoke training command exited with code $?"
} 2>&1 | tee "$LOG_PATH"
