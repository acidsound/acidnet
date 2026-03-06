# 루머 다양성 handoff

## 이번에 막 들어간 것

최근 마일스톤 커밋:

- `1c02f31` `Add DB-backed system prompt settings modal`
- `fc015f5` `Diversify seeded and dynamic village rumors`

현재 플레이 가능한 빌드는 다음 상태다.

- `local_peft`를 통해 full `Qwen/Qwen3.5-4B` WSL-trained adapter가 GUI에 연결되어 있다
- GUI와 event log에 dialogue model의 `loading -> ready` 상태가 표시된다
- GUI에 공유 system prompt를 수정할 수 있는 `Settings` modal이 있다
- SQLite에는:
  - 읽기 전용 기본 prompt를 담는 `prompt_presets`
  - 실제 런타임 prompt를 담는 `runtime_settings`
  가 분리되어 있다
- event log는 NPC, world, player 계열을 구분해서 보여준다
- rumor는 seed 다양성과 runtime 동적 생성이 모두 들어간 상태다

## 왜 이 수정이 필요했나

이전 rumor 루프는 겉으로는 돌고 있었지만 실제로는 좁았다.

- demo world가 사실상 하나의 지배적인 rumor로 시작했다
- rumor sharing이 `known_rumor_ids` 순서에 많이 의존했다
- 그래서 player 입장에서는 계속 같은 wheat shortage 문장만 듣게 됐다

즉 월드는 순환하고 있었지만 정보 계층은 순환하지 못하고 있었다.

## 무엇이 바뀌었나

관련 파일:

- `src/acidnet/world/demo.py`
- `src/acidnet/engine/simulation.py`
- `tests/test_simulation.py`

구현된 변경:

- demo world 시작 rumor를 economy, shortage, social, danger, event 범주로 다원화했다
- 여러 NPC가 서로 겹치지만 동일하지 않은 rumor set을 들고 시작한다
- 시뮬레이션은 이제 다음 조건에 따라 dynamic rumor를 추가 생성한다:
  - weather phase 변화
  - market scarcity 압력
  - bakery와 riverside의 공급 압력
- rumor 공유 선택은 이제 단순 삽입 순서가 아니라 value, recency, confidence, hop count 기준으로 정렬된다
- player rumor panel도 같은 정렬 기준을 쓴다

## 현재 기대 동작

이제 다른 NPC에게 rumor를 물으면 더 이상 아래 문장만 반복해서 보이지 않아야 한다.

- `The south field yield is down after the dry wind. Grain will be tight this week.`

예를 들어 `Neri`에게 묻고, `Warm Crust Bakery`로 가서 `Hobb`에게 다시 물으면 서로 다른 rumor를 얻을 수 있다. 시간이 지나면 weather, market, supply 상태를 반영한 rumor도 추가로 생긴다.

## 검증 상태

이 handoff 시점의 검증:

- `python -m pytest -q` -> `51 passed`
- `python -m compileall src/acidnet/engine/simulation.py src/acidnet/world/demo.py tests/test_simulation.py` 통과

rumor 관련 테스트는 현재 다음을 보장한다.

- 시작 시 여러 seeded rumor가 존재함
- player가 서로 다른 rumor를 수집할 수 있음
- world가 진행되면 dynamic rumor가 추가 생성됨

## 새 대화에서 먼저 읽을 문서

- `docs/roadmap/00-execution-checklist.md`
- `docs/roadmap/07-keyboard-gui-frontend.md`
- `docs/roadmap/18-wsl2-unsloth-train-path.md`
- `docs/roadmap/19-rumor-diversity-handoff.md`

## 다음 권장 작업

다음으로 가장 자연스러운 작업은 이렇다.

1. rumor distortion과 paraphrase drift를 추가해서 hop count가 confidence뿐 아니라 wording도 바꾸게 만든다
2. trade shock, starvation, shrine relief, guard incident 같은 event-driven rumor 생성을 더 강하게 넣는다
3. UI에 rumor history 관측 장치를 넣는다:
   - 최근 획득
   - 출처 NPC
   - age
   - confidence 변화
4. circulation만이 아니라 rumor diversity를 시간축으로 측정하는 evaluation을 추가한다

## 새 대화용 이어가기 문장

새 대화를 시작하면 가장 빠른 이어가기 문장은 아래다.

`docs/roadmap/19-rumor-diversity-handoff.md 를 읽고 현재 playable GUI build에서 계속 진행하자. 4B local model path와 SQLite prompt settings는 유지하고, 다음은 rumor distortion, event-driven rumor generation, information-layer observability에 집중한다.`
