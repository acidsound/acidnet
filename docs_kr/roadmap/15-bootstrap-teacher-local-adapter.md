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
재생성한 full bootstrap dataset에서 잘라낸 `2048 train / 256 eval` 기준의 runtime-dialogue smoke run도 성공했다.

artifact:

- `data/test_artifacts/train_bootstrap_smoke.jsonl`
- `data/test_artifacts/eval_bootstrap_smoke.jsonl`
- `data/test_artifacts/qwen3_5_4b_bootstrap_smoke_adapter/`
- `data/test_artifacts/train_runtime_dialogue_smoke_2048.jsonl`
- `data/test_artifacts/eval_runtime_dialogue_smoke_256.jsonl`
- `data/test_artifacts/qwen3_5_4b_runtime_dialogue_smoke_adapter/`

확인된 사실:

- 2 epoch 학습이 끝까지 완료됐다
- adapter weight가 정상적으로 기록됐다
- 해당 adapter를 local runtime server 뒤에 붙여 서빙할 수 있다
- 같은 adapter를 in-process `local_peft` backend로도 직접 실행할 수 있다
- runtime-dialogue smoke adapter는 combined model gate를 통과했다
- 현재 gate 결과: `prompt_avg=1.000`, `prompt_fail_rows=0`, `prompt_latency_ms=1672.6`, `circulation=0.925`

## Local Adapter Runtime

fine-tuned adapter 서빙:

```bash
python run_local_adapter_server.py ^
  --adapter-path data/test_artifacts/qwen3_5_4b_bootstrap_smoke_adapter ^
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
  -AdapterPath data/test_artifacts/qwen3_5_4b_bootstrap_smoke_adapter `
  -ModelAlias acidnet-qwen3.5-4b-smoke `
  -NoMonkey
```

같은 adapter를 HTTP bridge 없이 CLI나 GUI에 직접 붙여 실행:

```bash
python run_acidnet.py ^
  --no-persist ^
  --dialogue-backend local_peft ^
  --dialogue-model Qwen/Qwen3.5-4B ^
  --dialogue-adapter-path data/test_artifacts/qwen3_5_4b_runtime_dialogue_smoke_adapter
```

```bash
python run_acidnet_gui.py ^
  --no-persist ^
  --dialogue-backend local_peft ^
  --dialogue-model Qwen/Qwen3.5-4B ^
  --dialogue-adapter-path data/test_artifacts/qwen3_5_4b_runtime_dialogue_smoke_adapter
```

## 현재 판단

- end-to-end 기술 경로는 동작한다
- 첫 tiny smoke adapter는 승격할 수준이 아니었다
- runtime-dialogue smoke adapter는 현재 로컬 모델 baseline으로 써도 될 수준이다
- 작은 모델 경로에서는 training과 runtime 모두에서 thinking을 끈 상태를 유지해야 한다
- NPC 대사 승격 경로의 기본은 runtime dialogue SFT다
- 하지만 world mutation은 계속 rule-based simulation이 맡고 있어서 world circulation 자체는 안정적이다

## 바로 다음 작업

- smoke gate가 통과된 지금, full bootstrap dataset 기반의 더 큰 4B LoRA run 실행
- runtime transcript를 dataset mix에 다시 추가
- direct `local_peft` 경로의 latency 감소
- 더 큰 checkpoint가 자리 잡으면 GGUF export 경로 준비
