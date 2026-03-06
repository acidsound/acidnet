# 실행 체크리스트

## 목표

플레이어가 월드를 돌아다니며 NPC 와 대화하고 거래하고 rumor 를 모을 수 있는 simulation-first village RPG 를 만들고, 최종적으로는 이 세계에 맞게 조여진 local persona/dialogue model 을 붙인다.

## 최우선 목표

1. 월드 안에서 독립된 개체처럼 행동하면서 소형 로컬 언어 모델을 사용하는 NPC 를 완성한다.
2. entropy, 생산, 거래, 허기, rumor, 회복이 순환하며 정체되지 않는 월드를 완성한다.

## 모델 선택 원칙

- 충분하다면 더 작은 모델이 더 낫다.
- 더 잘 통제된다면 더 단순한 모델이 더 낫다.
- 표현력이 조금 높더라도 불안정한 모델보다, 더 정밀한 모델이 낫다.
- 더 작은 모델이 실제 월드 행동에서 분명히 실패할 때만 더 큰 모델로 올라간다.

## 지금 당장 후순위인 것

- simulation 과 local-model loop 가 검증되기 전의 대형 프론트엔드 확장
- 소형 모델 경로가 실제 게임 루프 안에서 입증되기 전의 9B 확장

## 작업 규칙

- 주요 시스템이나 실행 경로가 바뀌면 `docs/roadmap/` 와 `docs_kr/roadmap/` 를 함께 갱신한다.
- 문서 안의 경로는 프로젝트 루트 기준 상대경로만 사용하고, 절대경로는 쓰지 않는다.
- world mutation 은 rule-based 로 유지한다. local model 은 intent 나 dialogue 를 제안할 수 있지만 physics 나 economy 를 직접 쓰지 않는다.
- `GGUF q4_k_m` 는 deployment artifact 로 보고, primary fine-tuning artifact 로 다루지 않는다.
- Windows 기본 persistence 는 SQLite 로 두고, `zvec` 는 Linux/macOS 배포 경로의 optional 선택지로 유지한다.

## 단계 체크리스트

- [x] Step 00: 아키텍처 및 구현 계획 문서 작성
- [x] Step 01: 프로젝트 스켈레톤 및 코어 스키마 작성
- [x] Step 02: deterministic tick engine 및 scheduler 추가
- [x] Step 03: map, location, movement rule 추가
- [x] Step 04: hunger, food inventory, consumption 추가
- [x] Step 05: market price feedback 및 trade execution 추가
- [x] Step 06: rumor lifecycle 및 relationship update 추가
- [x] Step 07: 현재 lightweight hook 을 넘는 memory retrieval 및 belief reflection job 추가
- [x] Step 08: heuristic planner 및 intent validation 추가
- [x] Step 09: 플레이 가능한 터미널 MVP 추가
- [x] Step 10: SQLite world snapshot persistence 추가
- [x] Step 11: keyboard-driven GUI frontend 추가
- [x] Step 12: teacher prompt schema 및 synthetic dataset export 추가
- [ ] Step 13: Qwen3.5 4B 대 9B fine-tuning experiment harness 추가
- [ ] Step 14: 검증된 persona checkpoint 를 GGUF `q4_k_m` 로 export
- [ ] Step 15: local persona/dialogue runtime adapter 추가
- [ ] Step 16: evaluation harness 및 model selection report 추가
- [ ] Step 17: dialogue/persona consistency 전용 optional RL 추가

## 현재 집중 단계

현재 구현 초점은 Step 13 이다:

- 첫 4B baseline run 정의
- 9B challenger run 정의
- GPT-5.3 teacher prompt pack 을 JSONL 과 Parquet 로 대량 생성
- teacher completion 생성을 위한 OpenAI batch request artifact 준비
- OpenAI batch output 을 `teacher_outputs.jsonl` 로 정규화
- 4B baseline 용 첫 Unsloth training script 준비
- 긴 fine-tuning run 전에 prompt-only base-model 동작 검증
- 긴 fine-tuning run 전에 selection criteria 를 고정

실질적으로는 다음 뜻이다:

- 모델 크기 확장보다 소형 모델 기반 NPC 루프가 더 중요하다
- UI 확장보다 월드 순환성과 entropy 안정성이 더 중요하다
- player 의 생존과 earning loop 도 같은 rule-based economy 안에서 닫혀야 한다

## 프로토타입 상태

현재 저장소에는 다음이 있다:

- 터미널 런타임: `run_acidnet.py`
- 키보드 GUI 런타임: `run_acidnet_gui.py`
- SQLite persistence 경로: `data/acidnet.sqlite`
- teacher dataset export 경로: `run_teacher_prompt_export.py`
- fine-tuning experiment manifest export: `run_finetune_manifest_export.py`

구현된 시스템:

- village map 과 movement
- NPC dialogue 와 rumor sharing
- player 가 gold 를 벌거나 food 를 모을 수 있는 work loop
- vendor trading 과 food consumption
- deterministic tick progression
- heuristic NPC planner
- memory retrieval scoring 과 belief refresh
- deterministic fallback 이 있는 openai-compatible dialogue adapter boundary
- world snapshot persistence
- planner/dialogue 용 synthetic teacher prompt generation
- prompt-only baseline evaluation harness
- world circulation evaluation harness
- teacher run 용 OpenAI batch request 준비
- teacher-output JSONL 로의 OpenAI batch output 정규화
- Unsloth 4B baseline run-spec 과 training-script export

## 다음 단계의 종료 조건

- 첫 fine-tuning run 정의에서 4B baseline 과 9B challenger 가 모호하지 않게 구분되어야 한다
- export 된 dataset 은 고정 seed 로 재현 가능해야 한다
- evaluation 은 persona consistency, world consistency, latency, memory fit 을 포함해야 한다
