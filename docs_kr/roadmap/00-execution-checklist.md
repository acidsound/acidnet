# 실행 체크리스트

## 목표

플레이어가 월드를 돌아다니고, NPC와 대화하고, 거래하고, 루머를 모으며, 최종적으로는 이 세계에 타이트하게 맞춘 소형 로컬 persona/dialogue 모델을 붙인 simulation-first village RPG를 만든다.

## 최우선 목표

1. 소형 로컬 언어 모델을 사용하는 독립적인 NPC를 완성한다.
2. 엔트로피, 생산, 거래, 배고픔, 루머, 회복이 순환하면서도 정체되지 않는 월드 루프를 완성한다.

## 모델 선택 원칙

- 충분하다면 더 작은 모델이 낫다.
- 더 잘 통제할 수 있다면 더 단순한 모델이 낫다.
- 불안정하게 크게 말하는 모델보다 정밀한 모델이 낫다.
- 더 큰 모델은 작은 모델이 실제 월드에서 명확히 실패할 때만 후보가 된다.

## 지금 당장 비우선인 것

- 시뮬레이션과 로컬 모델 루프가 검증되기 전의 대형 프론트엔드 확장
- 소형 모델 경로가 증명되기 전의 9B 집착

## 작업 규칙

- 주요 시스템이나 실행 경로가 바뀌면 `docs/roadmap/`과 `docs_kr/roadmap/`을 같이 갱신한다.
- 문서 안 경로는 항상 프로젝트 루트 기준 상대경로만 쓴다.
- 월드 변화는 계속 rule-based로 유지한다. 로컬 모델은 intent나 dialogue를 제안할 수는 있지만 physics와 economy를 직접 쓰지는 않는다.
- `GGUF q4_k_m`는 학습 원본이 아니라 배포 산출물로 다룬다.
- Windows 기본 영속화는 SQLite로 유지하고, `zvec`는 선택적 Linux/macOS 경로로 본다.
- bootstrap teacher 생성 경로를 기본 dataset 경로로 삼는다. 외부 teacher completion은 선택적 보정이지 필수 전제가 아니다.

## 우선순위 해석

- 이 문서는 장기 제품 우선순위와 model-promotion baseline 을 담당한다.
- live next-slice queue 는 `docs/context/current-state.md` 를 기준으로 본다.
- active simulation/world-expansion track 순서는 `docs/roadmap/24-execution-roadmap.md` 를 기준으로 본다.
- step 의 exit criteria 와 remaining gap 은 `docs/roadmap/21-frontend-world-expansion-checklist.md` 를 기준으로 본다.
- promotion quality 와 simulation/world-loop hardening 은 병렬 관심사이며, 어느 한쪽이 다른 쪽을 무시해도 된다는 뜻이 아니다.

## 단계 체크리스트

- [x] Step 00: 아키텍처 및 구현 계획 문서 작성
- [x] Step 01: 프로젝트 스켈레톤과 핵심 스키마 생성
- [x] Step 02: deterministic tick engine과 scheduler 추가
- [x] Step 03: 맵, location, 이동 규칙 추가
- [x] Step 04: hunger, food inventory, consumption 추가
- [x] Step 05: market price feedback과 trade execution 추가
- [x] Step 06: rumor lifecycle과 relationship update 추가
- [x] Step 07: 기존 lightweight hook을 넘는 memory retrieval과 belief reflection 추가
- [x] Step 08: heuristic planner와 intent validation 추가
- [x] Step 09: 플레이 가능한 terminal MVP 추가
- [x] Step 10: SQLite world snapshot persistence 추가
- [x] Step 11: keyboard GUI frontend 추가
- [x] Step 12: teacher prompt schema와 synthetic dataset export 추가
- [x] Step 13: Qwen3.5 4B vs 9B fine-tuning experiment harness 추가
- [x] Step 14: 검증된 persona checkpoint용 GGUF runtime export 경로 추가
- [x] Step 15: local persona/dialogue runtime adapter 추가
- [x] Step 16: evaluation harness와 model selection report 추가
- [x] Step 17: dialogue/persona consistency 전용 optional RL 추가

## 현재 초점

현재 제품 수준 초점은 여전히 승격 품질이다.

- bootstrap-teacher dataset을 다듬어 첫 실전 4B run이 model gate를 넘게 한다
- 작은 모델 대사가 장황해지지 않도록 runtime과 training 모두에서 thinking을 끈다
- `Qwen/Qwen3.5-4B`를 기본 학습 checkpoint로 유지한다
- `Qwen/Qwen3.5-9B`는 4B가 충분히 안정화된 뒤에만 challenger로 본다
- WSL2를 쓸 수 있으면 4B LoRA는 WSL2 + Unsloth를 우선하고, Windows HF/PEFT는 fallback으로 둔다
- local OpenAI-compatible runtime으로 먼저 검증한 뒤 승격한다
- dialogue 품질이 heuristic control을 이기면서도 world circulation을 깨지 않는 checkpoint만 승격한다

실무적으로는 다음 뜻이다.

- 소형 모델 NPC 루프가 모델 크기 확장보다 중요하다
- 외부 API 의존보다 bootstrap teacher data가 중요하다
- player-facing NPC speech에서는 teacher JSON fidelity보다 runtime-aligned dialogue SFT가 중요하다
- 월드 순환성과 entropy 안정성이 UI 확장보다 중요하다
- player의 생존과 돈벌이 루프는 계속 같은 rule-based economy 안에 있어야 한다
- 더 큰 프런트엔드 확장 전에 graph-based travel time, actor movement cost, unified exchange 를 core simulation rule 로 먼저 고정한다
- 프런트엔드는 raw persistence snapshot 이 아니라 derived player-view scene state 를 소비하게 둔다
- world scale 을 키우기 전에는 bounded goal-monkey evaluation 으로 travel, exchange, shock handling 을 먼저 스트레스 테스트한다
- Tk 는 제거된 상태로 유지하고, 새 시뮬레이션 시스템의 parity 목표로 다시 들이지 않는다
- 프런트엔드 반복은 공유 가능한 웹 프로브를 주 관찰면으로 삼는다

이 섹션은 live per-slice queue 가 아니다.
현재 시뮬레이션 작업이 계속 만족해야 하는 장기 기준을 정리한 것이다.

## 현재 측정 상태

- in-process `local_peft` dev/eval 경로가 HTTP bridge 없이 최신 `Qwen/Qwen3.5-4B` LoRA adapter를 직접 실행한다
- 승격된 simulator runtime 경로는 `Q4_K_M` GGUF base model과 optional GGUF LoRA adapter를 `llama-server`로 서빙하고 `openai_compat`로 붙는 방식이다
- 최신 runtime-dialogue smoke adapter가 combined model gate를 통과했다
- 현재 gate 결과: `prompt_avg=1.000`, `prompt_fail_rows=0`, `prompt_latency_ms=1672.6`, `circulation=0.925`
- WSL2 + Unsloth 학습 경로는 기본 `.venv-wsl` 기준 Python 3.12에서 `flash-linear-attention`, `causal-conv1d`까지 포함해 다시 검증됐다
- 현재 유지 중인 WSL bench smoke `1024 / 128` 학습 시간: `169 s`
- 첫 full WSL2 + Unsloth 4B candidate가 완료됐고 combined model gate를 통과했다
- 현재 full WSL gate 결과: `prompt_avg=1.000`, `prompt_fail_rows=0`, `prompt_latency_ms=2994.443`, `circulation=0.925`
- 현재 full WSL `50000 / 4000` 학습 시간: `6999 s`
- 공유 가능한 web probe 가 현재 dialogue backend 검증용 active frontend surface 다
- web probe 에는 dialogue model startup readiness가 표시되고, `loading -> ready` 이벤트가 UI와 event log에 모두 남는다
- 공유 dialogue system prompt는 이제 web probe 에서 수정 가능하며, SQLite의 읽기 전용 preset 테이블과 수정 가능한 runtime settings 테이블에 저장된다
- rumor 다양성은 더 이상 단일 wheat shortage rumor에 고정되지 않고, demo world는 여러 seeded rumor로 시작하며 weather, scarcity, supply 변화에 따라 dynamic rumor를 생성한다
- 반복된 rumor 내용은 signature 기준으로 dedupe 되며, 오래된 dynamic rumor 는 월드에서 decay out 된다
- 다음 월드 설계 기준선은 `docs/roadmap/20-spatial-time-exchange-model.md` 에 정리되어 있다
- 단계별 후속 작업은 `docs/roadmap/21-frontend-world-expansion-checklist.md` 에 추적된다
- 공유 가능한 웹 프런트엔드 기준선은 `docs/roadmap/22-web-frontend-shareable.md` 에 정리되어 있다
- 브라우저 런타임 계약은 `docs/roadmap/23-web-client-api-spec.md` 에 정리되어 있다
- 현재 구현 순서는 `docs/roadmap/24-execution-roadmap.md` 에 정리되어 있다
- actor travel-cost baseline 필드로 fatigue, load, carry capacity, serialized travel state 가 추가되었다
- stdlib 기반 첫 웹 프로브가 브라우저 URL 을 통해 derived player-view state 와 raw-command submission 을 노출한다

## 프로토타입 상태

현재 저장소에는 다음이 있다.

- terminal runtime: `run_acidnet.py`
- shareable web runtime: `run_acidnet_web.py`
- SQLite persistence path: `data/acidnet.sqlite`
- bootstrap teacher data path: `run_bootstrap_qwen4b_pipeline.py`
- baseline launcher: `run_qwen4b_baseline_train.py`
- local adapter dev/eval server path: `run_local_adapter_server.py`
- Windows local adapter dev/eval loop: `run_local_adapter_dev_loop.ps1`
- direct in-process local adapter dev/eval path: `run_model_gate.py --dialogue-backend local_peft --dialogue-adapter-path ...`

구현된 시스템:

- village map과 movement
- NPC dialogue와 rumor sharing
- player work loop
- vendor trading과 food consumption
- deterministic tick progression
- heuristic NPC planner
- memory retrieval scoring과 belief refresh
- deterministic fallback이 붙은 openai-compatible dialogue adapter 경계
- world snapshot persistence
- derived player-view scene state 위에 올린 shareable web probe
- planner/dialogue용 synthetic teacher prompt generation
- 외부 completion 없이 동작하는 bootstrap teacher output generation
- latency와 fallback 측정이 들어간 prompt-only evaluation harness
- world circulation evaluation harness
- dialogue quality + world circulation combined model gate
- deterministic train/eval SFT split export
- Unsloth 및 HF/PEFT 4B baseline run-spec/training-script export
- `Qwen/Qwen3.5-4B` 대상 HF/PEFT LoRA smoke fine-tune
- fine-tuned checkpoint용 local OpenAI-compatible adapter server
- smoke LoRA checkpoint의 GGUF adapter export
- optional DPO/ORPO refinement용 dialogue preference dataset export
- optional DPO run-spec/training-script export

## 승격 종료 조건

- 첫 실전 4B checkpoint가 heuristic fallback 없이 model gate를 통과해야 한다
- local adapter runtime은 world state와 persona 제약을 계속 지켜야 한다
- checkpoint는 최종 GGUF runtime 경로로 export 가능해야 한다
- evaluation에는 계속 persona consistency, world consistency, latency, memory fit이 포함되어야 한다
