from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acidnet.training.gguf_export import merge_lora_adapter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge a LoRA adapter into its Qwen base checkpoint.")
    parser.add_argument("--adapter-path", required=True, help="Path to the fine-tuned adapter directory.")
    parser.add_argument("--base-model", default="Qwen/Qwen3.5-4B", help="Base model id used for the adapter.")
    parser.add_argument(
        "--output-dir",
        default=str(Path("data") / "merged" / "qwen3_5_4b_merged"),
        help="Directory where the merged HF checkpoint will be written.",
    )
    parser.add_argument("--dtype", choices=("bf16", "fp16"), default="bf16", help="Preferred merge dtype.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output_path = merge_lora_adapter(
        base_model_id=args.base_model,
        adapter_path=args.adapter_path,
        output_dir=args.output_dir,
        dtype=args.dtype,
    )
    print(f"Merged checkpoint: {output_path}")


if __name__ == "__main__":
    main()
