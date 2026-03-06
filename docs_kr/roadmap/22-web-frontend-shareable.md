# 공유 가능한 웹 프런트엔드 기준선

## 목표

현재 Tk 전용 표현 경로를 URL로 공유 가능한 웹 프로브로 바꿔, 시뮬레이션 피드백을 더 쉽게 모은다.

이 결정은 렌더러 우선 결정이 아니다.
시뮬레이션 관측성과 피드백 루프를 위한 결정이다.

## 렌더링 방향

최소 시각 목표는 NetHack 수준의 읽기 쉬운 인터페이스다.
가까운 상한 목표는 isometric 2D village view 다.

둘 다 반드시 simulation truth 의 하위 표현이어야 한다.
시각적 욕심 때문에 이동, 교환, 시간 규칙이 바뀌면 안 된다.

## 왜 지금 웹 프런트엔드인가

이제 시뮬레이션이 어느 정도 형태를 갖췄기 때문에, 로컬 Tk 셸만 다듬는 것보다 주변 피드백을 더 쉽게 받는 것이 중요하다.

기존 Tk 클라이언트는 이제 레거시 실험 도구로 보고, 새 시스템이 반드시 맞춰야 하는 기준으로 사용하지 않는다.

브라우저 프런트엔드는 다음에 유리하다.

- 로컬 네트워크 URL 만으로 라이브 빌드를 공유할 수 있다
- 타겟 지정, 거래, 루머 가독성, 이동 비용에 대한 피드백을 빠르게 모을 수 있다
- 시뮬레이션 상태와 표현 상태를 더 명확히 분리할 수 있다
- 다음 프런트엔드 반복을 실제 배포 표면에 더 가깝게 만들 수 있다

## 핵심 규칙

- Python simulation 만이 월드 진실의 권위다
- 프런트엔드는 intent 를 보내고 파생된 player-view state 만 렌더링한다
- 클라이언트 쪽 world rule 은 두지 않는다
- renderer 편의 때문에 시간, fatigue, exchange, rumor 규칙을 우회하지 않는다
- debug 나 omniscient view 는 플레이어 시야와 분리된 명시적 도구로 둔다

## 첫 웹 슬라이스

첫 웹 프런트엔드는 의도적으로 작게 유지한다.

- stdlib HTTP server
- 공유 가능한 단일 HTML client
- polling 기반 상태 갱신
- command POST endpoint
- 자유 이동이 아닌 단순 2D node map
- scene, target, trade, rumor, event feed 패널

이 정도면 너무 이른 시점에 무거운 프레임워크로 넘어가지 않으면서도 시뮬레이션을 충분히 관찰할 수 있다.

## 현재 상태 계약

현재 임시 계약은 Python runtime 이 노출하는 player-view payload 다.

현재 섹션:

- `dialogue`
- `world`
- `player`
- `actions`
- `scene`
- `target`
- `recent_events`
- `help`

현재 command 표면:

- `GET /api/state`
- `POST /api/command`

이 계약은 raw persistence snapshot 을 재사용하지 않고, simulation state 에서 파생된 뷰를 사용한다.

## 웹 프로브가 보여줘야 하는 것

- 현재 위치와 인접한 이동 가능 장소
- 누가 여기에 있고 누가 현재 타겟인지
- 보이는 stock 과 현재 유효한 거래 옵션
- player hunger, fatigue, load, money, travel state
- 최근 이벤트와 플레이어가 아는 루머
- 시뮬레이션 명령과 계속 정합성을 유지하는 action button

## 바로 다음 작업

첫 웹 프로브가 들어간 다음 프런트엔드 쪽 후속 작업은 이 순서가 좋다.

1. state contract 를 이름 있는 DTO 로 공식화한다
2. multi-turn movement 를 위해 route preview 와 travel progress 표현을 추가한다
3. 남아 있는 하드코드 UI 명령을 simulation 이 주는 action catalog 로 치환한다
4. travel 과 exchange 규칙이 안정된 뒤에만 더 풍부한 2D 표현으로 간다

## 아직 하지 않을 것

- 지금 당장 큰 JS framework 에 커밋하지 않는다
- 브라우저를 두 번째 simulation engine 으로 만들지 않는다
- travel, rest, exchange 가 맞기 전에 그래픽 복잡도를 올리지 않는다
- frontend 편의를 이유로 world cost 를 지워버리지 않는다
