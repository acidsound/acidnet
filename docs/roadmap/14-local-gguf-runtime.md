# Local GGUF Runtime

## Purpose

The project now supports two GGUF runtime shapes:

1. base `Q4_K_M` model plus a LoRA GGUF adapter
2. fully merged checkpoint converted to GGUF when llama.cpp quantization tools are available

The first path is the default promotion path on Windows because it avoids a large merged export step.
This is also the promoted simulator runtime path for `run_acidnet.py` and `run_acidnet_web.py`; keep `local_peft` for dev/eval parity only.

## Entry Points

- `run_export_gguf.py`
- `run_merge_lora_adapter.py`
- `run_llama_server.ps1`
- `run_local_qwen_dev_loop.ps1`
- `run_acidnet.py`
- `run_acidnet_web.py`

## Adapter GGUF Export

Export a fine-tuned LoRA adapter to GGUF:

```bash
python run_export_gguf.py ^
  --mode adapter ^
  --adapter-path data/test_artifacts/qwen3_5_4b_bootstrap_smoke_adapter ^
  --base-model Qwen/Qwen3.5-4B ^
  --llama-cpp-dir data/vendor/llama.cpp ^
  --output data/gguf/qwen3_5_4b_bootstrap_smoke_adapter-f16.gguf
```

Current smoke artifact:

- `data/gguf/qwen3_5_4b_bootstrap_smoke_adapter-f16.gguf`

## Merged GGUF Export

Merge first:

```bash
python run_merge_lora_adapter.py ^
  --adapter-path data/test_artifacts/qwen3_5_4b_bootstrap_smoke_adapter ^
  --base-model Qwen/Qwen3.5-4B ^
  --output-dir data/merged/qwen3_5_4b_bootstrap_smoke_merged
```

Then export the merged checkpoint to GGUF:

```bash
python run_export_gguf.py ^
  --mode merged ^
  --adapter-path data/test_artifacts/qwen3_5_4b_bootstrap_smoke_adapter ^
  --base-model Qwen/Qwen3.5-4B ^
  --llama-cpp-dir data/vendor/llama.cpp ^
  --merged-model-dir data/merged/qwen3_5_4b_bootstrap_smoke_merged ^
  --merge-first ^
  --output data/gguf/qwen3_5_4b_bootstrap_smoke-f16.gguf ^
  --quantization Q4_K_M
```

This merged path requires `llama-quantize`.

## Runtime With Base GGUF Plus Adapter GGUF

Start a local server with both the base quantized model and the exported adapter:

```powershell
powershell -ExecutionPolicy Bypass -File run_llama_server.ps1 `
  -ModelPath .\models\Qwen3.5-4B-Q4_K_M.gguf `
  -LoraPath data/gguf/qwen3_5_4b_bootstrap_smoke_adapter-f16.gguf `
  -Port 8000 `
  -ContextSize 4096 `
  -GpuLayers 99 `
  -Detached
```

Or use the combined loop:

```powershell
powershell -ExecutionPolicy Bypass -File run_local_qwen_dev_loop.ps1 `
  -ModelPath .\models\Qwen3.5-4B-Q4_K_M.gguf `
  -LoraPath data/gguf/qwen3_5_4b_bootstrap_smoke_adapter-f16.gguf `
  -Port 8000 `
  -ModelGateTurns 120
```

Point the playable runtimes at the same local endpoint:

```powershell
python run_acidnet.py `
  --dialogue-backend openai_compat `
  --dialogue-model qwen3.5-4b `
  --dialogue-endpoint http://127.0.0.1:8000/v1/chat/completions
```

```powershell
python run_acidnet_web.py `
  --dialogue-backend openai_compat `
  --dialogue-model qwen3.5-4b `
  --dialogue-endpoint http://127.0.0.1:8000/v1/chat/completions
```

## Notes

- `run_export_gguf.py --mode adapter` only needs the llama.cpp Python converter scripts
- merged `Q4_K_M` export needs `llama-quantize`
- the current smoke GGUF is an export-path proof, not a promotion-ready model
- promotion still depends on clearing the model gate with a stronger 4B checkpoint
