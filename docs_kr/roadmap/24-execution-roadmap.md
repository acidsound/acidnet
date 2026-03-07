# 현재 실행 로드맵

## 목적

현재 설계 수렴 상태를 다시 ad hoc UI 작업으로 흩뜨리지 않고, 실제 구현 순서로 고정한다.

이 로드맵은 `docs/roadmap/00-execution-checklist.md`를 장기 제품 우선순위 문서로 유지한다는 전제를 둔다.

## 우선순위 해석

- 문서가 충돌하면 live next-slice queue는 `docs/context/current-state.md`를 기준으로 본다.
- 이 문서는 active simulation/world-expansion track 내부의 구현 순서를 정의한다.
- `docs/roadmap/21-frontend-world-expansion-checklist.md`는 live queue 문서가 아니라 exit criteria와 remaining gap 참고 문서로 본다.
- structural repo-split 작업과 그 다음 realtime-transition refactor는 parallel boundary-hardening track으로 보고 `docs/context/current-state.md`에서 관리한다.

## 기준선

현재 프로젝트 기준선은 다음과 같다.

- simulation-first
- 주 프런트엔드 피드백 표면은 web client
- 디버깅 제어 표면은 terminal/raw-command 흐름
- Tk는 legacy이며 제거 가능한 경로로 본다
- graph travel, fatigue, load, recovery, unified exchange가 다음 핵심 시뮬레이션 작업이다
- bounded monkey evaluation은 random noise가 아니라 향후 world observation 도구다

## 활성 로드맵

### Phase 1: Contract Lock

- 전체 web client API spec을 작성하고 유지한다
- system prompt, shared output contract, persona context 사이의 모호함을 제거한다
- 모든 dialogue backend가 언어/형식 규칙을 포함한 shared output contract를 따르게 만든다
- `active_events`와 route disruption state는 raw omniscient event list가 아니라 player-visible filtering을 거쳐 흐른다
- runtime과 eval parser policy는 promoted runtime backend와 `local_peft` dev/eval-only 경로를 분리한다
- shared dialogue cleanup은 `heuristic`, `openai_compat`, `local_peft` 전부에서 hidden-reasoning wrapper와 code-fenced 또는 JSON-wrapped reply shell까지 제거한다

### Phase 2: Travel and Recovery

- `go <location>`을 multi-turn travel로 바꾼다
- 시간, 작업, 이동에서 fatigue가 증가하게 만든다
- `rest`와 `sleep`을 추가한다
- shelter quality가 sleep quality에 영향을 주게 만든다
- terminal과 web에서 route progress를 보여준다
- baseline travel, ETA, fatigue, recovery 동작은 이미 들어가 있다
- sleep은 이제 shelter-sensitive fatigue floor 아래로는 바로 떨어지지 않으므로, poor cover에서는 얕은 회복만 가능하고 shrine이나 tavern shelter에서는 더 깊은 회복이 가능하다
- travel은 이제 도착 전까지 예전 location-bound command surface를 명시적으로 막으므로, dead instant-move 가정이 regression으로 잠겨 있다
- `20B`는 이제 immediate queue에서 내릴 만큼 닫혔다

### Phase 3: Exchange Unification

- vendor-only trade 가정을 하나의 exchange path로 통합한다
- rule을 쪼개지 않고 gift, barter, debt, cash를 지원한다
- reserve floor와 urgency check로 이타적 교환이 안정적으로 유지되게 한다
- 현재 cash buy, ask, gift는 대부분 같은 rule path를 공유하고 있고, `share [npc] <item> <qty>` 는 같은 exchange path 위에서 저강도 social transfer를 give-vs-ask 기본 동작으로 묶는다
- barter 도 이제 `trade [npc] barter <give_item> <give_qty> for <get_item> <get_qty>` 를 통해 같은 exchange path 위에 올라왔고 non-vendor item-for-item exchange 도 가능하다
- debt 도 이제 `trade [npc] debt <item> <qty>` 를 통해 같은 exchange path 위에 올라왔고, `repay [npc] [amount]` 가 player-visible ledger 를 정리한다
- Phase 3 는 이제 닫혔고, 다음 queue 는 `20D` frontend state-contract cleanup 이다

### Phase 4: Goal Monkeys

- random monkeying을 role-driven proxy-PC run으로 교체한다
- 명시적 목표, 허용 명령, rule-based scoring을 추가한다
- monkey를 travel, exchange, shock 동작을 보는 표준 observation harness로 만든다
- role-driven runner, scoring, failure reporting은 이미 들어가 있다
- `shock_observer`는 field stress와 active shock event를 player side에서 추적한다
- `hoarder`는 storage-pressure 동작을 player side에서 검증한다
- `exploit_observer`는 reserve-constrained vendor 노출과 buy-floor refusal을 player side에서 점검한다
- `regional_observer`는 deterministic run에서 긴 regional travel을 빠르게 넘기고, mid-route에서 멈추지 않고 실제 cross-settlement observation을 검증한다
- `downstream_observer`는 요약 regional stock shift와 downstream market-price reaction을 player side에서 함께 기록한다
- `downstream_observer` scoring은 이제 분리된 downstream signal 나열만이 아니라 대략적인 route-delay -> transit -> regional-stock -> market-pressure response chain과 item overlap도 구분한다
- 다음 작업은 현재 summarized response-chain과 item-overlap 체크를 넘어 richer downstream-economy scoring으로 가는 것이다

### Phase 5: External Shocks and Recovery Loops

- 하나의 controllable state-dependent shock chain을 추가한다
- shock이 rumor, log, world state에 드러나게 만든다
- 모든 파괴적 chain에 plausible recovery path를 포함시킨다
- 첫 weather -> field stress -> harvest shortfall -> rain recovery 체인은 이미 들어가 있다

### Phase 5.5: Entropy Sinks

- inventory와 production이 영원히 완전 안정 상태로 머물지 않도록 internal sink를 추가한다
- sink는 punitive noise가 아니라 읽기 쉽고 회복 가능한 형태로 유지한다
- food spoilage, player-side tool wear, storage pressure, one-turn bakery 또는 tavern production delay는 이미 들어가 있다
- 같은 NPC에게 반복되는 food `ask` 요청은 이제 recent-help buffer에 걸려 zero-cash farm loop로 이어지기 전에 막힌다
- `exploit_observer`는 이제 reserve-constrained cash buy뿐 아니라 repeated gift-request refusal도 점검한다
- 현재 entropy-sink closure path는 simulation, monkey, circulation regression으로 잠겨 있다

### Phase 6: Multi-Settlement Scaling

- summarized regional node를 추가한다
- player나 tracked actor 근처에서만 local simulation을 high-resolution으로 유지한다
- settlement 사이 travel cost와 information flow가 중요해지게 만든다
- summarized regional node와 route metadata는 이미 world model과 web state에 들어가 있다
- summarized neighboring region의 low-cost offscreen stock drift가 매 turn 돈다
- `travel-region <region>`은 summarized route travel과 region anchor를 사용한다
- route-aware delay event는 world state, regional command output, web route metadata에 드러난다
- route pressure는 inter-region travel을 늦추고 summarized route throughput을 약화시킨다
- offscreen regional shortage와 route delay rumor는 local rumor layer로 흘러든다
- summarized regional transit pulse는 full offscreen NPC를 만들지 않고 goods를 이동시킨다
- web route payload는 player-visible `transit_count`를 노출한다
- `regional_observer`와 `downstream_observer`는 player side에서 route, transit, stock-shift, market-shift 관찰을 수행한다
- 다음 작업은 summarized transit가 더 풍부한 downstream economy effect를 만들어야 하는지, 그리고 그 효과를 observation run에서 어떻게 score할지 결정하는 것이다

## 바로 다음 작업

이 섹션은 active simulation/world-expansion track 전용 즉시 실행 큐다.
parallel structural boundary track과 우선순위가 겹치면 `docs/context/current-state.md`를 기준으로 본다.

현재 simulation-track queue는 다음과 같다.

1. later-phase tuning을 다시 main slice로 올리기 전에 남아 있는 `20D` frontend state contract gap을 조인다
2. 앞 단계 체크리스트가 더 조여진 뒤에 deeper downstream-economy scoring과 `20H` summarized regional scaling으로 다시 돌아간다

backend parity audit는 이제 immediate queue에서 내릴 만큼 닫혔다.
이후에도 prompt shaping, output cleanup, runtime parser policy, fallback behavior가 바뀌면 regression coverage로 parity를 계속 잠근다.
`20G`도 이제 immediate queue에서 뺄 만큼 닫혔다.
`20B`도 이제 immediate queue에서 뺄 만큼 닫혔다.
`20C`도 이제 immediate queue에서 뺄 만큼 닫혔다.

열려 있지만 현재 thin-slice queue의 맨 앞은 아닌 것:

- 현재 response-chain과 item-overlap 체크를 넘는 later `20E` downstream-economy monkey scoring 확장
- later `20H` summarized regional scaling 작업 계속

## 제거 작업

다음 경로들은 숨은 유지보수 비용이 계속 쌓이지 않게 해야 한다.

- Tk-specific parity work
- 계약과 조용히 갈라지는 backend-specific prompt behavior
- simulation state가 아니라 frontend 쪽에 박힌 action logic

## 리뷰 규율

모든 로직 변경에서 다음을 명시적으로 확인한다.

- API contract 영향
- backend parity 영향
- test coverage 영향
- dead path 또는 legacy client 영향
- documentation 영향

## 로드맵 슬라이스 완료 조건

한 슬라이스는 다음이 모두 만족돼야 완료로 본다.

- 코드 구현 완료
- 테스트 통과
- 문서 갱신
- player-visible state에 영향이 있으면 browser 경로까지 검증
- hidden legacy drift를 그냥 두지 않고 확인
