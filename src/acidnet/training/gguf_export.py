from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from acidnet.training.windows_env import ensure_windows_shims_on_path


@dataclass(frozen=True, slots=True)
class LlamaCppToolchain:
    repo_dir: str | None
    convert_hf_script: str | None
    convert_lora_script: str | None
    quantize_binary: str | None


@dataclass(frozen=True, slots=True)
class GGUFExportArtifacts:
    mode: str
    adapter_path: str | None
    base_model_id: str
    merged_model_dir: str | None
    adapter_gguf_path: str | None
    merged_f16_gguf_path: str | None
    quantized_gguf_path: str | None
    toolchain: LlamaCppToolchain


def resolve_llama_cpp_toolchain(llama_cpp_dir: str | Path | None = None) -> LlamaCppToolchain:
    repo_dir = _resolve_llama_cpp_dir(llama_cpp_dir)
    convert_hf_script = _first_existing(
        [
            repo_dir / "convert_hf_to_gguf.py" if repo_dir else None,
        ]
    )
    convert_lora_script = _first_existing(
        [
            repo_dir / "convert_lora_to_gguf.py" if repo_dir else None,
        ]
    )
    quantize_binary = _resolve_quantize_binary(repo_dir)
    return LlamaCppToolchain(
        repo_dir=str(repo_dir) if repo_dir else None,
        convert_hf_script=str(convert_hf_script) if convert_hf_script else None,
        convert_lora_script=str(convert_lora_script) if convert_lora_script else None,
        quantize_binary=quantize_binary,
    )


def merge_lora_adapter(
    *,
    base_model_id: str,
    adapter_path: str | Path,
    output_dir: str | Path,
    dtype: str = "bf16",
) -> Path:
    ensure_windows_shims_on_path()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    adapter_dir = Path(adapter_path)
    output_path = Path(output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    torch_dtype = torch.bfloat16 if dtype == "bf16" and torch.cuda.is_available() else torch.float16
    tokenizer = AutoTokenizer.from_pretrained(base_model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        dtype=torch_dtype,
        device_map="auto" if torch.cuda.is_available() else None,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
    )
    peft_model = PeftModel.from_pretrained(model, adapter_dir)
    merged_model = peft_model.merge_and_unload()
    merged_model.save_pretrained(output_path, safe_serialization=True)
    tokenizer.save_pretrained(output_path)
    return output_path


def export_lora_adapter_to_gguf(
    *,
    adapter_path: str | Path,
    output_path: str | Path,
    base_model_id: str,
    toolchain: LlamaCppToolchain,
    outtype: str = "f16",
    python_bin: str = sys.executable,
) -> Path:
    if not toolchain.convert_lora_script:
        raise RuntimeError("`convert_lora_to_gguf.py` was not found. Point `--llama-cpp-dir` at a llama.cpp checkout.")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = build_lora_to_gguf_command(
        adapter_path=adapter_path,
        output_path=destination,
        base_model_id=base_model_id,
        convert_lora_script=toolchain.convert_lora_script,
        outtype=outtype,
        python_bin=python_bin,
    )
    subprocess.run(command, check=True)
    return destination


def export_merged_checkpoint_to_gguf(
    *,
    merged_model_dir: str | Path,
    output_path: str | Path,
    toolchain: LlamaCppToolchain,
    outtype: str = "f16",
    quantization: str | None = "Q4_K_M",
    python_bin: str = sys.executable,
) -> tuple[Path, Path | None]:
    if not toolchain.convert_hf_script:
        raise RuntimeError("`convert_hf_to_gguf.py` was not found. Point `--llama-cpp-dir` at a llama.cpp checkout.")

    f16_output = Path(output_path)
    f16_output.parent.mkdir(parents=True, exist_ok=True)
    convert_command = build_hf_to_gguf_command(
        merged_model_dir=merged_model_dir,
        output_path=f16_output,
        convert_hf_script=toolchain.convert_hf_script,
        outtype=outtype,
        python_bin=python_bin,
    )
    subprocess.run(convert_command, check=True)

    quantized_output: Path | None = None
    if quantization:
        if not toolchain.quantize_binary:
            raise RuntimeError("`llama-quantize` was not found. Install/build llama.cpp and retry the quantized export.")
        quantized_output = f16_output.with_name(f"{f16_output.stem}-{quantization}{f16_output.suffix}")
        quantize_command = build_quantize_command(
            quantize_binary=toolchain.quantize_binary,
            source_path=f16_output,
            output_path=quantized_output,
            quantization=quantization,
        )
        subprocess.run(quantize_command, check=True)
    return f16_output, quantized_output


def build_lora_to_gguf_command(
    *,
    adapter_path: str | Path,
    output_path: str | Path,
    base_model_id: str,
    convert_lora_script: str | Path,
    outtype: str = "f16",
    python_bin: str = sys.executable,
) -> list[str]:
    command = [
        python_bin,
        str(convert_lora_script),
        str(adapter_path),
        "--outfile",
        str(output_path),
        "--outtype",
        outtype,
    ]
    base_path = Path(base_model_id)
    if base_path.exists():
        command.extend(["--base", str(base_path)])
    else:
        command.extend(["--base-model-id", base_model_id])
    return command


def build_hf_to_gguf_command(
    *,
    merged_model_dir: str | Path,
    output_path: str | Path,
    convert_hf_script: str | Path,
    outtype: str = "f16",
    python_bin: str = sys.executable,
) -> list[str]:
    return [
        python_bin,
        str(convert_hf_script),
        str(merged_model_dir),
        "--outfile",
        str(output_path),
        "--outtype",
        outtype,
    ]


def build_quantize_command(
    *,
    quantize_binary: str | Path,
    source_path: str | Path,
    output_path: str | Path,
    quantization: str,
) -> list[str]:
    return [
        str(quantize_binary),
        str(source_path),
        str(output_path),
        quantization,
    ]


def gguf_export_artifacts_to_dict(artifacts: GGUFExportArtifacts) -> dict[str, object]:
    payload = asdict(artifacts)
    payload["toolchain"] = asdict(artifacts.toolchain)
    return payload


def _resolve_llama_cpp_dir(explicit_dir: str | Path | None) -> Path | None:
    candidates: list[Path] = []
    if explicit_dir:
        candidates.append(Path(explicit_dir))
    env_dir = os.environ.get("LLAMA_CPP_DIR")
    if env_dir:
        candidates.append(Path(env_dir))

    root = Path(__file__).resolve().parents[3]
    candidates.extend(
        [
            root / "tools" / "llama.cpp",
            root / "data" / "vendor" / "llama.cpp",
            root.parent / "llama.cpp",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _resolve_quantize_binary(repo_dir: Path | None) -> str | None:
    if repo_dir is not None:
        repo_candidates = [
            repo_dir / "build" / "bin" / "llama-quantize.exe",
            repo_dir / "build" / "bin" / "Release" / "llama-quantize.exe",
            repo_dir / "build" / "bin" / "llama-quantize",
            repo_dir / "build" / "bin" / "Release" / "llama-quantize",
        ]
        resolved = _first_existing(repo_candidates)
        if resolved is not None:
            return str(resolved)

    for binary_name in ("llama-quantize.exe", "llama-quantize"):
        resolved = shutil.which(binary_name)
        if resolved:
            return resolved
    return None


def _first_existing(candidates: list[Path | None]) -> Path | None:
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return candidate
    return None
