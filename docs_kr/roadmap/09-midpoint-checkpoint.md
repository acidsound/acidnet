# 중간 점검

## 현재 프로젝트 위치

이 프로젝트는 이제 core world simulation 자체가 막혀 있는 상태가 아니다.

이미 있는 것:

- 터미널에서 플레이 가능한 village loop
- keyboard-driven GUI frontend
- deterministic NPC movement, trade, hunger, rumor flow
- SQLite persistence
- synthetic GPT-5.3 teacher prompt export
- 4B 대 9B experiment manifest generation

즉 남은 일은 "월드를 처음부터 만드는 것"이 아니다.
남은 일은 "determinism 을 잃지 않으면서 prototype 을 model-backed game loop 로 바꾸는 것"이다.

## 우선순위 재확인

가장 중요한 완료 조건은 두 가지다:

1. NPC 가 소형 로컬 언어 모델을 쓰면서도 월드 안에서 독립된 행위자로 동작해야 한다.
2. 월드가 entropy 와 회복을 반복하며 죽거나 고정된 상태로 멈추지 않아야 한다.

대형 프론트엔드 확장과 9B 확장은 이 두 조건보다 뒤다.

기본 편향은 다음으로 유지한다:

- 더 큰 것보다 더 작은 것
- 더 복잡한 것보다 더 단순한 것
- 인상적이지만 흔들리는 것보다 정밀하고 통제 가능한 것

## 종료까지의 핵심 경로

1. 첫 training/eval dataset split 을 고정한다.
2. export 된 prompt pack 에 GPT-5.3 teacher completion 을 붙인다.
3. 첫 `Qwen3.5-4B` baseline fine-tune 을 돌린다.
4. persona consistency, world consistency, latency, cost 평가 harness 를 만든다.
5. 그 다음에만 `Qwen3.5-9B` challenger 를 돌린다.
6. 승자를 고르고 검증된 런타임 artifact 를 `GGUF q4_k_m` 로 export 한다.
7. local dialogue/persona adapter 를 live simulation 에 연결한다.
8. NPC dialogue 가 관계와 rumor history 를 안정적으로 참조할 수 있을 만큼 memory retrieval 을 보강한다.
9. frontend 에 save/load 와 readability 개선을 넣는다.

## 완료라고 부르기 전에 아직 부족한 것

- teacher prompt pack 이 아니라 실제 teacher output
- fine-tuning runner script
- checkpoint evaluation 및 비교
- `talk`, `ask rumor` 에 연결되는 local model inference
- 현재 lightweight hook 을 넘는 memory retrieval
- world readability 와 progression feel 을 높이는 frontend pass

## Plan A

주계획은 좁게 유지하는 편이 맞다:

- 첫 실제 학습 대상은 `Qwen3.5-4B`
- 크지만 큐레이션된 synthetic dataset 생성
- 하나의 깔끔한 baseline run 수행
- 실제 simulator 안에서 측정
- 비용 대비 이득이 분명할 때만 9B 로 확장

현재 prototype 이 모델 없이도 world loop 가 동작한다는 점 때문에 이 경로가 가장 안전하다.

Plan A 의 성공 조건:

- 4B 급 모델만으로도 실행 중인 simulation 안에서 NPC 상호작용이 살아 있다고 느껴져야 한다
- world economy 와 rumor loop 가 수동 리셋 없이 계속 순환해야 한다

## Plan B

local fine-tuning 이 늦어지거나 품질이 약하면:

- heuristic planner 는 유지
- 모델 역할은 dialogue/persona 로만 제한
- 더 작은 범위의 4B dialogue adapter 와 강한 prompt conditioning 사용
- memory 와 rumor retrieval 은 외부 deterministic 시스템으로 유지
- 9B 는 전면 보류

이렇게 해도 플레이 가능한 월드와 그럴듯한 NPC dialogue 는 출하 가능하다.

## 필요하면 Plan C

training cost, latency, toolchain friction 이 감당이 안 되면:

- 현재 heuristic core 로 game loop 를 출하
- 중요한 상호작용에서만 selective local generation 사용
- fine-tuned model 은 post-MVP 업그레이드 경로로 둔다

선호안은 아니지만, 프로젝트가 멈추는 것보다는 낫다.

## 주요 리스크

- dataset quality drift
- teacher data 와 runtime 사이의 prompt-template mismatch
- 4B 검증 전에 9B 에 시간을 너무 쓰는 것
- memory retrieval 과 local generation 을 동시에 풀려고 하는 것
- model/runtime 안정성보다 frontend 욕심이 먼저 커지는 것

## 추천 종료 순서

1. Dataset split 과 teacher completion pipeline
2. 4B baseline fine-tune
3. Evaluation harness
4. Runtime local-model integration
5. Memory retrieval upgrade
6. 필요할 때만 9B challenger
7. Frontend polish 와 save/load

## 이 단계의 완료 조건

이 단계는 플레이어가 다음을 할 수 있을 때 끝난다:

- GUI 에서 village 를 돌아다닌다
- 반복 상호작용으로 관계를 만든다
- rumor 와 trade pressure 가 대화에 반영되는 것을 본다
- 검증된 local model 이 실제로 구동하는 NPC dialogue 와 상호작용한다
- 핵심 social state 를 잃지 않고 world 를 저장하고 이어서 플레이한다
