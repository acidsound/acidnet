# 공유 대화에서 추린 핵심 맥락

## 범위

이 문서는 공유된 대화에서 현재 프로젝트 방향에 실제로 도움이 되는 내용만 남긴 요약본이다.

검토한 공유 스레드:

- <https://chatgpt.com/share/69aa3ede-21ac-8011-9a9d-05193f800bf3>

## 유지할 고신호 포인트

- `Qwen3.5-4B`는 24GB VRAM 환경에서 4-bit LoRA 또는 QLoRA 경로로 충분히 시도 가능하다.
- NPC 시스템은 상태, 행동, 보상, 환경 경계를 명확히 나눠야 한다.
- 모델 내부 기억에 의존하지 말고 memory는 외부화해야 한다.
- 나중에 RL을 붙인다면 persona consistency, world consistency, action correctness 같은 reward target은 유효하다.
- 신뢰할 수 있는 RL loop를 만들려면 먼저 simulation environment가 존재해야 한다.
- world mutation은 모델 직접 실행보다 rule-based action execution이 안전하다.
- `SFT -> RL` 순서가 시작점으로 더 건강하다.

## 주의해서만 유지할 중간 신호 포인트

- Dual-model 표현은 개념적으로는 유용하다.
  - trainable policy 또는 persona model
  - 외부 reward 또는 evaluation component
- GRPO는 이후 작은 하드웨어에서 검토할 수 있는 RL 후보일 수 있다.

이 둘은 미래 옵션이지 현재 확정 사항은 아니다.

## 제외할 내용

- RL-only를 초기 주 경로로 삼는 것
- `200k RL episodes` 같은 고정 샘플 수 약속
- "Skyrim 수준", "BG3 수준" 같은 성능 비유
- 링크된 X 글을 세부까지 검증했다고 가정하는 조언
- 모델 출력을 직접 world-state executor로 사용하는 방식

## 이 저장소에 반영되는 실제 변화

- persona fine-tuning을 모델 중심 트랙으로 유지
- planner와 action execution은 구조화되고 검증된 상태로 유지
- RL은 simulator 안정화, dataset 준비, SFT 검증 뒤로 이동
- persona prompting 입력으로 memory summary를 1급 산출물로 다룸
