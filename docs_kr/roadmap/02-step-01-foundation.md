# Step 01 기반 작업

## 목표

시뮬레이션 루프를 만들기 전에 필요한 저장소 기반 구조를 만든다.

## 산출물

- Python 패키지 골격
- world, NPC, rumor, belief, intent, persona용 코어 스키마
- planner protocol 경계
- 스키마 검증용 최소 테스트

## 이번 단계에서 추가되는 파일

- `pyproject.toml`
- `src/acidnet/...`
- `tests/...`

## 완료 기준

- 코어 모델 import 시 circular dependency 문제가 없어야 한다
- intent, rumor, persona 필드가 구조화되고 검증되어야 한다
- planner가 구체 구현체가 아니라 protocol에 의존해야 한다
- 이후 engine 코드가 스키마 재설계 없이 이 모델들을 사용할 수 있어야 한다

## 바로 다음 단계

다음 구현 단계는 Step 02다.

- tick duration config 정의
- world clock 구현
- deterministic scheduler 구현
- simulation state container 도입

