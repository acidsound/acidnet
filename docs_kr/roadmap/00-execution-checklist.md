# 실행 체크리스트

## 목표

플레이어가 월드를 이동하고, NPC와 대화하고, 거래하고, 소문을 수집하며, 최종적으로는 작고 정밀한 로컬 persona/dialogue 모델을 붙여서 돌아가는 simulation-first village RPG를 만든다.

## 최우선 목표

1. 작은 로컬 언어모델을 사용하는 독립적인 NPC를 완성한다.
2. 엔트로피, 생산, 거래, 배고픔, 소문, 회복이 순환하면서 정체되지 않는 월드 루프를 완성한다.

## 모델 선택 원칙

- 충분하다면 더 작은 모델이 더 낫다.
- 더 통제 가능하다면 더 단순한 모델이 더 낫다.
- 불안정하게 풍부한 모델보다 정밀한 모델이 더 낫다.
- 더 큰 모델은 더 작은 모델이 실제 월드에서 명확히 실패할 때만 후보가 된다.

## 당장 비우선 항목

- 시뮬레이션과 로컬 모델 루프가 검증되기 전의 대형 프론트엔드 확장
- 소형 모델 경로가 증명되기 전의 9B 집착

## 작업 규칙

- 큰 실행 경로가 바뀔 때마다 `docs/roadmap/`와 `docs_kr/roadmap/`를 같이 갱신한다.
- 문서 안의 경로는 항상 프로젝트 루트 기준 상대경로만 사용한다.
- 월드 변경은 계속 rule-based로 유지한다. 로컬 모델은 intent나 dialogue를 제안할 수는 있지만 physics나 economy를 직접 쓰지 않는다.
- `GGUF q4_k_m`는 deployment artifact로 취급하고, 학습 원본으로 쓰지 않는다.
- Windows 기본 영속화는 SQLite로 유지하고, `zvec`는 선택적 배포 경로로만 본다.
- bootstrap teacher 생성 경로를 기본 dataset 경로로 사용한다. 외부 teacher completion은 선택적 보정 수단일 뿐 필수 경로가 아니다.

## 단계 체크리스트

- [x] Step 00: 아키텍처 및 구현 계획 문서 작성
- [x] Step 01: 프로젝트 골격과 핵심 스키마 생성
- [x] Step 02: deterministic tick engine 및 scheduler 추가
- [x] Step 03: 맵, location, 이동 규칙 추가
- [x] Step 04: hunger, food inventory, consumption 추가
- [x] Step 05: market price feedback 및 trade execution 추가
- [x] Step 06: rumor lifecycle 및 relationship update 추가
- [x] Step 07: lightweight hook을 넘는 memory retrieval 및 belief reflection 추가
- [x] Step 08: heuristic planner 및 intent validation 추가
- [x] Step 09: 플레이 가능한 terminal MVP 추가
- [x] Step 10: SQLite world snapshot persistence 추가
- [x] Step 11: keyboard GUI frontend 추가
- [x] Step 12: teacher prompt schema 및 synthetic dataset export 추가
- [x] Step 13: Qwen3.5 4B vs 9B fine-tuning experiment harness 추가
- [x] Step 14: 검증된 persona checkpoint를 위한 GGUF runtime export 경로 추가
- [x] Step 15: local persona/dialogue runtime adapter 추가
- [x] Step 16: evaluation harness 및 model selection report 추가
- [x] Step 17: dialogue/persona consistency 전용 optional RL 추가

## 현재 초점

현재 구현 초점은 승격 품질이다.

- bootstrap teacher dataset을 더 다듬어서 첫 실전 4B run이 model gate를 통과하게 만든다
- 작은 모델 대사가 장황해지지 않도록 runtime과 training 모두에서 thinking을 끈다
- `Qwen/Qwen3.5-4B`를 기본 학습 checkpoint로 유지한다
- `Qwen/Qwen3.5-9B`는 4B가 안정화된 뒤 challenger로만 본다
- Windows 기본 학습 backend는 HF/PEFT LoRA 경로로 유지한다
- local OpenAI-compatible adapter runtime에서 먼저 검증한다
- dialogue 품질은 heuristic control을 이기되, world circulation은 깨지지 않는 checkpoint만 승격한다

실무적으로는 다음을 뜻한다.

- 작은 모델 기반 NPC 루프가 모델 크기 확장보다 더 중요하다
- 외부 API 의존보다 bootstrap teacher data가 더 중요하다
- 플레이어가 직접 보는 NPC 대사에서는 teacher JSON 보존보다 runtime 정렬 dialogue SFT가 더 중요하다
- 월드 순환성과 entropy 안정성이 UI 확장보다 더 중요하다
- player 생존과 earning loop는 계속 같은 rule-based economy 안에 있어야 한다

## 프로토타입 상태

현재 저장소에는 다음이 있다.

- terminal runtime: `run_acidnet.py`
- keyboard GUI runtime: `run_acidnet_gui.py`
- SQLite persistence path: `data/acidnet.sqlite`
- bootstrap teacher data path: `run_bootstrap_qwen4b_pipeline.py`
- baseline launcher: `run_qwen4b_baseline_train.py`
- local adapter runtime path: `run_local_adapter_server.py`

구현된 시스템:

- village map 및 movement
- NPC dialogue 및 rumor sharing
- player work loop
- vendor trading 및 food consumption
- deterministic tick progression
- heuristic NPC planner
- memory retrieval scoring 및 belief refresh
- deterministic fallback이 있는 openai-compatible dialogue adapter 경계
- world snapshot persistence
- planner/dialogue용 synthetic teacher prompt generation
- 외부 completion 없이 동작하는 bootstrap teacher output generation
- latency/fallback 측정이 들어간 prompt-only evaluation harness
- world circulation evaluation harness
- dialogue quality + world circulation combined model gate
- deterministic train/eval SFT split export
- Unsloth 및 HF/PEFT 4B baseline run-spec/training-script export
- `Qwen/Qwen3.5-4B` 대상 HF/PEFT LoRA smoke fine-tune
- fine-tuned checkpoint를 위한 local OpenAI-compatible adapter server
- smoke LoRA checkpoint용 GGUF adapter export
- optional DPO/ORPO refinement용 dialogue preference dataset export
- optional DPO run-spec/training-script export

## 승격 종료 조건

- 첫 실전 4B checkpoint가 heuristic fallback 없이 model gate를 통과해야 한다
- local adapter runtime이 world state와 persona 제약을 계속 지켜야 한다
- checkpoint가 최종 GGUF runtime 경로로 export 가능해야 한다
- evaluation은 계속 persona consistency, world consistency, latency, memory fit를 포함해야 한다
