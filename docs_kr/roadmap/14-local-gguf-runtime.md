# Local GGUF Runtime

## 목적

이제 프로젝트는 두 가지 GGUF runtime 형태를 지원한다.

1. base `Q4_K_M` 모델 + LoRA GGUF adapter
2. llama.cpp quantization tool이 있을 때 merged checkpoint 전체를 GGUF로 변환하는 경로

Windows 기본 승격 경로는 첫 번째다. 큰 merged export 단계를 피할 수 있기 때문이다.
이 경로가 `run_acidnet.py`, `run_acidnet_web.py`의 승격 runtime 경로이기도 하며, `local_peft`는 dev/eval parity 용도로만 남긴다.

## 진입점

- `run_export_gguf.py`
- `run_merge_lora_adapter.py`
- `run_llama_server.ps1`
- `run_local_qwen_dev_loop.ps1`
- `run_acidnet.py`
- `run_acidnet_web.py`

## Base Model Location

Promoted runtime expects the base quantized model at:

- `models/Qwen3.5-4B-Q4_K_M.gguf`

This file is not tracked in git and is not stored in `acidsound/acidnet_model`.
On a new machine, restore or download the base model into that exact repo-relative path before starting `llama-server` or the promoted `openai_compat` runtime.

Maintained reference source:

- `https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf`

## Qwen Thinking Policy

Small-model runtime launches must keep Qwen thinking disabled.
For the promoted `llama-server` path this means forcing:

- `--reasoning-format none`
- `--reasoning-budget 0`

If thinking is left enabled, Qwen3.5 can emit an empty `message.content` plus `reasoning_content`, which the current runtime treats as a failed model reply and silently falls back to the heuristic adapter.

The promoted runtime also follows the `Qwen/Qwen3.5-4B` Hugging Face non-thinking general-task sampling guidance:

- `temperature=0.7`
- `top_p=0.8`
- `top_k=20`
- `min_p=0.0`
- `presence_penalty=1.5`
- `repeat_penalty=1.0` on the llama.cpp wire (`repetition_penalty` in the Qwen model card)

## Adapter GGUF Export

fine-tuned LoRA adapter를 GGUF로 export:

```bash
python run_export_gguf.py ^
  --mode adapter ^
  --adapter-path data/test_artifacts/qwen3_5_4b_bootstrap_smoke_adapter ^
  --base-model Qwen/Qwen3.5-4B ^
  --llama-cpp-dir data/vendor/llama.cpp ^
  --output data/gguf/qwen3_5_4b_bootstrap_smoke_adapter-f16.gguf
```

현재 smoke artifact:

- `data/gguf/qwen3_5_4b_bootstrap_smoke_adapter-f16.gguf`

## Merged GGUF Export

먼저 merge:

```bash
python run_merge_lora_adapter.py ^
  --adapter-path data/test_artifacts/qwen3_5_4b_bootstrap_smoke_adapter ^
  --base-model Qwen/Qwen3.5-4B ^
  --output-dir data/merged/qwen3_5_4b_bootstrap_smoke_merged
```

그 다음 merged checkpoint를 GGUF로 export:

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

이 merged 경로는 `llama-quantize`가 필요하다.

## Base GGUF + Adapter GGUF Runtime

base quantized model과 exported adapter를 같이 사용해 local server 시작:

```powershell
powershell -ExecutionPolicy Bypass -File run_llama_server.ps1 `
  -ModelPath .\models\Qwen3.5-4B-Q4_K_M.gguf `
  -LoraPath data/gguf/qwen3_5_4b_bootstrap_smoke_adapter-f16.gguf `
  -Port 8000 `
  -ContextSize 4096 `
  -GpuLayers 99 `
  -Detached
```

또는 combined loop 사용:

```powershell
powershell -ExecutionPolicy Bypass -File run_local_qwen_dev_loop.ps1 `
  -ModelPath .\models\Qwen3.5-4B-Q4_K_M.gguf `
  -LoraPath data/gguf/qwen3_5_4b_bootstrap_smoke_adapter-f16.gguf `
  -Port 8000 `
  -ModelGateTurns 120
```

같은 local endpoint를 playable runtime에 연결:

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

## 메모

- `run_export_gguf.py --mode adapter`는 llama.cpp Python converter script만 있으면 된다
- merged `Q4_K_M` export는 `llama-quantize`가 필요하다
- `run_llama_server.ps1`와 `run_local_qwen_dev_loop.ps1`는 이제 promoted Qwen3.5 runtime 경로에서 `--reasoning-format none`과 `--reasoning-budget 0`를 강제한다
- 현재 smoke GGUF는 export path 증명용이지, 승격 가능한 모델은 아니다
- 실제 승격은 더 강한 4B checkpoint가 model gate를 통과한 뒤에만 가능하다
