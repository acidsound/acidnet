#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$HOME/.local/bin"
export PYTHONNOUSERSITE=1
export UV_LINK_MODE=copy
PYTHON_VERSION="${ACIDNET_WSL_PYTHON_VERSION:-3.12}"
ENV_DIR="${ACIDNET_WSL_ENV_DIR:-.venv-wsl}"
export CUDA_HOME="${CUDA_HOME:-/usr/local/cuda}"
if [[ -d "$CUDA_HOME/bin" ]]; then
  export PATH="$CUDA_HOME/bin:$PATH"
fi

cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required inside WSL." >&2
  exit 1
fi

echo "[acidnet] Preparing WSL uv environment in $ROOT/$ENV_DIR with Python $PYTHON_VERSION"
uv python install "$PYTHON_VERSION"
uv venv --python "$PYTHON_VERSION" "$ENV_DIR"

source "$ENV_DIR/bin/activate"

uv pip install --upgrade pip setuptools wheel
uv pip install --index-url https://download.pytorch.org/whl/cu128 torch torchvision torchaudio
uv pip install unsloth datasets trl peft accelerate bitsandbytes sentencepiece protobuf pyarrow
uv pip install flash-linear-attention causal-conv1d
MAX_JOBS="${MAX_JOBS:-4}" uv pip install flash-attn --no-build-isolation
uv pip install -e ".[training]"

python - <<'PY'
import importlib
import sys
import torch

print("[acidnet] python", sys.version)
print("[acidnet] torch", torch.__version__)
print("[acidnet] cuda", torch.version.cuda)
print("[acidnet] cuda_available", torch.cuda.is_available())
if torch.cuda.is_available():
    print("[acidnet] gpu", torch.cuda.get_device_name(0))

for module_name in ("unsloth", "flash_attn", "fla", "causal_conv1d"):
    try:
        module = importlib.import_module(module_name)
        print(f"[acidnet] {module_name} ok", getattr(module, "__version__", ""))
    except Exception as exc:  # pragma: no cover - setup probe only
        raise SystemExit(f"[acidnet] {module_name} import failed: {exc}")
PY
