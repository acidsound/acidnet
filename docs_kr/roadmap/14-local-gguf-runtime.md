# Local GGUF Runtime

## 목적

이제 프로젝트는 두 가지 GGUF runtime 형태를 지원한다.

1. base `Q4_K_M` 모델 + LoRA GGUF adapter
2. llama.cpp quantization tool이 있을 때 merged checkpoint 전체를 GGUF로 변환하는 경로

Windows 기본 승격 경로는 첫 번째다. 큰 merged export 단계를 피할 수 있기 때문이다.

## 진입점

- `run_export_gguf.py`
- `run_merge_lora_adapter.py`
- `run_llama_server.ps1`
- `run_local_qwen_dev_loop.ps1`
- `run_dev_world.ps1`

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

## 메모

- `run_export_gguf.py --mode adapter`는 llama.cpp Python converter script만 있으면 된다
- merged `Q4_K_M` export는 `llama-quantize`가 필요하다
- 현재 smoke GGUF는 export path 증명용이지, 승격 가능한 모델은 아니다
- 실제 승격은 더 강한 4B checkpoint가 model gate를 통과한 뒤에만 가능하다
