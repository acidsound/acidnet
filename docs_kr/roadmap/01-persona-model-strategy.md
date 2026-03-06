# 퍼소나 모델 전략

## 결정 요약

- 24GB VRAM 기준 primary training baseline: `Qwen/Qwen3.5-4B-Base`
- 비교용 challenger: `Qwen3.5-9B` 계열 체크포인트, 런타임은 `unsloth/Qwen3.5-9B-GGUF`
- 선호 학습 방식: bf16 LoRA
- 선호 런타임 양자화: `Q4_K_M GGUF`
- 적용 범위: NPC persona, dialogue tone, rumor framing, social bias
- 비적용 범위: inventory mutation, pathfinding, economy settlement, physics

## 우선순위 규칙

- 실제 월드 안에서 독립적인 NPC 처럼 작동하는 더 작은 모델이, 샘플 품질만 조금 더 좋은 큰 모델보다 낫다.
- 모델 업그레이드는 entropy 기반 월드 순환성을 유지하는 것보다 앞설 수 없다.
- 실제 플레이를 버티는 가장 작고, 가장 단순하고, 가장 정밀한 모델이 우선이다.

## 왜 4B 를 baseline 으로 두는가

- 24GB GPU 에서 더 안전하게 맞는다
- sequence length, evaluation run, iteration speed 에 여유가 있다
- 타이트한 NPC persona model 이라는 목표에 더 비용 효율적일 가능성이 높다

## 왜 9B 를 여전히 봐야 하는가

- dialogue nuance, deception handling, style consistency 에서 더 좋을 수 있다
- 하지만 기본 가정이 아니라 challenger run 으로 다뤄야 한다
- 비용과 latency 를 정당화할 만큼 평가상 이길 때만 primary path 로 승격한다

## Training 과 Runtime 분리

- fine-tuning checkpoint 에서 학습한다
- 튜닝된 체크포인트를 export 전에 먼저 검증한다
- 검증된 결과를 `GGUF q4_k_m` 로 export 한다
- `GGUF` deployment artifact 자체를 직접 fine-tune 하지는 않는다

## 현재 엔지니어링 판단

- 먼저 4B 로 간다
- baseline data pipeline 과 evaluation harness 가 안정되면 9B 를 비교 실험한다
- persona/dialogue model 이 유효하다는 증거가 나오기 전까지 planner 는 heuristic 로 유지한다

## 데이터 계약

퍼소나 모델의 입력:

- NPC profile
- relationship summary
- salient beliefs
- active rumors
- player interaction context
- hunger 와 scarcity 같은 local world pressure

퍼소나 모델의 출력:

- 짧은 NPC dialogue
- rumor phrasing 또는 withholding
- social consistency 가 유지되는 응답

퍼소나 모델이 직접 만들면 안 되는 것:

- raw world write
- economy mutation
- rule engine 을 우회하는 pathfinding decision

## 데이터셋 계획

- source 1: synthetic village rollout 에서 뽑은 GPT-5.3 teacher prompt pack
- source 2: terminal 과 GUI 세션에서 쌓이는 runtime interaction transcript
- source 3: 이후 human review set 기반 preference/style correction

## 선별 기준

- persona consistency
- world consistency
- local runtime constraint 하의 responsiveness
- target machine 에서의 memory fit
- 절대 품질만이 아니라 4B baseline 대비 개선 폭
- 긴 세션에서의 controllability 와 prompt stability

## 운영 리스크

- 잘못된 artifact type 에 학습하는 것
- training/runtime template mismatch
- flavor 에 과적합되고 utility 를 잃는 것
- evaluation loop 가 안정되기 전에 9B 를 먼저 선택하는 것

## 참고 소스

- [Unsloth Qwen3.5 fine-tuning guide](https://unsloth.ai/docs/models/qwen3.5/fine-tune)
- [Qwen3.5-9B GGUF runtime repo](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF)
- [Qwen3.5-9B `Q4_K_M` runtime file](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-Q4_K_M.gguf)
- [Qwen3.5-4B GGUF runtime repo](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF)
