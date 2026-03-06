# Model Gate

## 목적

dataset 생성이나 fine-tuning, 더 큰 모델로 넘어가기 전에 backend 는 하나의 combined gate 를 통과해야 한다:

- dialogue 품질이 허용 가능한가
- world circulation 이 안정적인가

이 단계는 프로젝트가 `작고, 단순하고, 정밀한 모델` 원칙을 실제로 지키게 만든다.

## 진입점

- `src/acidnet/eval/model_gate.py`
- `run_model_gate.py`

## Gate 입력

- prompt-only dialogue evaluation
- 고정 turn 수에 대한 circulation evaluation

## 현재 통과 기준

- `prompt_average_score >= 0.85`
- `prompt_rows_with_failures <= 2`
- `average_active_locations >= 4.0`
- `starving_npc_count <= 1`
- `hard_clustering` flag 가 없어야 함

## 실행 예시

Heuristic control:

```bash
python run_model_gate.py --dialogue-backend heuristic --turns 60
```

OpenAI-compatible local backend:

```bash
python run_model_gate.py ^
  --dialogue-backend openai_compat ^
  --dialogue-model qwen3.5-4b ^
  --dialogue-endpoint http://127.0.0.1:8000/v1/chat/completions ^
  --turns 120
```

같은 gate 를 돌린 뒤 GUI 로 바로 관찰:

```powershell
powershell -ExecutionPolicy Bypass -File run_dev_world.ps1 `
  -DialogueBackend openai_compat `
  -DialogueModel qwen3.5-4b `
  -DialogueEndpoint http://127.0.0.1:8000/v1/chat/completions `
  -RunModelGate `
  -Detached
```

## 출력

```text
data/eval/model_gate_report.json
```

## 왜 중요한가

- heuristic, prompt-only 4B, future fine-tuned 4B 를 같은 report 형태로 비교할 수 있다
- sample dialogue 는 좋아 보여도 live world 를 망치는 모델 변경을 막는다
- 더 작은 모델이 명확히 실패하기 전까지 9B 로 새는 것을 막는다

## 다음 작업

- backend/model 별로 model-gate report 를 따로 저장
- local backend 의 latency 와 timeout 측정 추가
- SFT 이후 fine-tuned checkpoint 도 같은 gate 로 비교
