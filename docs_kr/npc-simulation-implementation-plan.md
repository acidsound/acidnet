# NPC 시뮬레이션 구현 계획서

## 1. 문서 목적

이 문서는 "LLM 기반 자율 NPC 마을 시뮬레이션"을 실제로 개발 가능한 수준까지 구체화한 구현 기준 문서다.

핵심 원칙은 아래 세 가지다.

```text
시뮬레이션 우선
LLM은 실행기가 아니라 플래너
시뮬레이션 루프가 안정화되기 전까지 RL은 보류
```

이 문서는 특히 다음 질문에 답하도록 구성한다.

1. 무엇부터 구현해야 하는가?
2. 각 시스템은 어떤 데이터 구조와 인터페이스를 가져야 하는가?
3. MVP에서 반드시 포함할 것과 제외할 것은 무엇인가?
4. 학습 데이터와 모델 파이프라인은 어느 시점에 붙이는가?

## 2. 프로젝트 목표

### 제품 목표

30~40명의 NPC가 살아가는 village simulation을 만든다.

NPC는 다음 성질을 가진다.

- 자율 행동
- 제한된 자원 환경에서의 생존
- rumor를 통한 정보 확산
- relationship과 belief에 기반한 사회적 의사결정
- LLM planner를 이용한 고수준 intent 생성

### MVP 목표

첫 MVP는 10명의 NPC가 있는 작은 village를 목표로 한다.

MVP에서 반드시 가능한 행동:

- 이동
- 대화
- 거래
- 음식 획득과 소비
- rumor 전달

### MVP 비목표

다음 항목은 MVP 범위에서 제외한다.

- 자연어 대화 품질 고도화
- RL 파인튜닝
- 전투 시스템
- 멀티 타운 또는 월드 스트리밍
- 고급 건축 시스템

## 3. 권장 기술 스택

저장소가 아직 비어 있으므로 초기 구현 기준 스택을 제안한다.

### 런타임

- Python 3.11+
- 스키마용 `pydantic`
- 관계 그래프용 `networkx` 또는 경량 커스텀 그래프
- 로컬 영속화용 `sqlite`
- 디버그 API 및 도구용 `FastAPI`
- 테스트용 `pytest`

### Python을 추천하는 이유

- 시뮬레이션 루프를 빠르게 구현할 수 있다
- LLM 추론과 학습 생태계가 가장 풍부하다
- 데이터 생성, LoRA 학습, 평가 파이프라인과 연결이 쉽다

### 이후 확장 가능 영역

- 시각화 클라이언트: Godot, Unity, Web Dashboard 중 택1
- 추론 서빙: vLLM 또는 llama.cpp 기반 래퍼
- 학습: transformers + peft + bitsandbytes

## 4. 상위 아키텍처

```text
+-------------------+
| world simulation  |
+---------+---------+
          |
          v
+-------------------+
| npc cognition     |
| perception        |
| memory retrieval  |
| belief update     |
+---------+---------+
          |
          v
+-------------------+
| planner           |
| LLM or heuristic  |
+---------+---------+
          |
          v
+-------------------+
| intent            |
+---------+---------+
          |
          v
+-------------------+
| rule engine       |
| movement/economy  |
| resource/social   |
+---------+---------+
          |
          v
+-------------------+
| world update      |
+-------------------+
```

### 시스템 경계

LLM은 아래 역할만 담당한다.

- 상황 해석
- 목표 우선순위 판단
- intent 생성

LLM이 담당하지 않아야 하는 것:

- 좌표 이동 계산
- 충돌 처리
- inventory 변경
- 가격 계산
- 아이템 생성 및 소멸
- death/revival 확정

이 부분은 모두 deterministic rule engine이 담당해야 한다.

## 5. 핵심 런타임 루프

월드는 시뮬레이션 tick 단위로 진행된다.

권장 tick 구조:

- 1 tick = 5 simulated seconds
- 12 ticks = 1 in-game minute
- planner는 매 tick 호출하지 않는다

### 월드 루프

```text
매 tick마다:
  1. 시간 진행
  2. 예약된 world event 처리
  3. 환경 상태 갱신 (날씨, 작물 성장, 부패)
  4. NPC perception 수집
  5. cognition trigger 실행
  6. intent를 실행 가능한 action으로 변환
  7. rule engine으로 action 해결
  8. memory, rumor, relationship 변화 기록
  9. 로그와 메트릭 출력
```

### Planner 호출 규칙

planner 호출은 비용이 크므로 trigger 기반으로 제한한다.

- 일정 시간 경과
- 목표 변경
- hunger threshold crossing
- social interaction 발생
- rumor 수신
- world event 발생
- 기존 intent 실패

권장 초기값:

- 일반 재계획 쿨다운: 60~180 simulated seconds
- 긴급 트리거: 즉시 재계획

## 6. 도메인 모델

### NPC 상태

```python
class NPCState(BaseModel):
    npc_id: str
    name: str
    profession: str
    skills: list[str]
    traits: list[str]
    goals: list[str]
    location_id: str
    inventory: dict[str, int]
    hunger: float
    energy: float
    money: int
    health: float
    social_status: float
    current_intent: str | None
```

### NPC 정체성 구성 방식

role은 hard-coded class보다 composition 방식으로 표현한다.

```text
profession + skills + traits + goals -> behavior profile
```

예:

```text
craftsman + metalwork + greedy + prestige_goal -> blacksmith-like behavior
```

### 월드 상태

```python
class WorldState(BaseModel):
    tick: int
    day: int
    weather: str
    locations: dict[str, "Location"]
    market: "MarketState"
    active_events: list["WorldEvent"]
```

### Intent 스키마

planner 출력은 항상 구조화된 intent여야 한다.

```json
{
  "intent_type": "trade|eat|move|talk|share_rumor|work|rest|investigate",
  "target_id": "npc_07",
  "target_location": "tavern",
  "reason": "Heard grain prices will rise",
  "dialogue": "I heard the miller is short on wheat.",
  "priority": 0.82
}
```

### Action 스키마

intent는 즉시 월드를 바꾸지 않는다.

rule engine은 intent를 하나 이상의 atomic action으로 변환한다.

예:

```text
intent: trade with baker
-> path_to_baker
-> initiate_trade
-> exchange_items
-> update_inventory
-> update_prices
-> create_memories
```

## 7. 모듈 경계

권장 디렉터리 구조:

```text
docs/
docs_kr/
src/
  engine/
  world/
  npc/
  memory/
  social/
  economy/
  actions/
  planner/
  training/
  api/
tests/
```

### 모듈 책임

`src/engine/`

- simulation loop
- tick scheduler
- event bus
- deterministic update ordering

`src/world/`

- map
- location graph
- weather
- world events

`src/npc/`

- npc state
- perception builder
- goal scoring
- intent queue

`src/memory/`

- episodic memory storage
- retrieval
- reflection jobs
- belief generation

`src/social/`

- relationships
- rumor lifecycle
- dialogue context

`src/economy/`

- resource production
- food demand
- prices
- spoilage
- scarcity feedback

`src/actions/`

- action schemas
- action validation
- action executor

`src/planner/`

- planner interface
- heuristic planner
- LLM planner adapter
- prompt builder
- output validation

`src/training/`

- synthetic state generator
- teacher prompting
- dataset validation
- SFT export

`src/api/`

- simulation inspection endpoints
- debug snapshots
- metrics access

## 8. 메모리와 belief 설계

### 메모리 계층

NPC memory는 최소 4개 층으로 나눈다.

1. episodic memory
2. beliefs
3. rumors
4. relationships

### 에피소드 메모리 레코드

```python
class EpisodicMemory(BaseModel):
    memory_id: str
    npc_id: str
    timestamp: int
    event_type: str
    summary: str
    entities: list[str]
    location_id: str | None
    importance: float
    sentiment: float
    tags: list[str]
```

### 검색 점수

초기 버전은 vector DB 없이 score 기반 retrieval로 시작한다.

```text
retrieval_score =
  recency_weight * recency
+ importance_weight * importance
+ relevance_weight * symbolic_relevance
+ emotion_weight * emotional_salience
```

초기 구현에서는 symbolic filtering만으로 충분하다.

- target entity match
- location match
- event type match
- goal tag match

### Belief 갱신

belief는 매 tick 생성하지 않는다.

reflection job이 일정 주기마다 memory를 요약해 belief를 만든다.

예:

```text
episodes:
- baker refused trade twice
- baker bought grain at high price

reflection:
"The baker is preparing for shortage."

belief:
subject=baker
predicate=expects_food_scarcity
confidence=0.68
```

## 9. Rumor 시스템 설계

rumor는 월드를 바꾸는 정보 엔진이다.

### Rumor 스키마

```python
class Rumor(BaseModel):
    rumor_id: str
    origin_npc_id: str
    subject_id: str | None
    content: str
    category: str
    confidence: float
    value: float
    distortion: float
    hop_count: int
    created_tick: int
    last_shared_tick: int
```

### Rumor 생명주기

```text
event
-> observation
-> rumor creation
-> sharing opportunity
-> listener interpretation
-> belief adjustment
-> new behavior
-> world change
```

### 공유 결정 요소

- relationship closeness
- rumor value
- rumor confidence
- personality trait
- current goal relevance
- social setting

### 조작 메커니즘

초기 버전에서는 왜곡을 단순 수치로 관리한다.

- honest NPC: distortion 상승이 적다
- greedy/deceitful NPC: distortion 상승이 크다
- hop_count 증가 시 confidence는 감소한다

권장 규칙:

```text
effective_confidence =
  base_confidence
  - hop_count_penalty
  - distortion_penalty
  + trust_bonus
```

## 10. 음식 경제와 entropy

이 프로젝트의 핵심 동력은 "배고픔이 행동을 밀어낸다"는 점이다.

### 최소 음식 루프

```text
crop production
-> harvest
-> storage
-> cooking or direct consumption
-> hunger reduction
-> depletion
-> scarcity
```

### MVP에 필요한 역할

- farmer
- cook
- merchant
- common villager

`priest -> revival`은 alpha 이후에 도입한다.

### 경제 상태

최소 상태:

- stock per food item
- daily production
- daily consumption
- spoilage timer
- current price
- scarcity index

### Entropy 발생원

- 시간 경과에 따른 hunger 증가
- 생산에 영향을 주는 날씨
- 음식 부패
- rumor 기반 사재기
- planner의 실수나 지연

### 안정화 장치

붕괴를 막기 위해 아래 장치를 초기에 넣는다.

- wild food fallback
- 최대 starvation 유예 시간
- price cap and floor
- 디버깅용 emergency market injection toggle

## 11. Goal 시스템

goal system은 planner보다 먼저 존재해야 한다.

planner는 무(無)에서 행동을 만드는 것이 아니라 goal 후보 중 우선순위를 선택해야 한다.

### Goal 카테고리

- survival
- economic
- social
- reputation
- curiosity
- duty

### Goal 평가

각 NPC는 매 주기마다 utility score를 계산한다.

예시:

```text
survival_score = hunger + health_risk + inventory_food_shortage
economic_score = profit_opportunity + debt_pressure
social_score = relationship_need + rumor_value
```

planner 입력에는 top-N goals만 전달한다.

권장 방향:

- heuristic goal scorer
- LLM은 선택과 설명만 담당

## 12. Planner 전략

### Planner 추상화

초기부터 planner는 교체 가능하게 설계한다.

```python
class Planner(Protocol):
    def plan(self, context: PlannerContext) -> PlannerOutput:
        ...
```

구현체:

- `HeuristicPlanner`
- `LLMPlanner`
- `ReplayPlanner` for testing

### Heuristic 우선인 이유

LLM 없이도 end-to-end simulation이 돌아가야 한다.

이유:

- 디버깅이 쉽다
- baseline 성능 비교가 가능하다
- planner failure와 simulation failure를 분리할 수 있다

### LLM 컨텍스트 페이로드

planner에 넣는 입력은 제한해야 한다.

필수 입력:

- current state summary
- top goals
- salient beliefs
- top rumors
- nearby entities
- recent failures
- allowed actions

제외해야 하는 입력:

- full raw memory dump
- entire map
- irrelevant NPC full states

## 13. 학습과 데이터 파이프라인

### Teacher 파이프라인

```text
state generator
-> prompt builder
-> teacher planner call
-> JSON validation
-> auto-repair if needed
-> dataset row
-> offline evaluation
```

### 데이터셋 형태

각 row는 최소 아래 구조를 가져야 한다.

```json
{
  "state": {},
  "goal_candidates": [],
  "beliefs": [],
  "rumors": [],
  "allowed_actions": [],
  "teacher_output": {
    "intent_type": "trade",
    "target_id": "npc_03",
    "reason": "Need bread before night"
  }
}
```

### 데이터셋 규모

권장 단계:

- phase 1: 스키마와 프롬프트 디버깅용 5k samples
- phase 2: 첫 SFT baseline용 25k samples
- phase 3: 더 견고한 planner 행동용 50k~150k samples

### 데이터 품질 검사

반드시 자동 검사해야 하는 항목:

- JSON validity
- allowed action conformity
- target existence
- reason 길이 제한
- state와의 모순 여부
- duplicate sample 비율

## 14. SFT와 RL 계획

### SFT 우선

Qwen-4B LoRA fine-tuning은 planner task에만 먼저 적용한다.

입력:

- compact planner context

출력:

- structured intent JSON

### 하드웨어 목표

- 24GB VRAM
- 4-bit quantization
- LoRA adapters

### RL은 이후

RL은 아래 조건을 만족할 때만 검토한다.

1. heuristic baseline 존재
2. LLM planner SFT baseline 존재
3. 시뮬레이션 reward가 충분히 안정적임
4. 평가 지표가 정의됨

초기 RL 대상은 planner보다 dialogue 또는 persuasion behavior가 더 적합하다.

이유:

- reward를 설계하기 쉽다
- planner는 rule constraint가 강해 SFT만으로도 충분할 수 있다

## 15. 관측성과 디버깅

이 프로젝트는 관측 가능성이 낮으면 개발이 멈춘다.

초기부터 다음을 넣어야 한다.

### 필수 디버그 뷰

- current world tick
- NPC별 상태 패널
- current intent
- top goals
- hunger와 food inventory
- latest memories
- latest rumors
- relationship deltas
- market prices

### 필수 로그

- planner request/response
- rejected actions와 이유
- starvation events
- rumor propagation events
- trade events
- belief updates

### 메트릭

- 평균 hunger
- starvation count
- rumor spread depth
- 일별 trade count
- intent success rate
- planner call count
- mean planner latency

## 16. 테스트 전략

### 단위 테스트

- hunger progression
- spoilage
- price adjustment
- rumor confidence decay
- memory retrieval ordering
- intent validation

### 시뮬레이션 테스트

- 1 day village survival test
- no-food scarcity collapse test
- rumor spread test
- farmer-cook-consumer supply chain test

### 회귀 테스트

특정 seed로 deterministic replay를 남긴다.

검증 항목:

- starvation count 상한
- 최소 food stock 임계값
- expected rumor reach
- trade frequency 범위

## 17. 전달 로드맵

### Phase 0 - Foundations

목표:

- simulation shell 구축
- deterministic tick loop
- basic map and movement

완료 기준:

- 2~3개 location
- 3 NPC 이동 가능
- tick replay log 존재

### Phase 1 - Village MVP

목표:

- 10 NPC village
- hunger and food economy
- talk, trade, eat, share rumor

완료 기준:

- 3 in-game days 이상 붕괴 없이 실행
- 최소 1개 rumor chain 발생
- 최소 1개 scarcity response 발생

### Phase 2 - Social Depth

목표:

- relationships
- belief reflections
- planner integration

완료 기준:

- NPC가 relationship과 rumor를 반영해 대상을 선택
- 동일 상황에서 성격 차이에 따른 행동 차이를 관찰 가능

### Phase 3 - Scale and Training

목표:

- 30~40 NPC scale
- teacher dataset generation
- SFT planner baseline

완료 기준:

- planner swap 가능
- offline evaluation script 존재
- baseline metrics 저장

## 18. 첫 구현 스프린트

즉시 시작할 첫 스프린트 범위는 아래처럼 고정하는 것이 좋다.

### 스프린트 목표

"LLM 없이도 10 NPC village가 먹고 움직이며 거래하고 rumor를 전달하는 deterministic simulation" 만들기

### 스프린트 산출물

1. world tick engine
2. location graph and path steps
3. NPC state model
4. hunger progression and eating
5. food inventory and simple market prices
6. goal scorer
7. heuristic planner
8. trade action executor
9. rumor create/share/receive flow
10. debug snapshot API

### 스프린트 작업 분해

#### Track A - Engine

- tick scheduler 정의
- event queue 구현
- deterministic action resolution order 구현

#### Track B - NPC

- `NPCState` 정의
- perception snapshot builder 구현
- goal scoring 구현

#### Track C - Economy

- food item config 정의
- 생산, 소비, 부패 구현
- 가격 피드백 구현

#### Track D - Social

- rumor schema 정의
- rumor propagation 구현
- relationship scalar update 구현

#### Track E - Planner

- `Planner` protocol 구현
- `HeuristicPlanner` 구현
- intent validation 구현

## 19. 리스크와 대응

### Risk 1: LLM 비용이 반복 속도를 잡아먹음

대응:

- heuristic planner를 baseline으로 유지
- LLM planner 호출을 trigger 기반으로 제한
- replay dataset으로 offline inspection

### Risk 2: 시뮬레이션이 너무 쉽게 붕괴함

대응:

- wild food fallback
- debug economy injection
- scarcity tuning via config

### Risk 3: NPC 행동이 그럴듯하지 않고 랜덤하게 보임

대응:

- goal scorer를 먼저 명확히 설계
- relationship과 belief를 planner 입력에 포함
- action space를 작게 유지

### Risk 4: Memory 시스템 비용이 너무 커짐

대응:

- symbolic retrieval first
- reflection batch jobs
- capped memory windows

## 20. 실제 구현 순서

실제 구현은 아래 순서가 가장 안전하다.

1. tick engine
2. map and movement
3. NPC state and config loading
4. hunger and food inventory
5. production/consumption loop
6. trade and price update
7. rumor lifecycle
8. relationship updates
9. heuristic planner
10. memory retrieval
11. belief reflection
12. LLM planner adapter
13. synthetic dataset generator
14. SFT baseline

## 21. 바로 다음 액션

문서 이후 바로 이어서 할 수 있는 가장 실용적인 작업은 아래 셋이다.

1. `src/` 기준 프로젝트 skeleton 생성
2. `NPCState`, `WorldState`, `Intent`, `Rumor` 스키마부터 구현
3. heuristic planner와 tick loop를 먼저 연결

권장 순서상 다음 작업은 "코드 레벨 skeleton 생성"이다.
