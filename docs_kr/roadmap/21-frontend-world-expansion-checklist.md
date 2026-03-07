# 프런트엔드와 월드 확장 체크리스트

## 목표

공간-시간-교환 모델을 실행 기준선으로 삼고, 월드 안정성을 잃지 않으면서 시스템을 하나씩 추가한다.

참고:

- `docs/roadmap/20-spatial-time-exchange-model.md`
- `docs/roadmap/23-web-client-api-spec.md`
- `docs/roadmap/24-execution-roadmap.md`

## 실행 규칙

- 한 번에 시스템 하나씩 착지시킨다
- 모든 새 시스템에는 테스트와 관찰 훅을 붙인다
- 넓은 현실성보다 단순하고 튜닝 가능한 규칙을 우선한다
- offscreen simulation은 요약 상태로 유지한다
- 프런트엔드 요구가 simulation truth를 다시 정의하게 두지 않는다

## 이 체크리스트를 읽는 법

- live next-slice queue는 `docs/context/current-state.md`를 기준으로 본다
- active simulation track 순서는 `docs/roadmap/24-execution-roadmap.md`를 기준으로 본다
- 이 문서는 exit criteria, landed progress, remaining gap 참고 문서다
- `[x]`는 해당 step의 exit criteria가 phase를 닫을 만큼 충족됐다는 뜻이다
- `[ ]`는 하위 slice가 많이 들어갔더라도 step 자체는 아직 열려 있다는 뜻이다

## 체크리스트

- [x] Step 20A: travel용 actor cost schema 추가
  Exit criteria:
  - player와 NPC state에 `fatigue`, `carried_weight`, `carry_capacity`, `travel_state`가 들어간다
  - bounds와 serialization 테스트가 있다
  - snapshot과 storage가 새 필드를 정상 처리한다

- [ ] Step 20B: 이동을 multi-turn travel로 전환
  Exit criteria:
  - `go <location>`이 ETA를 가진 travel action이 된다
  - 도착 전까지 시간과 비용이 실제로 소모된다
  - route modifier로 travel이 지연되거나 막힐 수 있다
  - `rest`와 `sleep`이 이동 비용의 회복축으로 존재한다
  - fatigue가 shelter quality와 sleep quality에 연결되어 실제 차별성을 가진다
  - raw-command client와 web frontend가 모두 travel progress를 보여준다
  Progress:
  - `go <location>`은 이제 즉시 teleport가 아니라 ETA가 붙은 multi-turn travel을 시작한다
  - travel은 이미 도착 전까지 시간, hunger, fatigue, load, weather-sensitive route cost를 소모한다
  - `rest`와 `sleep`은 이미 command surface와 browser action catalog에 들어가 있다
  - terminal과 web state는 `player.travel_state`와 scene text로 travel progress를 노출한다
  - Remaining gap: shelter/recovery semantics를 더 조여 fatigue가 hunger와 다른 축으로 남게 하고, dead instant-move path를 계속 감사한다

- [ ] Step 20C: exchange mode 통합
  Exit criteria:
  - buy, sell, gift, barter, debt가 하나의 rule path를 사용한다
  - reserve-floor logic이 자기파괴적 관대함을 막는다
  - reserve floor가 안전하면 gift가 기본 저강도 교환 모드가 된다
  - survival loop가 money-first 경제에만 의존하지 않는다
  - 관계와 긴급도가 수락 여부에 영향을 준다
  - free transfer, refusal, 비대칭 교환 테스트가 있다
  Progress:
  - 현재 cash buy, ask, gift는 대부분 같은 rule path와 reserve-floor logic을 공유한다
  - reserve floor는 vendor stock과 player-side gifting 양쪽에서 자기파괴적 depletion을 막는다
  - 남은 gap은 barter, debt, 그리고 exchange가 vendor trade와 social transfer로 다시 갈라지지 않게 하는 clearer gift-default behavior다

- [ ] Step 20D: frontend state contract 정의
  Exit criteria:
  - raw persistence snapshot과 분리된 derived scene DTO를 갖춘다
  - 기본값으로 omniscient world state가 아니라 player-visible state를 노출한다
  - route preview, target detail, valid action catalog를 포함한다
  - 더 큰 frontend 개편 전에 계약 문서를 먼저 정리한다

현재 메모:

- web probe는 이제 `src/acidnet/frontend/web_app.py`와 `src/acidnet/frontend/client/index.html`에 있다
- 브라우저는 이미 raw persistence snapshot 대신 derived player-view state와 command POST를 사용한다
- HTTP contract는 `docs/context/frontend-api-handoff.md`와 `docs/roadmap/23-web-client-api-spec.md`에 문서화돼 있다
- formal DTO naming, route preview, 더 넓은 action catalog가 아직 남아 있으므로 `20D`는 아직 완료가 아니다

- [ ] Step 20E: random monkey를 goal monkey로 교체
  Exit criteria:
  - survivor, trader, rumor verifier, altruist 같은 bounded monkey role을 추가한다
  - 명시적 목표와 허용 명령을 가진 타이트한 action prompt를 사용한다
  - monkey run을 random noise가 아니라 proxy-PC observation run으로 다룬다
  - scoring은 계속 rule-based로 유지한다
  - tuning에 바로 쓸 수 있는 failure reason을 출력한다
  Progress:
  - `wanderer`, `survivor`, `trader`, `rumor_verifier`, `altruist` role을 포함한 초기 role-driven runner가 들어갔다
  - observation role은 이제 `shock_observer`, `hoarder`, `exploit_observer`, `regional_observer`, `downstream_observer`까지 확장됐다
  - 각 step은 선택한 command와 함께 goal label을 기록한다
  - rule-based scoring과 actionable failure summary가 monkey report에 들어간다
  - Remaining gap: 현재 route, transit, stock-shift, price-shift 관찰을 넘는 richer downstream-economy scoring

- [ ] Step 20F: 첫 controllable external shock 추가
  Exit criteria:
  - weather -> harvest shortfall -> scarcity 같은 체인 하나를 고른다
  - trigger, duration, blast radius, recovery path를 정의한다
  - downside와 regenerative 또는 recovery-side effect를 함께 넣는다
  - shock을 log와 rumor generation에 드러낸다
  - manual reset 없이 회복 가능한지 검증한다
  Progress:
  - 첫 체인은 `dry_wind/dusty_heat -> field_stress -> harvest_shortfall -> cool_rain recovery`로 들어갔다
  - `field_stress`와 `active_events`는 simulation status와 web state에 노출된다
  - 남은 gap은 더 넓은 blast radius와 더 긴 economic knock-on effect다

- [x] Step 20G: 경제 루프에 entropy sink 추가
  Exit criteria:
  - spoilage, storage pressure, tool wear, reserve floor, delayed production 중 최소 둘 이상이 들어간다
  - work와 trade가 여전히 할 가치가 있는지 검증한다
  - 플레이어가 쉽게 무한 안정성을 재배할 수 없는지 확인한다
  Progress:
  - 첫 sink는 food spoilage, player-side tool wear, storage pressure, delayed production 형태로 이미 들어갔다
  - 같은 NPC에게 반복되는 food `ask` 요청은 이제 recent-help buffer에 걸려 zero-cash farm loop로 이어지기 전에 막힌다
  - `exploit_observer`는 이제 repeated gift-request refusal과 reserve-constrained cash buy를 함께 점검한다
  - circulation과 monkey regression이 현재 entropy slice의 closure path를 잠근다

- [ ] Step 20H: regional scaling 추가
  Exit criteria:
  - summarized regional node를 통해 여러 settlement를 지원한다
  - 필요한 곳에서만 local area를 high-resolution으로 유지한다
  - settlement 간 route travel이 의미 있는 시간과 위험을 가진다
  - observation run에서 수용 가능한 runtime cost를 확인한다
  Progress:
  - world state는 이미 summarized `regions`와 `regional_routes`를 포함한다
  - demo world는 Greenfall을 high-resolution home region으로, 두 개의 주변 settlement를 summarized neighbor로 노출한다
  - offscreen summarized region은 낮은 비용으로 stock signal drift를 수행한다
  - `travel-region <region>`은 summarized regional route를 따라 region anchor location으로 이동한다
  - web state는 current region과 summarized regional route metadata를 노출한다
  - route-aware delay event는 world state, `regions`, web regional route payload에 모두 드러난다
  - route pressure는 inter-region ETA를 늘리고 bad weather에서 throughput을 약화시킨다
  - offscreen regional shortage와 route delay는 local regional rumor를 밀어 넣는다
  - summarized `regional_transits`는 full offscreen NPC loop 없이 settlement 사이 goods를 이동시킨다
  - web regional route payload는 summarized `transit_count`를 노출한다
  - `regional_observer`와 `downstream_observer`는 player side에서 cross-settlement route, transit, stock-shift, market-shift 관찰을 수행한다
  - 남은 gap은 summarized transit의 downstream economy impact를 얼마나 더 키울지, 그리고 그 효과를 observation run에서 어떻게 score할지 정하는 것이다

## Step 의존 순서

1. `20A`
2. `20B`
3. `20C`
4. `20D`
5. `20E`
6. `20F`
7. `20G`
8. `20H`

이 순서는 원래 dependency order이지, later step이 일부 착지한 뒤의 live next-slice queue를 뜻하지는 않는다.

## 아직 하지 말아야 할 것

- `20D` 전에 무거운 renderer에 커밋하지 않는다
- `20F`가 안정되기 전에 재난 시스템을 많이 넣지 않는다
- route cost와 offscreen summarization이 준비되기 전에 village를 많이 늘리지 않는다
- monkey test를 rule-based evaluation 없는 open-ended chat로 만들지 않는다
- Tk 프로토타입을 simulation 변경과 계속 parity 맞추는 데 시간을 쓰지 않는다
