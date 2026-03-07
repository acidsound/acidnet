# 현재 실행 로드맵

## 목적

지금까지 좁혀진 설계 합의를, 다시 임시 UI 작업으로 흐트러지지 않도록 실제 구현 순서로 고정한다.

이 로드맵은 `docs/roadmap/00-execution-checklist.md` 를 장기 제품 우선순위 문서로 유지한다는 전제 위에 있다.

## 우선순위 해석

- 문서끼리 충돌하면 live next-slice queue 는 `docs/context/current-state.md` 를 기준으로 본다.
- 이 문서는 active simulation/world-expansion track 안에서의 구현 순서를 정의한다.
- `docs/roadmap/21-frontend-world-expansion-checklist.md` 는 live queue 문서가 아니라 exit criteria 와 remaining gap 참고 문서다.
- structural repo-split 작업과 그 다음 realtime-transition refactor 는 parallel boundary-hardening track 으로 보고 `docs/context/current-state.md` 에서 관리한다.

## 기준선

현재 프로젝트 기준선은 다음과 같다.

- simulation-first
- 주 프런트엔드 피드백 표면은 web client
- 디버깅 제어 표면은 terminal/raw-command 흐름
- Tk 는 레거시이며 제거 가능 대상으로 본다
- graph travel, fatigue, load, recovery, unified exchange 가 다음 핵심 시뮬레이션 작업이다
- bounded monkey evaluation 은 미래의 world observation 도구이며 random noise 가 아니다

## 현재 로드맵

### Phase 1: Contract Lock

- full web client API spec 을 작성하고 유지한다
- system prompt, shared output contract, persona context 의 역할을 명확히 분리한다
- 모든 dialogue backend 가 언어 규칙을 포함한 shared output contract 를 따르게 만든다
- `active_events` 와 route disruption state 는 raw omniscient event list 가 아니라 player-visible filtering 을 거쳐 흐르게 만든다

### Phase 2: Travel and Recovery

- `go <location>` 을 multi-turn travel 로 바꾼다
- 시간, work, travel 에 따라 fatigue 가 증가하게 만든다
- `rest` 와 `sleep` 을 추가한다
- shelter quality 가 sleep quality 에 영향을 주게 만든다
- terminal 과 web 에 route progress 를 드러낸다
- baseline travel, ETA, fatigue, recovery 동작은 이미 들어가 있고, 남은 일은 recovery coupling 을 더 조이고 dead instant-move 가정이 남지 않게 정리하는 것이다

### Phase 3: Exchange Unification

- vendor-only trade 가정 대신 하나의 exchange path 로 통합한다
- rules 를 쪼개지 않고 gift, barter, debt, cash 를 지원한다
- reserve floor 와 urgency check 로 이타성을 안정화한다
- 현재는 cash buy, ask, gift 가 대부분 같은 rule path 를 공유하며, 남은 일은 barter, debt, gift-default semantics 를 더 분명히 하는 것이다

### Phase 4: Goal Monkeys

- random monkeying 을 role-driven proxy-PC run 으로 교체한다
- 명시적 목표, 허용 명령, rule-based scoring 을 추가한다
- monkey 를 travel, exchange, shock 행동을 보는 표준 observation harness 로 만든다
- role-driven runner, scoring, failure reporting 은 이미 들어가 있다
- `shock_observer` 는 field stress 와 active shock event 를 player side 에서 추적한다
- `hoarder` 는 storage-pressure 동작을 player side 에서 검증한다
- `exploit_observer` 는 reserve-constrained vendor 노출과 buy-floor refusal 을 player side 에서 탐침한다
- `regional_observer` 는 deterministic run 에서 긴 regional travel 을 빠르게 넘기고 실제 cross-settlement observation 이 mid-route 에서 멈추지 않게 만든다
- `downstream_observer` 는 요약 regional stock shift 와 downstream market-price reaction 을 player side 에서 함께 기록한다
- 다음 작업은 현재 route, transit, stock, price 관찰을 넘어서는 richer downstream-economy scoring 이다

### Phase 5: External Shocks and Recovery Loops

- 하나의 controllable state-dependent shock chain 을 추가한다
- shock 이 rumor, log, world state 에 드러나게 만든다
- 모든 파괴적 chain 에 plausable recovery path 가 포함되게 만든다
- 첫 weather -> field stress -> harvest shortfall -> rain recovery 체인은 이제 들어가 있다

### Phase 5.5: Entropy Sinks

- inventory 와 production 이 영원히 완전히 고정되지 않도록 internal sink 를 추가한다
- sink 는 punitive noise 가 아니라 읽히고 회복 가능한 형태를 유지한다
- food spoilage, player-side tool wear, storage pressure, one-turn bakery 또는 tavern production delay 는 이미 들어가 있다
- 다음 작업은 economy sink 또는 buffer rule 한 조각 더 추가하고, exploit resistance monkey validation 을 더 강하게 한 뒤, circulation 을 깨지 않는 NPC-side sink 가 필요한지 판단하는 것이다

### Phase 6: Multi-Settlement Scaling

- 요약된 regional node 를 추가한다
- 플레이어나 tracked actor 근처에서만 local simulation 을 high-resolution 으로 유지한다
- settlement 사이에서 travel cost 와 information flow 가 의미를 갖게 만든다
- summarized regional node 와 route metadata 는 이미 world model 과 web state 에 들어가 있다
- summarized neighboring region 의 low-cost offscreen stock drift 가 매 turn 돌아간다
- `travel-region <region>` 은 summarized route travel 과 region anchor 를 사용한다
- route-aware delay event 는 world state, regional command output, web route metadata 에 모두 나타난다
- route pressure 는 inter-region travel 을 늦추고 summarized route throughput 을 낮춘다
- offscreen summary 의 regional shortage 와 route delay rumor 가 local rumor layer 로 흘러들어온다
- summarized regional transit pulse 는 full offscreen NPC 를 만들지 않고 goods 를 이동시킨다
- web route payload 는 player-visible `transit_count` 를 노출한다
- `regional_observer` 와 `downstream_observer` 는 player side 에서 route, transit, stock-shift, market-shift 관찰을 수행한다
- 다음 작업은 summarized transit 이 더 풍부한 downstream economy effect 를 가져야 하는지와, 그 효과를 observation run 에서 어떻게 score 할지 정하는 것이다

## 바로 다음 작업

이 섹션은 active simulation/world-expansion track 의 즉시 실행 큐다.
parallel structural boundary track 과 우선순위가 겹치면 `docs/context/current-state.md` 를 기준으로 본다.

현재 simulation track 큐는 다음과 같다.

1. backend parity audit: heuristic vs openai-compatible vs local-peft
2. `20G` 를 economy sink 또는 buffer rule 한 조각 더 추가해서 마무리
3. route, transit, stock, price 관찰 이후를 보는 downstream-economy monkey scoring 확장
4. `20H` summarized regional scaling 계속 진행

열려 있지만 현재 thin-slice 큐의 맨 앞은 아닌 일:

- 남은 `20B` travel/recovery hardening 작업 마무리
- 남은 `20C` exchange unification 작업 마무리

## 제거 작업

다음 경로는 숨은 유지보수 비용이 더 쌓이지 않게 해야 한다.

- Tk-specific parity work
- 계약과 조용히 어긋나는 backend-specific prompt behavior
- simulation state 가 아니라 frontend 에 박혀 있는 action logic

## 리뷰 규율

모든 로직 변경에서 다음을 명시적으로 점검한다.

- API contract 영향
- backend parity 영향
- test coverage 영향
- dead path 또는 legacy client 영향
- documentation 영향

## 로드맵 슬라이스 완료 조건

한 슬라이스는 다음을 모두 만족해야 완료로 본다.

- 코드 구현 완료
- 테스트 통과
- 문서 갱신
- player-visible state 에 영향이 있으면 browser 경로까지 검증
- 숨은 legacy drift 를 그냥 두지 않고 점검
