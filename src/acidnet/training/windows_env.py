from __future__ import annotations

import os
from pathlib import Path


def ensure_windows_shims_on_path() -> str | None:
    if os.name != "nt":
        return None
    shim_dir = Path(__file__).resolve().parents[3] / "tools" / "windows_shims"
    current_path = os.environ.get("PATH", "")
    shim_str = str(shim_dir)
    if shim_str.lower() not in current_path.lower():
        os.environ["PATH"] = shim_str + os.pathsep + current_path
    return shim_str
