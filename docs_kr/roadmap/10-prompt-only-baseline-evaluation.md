# Prompt-Only Baseline 평가

## 왜 이 단계가 필요한가

파인튜닝 전에, base 소형 모델이 prompt engineering 만으로도 실제 생태계 안에서 어느 정도 기능하는지 먼저 검증한다.

이 단계가 중요한 이유:

- 파인튜닝이 정말 필요한지 먼저 알 수 있다
- 파인튜닝이 필요해도 supervision 범위를 줄일 수 있다
- prompt 제어만으로 충분한 부분까지 과하게 학습시키는 일을 막는다

## 현재 구현

구현 완료:

- runtime dialogue adapter boundary
- deterministic rule-based fallback
- local model server 를 위한 openai-compatible backend hook
- 고정 demo case 기반 prompt-only evaluation harness

진입점:

- `src/acidnet/llm/`
- `run_prompt_only_baseline_eval.py`
- `src/acidnet/eval/prompt_only.py`

## 권장 검증 순서

1. heuristic backend 를 control 로 먼저 돌린다.
2. openai-compatible local server 에 붙인 base `Qwen3.5-4B` 를 돌린다.
3. 어떤 fine-tuning run 이든 시작하기 전에 prompt-only 결과를 비교한다.

## 실행 예시

Heuristic control:

```bash
python run_prompt_only_baseline_eval.py --dialogue-backend heuristic
```

Prompt-only local model 점검:

```bash
python run_prompt_only_baseline_eval.py ^
  --dialogue-backend openai_compat ^
  --dialogue-model qwen3.5-4b ^
  --dialogue-endpoint http://127.0.0.1:8000/v1/chat/completions
```

같은 backend 로 live CLI 실행:

```bash
python run_acidnet.py ^
  --dialogue-backend openai_compat ^
  --dialogue-model qwen3.5-4b ^
  --dialogue-endpoint http://127.0.0.1:8000/v1/chat/completions
```

같은 backend 로 GUI 실행:

```bash
python run_acidnet_gui.py ^
  --dialogue-backend openai_compat ^
  --dialogue-model qwen3.5-4b ^
  --dialogue-endpoint http://127.0.0.1:8000/v1/chat/completions
```

## Harness 가 보는 항목

- 빈 응답이 아닌가
- 길이가 과도하지 않은가
- meta leakage 가 없는가
- rumor 질문에서 rumor 를 언급하는가
- trade 질문에서 실제 stock 을 언급하는가

## 판단 규칙

- prompt-only 4B 가 dialogue/persona 에 이미 충분하면 fine-tuning 범위를 더 좁힌다
- prompt-only 4B 가 주로 consistency 에서만 약하면 dialogue/persona 만 fine-tune 한다
- prompt-only 4B 가 intent quality 에서 심하게 흔들리면 planner 는 heuristic 로 유지하고 모델에 world control 을 맡기지 않는다

## 다음 작업

- 실제 base `Qwen3.5-4B` 서버에 붙여 prompt-only 평가 로그를 남긴다
- 주관적인 persona 품질에 대한 human review 를 추가한다
- 평가가 허용하는 최소 범위만 fine-tuning 한다
