# Bootstrap Teacher 에서 Local Adapter 까지

## 목적

외부 teacher completion에 의존하지 않고 첫 소형 모델 루프를 닫는다.

1. synthetic prompt pack 생성
2. 같은 월드 맥락에서 bootstrap teacher output 합성
3. SFT JSONL / Parquet dataset 생성
4. LoRA fine-tune 실행
5. 기존 OpenAI-compatible runtime 경계 뒤에 adapter를 붙여 서빙

## 구현된 진입점

- `src/acidnet/training/bootstrap_teacher.py`
- `run_bootstrap_qwen4b_pipeline.py`
- `src/acidnet/training/hf_peft_runner.py`
- `run_qwen4b_baseline_train.py`
- `run_local_adapter_server.py`
- `run_local_adapter_dev_loop.ps1`

## 현재 기본 경로

전체 bootstrap dataset 생성:

```bash
python run_bootstrap_qwen4b_pipeline.py ^
  --mode synthetic ^
  --scenarios 2048 ^
  --turns 4 ^
  --tasks dialogue ^
  --format both ^
  --train-rows 50000 ^
  --eval-rows 4000 ^
  --trainer-backend hf_peft ^
  --sft-variant runtime_dialogue
```

full `50k / 4k` runtime-dialogue LoRA 본학습을 올리고, 끝나면 `local_peft` 기준 gate까지 바로 확인:

```bash
python run_bootstrap_qwen4b_pipeline.py ^
  --mode synthetic ^
  --scenarios 2048 ^
  --turns 4 ^
  --tasks dialogue ^
  --format both ^
  --train-rows 50000 ^
  --eval-rows 4000 ^
  --trainer-backend hf_peft ^
  --sft-variant runtime_dialogue ^
  --training-output-dir data/training/qwen3_5_4b_runtime_dialogue_full_adapter ^
  --run-spec-output data/training/qwen3_5_4b_runtime_dialogue_full_run_spec.json ^
  --training-script-output data/training/train_qwen3_5_4b_runtime_dialogue_full.py ^
  --launch-train ^
  --run-gate ^
  --gate-output data/eval/qwen3_5_4b_runtime_dialogue_full_gate_report.json
```

현재 생성되는 주요 artifact:

- `data/prompt_packs/bootstrap_teacher_requests.jsonl`
- `data/prompt_packs/bootstrap_teacher_requests.parquet`
- `data/prompt_packs/bootstrap_teacher_outputs.jsonl`
- `data/sft/bootstrap_teacher_sft_dataset.jsonl`
- `data/sft/bootstrap_teacher_sft_dataset.parquet`
- `data/sft/train_bootstrap_teacher_sft_dataset.jsonl`
- `data/sft/train_bootstrap_teacher_sft_dataset.parquet`
- `data/sft/eval_bootstrap_teacher_sft_dataset.jsonl`
- `data/sft/eval_bootstrap_teacher_sft_dataset.parquet`
- `data/training/qwen3_5_4b_bootstrap_baseline_run_spec.json`
- `data/training/train_qwen3_5_4b_bootstrap_baseline.py`

## 현재 데이터셋 스냅샷

최근 생성된 bootstrap dataset:

- prompt rows: `73728`
- teacher rows: `73728`
- train rows: `50000`
- eval rows: `4000`
- task focus: `dialogue`
- trainer backend: `hf_peft`
- sft variant: `runtime_dialogue`

상세:

- `data/training/bootstrap_qwen4b_pipeline.json`

## Smoke Fine-Tune 결과

bootstrap dataset 형태를 대상으로 하는 작은 HF/PEFT LoRA smoke run은 이미 성공했다.
유지 중인 runtime-dialogue smoke benchmark는 이제 `data/sft` 아래의 표준 `1024 train / 128 eval` bench split을 기준으로 돈다.

artifact:

- `data/test_artifacts/train_bootstrap_smoke.jsonl`
- `data/test_artifacts/eval_bootstrap_smoke.jsonl`
- `data/test_artifacts/qwen3_5_4b_bootstrap_smoke_adapter/`
- `data/sft/bench_train_1024.jsonl`
- `data/sft/bench_eval_128.jsonl`
- `data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_adapter/`

확인된 사실:

- 유지 중인 bench split 기준 학습이 정상 완료됐다
- adapter weight가 정상적으로 기록됐다
- 최신 표준 WSL smoke benchmark는 Python 3.12 기준 `train_runtime=169 s`, `train_samples_per_second=6.06`, `train_steps_per_second=0.379` 이다
- WSL fast-path 는 `flash-linear-attention`, `causal-conv1d`가 활성화된 상태다
- runtime-dialogue smoke 트랙은 이미 `prompt_avg=1.000`, `prompt_fail_rows=0`, `prompt_latency_ms=1672.6`, `circulation=0.925` 수준의 gate-clearing adapter를 보여줬다

## Local Adapter Runtime

fine-tuned adapter 서빙:

```bash
python run_local_adapter_server.py ^
  --adapter-path data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_adapter ^
  --base-model Qwen/Qwen3.5-4B ^
  --model-alias acidnet-qwen3.5-4b-smoke ^
  --port 8011
```

기존 evaluation/runtime 경로에 연결:

```bash
python run_prompt_only_baseline_eval.py ^
  --dialogue-backend openai_compat ^
  --dialogue-model acidnet-qwen3.5-4b-smoke ^
  --dialogue-endpoint http://127.0.0.1:8011/v1/chat/completions
```

```powershell
powershell -ExecutionPolicy Bypass -File run_local_adapter_dev_loop.ps1 `
  -AdapterPath data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_adapter `
  -ModelAlias acidnet-qwen3.5-4b-smoke `
  -TailLog
```

같은 adapter를 HTTP bridge 없이 CLI나 GUI에 직접 붙여 실행:

```bash
python run_acidnet.py ^
  --no-persist ^
  --dialogue-backend local_peft ^
  --dialogue-model Qwen/Qwen3.5-4B ^
  --dialogue-adapter-path data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke_adapter
```

또는 dev launcher 에 직접 local adapter 를 연결:

```powershell
powershell -ExecutionPolicy Bypass -File run_local_adapter_dev_loop.ps1 `
  -AdapterPath data/training/qwen3_5_4b_runtime_dialogue_unsloth_wsl_full_adapter `
  -ModelAlias acidnet-qwen3.5-4b-full `
  -TailLog
```

## 현재 판단

- end-to-end 기술 경로는 동작한다
- 첫 tiny smoke adapter는 승격할 수준이 아니었다
- runtime-dialogue smoke adapter는 현재 로컬 모델 baseline으로 써도 될 수준이다
- 작은 모델 경로에서는 training과 runtime 모두에서 thinking을 끈 상태를 유지해야 한다
- NPC 대사 승격 경로의 기본은 runtime dialogue SFT다
- runtime dialogue SFT 는 예전 bootstrap interaction label 을 실제 runtime 모드인 `talk`, `rumor_request`, `trade_request`, `direct_say` 로 정규화한다
- 하지만 world mutation은 계속 rule-based simulation이 맡고 있어서 world circulation 자체는 안정적이다

## 바로 다음 작업

- smoke gate가 통과된 지금, full bootstrap dataset 기반의 더 큰 4B LoRA run을 실행하고 direct `local_peft` gate 를 통과한 첫 checkpoint 를 승격
- runtime transcript를 dataset mix에 다시 추가
- direct `local_peft` 경로의 latency 감소
- 더 큰 checkpoint가 자리 잡으면 GGUF export 경로 준비
