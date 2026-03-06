#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$HOME/.local/bin"
export PYTHONNOUSERSITE=1
export UV_LINK_MODE=copy

cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required inside WSL." >&2
  exit 1
fi

echo "[acidnet] Preparing WSL uv environment in $ROOT/.venv-wsl"
uv python install 3.11
uv venv --python 3.11 .venv-wsl

source .venv-wsl/bin/activate

uv pip install --upgrade pip setuptools wheel
uv pip install --index-url https://download.pytorch.org/whl/cu128 torch torchvision torchaudio
uv pip install unsloth datasets trl peft accelerate bitsandbytes sentencepiece protobuf pyarrow
uv pip install flash-linear-attention causal-conv1d
uv pip install -e ".[training]"

python - <<'PY'
import torch

print("[acidnet] torch", torch.__version__)
print("[acidnet] cuda", torch.version.cuda)
print("[acidnet] cuda_available", torch.cuda.is_available())
if torch.cuda.is_available():
    print("[acidnet] gpu", torch.cuda.get_device_name(0))

try:
    import unsloth  # noqa: F401
    print("[acidnet] unsloth ok")
except Exception as exc:  # pragma: no cover - setup probe only
    raise SystemExit(f"[acidnet] unsloth import failed: {exc}")
PY
