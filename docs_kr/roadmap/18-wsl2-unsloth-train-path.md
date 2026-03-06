# WSL2 Unsloth 학습 경로

## 목적

4B LoRA 학습을 Windows fallback 경로에서 분리하고, Qwen3.5 최적화 커널을 더 쓰기 쉬운 Linux 중심 스택으로 옮긴다.

이 경로는 학습 전용이다.
Windows GUI와 실제 플레이 루프는 그대로 유지한다.

## 이 경로가 필요한 이유

현재 Windows HF/PEFT 경로는 기능적으로는 맞지만, 승격용 본학습을 돌리기에는 너무 느리다.
이유는 다음과 같다.

- `torch` 자체는 정상이다
- 하지만 Qwen3.5 fast path를 타지 못한다
- 로그에 `flash-linear-attention`, `causal-conv1d` 부재로 fallback이 찍힌다
- 현재 Windows Python 환경에는 invalid distribution 경고도 있다

WSL2는 Unsloth와 관련 CUDA 커널을 더 깨끗하게 설치할 수 있는 Linux 패키지 경로를 제공한다.

## 진입점

- `run_wsl_qwen_training.ps1`
- `scripts/setup_wsl_uv_unsloth.sh`
- `scripts/launch_qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke.sh`
- `scripts/launch_qwen3_5_4b_runtime_dialogue_unsloth_wsl_full.sh`

## 설정

WSL 전용 `uv` 환경을 만든다.

```powershell
powershell -ExecutionPolicy Bypass -File run_wsl_qwen_training.ps1 -Mode setup
```

이 명령은 프로젝트 루트에 `.venv-wsl`을 만들고 Python 3.11과 다음 패키지를 설치한다.

- CUDA `torch`
- `unsloth`
- `datasets`
- `trl`
- `peft`
- `accelerate`
- `bitsandbytes`
- `flash-linear-attention`
- `causal-conv1d`
- 프로젝트 학습 extra

## Smoke Benchmark

기존 runtime-dialogue smoke dataset으로 작은 WSL Unsloth benchmark를 돌린다.

```powershell
powershell -ExecutionPolicy Bypass -File run_wsl_qwen_training.ps1 -Mode smoke
```

생성물:

- log: `data/logs/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke.log`
- adapter dir: `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_adapter`
- run spec: `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_run_spec.json`

## Full WSL Run

smoke benchmark가 통과하면 full 50k / 4k dataset으로 넘어간다.

```powershell
powershell -ExecutionPolicy Bypass -File run_wsl_qwen_training.ps1 -Mode full
```

생성물:

- log: `data/logs/qwen3_5_4b_runtime_dialogue_unsloth_wsl_full.log`
- adapter dir: `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_full_adapter`
- run spec: `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_full_run_spec.json`

## 현재 측정 결과

WSL smoke 경로는 이제 검증됐다.

- adapter: `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_adapter`
- gate report: `data/eval/model_gate_runtime_dialogue_unsloth_wsl_smoke_report.json`
- gate 결과: `PASS`
- prompt average score: `1.000`
- prompt average latency: `2554.396 ms`
- circulation score: `0.925`
- starving NPCs: `0`

같은 `2048 / 256` smoke dataset 기준 학습 시간 개선:

- fast-path 설치 전 WSL smoke: `train_runtime = 1204 s`
- `flash-linear-attention`, `causal-conv1d` 설치 후 WSL smoke: `train_runtime = 335 s`

## 메모

- WSL2가 안정적으로 사용 가능하면 이 경로를 우선한다
- `uv`는 환경 재현성을 높이지만, 그 자체로 학습 속도를 올리지는 않는다
- 실제 성능 개선은 Linux 중심 Unsloth 경로를 타는 데서 기대한다
- 이후 더 큰 학습에서는 `/mnt/...` 마운트보다 WSL 내부 파일시스템으로 hot data와 cache를 옮기는 편이 낫다
