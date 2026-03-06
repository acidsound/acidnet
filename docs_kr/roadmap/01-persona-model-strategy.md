# 퍼소나 모델 전략

## 결정 요약

- 24GB VRAM 기준 기본 학습 checkpoint: `Qwen/Qwen3.5-4B`
- 비교용 challenger: `Qwen/Qwen3.5-9B`
- 선호 학습 방식: bf16 LoRA
- 선호 런타임 양자화: `Q4_K_M GGUF`
- 적용 범위: NPC persona, dialogue tone, rumor framing, social bias
- 비적용 범위: inventory mutation, pathfinding, economy settlement, physics

## 우선순위 규칙

- 실제 월드 안에서 독립적인 NPC처럼 버티는 작은 모델이, 샘플만 더 좋아 보이는 큰 모델보다 낫다.
- 모델 업그레이드보다 entropy 기반 월드 순환을 유지하는 것이 우선이다.
- 실제 플레이를 버티는 가장 작고, 단순하고, 정밀한 모델이 우선이다.

## 왜 4B를 baseline으로 두는가

- 24GB GPU에 더 안전하게 맞는다.
- sequence length, evaluation run, iteration speed에 여유가 남는다.
- 좁게 설계된 NPC persona 모델로는 비용 효율적일 가능성이 높다.
- `dataset -> LoRA -> runtime -> model gate` 전체 루프를 가장 먼저 강제할 모델이다.

## 왜 9B도 남겨두는가

- dialogue nuance, deception handling, style consistency에서 더 좋을 가능성은 있다.
- 하지만 기본 가정이 아니라 challenger run으로만 다룬다.
- 비용과 latency를 정당화할 만큼 평가 이득이 있을 때만 primary path가 된다.

## Training 과 Runtime 분리

- GGUF runtime artifact가 아니라 fine-tuning checkpoint에서 학습한다.
- 학습된 checkpoint는 local OpenAI-compatible adapter runtime에서 먼저 검증한다.
- 검증된 결과만 `GGUF q4_k_m`로 export한다.
- `GGUF` deployment artifact 자체를 직접 fine-tune하지 않는다.

## 현재 엔지니어링 판단

- 먼저 `Qwen/Qwen3.5-4B`로 간다.
- planner는 persona/dialogue 모델의 유효성이 증명될 때까지 heuristic으로 유지한다.
- Windows 기본 학습 backend는 HF/PEFT LoRA 경로로 둔다.
- 외부 teacher completion은 기본 bootstrap 경로가 아니라 선택적 보정 경로로 본다.

## 데이터 계약

퍼소나 모델 입력:

- NPC profile
- relationship summary
- salient beliefs
- active rumors
- player interaction context
- hunger, scarcity 같은 local world pressure

퍼소나 모델 출력:

- 짧은 NPC dialogue
- rumor phrasing 또는 withholding
- social consistency를 유지하는 응답

퍼소나 모델이 직접 만들면 안 되는 것:

- raw world write
- economy mutation
- rule engine을 우회하는 pathfinding decision

## 데이터셋 계획

- source 1: synthetic village rollout에서 직접 만든 bootstrap teacher output
- source 2: terminal/GUI 세션에서 얻는 runtime interaction transcript
- source 3: 선택적 외부 teacher completion
- source 4: 이후 human review set 기반 preference/style correction

## 선택 기준

- persona consistency
- world consistency
- local runtime constraint 하의 responsiveness
- adapter server 경로에서의 latency
- target machine에서의 memory fit
- 절대 품질보다 4B baseline 대비 개선 여부
- 장기 세션에서의 controllability와 prompt stability

## 운영 리스크

- 잘못된 artifact type에 학습하는 것
- training/runtime template mismatch
- flavor에 과적합하고 utility를 잃는 것
- evaluation loop가 안정되기 전에 9B를 먼저 고르는 것
- smoke fine-tune을 곧바로 승격 가능한 checkpoint로 착각하는 것

## 참고 소스

- [Unsloth Qwen3.5 fine-tuning guide](https://unsloth.ai/docs/models/qwen3.5/fine-tune)
- [Qwen3.5-9B GGUF runtime repo](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF)
- [Qwen3.5-9B `Q4_K_M` runtime file](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-Q4_K_M.gguf)
- [Qwen3.5-4B GGUF runtime repo](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF)
