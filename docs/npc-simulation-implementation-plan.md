# NPC Simulation Implementation Plan

## 1. 문서 목적

이 문서는 "LLM 기반 자율 NPC 마을 시뮬레이션"을 실제 개발 가능한 수준으로 내리기 위한 구현 기준 문서다.

핵심 원칙은 다음 세 가지다.

```text
simulation first
LLM as planner, not executor
RL is optional until the simulation loop is stable
```

이 문서는 특히 아래 질문에 답하도록 구성한다.

1. 어떤 시스템부터 구현해야 하는가?
2. 각 시스템은 어떤 데이터와 인터페이스를 가져야 하는가?
3. MVP에서 무엇을 빼고 무엇을 반드시 넣어야 하는가?
4. 학습 데이터와 모델 파이프라인은 언제 붙이는가?

## 2. 프로젝트 목표

### Product Goal

30-40명의 NPC가 살아가는 village simulation을 만든다.

NPC는 다음 특성을 가진다.

- 자율 행동
- 제한된 자원 환경에서 생존
- rumor를 통한 정보 확산
- relationship과 belief에 기반한 사회적 의사결정
- LLM planner를 통한 고수준 intent 생성

### MVP Goal

첫 MVP는 10명의 NPC가 있는 작은 village를 목표로 한다.

MVP에서 반드시 가능한 행동:

- 이동
- 대화
- 거래
- 음식 획득/소비
- rumor 전달

### Non-Goals for MVP

다음은 MVP 범위에서 제외한다.

- full natural dialogue quality optimization
- RL fine-tuning
- combat system
- multi-town or world streaming
- advanced building construction

## 3. 권장 기술 스택

저장소가 비어 있으므로 초기 구현 기준 스택을 제안한다.

### Runtime

- Python 3.11+
- `pydantic` for schemas
- `networkx` or lightweight custom graph for relationships
- `sqlite` for local persistence
- `FastAPI` for debug API and tooling
- `pytest` for tests

### Simulation Rationale

Python을 추천하는 이유:

- simulation loop 구현이 빠르다
- LLM inference and training ecosystem이 가장 풍부하다
- dataset generation, LoRA training, evaluation 파이프라인과 연결이 쉽다

### Future Extensions

- visualization client: Godot, Unity, web dashboard 중 택1
- inference serving: vLLM or llama.cpp based wrapper
- training: transformers + peft + bitsandbytes

## 4. High-Level Architecture

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

### System Boundary

LLM은 아래만 담당한다.

- 상황 해석
- 목표 우선순위 판단
- intent 생성

LLM이 담당하지 않아야 하는 것:

- 좌표 이동 계산
- 충돌 처리
- inventory 변경
- 가격 계산
- item 생성/소멸
- death/revival 확정

이것들은 모두 deterministic rule engine이 담당한다.

## 5. Core Runtime Loop

시뮬레이션 tick 단위를 기준으로 world가 진행된다.

권장 tick 구조:

- 1 tick = 5 simulated seconds
- 12 ticks = 1 in-game minute
- planner는 매 tick 호출하지 않는다

### World Loop

```text
for each tick:
  1. advance time
  2. process scheduled world events
  3. update environment state (weather, crop growth, spoilage)
  4. collect NPC perceptions
  5. run cognition triggers
  6. convert intent -> executable actions
  7. resolve actions through rule engine
  8. write memories, rumors, relationship deltas
  9. emit logs/metrics
```

### Planner Trigger Rules

planner 호출은 비용이 크므로 trigger 기반으로 제한한다.

- 일정 시간 경과
- 목표 변경
- hunger threshold crossing
- social interaction 발생
- rumor 수신
- world event 발생
- 기존 intent 실패

권장 초기값:

- normal cooldown: 60-180 simulated seconds
- urgent trigger: immediate replanning

## 6. Domain Model

### NPC State

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

### NPC Identity Composition

role은 hard-coded class보다 composition을 사용한다.

```text
profession + skills + traits + goals -> behavior profile
```

예:

```text
craftsman + metalwork + greedy + prestige_goal -> blacksmith-like behavior
```

### World State

```python
class WorldState(BaseModel):
    tick: int
    day: int
    weather: str
    locations: dict[str, "Location"]
    market: "MarketState"
    active_events: list["WorldEvent"]
```

### Intent Schema

planner output은 항상 구조화된 intent여야 한다.

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

### Action Schema

intent는 즉시 world를 바꾸지 않는다.

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

## 7. Module Boundaries

권장 디렉터리 구조:

```text
docs/
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

### Module Responsibilities

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

## 8. Memory and Belief Design

### Memory Layers

NPC memory는 최소 4개 층으로 나눈다.

1. episodic memory
2. beliefs
3. rumors
4. relationships

### Episodic Memory Record

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

### Retrieval Score

초기 버전은 vector DB 없이 score 기반 retrieval로 시작한다.

```text
retrieval_score =
  recency_weight * recency
+ importance_weight * importance
+ relevance_weight * symbolic_relevance
+ emotion_weight * emotional_salience
```

초기 구현은 symbolic filtering만으로 충분하다.

- target entity match
- location match
- event type match
- goal tag match

### Belief Update

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

## 9. Rumor System Design

rumor는 world를 바꾸는 정보 엔진이다.

### Rumor Schema

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

### Rumor Lifecycle

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

### Share Decision Factors

- relationship closeness
- rumor value
- rumor confidence
- personality trait
- current goal relevance
- social setting

### Manipulation Mechanics

초기 버전에서는 왜곡을 단순 수치로 관리한다.

- honest NPC: distortion 상승 적음
- greedy/deceitful NPC: distortion 상승 큼
- hop_count 증가 시 confidence 감소

권장 규칙:

```text
effective_confidence =
  base_confidence
  - hop_count_penalty
  - distortion_penalty
  + trust_bonus
```

## 10. Food Economy and Entropy

이 프로젝트의 핵심 동력은 "배고픔이 행동을 밀어낸다"는 점이다.

### Minimal Food Loop

```text
crop production
-> harvest
-> storage
-> cooking or direct consumption
-> hunger reduction
-> depletion
-> scarcity
```

### Required Roles for MVP

- farmer
- cook
- merchant
- common villager

`priest -> revival`은 alpha 이후에 도입한다.

### Economy State

최소 상태:

- stock per food item
- daily production
- daily consumption
- spoilage timer
- current price
- scarcity index

### Entropy Sources

- hunger increase over time
- weather effects on production
- food spoilage
- rumor-driven hoarding
- planner mistakes or delays

### Stability Mechanisms

붕괴를 막기 위해 아래 장치를 초기에 넣는다.

- wild food fallback
- maximum starvation grace period
- price cap and floor
- emergency market injection toggle for debugging

## 11. Goal System

goal system은 planner 이전에 존재해야 한다.

planner는 무(無)에서 행동을 만드는 것이 아니라 goal 후보 중 우선순위를 선택해야 한다.

### Goal Categories

- survival
- economic
- social
- reputation
- curiosity
- duty

### Goal Evaluation

각 NPC는 매 주기마다 utility score를 계산한다.

예시:

```text
survival_score = hunger + health_risk + inventory_food_shortage
economic_score = profit_opportunity + debt_pressure
social_score = relationship_need + rumor_value
```

planner 입력에는 top-N goals만 전달한다.

권장:

- heuristic goal scorer
- LLM은 선택과 설명만 담당

## 12. Planner Strategy

### Planner Abstraction

초기부터 planner를 교체 가능하게 설계한다.

```python
class Planner(Protocol):
    def plan(self, context: PlannerContext) -> PlannerOutput:
        ...
```

구현체:

- `HeuristicPlanner`
- `LLMPlanner`
- `ReplayPlanner` for testing

### Why Heuristic First

LLM 없이도 end-to-end simulation이 돌아가야 한다.

그 이유:

- 디버깅이 쉽다
- baseline 성능 비교가 가능하다
- planner failure와 simulation failure를 분리할 수 있다

### LLM Context Payload

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

## 13. Training and Data Pipeline

### Teacher Pipeline

```text
state generator
-> prompt builder
-> teacher planner call
-> JSON validation
-> auto-repair if needed
-> dataset row
-> offline evaluation
```

### Dataset Shape

각 row는 최소 아래를 가진다.

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

### Dataset Volume

권장 단계:

- phase 1: 5k samples for schema and prompt debugging
- phase 2: 25k samples for first SFT baseline
- phase 3: 50k-150k samples for robust planner behavior

### Data Quality Checks

반드시 자동 검사해야 하는 항목:

- JSON validity
- allowed action conformity
- target existence
- reason length bounds
- contradiction with state
- duplicate sample ratio

## 14. SFT and RL Plan

### SFT First

Qwen-4B LoRA fine-tuning은 planner task에만 먼저 적용한다.

입력:

- compact planner context

출력:

- structured intent JSON

### Hardware Target

- 24GB VRAM
- 4-bit quantization
- LoRA adapters

### RL Later

RL은 아래 조건을 만족할 때만 검토한다.

1. heuristic baseline 존재
2. LLM planner SFT baseline 존재
3. 시뮬레이션 reward가 충분히 안정적임
4. 평가 지표가 정의됨

초기 RL 대상은 planner보다 dialogue 또는 persuasion behavior가 더 적합하다.

이유:

- reward를 설계하기 쉽다
- planner는 rule constraints가 강해 SFT만으로도 충분할 수 있다

## 15. Observability and Debugging

이 프로젝트는 관측 가능성이 낮으면 개발이 멈춘다.

초기부터 다음을 넣는다.

### Required Debug Views

- current world tick
- per-NPC state panel
- current intent
- top goals
- hunger and food inventory
- latest memories
- latest rumors
- relationship deltas
- market prices

### Required Logs

- planner request/response
- rejected actions and reasons
- starvation events
- rumor propagation events
- trade events
- belief updates

### Metrics

- average hunger
- starvation count
- rumor spread depth
- trade count per day
- intent success rate
- planner call count
- mean planner latency

## 16. Testing Strategy

### Unit Tests

- hunger progression
- spoilage
- price adjustment
- rumor confidence decay
- memory retrieval ordering
- intent validation

### Simulation Tests

- 1 day village survival test
- no-food scarcity collapse test
- rumor spread test
- farmer-cook-consumer supply chain test

### Regression Tests

특정 seed로 deterministic replay를 남긴다.

검증 항목:

- starvation count upper bound
- min food stock threshold
- expected rumor reach
- trade frequency band

## 17. Delivery Roadmap

### Phase 0 - Foundations

목표:

- simulation shell 구축
- deterministic tick loop
- basic map and movement

완료 기준:

- 2-3 locations
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

- NPC가 관계와 rumor를 반영해 대상 선택
- 동일 상황에서 성격 차이에 따른 행동 차이 관찰 가능

### Phase 3 - Scale and Training

목표:

- 30-40 NPC scale
- teacher dataset generation
- SFT planner baseline

완료 기준:

- planner swap 가능
- offline evaluation script 존재
- baseline metrics 저장

## 18. First Implementation Sprint

즉시 시작할 첫 스프린트 범위를 아래처럼 고정하는 것을 추천한다.

### Sprint Goal

"LLM 없이도 10 NPC village가 먹고 움직이며 거래하고 rumor를 전달하는 deterministic simulation" 만들기

### Sprint Deliverables

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

### Sprint Task Breakdown

#### Track A - Engine

- define tick scheduler
- implement event queue
- implement deterministic action resolution order

#### Track B - NPC

- define `NPCState`
- implement perception snapshot builder
- implement goal scoring

#### Track C - Economy

- define food item configs
- implement production, consumption, spoilage
- implement price feedback

#### Track D - Social

- define rumor schema
- implement rumor propagation
- implement relationship scalar updates

#### Track E - Planner

- implement `Planner` protocol
- implement `HeuristicPlanner`
- implement intent validation

## 19. Risks and Mitigations

### Risk 1: LLM cost dominates iteration speed

대응:

- heuristic planner를 baseline으로 유지
- LLM planner 호출을 trigger 기반으로 제한
- replay dataset으로 offline inspection

### Risk 2: Simulation collapses too easily

대응:

- wild food fallback
- debug economy injection
- scarcity tuning via config

### Risk 3: NPC behavior looks random, not believable

대응:

- goal scorer를 먼저 명확히 설계
- relationship and belief를 planner 입력에 포함
- action space를 작게 유지

### Risk 4: Memory system becomes too expensive

대응:

- symbolic retrieval first
- reflection batch jobs
- capped memory windows

## 20. Concrete Build Order

실제 구현 순서는 아래가 가장 안전하다.

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

## 21. Immediate Next Actions

문서 이후 바로 이어서 할 수 있는 가장 실용적인 작업은 아래 셋이다.

1. `src/` 기준 프로젝트 skeleton 생성
2. `NPCState`, `WorldState`, `Intent`, `Rumor` 스키마부터 구현
3. heuristic planner와 tick loop를 먼저 연결

권장 순서상 다음 작업은 "코드 레벨 skeleton 생성"이다.
