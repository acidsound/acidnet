# 모델 선별 및 데이터셋 파이프라인

## 현재 상태

구현 완료:

- 4B 대 9B 모델 실험 레지스트리
- GPT-5.3 teacher prompt 템플릿
- synthetic scenario 생성기
- JSONL export
- optional `pyarrow` 기반 Parquet export
- teacher-output 에서 SFT dataset 으로 병합하는 경로

진입점:

- `run_teacher_prompt_export.py`
- `run_teacher_sft_merge.py`
- `src/acidnet/training/experiment_registry.py`
- `src/acidnet/training/dataset_builder.py`
- `src/acidnet/training/teacher_prompts.py`
- `src/acidnet/training/sft_dataset.py`

## 실험 순서

- baseline: `Qwen3.5-4B`
- challenger: `Qwen3.5-9B`
- 판단 기준: 9B는 비용과 지연을 감수할 만큼 persona fidelity와 world consistency에서 확실히 이길 때만 채택

## 데이터셋 형태

각 rollout은 다음 supervision을 만든다:

- planner supervision row
- dialogue supervision row
- dialogue sample 안의 player interaction context
- 필터링과 평가에 쓸 scenario metadata

현재 synthetic dataset에는 다음이 들어간다:

- world tick, day, weather, scarcity, market prices
- location context
- player inventory, money, hunger, rumor knowledge
- NPC inventory, hunger, beliefs, relationships, memories, vendor flag
- nearby NPC summary
- player prompt 와 expected focus 를 포함한 interaction context

## 실행 명령

Parquet 지원이 필요하면:

```bash
python -m pip install -e .[training]
```

작은 검증용 prompt pack:

```bash
python run_teacher_prompt_export.py --mode synthetic --scenarios 32 --turns 4 --format both
```

현재 9-NPC village 기준 약 5만 row:

```bash
python run_teacher_prompt_export.py --mode synthetic --scenarios 704 --turns 4 --format both
```

현재 9-NPC village 기준 약 14.7만 row:

```bash
python run_teacher_prompt_export.py --mode synthetic --scenarios 2048 --turns 4 --format both
```

row 계산식:

```text
rows = scenarios * turns * npc_count * 2
```

## Parquet 메모

- JSONL은 teacher request artifact 로 가장 다루기 쉽다.
- Parquet는 학습 전처리, 필터링, batch analytics 에 더 적합하다.
- 현재 Parquet export 는 `pyarrow` 에 의존한다.

## 다음 작업

- export 한 prompt pack 에 실제 GPT-5.3 teacher response 를 수집하기
- 장시간 파인튜닝 전에 evaluation split 을 고정하기
- 첫 4B baseline run 설정을 문서와 스크립트로 확정하기
