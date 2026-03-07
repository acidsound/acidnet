# 프런트엔드 및 월드 확장 체크리스트

## 목표

공간-시간-교환 모델을 실행 기준으로 삼고, 월드 안정성을 잃지 않으면서 새 시스템을 한 번에 하나씩 추가한다.

참조:

- `docs/roadmap/20-spatial-time-exchange-model.md`
- `docs/roadmap/23-web-client-api-spec.md`
- `docs/roadmap/24-execution-roadmap.md`

## 실행 규칙

- 시스템은 하나씩만 착지시킨다
- 새 시스템마다 테스트와 관측 훅을 붙인다
- 넓은 현실성보다 단순하고 튜닝 가능한 규칙을 우선한다
- offscreen simulation 은 계속 요약 상태로 유지한다
- 프런트엔드 편의가 simulation truth 를 다시 정의하게 두지 않는다

## 이 체크리스트를 읽는 법

- live next-slice queue 는 `docs/context/current-state.md` 를 기준으로 본다
- active simulation track 순서는 `docs/roadmap/24-execution-roadmap.md` 를 기준으로 본다
- 이 문서는 exit criteria, landed progress, remaining gap 참고 문서다
- `[x]` 는 해당 step 의 exit criteria 를 닫을 만큼 완료됐다는 뜻이다
- `[ ]` 는 하위 slice 가 많이 들어갔더라도 아직 step 이 열려 있다는 뜻이다

## 체크리스트

- [x] Step 20A: travel 용 actor cost schema 추가
  Exit criteria:
  - player 와 NPC state 에 `fatigue`, `carried_weight`, `carry_capacity`, `travel_state` 가 들어간다
  - bounds 와 serialization 테스트가 있다
  - snapshot 과 storage 가 새 필드를 정상 처리한다

- [ ] Step 20B: 이동을 multi-turn travel 로 전환
  Exit criteria:
  - `go <location>` 이 ETA 를 가진 travel action 이 된다
  - 도착 전까지 시간과 비용을 실제로 소모한다
  - route modifier 로 travel 이 지연되거나 막힐 수 있다
  - `rest` 와 `sleep` 이 이동 비용의 회복축으로 함께 들어간다
  - fatigue 가 shelter quality 와 sleep quality 와 연결되어 실제 의미를 가진다
  - raw-command 클라이언트와 웹 프런트엔드가 둘 다 travel progress 를 보여준다
  Progress:
  - `go <location>` 은 이제 즉시 teleport 가 아니라 ETA 가 붙은 multi-turn travel 을 시작한다
  - travel 은 도착 전까지 시간, hunger, fatigue, load, weather-sensitive route cost 를 이미 소모한다
  - `rest` 와 `sleep` 은 이미 command surface 와 browser action catalog 에 들어가 있다
  - terminal 과 web state 둘 다 `player.travel_state` 와 scene text 로 travel progress 를 드러낸다
  - Remaining gap: shelter/recovery semantics 를 더 조여 fatigue 가 hunger 와 다른 축으로 남게 하고, dead instant-move path 가 남지 않게 계속 감사한다

- [ ] Step 20C: exchange mode 통합
  Exit criteria:
  - buy, sell, gift, barter, debt 가 하나의 rule path 를 사용한다
  - reserve-floor 로 자기파괴적 이타성을 막는다
  - reserve floor 가 안전하면 gift 가 낮은 강도의 기본 교환 모드가 된다
  - 생존 루프가 money-first 경제에 의존하지 않는다
  - 관계와 긴급도가 수락 여부에 영향을 준다
  - free transfer, refusal, 비대칭 교환 테스트가 있다
  Progress:
  - 현재 cash buy, ask, gift 는 대부분 같은 rule path 와 reserve-floor logic 을 공유한다
  - reserve floor 는 vendor stock 과 player-side gifting 양쪽에서 자기파괴적 depletion 을 막는다
  - 남은 공백은 barter, debt, 그리고 exchange 가 vendor trade 와 social transfer 로 다시 갈라지지 않게 하는 clearer gift-default behavior 다

- [ ] Step 20D: frontend state contract 정의
  Exit criteria:
  - raw persistence snapshot 과 분리된 scene DTO 가 생긴다
  - 기본은 omniscient state 가 아니라 player-visible state 를 노출한다
  - route preview, target detail, valid action catalog 가 포함된다
  - 큰 프런트엔드 개편 전에 계약 문서가 먼저 정리된다

현재 메모:

- 웹 프로브는 이제 `src/acidnet/frontend/web_app.py` 와 `src/acidnet/frontend/client/index.html` 에 있다
- 브라우저는 이미 raw persistence snapshot 대신 derived player-view state 와 command POST 를 사용한다
- HTTP contract 는 `docs/context/frontend-api-handoff.md` 와 `docs/roadmap/23-web-client-api-spec.md` 에 문서화되어 있다
- formal DTO naming, route preview, 더 넓은 action catalog 는 아직 남아 있으므로 `20D` 는 아직 완료가 아니다

- [ ] Step 20E: random monkey 를 goal monkey 로 교체
  Exit criteria:
  - survivor, trader, rumor verifier, altruist 같은 bounded monkey role 이 추가된다
  - 명시적 목표와 허용 명령을 가진 타이트한 action prompt 를 사용한다
  - monkey run 을 random noise 가 아니라 proxy-PC observation run 으로 다룬다
  - scoring 은 계속 rule-based 로 유지한다
  - tuning 에 바로 쓸 수 있는 failure reason 을 출력한다
  Progress:
  - `wanderer`, `survivor`, `trader`, `rumor_verifier`, `altruist` role 이 있는 초기 role-driven runner 가 들어갔다
  - observation role 은 이제 `shock_observer`, `hoarder`, `exploit_observer`, `regional_observer`, `downstream_observer` 까지 확장됐다
  - 각 step 은 선택된 command 와 함께 goal label 을 남긴다
  - rule-based scoring 과 actionable failure summary 가 이제 monkey report 에 들어간다
  - Remaining gap: 현재 route, transit, stock-shift, price-shift 관찰을 넘어서는 richer downstream-economy scoring

- [ ] Step 20F: 첫 controllable external shock 추가
  Exit criteria:
  - 예를 들어 weather -> harvest shortfall -> scarcity 같은 체인 하나를 고른다
  - trigger, duration, blast radius, recovery path 가 정의된다
  - downside 와 regenerative 또는 recovery-side effect 가 함께 들어간다
  - shock 이 log 와 rumor generation 에 드러난다
  - manual reset 없이 회복 가능한지 검증한다
  Progress:
  - 첫 체인은 `dry_wind/dusty_heat -> field_stress -> harvest_shortfall -> cool_rain recovery` 로 들어갔다
  - `field_stress` 와 `active_events` 가 simulation status 와 web state 에 노출된다
  - 남은 공백은 더 넓은 blast radius 와 장기 economic knock-on effect 다

- [ ] Step 20G: 경제 루프에 entropy sink 추가
  Exit criteria:
  - spoilage, storage pressure, tool wear, reserve floor, delayed production 중 최소 둘이 들어간다
  - work 와 trade 가 여전히 할 가치가 있는지 검증한다
  - 플레이어가 쉽게 무한 안정성을 파밍하지 못함을 확인한다
  Progress:
  - 첫 sink 는 food spoilage, player-side tool wear, storage pressure, delayed production 형태로 이미 들어갔다
  - 남은 공백은 economy sink 또는 buffer rule 한 조각 더 추가하고, exploit loop 에 대한 monkey validation 을 더 강하게 거는 것이다

- [ ] Step 20H: regional scaling 추가
  Exit criteria:
  - 요약된 regional node 를 통해 여러 settlement 를 지원한다
  - 필요한 local area 만 high-resolution 으로 유지한다
  - settlement 간 route travel 이 의미 있는 시간과 위험을 가진다
  - observation run 에서 허용 가능한 runtime cost 를 확인한다
  Progress:
  - world state 는 이미 summarized `regions` 와 `regional_routes` 를 포함한다
  - demo world 는 Greenfall 을 high-resolution home region 으로, 두 이웃 settlement 를 summarized neighbor 로 노출한다
  - offscreen summarized region 은 낮은 비용으로 stock signal 을 drift 시킨다
  - `travel-region <region>` 은 summarized regional route 를 따라 region anchor location 으로 이동한다
  - web state 는 current region 과 summarized regional route metadata 를 노출한다
  - route-aware delay event 는 world state, `regions`, web regional route payload 에 모두 나타난다
  - route pressure 는 inter-region ETA 를 올리고 bad weather 에서 throughput 을 약화시킨다
  - offscreen regional shortage 와 route delay 는 local regional rumor 를 뿌린다
  - summarized `regional_transits` 는 full offscreen NPC loop 없이 settlement 사이 goods 를 움직인다
  - web regional route payload 는 summarized `transit_count` 를 노출한다
  - `regional_observer` 와 `downstream_observer` 는 player side 에서 cross-settlement route, transit, stock-shift, market-shift 관찰을 수행한다
  - 남은 공백은 summarized transit 이 더 풍부한 downstream economy impact 를 얼마나 가져야 하는지와, 그것을 observation run 에서 어떻게 score 할지 정하는 것이다

## Step 의 의존 순서

1. `20A`
2. `20B`
3. `20C`
4. `20D`
5. `20E`
6. `20F`
7. `20G`
8. `20H`

이 순서는 원래의 dependency order 이며, later step 이 일부 착지한 뒤의 live next-slice queue 를 뜻하지는 않는다.

## 아직 하지 말아야 할 것

- `20D` 전에는 무거운 renderer 에 커밋하지 않는다
- `20F` 가 안정되기 전에는 재난 시스템을 많이 넣지 않는다
- route cost 와 offscreen summarization 이 생기기 전에는 village 를 많이 늘리지 않는다
- monkey test 를 rule-based evaluation 없는 open-ended chat 으로 만들지 않는다
- Tk 프로토타입을 시뮬레이션 변경과 계속 parity 맞추는 데 시간을 쓰지 않는다
