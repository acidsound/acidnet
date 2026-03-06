# GGUF Export 상태

## 현재 상태

GGUF export 경로는 구현됐고, LoRA adapter 기준 smoke test까지 끝났다.

구현된 항목:

- llama.cpp toolchain 탐지
- adapter GGUF export
- merged HF checkpoint merge helper
- merged GGUF export command 생성
- optional quantization command 생성
- `llama-server`에 `--lora` / `--lora-scaled`를 전달할 수 있는 runtime launcher

## Smoke Artifact

생성된 artifact:

- `data/gguf/qwen3_5_4b_bootstrap_smoke_adapter-f16.gguf`

manifest:

- `data/gguf/qwen3_5_4b_bootstrap_smoke_adapter_manifest.json`

## 실전 승격 경로

1. model gate를 통과하는 4B checkpoint를 학습한다
2. adapter를 GGUF로 export한다
3. base `Q4_K_M` GGUF와 adapter GGUF를 같이 `llama-server`에 태운다
4. 같은 checkpoint를 실제 GUI loop에서 다시 검증한다
5. 그 다음에야 fully merged `Q4_K_M` 빌드를 검토한다

## 왜 이 경로가 먼저인가

- runtime footprint가 더 작다
- iteration 비용이 더 낮다
- 모델 revision마다 큰 merged checkpoint를 계속 쓰지 않아도 된다
- 검증된 training artifact와 deployment artifact의 거리가 더 가깝다
