# 공간, 시간, 교환 모델

## 목적

더 큰 프런트엔드 작업에 들어가기 전에 거리, 이동 시간, actor 비용, 비대칭 교환에 대한 월드 모델을 먼저 고정한다.

이 문서는 공간을 렌더링 문제가 아니라 시뮬레이션 문제로 다룬다.

## 왜 이 문서가 먼저 필요한가

다음 프런트엔드는 즉시 이동, vendor 전용 대칭 거래, 시간 비용이 드러나지 않는 장면 모델 위에 세워지면 안 된다.

이동, 비용, 교환 규칙이 틀리면 프런트는 잘못된 규칙을 더 보기 좋게 포장하는 역할만 하게 된다.

## 핵심 원칙

- 거리는 시간, 노력, 위험으로 표현되어야 한다
- 이동은 즉시 위치 교환이 아니라 여러 턴에 걸친 행동이다
- world truth 와 player-visible state 는 분리되어야 한다
- 유상 거래, 증여, 물물교환, 외상은 하나의 교환 규칙 경로를 공유해야 한다
- 필요 기반 증여는 예외가 아니라 기본 상식이어야 한다
- actor 는 자신이 가진 자원의 절대적 소유자라기보다 일시적 관리자로 보는 편이 맞다
- money 는 나중에 편의나 ledger 로 존재할 수 있지만, world loop 가 money-first 생존 구조에 의존하면 안 된다
- offscreen 시뮬레이션은 플레이어 또는 추적 actor 가 가까워지기 전까지 요약 상태로 유지한다
- 엔트로피는 내부 소모와 외부 충격 둘 다에서 와야 한다
- 파괴적 충격은 일방적 붕괴가 아니라 회복 경로도 함께 열어야 한다

## 공간 모델

계층형 그래프를 사용한다.

### Layer 1: 지역 정착지 그래프

현재 village 규모 location 그래프가 여기에 해당한다.

각 node 는 최소한 다음을 가진다.

- `location_id`
- `kind`
- `capacity`
- `shelter_rating`
- `resource_tags`
- `danger_tags`

각 edge 는 최소한 다음을 가진다.

- `from_location`
- `to_location`
- `travel_ticks`
- `effort_cost`
- `exposure_risk`
- `load_modifier`
- `weather_modifier`
- `is_blockable`

### Layer 2: 지역 간 경로 그래프

각 village 또는 주요 site 를 region node 로 본다.

지역 간 edge 는 최소한 다음을 가진다.

- `route_id`
- `travel_ticks`
- `cargo_risk`
- `weather_sensitivity`
- `bandit_or_wildlife_risk`
- `seasonal_capacity`

플레이어와 가까운 NPC 는 고해상도 local simulation 을 사용한다.
먼 정착지는 주기적 수입/수출만 반영하는 요약 상태로 돌린다.

## Actor 요구사항

현재의 `location_id`, `inventory`, `money`, `hunger` 만으로는 부족하다.

최소한 다음이 추가되어야 한다.

- `fatigue`
- `carried_weight`
- `carry_capacity`
- `travel_state`
- 여러 village 가 생기면 `home_region_id`

권장 `travel_state` 필드:

- `is_traveling`
- `route`
- `origin_location_id`
- `destination_location_id`
- `ticks_remaining`
- `risk_budget`

fatigue 는 hunger 와 다른 회복 문제를 만들 때만 의미가 있다.
따라서 `rest` 와 `sleep` 은 장식이 아니라 핵심 행동이어야 한다.

## 이동 해석 규칙

`go <location>` 은 즉시 이동이 아니라 travel intent 가 되어 시간에 걸쳐 해석되어야 한다.

권장 규칙 흐름:

1. route edge 선택
2. `travel_ticks` 소모
3. 구간별 hunger 와 fatigue 증가
4. load 와 weather modifier 적용
5. route event window 처리
6. 도착, 실패, 후퇴 중 하나로 종료

이동은 회복과 한 묶음이어야 한다.
첫 구현부터 `rest` 는 짧은 회복, `sleep` 은 shelter quality 와 safety 에 의존하는 강한 회복으로 다루는 편이 낫다.

### 비용 모델

첫 버전은 단순하고 읽히게 유지한다.

- 기본 hunger 압력은 시간에서 온다
- 추가 hunger 압력은 노력과 적재 중량에서 온다
- fatigue 는 장거리 이동에서 hunger 보다 더 빠르게 오른다
- 악천후는 우선 randomness 보다 travel time 을 먼저 늘려야 한다

예시 1차 공식:

```text
effective_travel_ticks =
  base_travel_ticks
  * weather_modifier
  * load_modifier

hunger_delta =
  base_time_hunger
  + effort_cost * 0.15

fatigue_delta =
  effort_cost
  + carried_weight_ratio * 4
```

상수는 바뀔 수 있다.
중요한 것은 거리가 언제나 기회비용을 만든다는 점이다.

## 교환 모델

증여를 별도 시스템으로 빼지 않는다.
비대칭 교환의 한 형태로 본다.

또한 money 를 자연스러운 기본값으로 가정하지 않는다.
대부분의 교환이 money 없이도 성립하는 세계가 기본이 되어야 한다.

### 통합 교환 개념

모든 자원 이전은 같은 구조를 사용한다.

- `from_actor`
- `to_actor`
- `items_out`
- `items_in`
- `payment_mode`
- `money_amount`
- `debt_terms`
- `reason`

초기 `payment_mode`:

- `gift`
- `cash`
- `barter`
- `debt`

순서가 중요하다.
reserve floor 가 안전할 때 `gift` 는 낮은 강도의 필요 기반 이전에서 기본값이어야 한다.

### 검증 규칙

모든 교환 모드는 같은 rule engine 검사를 통과해야 한다.

- 재고 존재 여부
- reserve floor
- 관계 점수
- 절박함 또는 긴급도
- profession 규범
- debt ceiling

이렇게 해야 이타성이 가능하면서도 월드가 무한 무료 재분배로 무너지지 않는다.

### Reserve Floor 가 중요한 이유

배고픈 NPC 를 돕기 위해 음식을 나눠줄 수는 있어야 하지만, 자기 자신을 굶기면서까지 줘서는 안 된다.

따라서 각 actor 에게 다음과 같은 최소 재고 규칙이 필요하다.

- 자신과 household 를 위한 `N` 끼 보존
- 핵심 생산 입력은 reserve 이하로 증여하지 않음
- emergency state 에서는 평소보다 완화된 기준을 사용할 수 있음

### Money Boundary

money 는 신중하게 다뤄야 한다.

나중에 도입하거나 확대하더라도:

- 생존 필수 교환의 전제여서는 안 되고
- 발행과 소멸 규칙이 명시되어야 하며
- stock, labor, trust, need 보다 앞서는 기본 축이 되어서는 안 된다

이 세계가 살아있기 위해 자본주의형 기본 구조를 강제할 필요는 없다.

## 외부 충격

외부 압력은 완전 랜덤보다 상태 의존 랜덤이어야 한다.

좋은 초기 충격:

- 날씨 변화 -> 작황 압박
- 운송 지연 -> 시장 희소성
- 고온 + 방치 -> 화재 위험
- 폭풍 + 나쁜 경로 상태 -> 이동 지연

좋지 않은 초기 충격:

- 서로 상관없는 재난 시스템을 한꺼번에 많이 넣는 것
- 회복 경로 없는 파국적 randomness

각 충격은 다음을 정의해야 한다.

- trigger conditions
- impact radius
- duration
- affected resources
- recovery path

여기에 한 가지를 더 붙인다.

- shock 은 대개 loss channel 과 recovery 또는 regeneration channel 을 함께 가져야 한다

예시:

```text
불이 나서 shelter 가 손상된다
-> 재와 무기물이 토양에 유입된다
-> 작물 생장이 회복된다
-> 곤충과 수분이 돌아온다
-> 목재 공급이 회복된다
-> shelter 를 다시 지을 수 있다
```

이렇게 해야 파괴적 randomness 가 의미 없는 일방적 붕괴가 되지 않는다.

## 프런트엔드 계약에 대한 함의

프런트엔드가 전체 persistence snapshot 을 그대로 장면 계약으로 소비하면 안 된다.
프런트엔드는 simulation truth 위의 표현 레이어여야지, 두 번째 규칙 엔진이 되면 안 된다.

다음과 같은 파생 DTO 를 도입한다.

- `SceneFrame`
- `PlayerFrame`
- `VisibleNPCFrame`
- `RoutePreview`
- `ActionCatalog`
- `EventFeed`

프런트엔드는 다음을 보여줘야 한다.

- 플레이어 위치
- 현재 보이는 것
- 가능한 행동
- 이동에 필요한 시간, fatigue, 위험
- 현재 target 에게 가능한 교환 옵션

프런트엔드가 시뮬레이션 진실을 재계산해서는 안 된다.

## Monkey 에 대한 함의

Monkey runner 는 랜덤 명령 샘플링에서 bounded goal-play 로 진화해야 한다.
이제 monkey 는 world 를 돌아다니며 사건을 유발하고 관찰하는 proxy player-character 에 가까워져야 한다.

유용한 monkey 역할:

- survivor
- trader
- rumor verifier
- altruist
- stress tester

이 monkey 들은 다음을 보고 행동해야 한다.

- current scene
- current goal
- valid actions
- recent events
- 주입된 behavior policy 또는 role prompt

언어모델은 다음 행동을 고를 수 있지만, 채점은 계속 규칙 기반이어야 한다.

## 다중 마을 확장

여러 정착지가 생기면:

- local play 는 고해상도로 유지
- 먼 정착지는 요약 상태로 처리
- route 는 시간, 위험, 보급 비용을 함께 가짐
- 뉴스와 rumor 는 상품보다 더 빨리 이동할 수 있음

이 구조가 성능을 지키면서도 즉시 이동에 세계가 평평해지는 문제를 막는다.

## 비목표

- 2D 또는 3D renderer 확정
- full physics simulation
- continuous free-movement 좌표
- 전역 상시 고해상도 월드 업데이트

## 기준 결정

다음 큰 프런트엔드 도입 전까지 프로젝트는 다음을 기본 전제로 삼는다.

- 그래프 기반 공간
- 여러 턴에 걸친 travel
- hunger + fatigue + 하중 기반 이동 비용
- gift 를 별도 시스템으로 빼지 않는 unified exchange
- 요약된 offscreen region
- 상태 의존형 외부 충격
