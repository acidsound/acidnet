# WSL2 Unsloth 학습 경로

## 목적

4B LoRA 학습을 Windows fallback 경로에서 분리하고, Qwen3.5 최적화 커널을 더 자연스럽게 쓰는 Linux 우선 스택으로 옮긴다.

이 경로는 학습 전용이다.
Windows GUI와 로컬 플레이 루프는 그대로 유지된다.

## 왜 이 경로가 필요한가

현재 Windows HF/PEFT 경로는 기능적으로는 맞지만, 실사용 승격 런을 돌리기에는 너무 느리다.

- `torch` 자체는 동작한다
- 하지만 Qwen3.5 fast path를 타지 못한다
- 로그에 `flash-linear-attention`, `causal-conv1d` 부재로 인한 fallback이 찍힌다
- 현재 Windows Python 환경에는 invalid distribution 경고도 섞여 있다

WSL2는 Unsloth와 관련 CUDA 커널을 더 안정적으로 다룰 수 있는 Linux 패키지 경로를 제공한다.

## 진입점

- `run_wsl_qwen_training.ps1`
- `scripts/setup_wsl_uv_unsloth.sh`
- `scripts/launch_qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke.sh`
- `scripts/launch_qwen3_5_4b_runtime_dialogue_unsloth_wsl_full.sh`
- `run_bootstrap_qwen4b_pipeline.py`
- `run_export_gguf.py`
- `run_publish_hf_artifacts.py`

## 설정

WSL 전용 `uv` 환경을 만든다.

```powershell
powershell -ExecutionPolicy Bypass -File run_wsl_qwen_training.ps1 -Mode setup
```

이 명령은 기본적으로 프로젝트 루트에 Python 3.12 기반 `.venv-wsl`을 만들고 다음 패키지를 설치한다.

- CUDA `torch`
- `unsloth`
- `datasets`
- `trl`
- `peft`
- `accelerate`
- `bitsandbytes`
- `flash-linear-attention`
- `causal-conv1d`
- 프로젝트 training extras

이전 known-good 기준과 비교하거나 버전별 이슈를 분리해야 할 때만 `-PythonVersion 3.11`을 사용한다.

## Smoke Benchmark

유지 중인 runtime-dialogue bench split으로 WSL Unsloth benchmark를 돌린다.

```powershell
powershell -ExecutionPolicy Bypass -File run_wsl_qwen_training.ps1 -Mode smoke
```

기본 데이터셋:

- `data/sft/bench_train_1024.jsonl`
- `data/sft/bench_eval_128.jsonl`

특수 subset이 필요하면 `ACIDNET_WSL_TRAIN_DATASET`, `ACIDNET_WSL_EVAL_DATASET` override를 사용할 수 있다.

산출물:

- log: `data/logs/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke.log`
- adapter dir: `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_adapter`
- run spec: `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_run_spec.json`

## Full WSL Run

smoke benchmark가 통과하면 full 50k / 4k 데이터셋으로 진행한다.

```powershell
powershell -ExecutionPolicy Bypass -File run_wsl_qwen_training.ps1 -Mode full
```

산출물:

- log: `data/logs/qwen3_5_4b_runtime_dialogue_unsloth_wsl_full.log`
- adapter dir: `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_full_adapter`
- run spec: `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_full_run_spec.json`

## Hugging Face 복원 구조

현재 portability 경로는 Hugging Face repo 두 개를 기준으로 한다.

- model repo: `acidsound/acidnet_model`
- dataset repo: `acidsound/acidnet_dataset`

각 publish run은 `runs/<run-name>/` 아래에 안정된 내부 이름으로 저장된다.

Dataset repo 구조:

- `runs/<run-name>/prompt_packs/requests.parquet`
- `runs/<run-name>/prompt_packs/teacher_outputs.jsonl`
- `runs/<run-name>/sft/train.jsonl`
- `runs/<run-name>/sft/eval.jsonl`
- `runs/<run-name>/sft/bench_train_1024.jsonl`
- `runs/<run-name>/sft/bench_eval_128.jsonl`
- `runs/<run-name>/preferences/preferences.parquet`
- `runs/<run-name>/preferences/manifest.json`
- `runs/<run-name>/manifests/pipeline.json`
- `runs/<run-name>/manifests/run_spec.json`
- `runs/<run-name>/manifests/gate_report.json`
- `runs/<run-name>/manifests/publish_manifest.json`

Model repo 구조:

- `runs/<run-name>/adapter/...`
- `runs/<run-name>/gguf/adapter-f16.gguf`
- `runs/<run-name>/gguf/adapter_manifest.json`
- `runs/<run-name>/manifests/publish_manifest.json`

Hub repo는 registry일 뿐이다.
실제 학습과 런타임은 여전히 로컬 `data/`와 `models/` 경로를 읽는다.

새 머신에서 복원할 때의 로컬 경로:

- prompt-pack provenance -> `data/prompt_packs/`
- train/eval 및 bench split -> `data/sft/`
- optional RL 선행 preference bundle -> `data/preferences/`
- pipeline 및 run metadata -> `data/training/`
- gate reports -> `data/eval/`
- final PEFT adapter -> `data/training/<run-name>_adapter/`
- LoRA GGUF -> `data/gguf/`
- base quantized model -> `models/Qwen3.5-4B-Q4_K_M.gguf`

Base `Q4_K_M` 파일은 의도적으로 HF adapter repo 밖에 둔다.
새 머신에 이 파일이 없다면 승격된 runtime 경로에서 `llama-server`를 띄우기 전에 `models/Qwen3.5-4B-Q4_K_M.gguf`로 먼저 복원하거나 다운로드해야 한다.
Maintained reference source:

- `https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf`

Promoted runtime note:

- `llama-server` 경로에서는 `--reasoning-format none`과 `--reasoning-budget 0`로 Qwen thinking을 꺼둔다
- 이 small-model runtime에서는 thinking mode가 `reasoning_content`로 출력이 빠져 heuristic fallback을 유발할 수 있으므로 deployment error로 취급한다

## End-To-End 갱신 순서

유지 중인 갱신 순서는 다음과 같다.

1. canonical bootstrap 데이터를 다시 생성한다.

```powershell
python run_bootstrap_qwen4b_pipeline.py
```

2. WSL smoke lane을 돌린다.

```powershell
powershell -ExecutionPolicy Bypass -File run_wsl_qwen_training.ps1 -Mode smoke
```

3. WSL full lane을 돌린다.

```powershell
powershell -ExecutionPolicy Bypass -File run_wsl_qwen_training.ps1 -Mode full
```

4. fresh adapter를 gate한다.

```powershell
python run_model_gate.py `
  --dialogue-backend local_peft `
  --dialogue-model Qwen/Qwen3.5-4B `
  --dialogue-adapter-path data/training/<run-name>_adapter `
  --turns 120 `
  --output data/eval/model_gate_<run-name>_report.json
```

5. adapter GGUF를 export한다.

```powershell
python run_export_gguf.py `
  --mode adapter `
  --adapter-path data/training/<run-name>_adapter `
  --base-model Qwen/Qwen3.5-4B `
  --llama-cpp-dir data/vendor/llama.cpp `
  --output data/gguf/<run-name>_adapter-f16.gguf `
  --manifest-output data/gguf/<run-name>_adapter_manifest.json
```

6. run 전체를 Hugging Face에 publish한다.

```powershell
python run_publish_hf_artifacts.py `
  --run-name <run-name> `
  --adapter-dir data/training/<run-name>_adapter_publish `
  --gguf-path data/gguf/<run-name>_adapter-f16.gguf `
  --gguf-path data/gguf/<run-name>_adapter_manifest.json `
  --dataset-file data/prompt_packs/bootstrap_teacher_requests.parquet `
  --dataset-file data/prompt_packs/bootstrap_teacher_outputs.jsonl `
  --dataset-file data/sft/train_bootstrap_teacher_sft_dataset.jsonl `
  --dataset-file data/sft/eval_bootstrap_teacher_sft_dataset.jsonl `
  --dataset-file data/sft/bench_train_1024.jsonl `
  --dataset-file data/sft/bench_eval_128.jsonl `
  --dataset-file data/preferences/bootstrap_dialogue_preferences.parquet `
  --dataset-file data/preferences/bootstrap_dialogue_preferences_manifest.json `
  --dataset-file data/training/bootstrap_qwen4b_pipeline.json `
  --dataset-file data/training/<run-name>_run_spec.json `
  --dataset-file data/eval/model_gate_<run-name>_report.json `
  --base-model Qwen/Qwen3.5-4B
```

## 현재 측정 결과

기본 WSL smoke 경로는 Python 3.12 기준으로 다시 검증됐다.

- 기본 `.venv-wsl` setup probe 결과는 `Python 3.12.10`, `unsloth 2026.3.3`, `fla 0.4.1`, `causal_conv1d 1.6.0`
- 표준 smoke artifact:
  - `data/logs/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke.log`
  - `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_adapter/`
  - `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_run_spec.json`
- 현재 유지 중인 `1024 / 128` bench smoke 학습 시간: `train_runtime = 169 s`
- 현재 유지 중인 `1024 / 128` bench smoke 처리량: `train_samples_per_second = 6.06`, `train_steps_per_second = 0.379`
- 표준 smoke 로그에는 `Fast Qwen3_5 patching`, `FA [Xformers = 0.0.35. FA2 = False]`가 확인된다
- launcher-side dependency check는 이제 `unsloth`를 `trl`보다 먼저 import하므로 예전 import-order warning이 다시 나오지 않는다

첫 full WSL candidate도 완료되어 있다.

- adapter: `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_full_adapter`
- gate report: `data/eval/model_gate_runtime_dialogue_unsloth_wsl_full_report.json`
- full gate 결과: `PASS`
- full prompt average score: `1.000`
- full prompt average latency: `2994.443 ms`
- full circulation score: `0.925`
- full starving NPCs: `0`
- full train runtime: `6999 s`

Windows `local_peft` loader는 이제 adapter metadata를 읽으므로 WSL에서 학습한 Unsloth adapter를 예전 missing-key warning 없이 로드한다.

## 메모

- WSL2가 안정적으로 가능하면 이 경로를 우선한다
- `uv`는 환경 재현성을 높이지만, 그것만으로 학습 속도가 빨라지는 것은 아니다
- 실제 성능 개선은 Linux 우선 Unsloth 경로를 타는 데서 기대한다
- 더 큰 미래 런에서는 `/mnt/...`보다 WSL 내부 파일시스템으로 hot data와 cache를 옮기는 편이 좋다
- 큰 raw log는 기본 Hugging Face publish 대상에 넣지 말고, 요약 수치와 portable manifest를 Hub에 남기는 쪽이 낫다
- launcher/generator source는 git에 두고, generated `train_*.py`는 canonical source가 아니라 run artifact로 취급한다
