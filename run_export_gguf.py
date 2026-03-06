from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acidnet.training.gguf_export import (
    GGUFExportArtifacts,
    export_lora_adapter_to_gguf,
    export_merged_checkpoint_to_gguf,
    gguf_export_artifacts_to_dict,
    merge_lora_adapter,
    resolve_llama_cpp_toolchain,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export LoRA adapters or merged checkpoints to GGUF via llama.cpp.")
    parser.add_argument("--mode", choices=("adapter", "merged"), default="adapter", help="Export mode.")
    parser.add_argument("--adapter-path", required=True, help="Path to the LoRA adapter directory.")
    parser.add_argument("--base-model", default="Qwen/Qwen3.5-4B", help="Base model id used for the adapter.")
    parser.add_argument("--llama-cpp-dir", default=None, help="Path to a llama.cpp checkout.")
    parser.add_argument("--python-bin", default=sys.executable, help="Python interpreter used for llama.cpp converter scripts.")
    parser.add_argument("--outtype", default="f16", help="GGUF outtype passed to llama.cpp converter scripts.")
    parser.add_argument(
        "--output",
        default=str(Path("data") / "gguf" / "qwen3_5_4b_adapter.gguf"),
        help="GGUF output file for adapter mode or the intermediate f16 GGUF for merged mode.",
    )
    parser.add_argument(
        "--manifest-output",
        default=str(Path("data") / "gguf" / "gguf_export_manifest.json"),
        help="Manifest JSON describing the export artifacts.",
    )
    parser.add_argument(
        "--merged-model-dir",
        default=str(Path("data") / "merged" / "qwen3_5_4b_merged"),
        help="HF checkpoint directory used in merged mode.",
    )
    parser.add_argument(
        "--merge-first",
        action="store_true",
        help="Merge the adapter into the base checkpoint before merged GGUF export.",
    )
    parser.add_argument(
        "--quantization",
        default="Q4_K_M",
        help="Quantization mode used after merged f16 GGUF export. Set to `none` to skip quantization.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    toolchain = resolve_llama_cpp_toolchain(args.llama_cpp_dir)

    adapter_gguf_path: str | None = None
    merged_f16_gguf_path: str | None = None
    quantized_gguf_path: str | None = None
    merged_model_dir: str | None = None

    if args.mode == "adapter":
        adapter_output = export_lora_adapter_to_gguf(
            adapter_path=args.adapter_path,
            output_path=args.output,
            base_model_id=args.base_model,
            toolchain=toolchain,
            outtype=args.outtype,
            python_bin=args.python_bin,
        )
        adapter_gguf_path = str(adapter_output)
        print(f"Adapter GGUF: {adapter_output}")
    else:
        merged_model_dir = args.merged_model_dir
        merged_dir_path = Path(args.merged_model_dir)
        if args.merge_first or not merged_dir_path.exists():
            merged_dir_path = merge_lora_adapter(
                base_model_id=args.base_model,
                adapter_path=args.adapter_path,
                output_dir=args.merged_model_dir,
            )
            merged_model_dir = str(merged_dir_path)
            print(f"Merged checkpoint: {merged_dir_path}")

        quantization = None if args.quantization.lower() == "none" else args.quantization
        f16_output, quantized_output = export_merged_checkpoint_to_gguf(
            merged_model_dir=merged_dir_path,
            output_path=args.output,
            toolchain=toolchain,
            outtype=args.outtype,
            quantization=quantization,
            python_bin=args.python_bin,
        )
        merged_f16_gguf_path = str(f16_output)
        quantized_gguf_path = str(quantized_output) if quantized_output else None
        print(f"Merged GGUF: {f16_output}")
        if quantized_output is not None:
            print(f"Quantized GGUF: {quantized_output}")

    artifacts = GGUFExportArtifacts(
        mode=args.mode,
        adapter_path=args.adapter_path,
        base_model_id=args.base_model,
        merged_model_dir=merged_model_dir,
        adapter_gguf_path=adapter_gguf_path,
        merged_f16_gguf_path=merged_f16_gguf_path,
        quantized_gguf_path=quantized_gguf_path,
        toolchain=toolchain,
    )
    manifest_path = Path(args.manifest_output)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(gguf_export_artifacts_to_dict(artifacts), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
