# GGUF Export Status

## Current State

The GGUF export path is implemented and smoke-tested for LoRA adapters.

Implemented:

- llama.cpp toolchain discovery
- adapter GGUF export
- merged HF checkpoint merge helper
- merged GGUF export command generation
- optional quantization command generation
- runtime launchers that can pass `--lora` / `--lora-scaled` to `llama-server`

## Smoke Artifact

Produced artifact:

- `data/gguf/qwen3_5_4b_bootstrap_smoke_adapter-f16.gguf`

Manifest:

- `data/gguf/qwen3_5_4b_bootstrap_smoke_adapter_manifest.json`

## Practical Promotion Path

1. train a 4B checkpoint that clears the model gate
2. export the adapter to GGUF
3. run the base `Q4_K_M` GGUF plus the adapter GGUF through `llama-server`
4. verify the same checkpoint in the live GUI loop
5. only then consider a fully merged `Q4_K_M` build

## Why This Path Wins First

- smaller runtime footprint
- cheaper iteration
- no large merged checkpoint write during every model revision
- keeps the deployment artifact close to the validated training artifact
