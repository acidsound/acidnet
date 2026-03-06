# 현재 실행 로드맵

## 목적

지금까지 좁혀진 설계 합의를, 다시 임시 UI 작업으로 흐트러지지 않도록 실제 구현 순서로 고정한다.

이 로드맵은 `docs/roadmap/00-execution-checklist.md` 를 최상위 우선순위 문서로 유지한다는 전제 위에 있다.

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

### Phase 2: Travel and Recovery

- `go <location>` 을 multi-turn travel 로 바꾼다
- 시간, work, travel 에 따라 fatigue 가 증가하게 만든다
- `rest` 와 `sleep` 을 추가한다
- shelter quality 가 sleep quality 에 영향을 주게 만든다
- terminal 과 web 에 route progress 를 드러낸다

### Phase 3: Exchange Unification

- vendor-only trade 가정 대신 하나의 exchange path 로 통합한다
- rules 를 쪼개지 않고 gift, barter, debt, cash 를 지원한다
- reserve floor 와 urgency check 로 이타성을 안정화한다

### Phase 4: Goal Monkeys

- random monkeying 을 role-driven proxy-PC run 으로 교체한다
- 명시적 목표, 허용 명령, rule-based scoring 을 추가한다
- monkey 를 travel, exchange, shock 행동을 보는 표준 observation harness 로 만든다
- 초기 role-driven runner 는 들어갔고, 남은 핵심 공백은 scoring/failure reporting 이다

### Phase 5: External Shocks and Recovery Loops

- 하나의 controllable state-dependent shock chain 을 추가한다
- shock 이 rumor, log, world state 에 드러나게 만든다
- 모든 파괴적 chain 에 plausable recovery path 가 포함되게 만든다

### Phase 6: Multi-Settlement Scaling

- 요약된 regional node 를 추가한다
- 플레이어나 tracked actor 근처에서만 local simulation 을 high-resolution 으로 유지한다
- settlement 사이에서 travel cost 와 information flow 가 의미를 갖게 만든다

## 바로 다음 작업

현재 즉시 실행 큐는 다음과 같다.

1. `23`: API contract 고정
2. backend parity audit: heuristic vs openai-compatible vs local-peft
3. `20B`: travel, rest, sleep, fatigue, route progress
4. `20C`: unified exchange
5. `20E`: goal monkeys

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
