# 현재 실행 로드맵

## 목적

현재 설계 수렴 상태를 다시 ad hoc UI 작업으로 흩트리지 않고, 실제 구현 순서로 고정한다.

이 로드맵은 `docs/roadmap/00-execution-checklist.md`를 장기 제품 우선순위 문서로 유지한다는 전제를 둔다.

## 우선순위 해석

- 문서가 충돌하면 live next-slice queue는 `docs/context/current-state.md`를 기준으로 본다.
- 이 문서는 active simulation/world-expansion track 내부의 구현 순서를 정의한다.
- `docs/roadmap/21-frontend-world-expansion-checklist.md`는 live queue 문서가 아니라 exit criteria와 remaining gap 참고 문서로 본다.
- structural repo-split 작업과 그 다음 realtime-transition refactor는 parallel boundary-hardening track으로 보고 `docs/context/current-state.md`에서 관리한다.

## 기준선

현재 프로젝트 기준선은 다음과 같다.

- simulation-first
- 주 프론트엔드 피드백 표면은 web client
- 디버깅 제어 표면은 terminal/raw-command 흐름
- Tk는 legacy이며 제거 가능 경로로 본다
- graph travel, fatigue, load, recovery, unified exchange가 다음 핵심 시뮬레이션 작업이다
- bounded monkey evaluation은 random noise가 아니라 미래의 world observation 도구다

## 활성 로드맵

### Phase 1: Contract Lock

- full web client API spec를 작성하고 유지한다
- system prompt, shared output contract, persona context 사이의 모호함을 제거한다
- 모든 dialogue backend가 언어/형식 규칙을 포함한 shared output contract를 따르게 만든다
- `active_events`와 route disruption state는 raw omniscient event list가 아니라 player-visible filtering을 거쳐 흐른다
- runtime과 eval parser policy도 promoted runtime backend와 `local_peft` dev/eval-only 경로를 분리한다
- shared dialogue cleanup은 `heuristic`, `openai_compat`, `local_peft` 전부에서 hidden-reasoning wrapper와 code-fenced 또는 JSON-wrapped reply shell까지 제거한다

### Phase 2: Travel and Recovery

- `go <location>`을 multi-turn travel로 바꾼다
- 시간, work, travel에 따라 fatigue가 증가하게 만든다
- `rest`와 `sleep`을 추가한다
- shelter quality가 sleep quality에 영향을 주게 만든다
- terminal과 web에 route progress를 드러낸다
- baseline travel, ETA, fatigue, recovery 동작은 이미 들어가 있고, 남은 일은 recovery coupling 보강과 dead instant-move 가정 정리다

### Phase 3: Exchange Unification

- vendor-only trade 가정을 하나의 exchange path로 통합한다
- rule을 쪼개지 않고 gift, barter, debt, cash를 지원한다
- reserve floor와 urgency check로 이타적 교환을 안정화한다
- 현재 cash buy, ask, gift는 대부분 같은 rule path를 공유하고, 남은 일은 barter, debt, gift-default semantics를 분명히 하는 것이다

### Phase 4: Goal Monkeys

- random monkeying을 role-driven proxy-PC run으로 교체한다
- 명시적 목표, 허용 명령, rule-based scoring을 추가한다
- monkey를 travel, exchange, shock 동작을 보는 표준 observation harness로 만든다
- role-driven runner, scoring, failure reporting은 이미 들어가 있다
- `shock_observer`는 field stress와 active shock event를 player side에서 추적한다
- `hoarder`는 storage-pressure 동작을 player side에서 검증한다
- `exploit_observer`는 reserve-constrained vendor 노출과 buy-floor refusal을 player side에서 점검한다
- `regional_observer`는 deterministic run에서 긴 regional travel을 빠르게 넘기고 실제 cross-settlement observation이 mid-route에서 멈추지 않게 만든다
- `downstream_observer`는 요약 regional stock shift와 downstream market-price reaction을 player side에서 함께 기록한다
- 다음 작업은 현재 route, transit, stock, price 관찰을 넘는 richer downstream-economy scoring이다

### Phase 5: External Shocks and Recovery Loops

- 하나의 controllable state-dependent shock chain을 추가한다
- shock을 rumor, log, world state에 드러나게 만든다
- 모든 파괴적 chain에 plausible recovery path를 포함시킨다
- 첫 weather -> field stress -> harvest shortfall -> rain recovery 체인은 이미 들어가 있다

### Phase 5.5: Entropy Sinks

- inventory와 production이 영원히 완전 안정 상태에 머물지 않도록 internal sink를 추가한다
- sink는 punitive noise가 아니라 읽기 쉽고 회복 가능한 형태를 유지한다
- food spoilage, player-side tool wear, storage pressure, one-turn bakery 또는 tavern production delay는 이미 들어가 있다
- 다음 작업은 economy sink 또는 buffer rule 한 조각을 더 추가하고, circulation을 깨지 않는 선에서 exploit resistance monkey validation을 더 강하게 하는 것이다

### Phase 6: Multi-Settlement Scaling

- summarized regional node를 추가한다
- 플레이어나 tracked actor 근처에서만 local simulation을 high-resolution으로 유지한다
- settlement 사이 travel cost와 information flow가 중요해지게 만든다
- summarized regional node와 route metadata는 이미 world model과 web state에 들어가 있다
- summarized neighboring region의 low-cost offscreen stock drift가 매 turn 돈다
- `travel-region <region>`은 summarized route travel과 region anchor를 사용한다
- route-aware delay event는 world state, regional command output, web route metadata에 모두 나타난다
- route pressure는 inter-region travel을 늦추고 summarized route throughput을 약화시킨다
- offscreen summary의 regional shortage와 route delay rumor가 local rumor layer로 흘러 들어온다
- summarized regional transit pulse는 full offscreen NPC를 만들지 않고 goods를 이동시킨다
- web route payload는 player-visible `transit_count`를 노출한다
- `regional_observer`와 `downstream_observer`는 player side에서 route, transit, stock-shift, market-shift 관찰을 수행한다
- 다음 작업은 summarized transit이 더 풍부한 downstream economy effect를 만들어야 하는지, 그리고 그 효과를 observation run에서 어떻게 score할지 정하는 것이다

## 바로 다음 작업

이 섹션은 active simulation/world-expansion track 전용의 즉시 실행 큐다.
parallel structural boundary track과 우선순위가 겹치면 `docs/context/current-state.md`를 기준으로 본다.

현재 simulation-track queue는 다음과 같다.

1. `20G`를 economy sink 또는 buffer rule 한 조각 더 추가해서 마무리한다
2. route, transit, stock, price 관찰 이후를 보는 downstream-economy monkey scoring을 확장한다
3. `20H` summarized regional scaling을 계속 진행한다

backend parity audit는 immediate queue에서 내릴 만큼 닫혔다.
이후에는 prompt shaping, output cleanup, runtime parser policy, fallback behavior가 바뀔 때 regression coverage로 parity를 잠근다.

열려 있지만 현재 thin-slice queue의 맨 앞은 아닌 것:

- 남은 `20B` travel/recovery hardening 마무리
- 남은 `20C` exchange unification 마무리

## 제거 작업

다음 경로들은 숨은 유지보수 비용을 더 쌓지 않게 해야 한다.

- Tk-specific parity work
- 계약과 조용히 갈라지는 backend-specific prompt behavior
- simulation state가 아니라 frontend 쪽에 박혀 있는 action logic

## 리뷰 규율

모든 로직 변경에서 다음을 명시적으로 확인한다.

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
- player-visible state에 영향이 있으면 browser 경로까지 검증
- hidden legacy drift를 그냥 두지 않고 확인
