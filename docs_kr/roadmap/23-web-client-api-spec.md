# Web Client 와 Simulation API Spec

## 목적

웹 클라이언트와 시뮬레이션 런타임 사이의 전체 브라우저 계약을 정의한다.

이 문서는 HTTP 경계에서의 입력과 출력 구조에 대한 기준 문서다.
누가 읽더라도 현재 HTML을 보지 않고 호환 클라이언트를 만들 수 있어야 한다.

## 설계 규칙

- simulation runtime 만이 world truth 의 권위다
- 클라이언트는 intent 또는 raw command 를 보내고 player-visible derived state 를 받는다
- 클라이언트는 economy, rumor, travel, relationship 규칙을 임의로 재계산하거나 발명하지 않는다
- omniscient 나 debug view 는 기본 플레이어 계약과 분리된 별도 도구다
- 계약은 프런트엔드 프레임워크가 아니라 문서와 테스트로 버전 관리한다

## 런타임 소유 지점

현재 구현은 다음 파일에 있다.

- `src/acidnet/frontend/web_app.py`
- `docs/context/frontend-api-handoff.md`
- `src/acidnet/frontend/client/index.html`
- `tests/test_web_frontend.py`

브라우저는 `src/acidnet/frontend/web_app.py` 를 실제 HTTP 표면의 기준 구현으로 봐야 한다.

## 전송

- protocol: HTTP
- API 응답 content type: `application/json; charset=utf-8`
- 쓰기 요청 content type: `application/json`
- 프런트 refresh 모델: 현재는 polling

## 엔드포인트

### `GET /`

현재 정적 웹 클라이언트 자산을 반환한다.

### `GET /api/state`

현재 player-visible world state 를 반환한다.

응답 구조:

```json
{
  "dialogue": {
    "ready": true,
    "loading": false,
    "message": "Heuristic dialogue ready.",
    "backend": "RuleBasedDialogueAdapter"
  },
  "world": {
    "day": 1,
    "tick": 0,
    "weather": "storm_front",
    "field_stress": 0.18,
    "scarcity_index": 0.4,
    "market_prices": {
      "bread": 5,
      "fish": 4,
      "stew": 7,
      "tool": 15,
      "wheat": 2
    },
    "location_id": "square",
    "location_name": "Market Square",
    "region_id": "region.greenfall",
    "region_name": "Greenfall Village",
    "active_events": [
      {
        "event_id": "event.route.route.greenfall.hollowmarket.delay",
        "event_type": "route_delay",
        "summary": "The road toward Hollow Market is slowing under the storm front, and caravans are arriving late."
      }
    ]
  },
  "player": {
    "name": "Player",
    "location_id": "square",
    "money": 35,
    "hunger": 12.0,
    "fatigue": 0.0,
    "carried_weight": 0.5,
    "carry_capacity": 14.0,
    "focused_npc_id": null,
    "inventory": [
      {"item": "bread", "quantity": 1}
    ],
    "debts": [],
    "travel_state": {
      "is_traveling": false,
      "route_id": null,
      "origin_location_id": null,
      "destination_location_id": null,
      "ticks_remaining": 0,
      "risk_budget": 0.0
    }
  },
  "actions": {
    "common": [
      {"label": "Look", "command": "look"},
      {"label": "Work", "command": "work"},
      {"label": "Meal", "command": "meal", "enabled": true, "item": "bread"},
      {"label": "Rest", "command": "rest 1"},
      {"label": "Sleep", "command": "sleep 3"},
      {"label": "Next", "command": "next 1"}
    ],
    "consume": [
      {"label": "Eat Bread", "command": "eat bread", "item": "bread", "quantity": 1}
    ],
    "target": [
      {"label": "Inspect", "command": "inspect", "requires_target": true, "enabled": false},
      {"label": "Talk", "command": "talk", "requires_target": true, "enabled": false},
      {"label": "Ask Rumor", "command": "ask rumor", "requires_target": true, "enabled": false}
    ],
    "travel": [
      {
        "label": "Go Warm Crust Bakery",
        "command": "go bakery",
        "enabled": true,
        "kind": "local",
        "destination_location_id": "bakery",
        "destination_region_id": "region.greenfall",
        "travel_ticks": 18,
        "travel_turns": 2,
        "blocked_reason": null,
        "route_id": null
      }
    ]
  },
  "scene": {
    "description": "You are at Market Square [market].\nExits: ...",
    "people": [],
    "rumors": [],
    "route_preview": [],
    "map_nodes": [],
    "map_edges": [],
    "regional_nodes": [],
    "regional_routes": []
  },
  "target": null,
  "recent_events": [],
  "help": ["Commands:", "  look ..."]
}
```

### `POST /api/command`

시뮬레이션에 raw command 문자열 하나를 보낸다.

요청 구조:

```json
{
  "command": "focus npc.mara"
}
```

성공 응답 구조:

```json
{
  "ok": true,
  "command": "focus npc.mara",
  "entries": [
    {"kind": "system", "text": "Interaction target set to Mara."}
  ],
  "state": {},
  "debug": {
    "dialogue_trace": {
      "path": "trade_adjudicated",
      "interaction_mode": "direct_say",
      "trade_intent": "trade_quote",
      "trade_fact_kind": "trade_quote",
      "adapter_name": "openai_compat",
      "response_guard": "llm_ok"
    }
  }
}
```

주의:

- `state` 는 `GET /api/state` 와 같은 player-view snapshot 구조를 그대로 반환한다
- `entries` 는 이번 command 결과에 바로 붙여 그릴 수 있는 이벤트 목록이지 `recent_events` 전체를 대체하지 않는다

실패 응답 구조:

```json
{
  "ok": false,
  "error": "Dialogue model is still loading. Wait for the ready message.",
  "entries": [],
  "state": {}
}
```

### `GET /api/dialogue-prompt`

현재 활성화된 global dialogue system prompt 와 read-only default prompt 를 반환한다.

응답 구조:

```json
{
  "current_prompt": "You are a small NPC dialogue model ...",
  "default_prompt": "You are a small NPC dialogue model ...",
  "current_lines": 7,
  "current_chars": 312
}
```

### `POST /api/dialogue-prompt`

현재 global dialogue system prompt 를 저장하거나 기본값으로 되돌린다.

저장 요청:

```json
{
  "prompt": "Respond in Korean only."
}
```

리셋 요청:

```json
{
  "reset_default": true
}
```

저장 성공 응답:

```json
{
  "ok": true,
  "message": "Dialogue system prompt updated.",
  "prompt": {
    "current_prompt": "...",
    "default_prompt": "...",
    "current_lines": 3,
    "current_chars": 44
  }
}
```

실패 응답:

```json
{
  "ok": false,
  "error": "The dialogue system prompt cannot be empty."
}
```

## 필드 의미

### `dialogue`

- `ready`: 지금 NPC dialogue generation 이 가능한지
- `loading`: background preparation 이 진행 중인지
- `message`: 현재 backend 상태를 보여주는 player-facing 문자열
- `backend`: 현재 runtime 에 바인딩된 adapter class 이름

### `world`

- `day`, `tick`, `weather`: 현재 시뮬레이션 시간과 환경
- `field_stress`: 첫 shock chain 에서 쓰는 현재 농장 yield 압박 수치
- `scarcity_index`: live local snapshot 과 summarized regional support 에서 파생된 현재 player-visible market scarcity 압박 수치
- `market_prices`: 공유 market snapshot 에 대한 현재 server-authoritative item 가격 목록
- `location_id`, `location_name`: 현재 player anchor location
- `region_id`, `region_name`: 현재 player 가 속한 region 기준 정보이며 regional UI context 와 route labeling 에 안전하게 쓸 수 있다
- `active_events`: 현재 player region 또는 현재 travel route 에서 보이는 shock, route-event, item-aware market-flow summary 목록이다. omniscient global list 가 아니다
- `active_events` 의 개별 항목은 현재 `event_id`, `event_type`, `summary` 를 노출한다
- visible summarized regional transit가 local market를 actively steadying, tightening, 또는 crisis-relief 하는 동안 `market_support` 또는 `market_pressure` entry가 들어올 수 있다
- 플레이어가 traveling 중일 때는 route progress 의 기준 정보는 `scene.description` 과 `player.travel_state` 다

### `player`

- `name`: 현재 세션의 single-player identity 이며 runtime setting 에서 로드된다
- `focused_npc_id`: 현재 interaction target 또는 `null`
- `inventory`: 수량이 양수인 visible inventory 만 노출
- `travel_state`: route progress 와 travel metadata
- `money`, `hunger`, `fatigue`, `carried_weight`, `carry_capacity`: 생존과 하중 관련 상태

- `debts`: player debt summary (`npc_id`, `name`, `amount`)

### `actions`

이건 derived command catalog 이지 두 번째 rules engine 이 아니다.

- `common`: 전역 저마찰 액션
- `consume`: 현재 inventory 에서 파생되는 item-specific consumption 액션
- `target`: 현재 focused NPC 에 의존하는 액션
- `travel`: `scene.route_preview` 와 맞물린 local/regional travel action catalog

클라이언트는 이 목록을 직접 렌더링할 수 있다.
빠진 액션을 클라이언트가 임의로 유효하다고 가정하면 안 된다.

### `scene.description`

사람이 읽는 현재 장면 텍스트다.

- stationary: location description
- traveling: route 와 ETA 설명

### `scene.people`

현재 장면에서 보이는 NPC 카드 목록이다.

개별 항목 구조:

```json
{
  "npc_id": "npc.mara",
  "name": "Mara",
  "profession": "merchant",
  "mood": "eat",
  "is_vendor": true,
  "is_target": false,
  "stock": [
    {"item": "bread", "quantity": 6}
  ],
  "buy_options": [
    {"item": "bread", "quantity": 6, "price": 5}
  ],
  "sell_options": [
    {"item": "bread", "quantity": 1, "price": 2}
  ],
  "ask_options": [
    {"item": "bread", "quantity": 1, "price": null}
  ],
  "give_options": [
    {"item": "bread", "quantity": 1, "price": null}
  ],
  "debt_options": [
    {"item": "bread", "quantity": 1, "price": 6}
  ]
}
```

주의:

- `stock` 은 현재 보이는 재고이지 숨겨진 전체 세계 상태가 아니다
- `buy_options` 는 플레이어가 이 NPC에게서 살 수 있는 것
- `sell_options` 는 플레이어가 이 NPC에게 팔 수 있는 것
- `ask_options` 는 플레이어가 이 NPC에게 무상으로 요청할 수 있는 것
- `give_options` 는 플레이어가 reserve 를 깨지 않고 무상으로 줄 수 있는 것

- `debt_options` 는 debt 로 받을 수 있는 항목이며 `price` 는 unit 당 owed gold 다

### `scene.rumors`

플레이어가 알고 있는 rumor 만 반환한다.

개별 항목 구조:

```json
{
  "content": "The south field yield is down after the dry wind.",
  "confidence": 0.82
}
```

### `scene.route_preview`

지금 이동 가능한 local / regional route preview DTO 목록이다.

개별 항목 구조:

```json
{
  "connection_kind": "regional",
  "destination_location_id": "hollowmarket_gate",
  "destination_region_id": "region.hollowmarket",
  "destination_name": "Hollow Market",
  "command": "travel-region Hollow Market",
  "travel_ticks": 96,
  "travel_turns": 8,
  "enabled": true,
  "blocked_reason": null,
  "route_id": "route.greenfall.hollowmarket",
  "status": "ready",
  "status_summary": null
}
```

- browser 가 topology 를 다시 해석하지 않도록 server-authoritative route preview DTO 를 직접 준다
- local preview 는 현재 weather/load 때문에 막힌 경로를 `blocked_reason` 으로 보여줄 수 있다
- regional preview 는 현재 player-visible delayed-route summary 를 같이 실을 수 있다

### `scene.map_nodes`

현재 node-map 표현 데이터를 담는다.

개별 항목 구조:

```json
{
  "location_id": "square",
  "name": "Market Square",
  "kind": "market",
  "row": 2,
  "column": 3,
  "glyph": "+",
  "is_player_here": true,
  "is_adjacent": true,
  "is_reachable": true,
  "move_command": "look",
  "connection_kind": "local",
  "occupant_count": 3
}
```

주의:

- `row`, `column`, `glyph` 는 frontend 상수가 아니라 world/location data 에서 온다
- `move_command` 는 타일 활성화 시 client 가 보내야 하는 server-authoritative command 다
- `connection_kind` 는 현재 `local` 또는 `regional` 이다
- `is_adjacent` 는 local topology 힌트일 뿐이고, 실제 상호작용 가능 여부는 `move_command` 와 `is_reachable` 를 기준으로 본다

### `scene.map_edges`

브라우저 프로브용 현재 visible map connection 목록이다.

개별 항목 구조:

```json
{
  "from_location_id": "square",
  "to_location_id": "farm",
  "kind": "local",
  "route_id": null,
  "is_delayed": false
}
```

주의:

- `kind` 는 현재 `local` 또는 `regional` 이다
- local edge 는 같은 region 안의 직접 이동 링크다
- regional edge 는 anchor location 사이의 summarized inter-region route 다
- client 는 이것을 display hint 로만 렌더링해야 하며, 실제 route validity 는 여전히 server command 결과를 따른다

### `scene.regional_nodes`

현재 알려진 regional graph 에 대한 summarized region card 목록이다.

개별 항목 구조:

```json
{
  "region_id": "region.greenfall",
  "name": "Greenfall Village",
  "kind": "settlement",
  "summary": "The current high-resolution village where the player starts.",
  "risk_level": 0.22,
  "is_current_region": true,
  "known_local_locations": ["bakery", "farm", "riverside", "shrine", "smithy", "square", "tavern"],
  "stock_signals": {
    "bread": 10,
    "fish": 8,
    "wheat": 18,
    "tool": 2
  }
}
```

주의:

- `stock_signals` 는 player-facing regional summary 이지 raw offscreen actor inventory 가 아니다
- `risk_level` 은 offscreen stock, route throughput, local scarcity 압력을 합친 dynamic summarized pressure signal 이다
- `known_local_locations` 는 map 과 route presentation 을 돕는 region-summary 힌트이지 두 번째 navigation rules engine 이 아니다
- `is_current_region` 은 summarized graph 에서 플레이어의 현재 region 을 표시한다

### `scene.regional_routes`

요약된 inter-settlement route metadata 다.

개별 항목 구조:

```json
{
  "route_id": "route.greenfall.hollowmarket",
  "from_region_id": "region.greenfall",
  "to_region_id": "region.hollowmarket",
  "travel_ticks": 96,
  "cargo_risk": 0.24,
  "weather_sensitivity": 0.45,
  "seasonal_capacity": 1.0,
  "transit_count": 1,
  "status": "delayed",
  "status_summary": "The road toward Hollow Market is slowing under the storm front, and caravans are arriving late."
}
```

주의:

- `transit_count` 는 route 에 대한 player-visible summarized logistics count 이지 전체 NPC 목록이 아니다
- `status` 는 player-visible route knowledge 이지 omniscient logistics channel 이 아니다
- 현재 기대값은 `stable`, `delayed`, `unknown` 이다
- `unknown` 은 regional graph 에 route 가 있지만 플레이어가 현재 그 disruption state 를 직접 볼 수 없다는 뜻이다

### `target`

현재 target detail card 또는 `null`.

구조:

```json
{
  "npc_id": "npc.mara",
  "name": "Mara",
  "detail_text": "Target: Mara (merchant)\nLocation: Market Square\n..."
}
```

### `recent_events`

최근 관찰 feed 의 append-only 버퍼다.

개별 항목 구조:

```json
{
  "kind": "npc",
  "text": "Mara: Prices move faster than patience here.",
  "day": 1,
  "tick": 24
}
```

현재 kind 예시는 다음과 같다.

- `system`
- `input`
- `world`
- `npc`
- `ui`

### `help`

현재 runtime command contract 의 line-split help text.

## Command Contract

현재 canonical write interface 는 raw text command 다.

중요 command 그룹:

- observation: `look`, `status`, `inventory`, `rumors`, `npcs`, `map`, `help`
- targeting: `focus <npc>`, `focus clear`, `inspect [npc]`
- dialogue: `talk [npc]`, `say <npc> <message>`, `ask [npc] rumor`
- economy: `trade [npc] buy <item> <qty>`, `trade [npc] sell <item> <qty>`, `trade [npc] ask <item> <qty>`, `trade [npc] give <item> <qty>`, `trade [npc] debt <item> <qty>`, `trade [npc] barter <give_item> <give_qty> for <get_item> <get_qty>`, `share [npc] <item> <qty>`, `repay [npc] [amount]`
- survival: `meal`, `eat [item]`, `work`, `next [turns]`
- travel and recovery: `go <location>`, `rest [turns]`, `sleep [turns]`

`share [npc] <item> <qty>` 는 기본 저강도 social-transfer shortcut 이다:

- player 가 이미 그 item 을 들고 있으면 `trade ... give ...` 로 간다
- 그렇지 않으면 `trade ... ask ...` 로 간다

`trade [npc] barter <give_item> <give_qty> for <get_item> <get_qty>` 는 item-for-item exchange 형식이다:

- 다른 exchange mode 와 같은 reserve-floor 및 acceptance path 위에 있다
- cash vendor 에만 묶이지 않는다

`trade [npc] debt <item> <qty>` 는 credit-transfer 형식이다:

- stock, reserve-floor, relationship, urgency, debt ceiling 을 같은 exchange path 에서 검사한다
- 결과 debt 는 `player.debts` 로 노출된다

`repay [npc] [amount]` 는 outstanding debt 를 갚는 명령이다:

- `amount` 를 생략하면 남은 전액을 갚는다
- repayment 도 여전히 location-bound raw command surface 를 사용한다

## Error Contract

현재 이해 가능한 클라이언트 실수는 HTTP `400` 으로 반환한다.

현재 사례:

- empty command
- invalid JSON body
- dialogue backend 가 아직 loading 중인데 dialogue command 를 보낸 경우
- empty prompt text 같은 invalid prompt update

`/api/command` 에서 생긴 실패는 가능하면 `state` 필드를 같이 유지해야 한다.

## Backend Notes

Dialogue backend 선택은 runtime concern 이지 client concern 이 아니다.

하지만 backend 동작 차이는 계약에 영향을 준다.

- `heuristic` 도 언어와 형식 같은 shared output contract 를 따라야 한다
- `openai_compat` 와 `local_peft` 는 full system prompt 를 직접 소비한다
- frontend client 는 adapter 종류에 따라 기본 NPC 렌더링을 갈라치면 안 된다

## 버전 관리 규칙

어떤 endpoint, field name, response shape, command meaning 이 바뀌면:

1. 이 문서를 갱신한다
2. `docs/context/frontend-api-handoff.md` 를 같이 갱신한다
3. `docs_kr/roadmap/23-web-client-api-spec.md` 를 같이 갱신한다
4. 계약을 고정하는 테스트를 수정한다
5. 그 필드를 소비하는 현재 frontend 구현도 같이 갱신한다

## 비목표

- private in-process Python helper 를 API 처럼 문서화하는 것
- omniscient debug payload 를 여기서 정의하는 것
- renderer layout 이나 CSS 를 protocol 일부로 고정하는 것
