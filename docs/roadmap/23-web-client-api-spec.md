# Web Client and Simulation API Spec

## Purpose

Define the full browser-facing contract between the web client and the simulation runtime.

This document is the source of truth for input and output shapes at the HTTP boundary.
Anyone implementing a new client should be able to read this file and build a compatible UI without reading the current HTML.

## Design Rules

- the simulation runtime is the only authority on world truth
- the client sends intents or raw commands and receives player-visible derived state
- the client must not invent or recompute economy, rumor, travel, or relationship rules
- omniscient or debug views are separate tools, not the default player contract
- the contract is versioned by document and tests, not by frontend framework choice

## Runtime Ownership

The current implementation lives in:

- `src/acidnet/frontend/web_app.py`
- `docs/context/frontend-api-handoff.md`
- `src/acidnet/frontend/client/index.html`
- `tests/test_web_frontend.py`

The browser should treat `src/acidnet/frontend/web_app.py` as the canonical HTTP surface.

## Transport

- protocol: HTTP
- content type for API responses: `application/json; charset=utf-8`
- content type for write operations: `application/json`
- frontend refresh model: polling for now

## Endpoints

### `GET /`

Returns the current static web client asset.

### `GET /api/state`

Returns the current player-visible world state.

Response shape:

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

Submits one raw command string to the simulation.

Request shape:

```json
{
  "command": "focus npc.mara"
}
```

Success response shape:

```json
{
  "ok": true,
  "command": "focus npc.mara",
  "entries": [
    {"kind": "system", "text": "Interaction target set to Mara."}
  ],
  "state": {}
}
```

Notes:

- `state` is the same player-view snapshot shape returned by `GET /api/state`
- `entries` is the appendable event list for the submitted command, not a full replacement for `recent_events`

Failure response shape:

```json
{
  "ok": false,
  "error": "Dialogue model is still loading. Wait for the ready message.",
  "entries": [],
  "state": {}
}
```

### `GET /api/dialogue-prompt`

Returns the currently active global dialogue system prompt plus the read-only default prompt.

Response shape:

```json
{
  "current_prompt": "You are a small NPC dialogue model ...",
  "default_prompt": "You are a small NPC dialogue model ...",
  "current_lines": 7,
  "current_chars": 312
}
```

### `POST /api/dialogue-prompt`

Updates or resets the active global dialogue system prompt.

Save request:

```json
{
  "prompt": "Stay grounded in the supplied state. Reply with one short in-character answer."
}
```

Reset request:

```json
{
  "reset_default": true
}
```

Save success response:

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

Failure response:

```json
{
  "ok": false,
  "error": "The dialogue system prompt cannot be empty."
}
```

## Field Semantics

### `dialogue`

- `ready`: whether NPC dialogue generation can run right now
- `loading`: whether background preparation is still running
- `message`: player-facing status string for the current backend
- `backend`: adapter class name currently bound in runtime

### `world`

- `day`, `tick`, `weather`: current simulation time and broad environment
- `field_stress`: current farm-yield pressure scalar used by the first shock chain
- `scarcity_index`: current player-visible market scarcity pressure derived from the live local snapshot plus summarized regional support
- `market_prices`: current server-authoritative item prices for the shared market snapshot
- `location_id`, `location_name`: current player anchor location
- `region_id`, `region_name`: current player region anchor, safe for regional UI context and route labeling
- `active_events`: currently visible shock, route-event, or item-aware market-flow summaries from the player's current region or current travel route, not the omniscient global list
- `active_events` entries currently expose `event_id`, `event_type`, and `summary`
- `active_events` may now include `market_support` or `market_pressure` entries when visible summarized regional transit is actively steadying, tightening, or relieving a local market crisis
- when the player is traveling, the scene description and player travel state are the authoritative source for route progress

### `player`

- `name`: runtime-configured single-player identity for the current session
- `focused_npc_id`: current interaction target or `null`
- `inventory`: positive-count visible inventory only
- `debts`: outstanding player debt entries with `npc_id`, `name`, and `amount`
- `travel_state`: route progress and travel metadata
- `money`, `hunger`, `fatigue`, `carried_weight`, `carry_capacity`: player survival and load stats

### `actions`

This is a derived command catalog, not a second rules engine.

- `common`: globally available low-friction actions
- `consume`: item-specific consumption actions derived from current inventory
- `target`: actions that rely on the currently focused NPC
- `travel`: server-authored local and regional travel actions aligned with `scene.route_preview`

The client may render these directly.
The client must not assume missing actions are still valid.

### `scene.description`

Human-readable current scene text.

- stationary: location description
- traveling: route and ETA description

### `scene.people`

Visible NPC cards for the current scene.

Per-person shape:

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

Notes:

- `stock` is visible stock, not necessarily the full hidden world state
- `buy_options` means what the player can buy from this NPC
- `sell_options` means what the player can sell to this NPC
- `ask_options` means what the player can request as a no-cash gift from this NPC
- `give_options` means what the player can give away without payment while staying above reserve
- `debt_options` means what the player can take on debt right now, with `price` showing the gold that will be owed per unit

### `scene.rumors`

Player-known rumors only.

Per-rumor shape:

```json
{
  "content": "The south field yield is down after the dry wind.",
  "confidence": 0.82
}
```

### `scene.route_preview`

Server-authored route preview DTOs for reachable local and regional movement options.

Per-entry shape:

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

Notes:

- this is the browser-safe route preview DTO, not a raw topology dump that the client must reinterpret
- local previews can surface `blocked_reason` when weather or load currently prevents travel
- regional previews reuse the current player-visible route state and may surface delayed-route summaries

### `scene.map_nodes`

Current node-map presentation data.

Per-node shape:

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

Notes:

- `row`, `column`, and `glyph` come from world/location data, not frontend-only constants
- `move_command` is the server-authoritative command the client should send if the tile is activated
- `connection_kind` is currently `local` or `regional`
- `is_adjacent` remains a local-topology hint; the client should use `move_command` and `is_reachable` for interaction state

### `scene.map_edges`

Current visible map connections for the browser probe.

Per-edge shape:

```json
{
  "from_location_id": "square",
  "to_location_id": "farm",
  "kind": "local",
  "route_id": null,
  "is_delayed": false
}
```

Notes:

- `kind` is currently `local` or `regional`
- local edges represent direct in-region movement links
- regional edges represent summarized inter-region routes between anchor locations
- the client should render these as display hints only; route validity still comes from commands returned by the server

### `scene.regional_nodes`

Summarized region cards for the current known regional graph.

Per-node shape:

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

Notes:

- `stock_signals` is a summarized regional stock view for player-facing context, not raw offscreen actor inventory
- `risk_level` is now a dynamic summarized pressure signal driven by offscreen stock, route throughput, and local scarcity context
- `known_local_locations` is a region-summary hint for map and route presentation, not a second navigation rules engine
- `is_current_region` marks the player's present region in the summarized graph

### `scene.regional_routes`

Summarized inter-settlement route metadata.

Per-route shape:

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

Notes:

- `transit_count` is a player-visible summarized logistics count for that route, not a full NPC list
- `status` is player-visible route knowledge, not an omniscient logistics channel
- expected values are currently `stable`, `delayed`, or `unknown`
- `unknown` means the route exists in the known regional graph but the player does not currently have direct visibility into its disruption state

### `target`

Detailed current target card or `null`.

Shape:

```json
{
  "npc_id": "npc.mara",
  "name": "Mara",
  "detail_text": "Target: Mara (merchant)\nLocation: Market Square\n..."
}
```

### `recent_events`

Append-only recent observation feed.

Per-entry shape:

```json
{
  "kind": "npc",
  "text": "Mara: Prices move faster than patience here.",
  "day": 1,
  "tick": 24
}
```

Kinds currently include:

- `system`
- `input`
- `world`
- `npc`
- `ui`

### `help`

Line-split raw command help text for the current runtime contract.

## Command Contract

Commands are raw text and are currently the canonical write interface.

Important command groups:

- observation: `look`, `status`, `inventory`, `rumors`, `npcs`, `map`, `help`
- targeting: `focus <npc>`, `focus clear`, `inspect [npc]`
- dialogue: `talk [npc]`, `say <npc> <message>`, `ask [npc] rumor`
- economy: `trade [npc] buy <item> <qty>`, `trade [npc] sell <item> <qty>`, `trade [npc] ask <item> <qty>`, `trade [npc] give <item> <qty>`, `trade [npc] debt <item> <qty>`, `trade [npc] barter <give_item> <give_qty> for <get_item> <get_qty>`, `share [npc] <item> <qty>`, `repay [npc] [amount]`
- survival: `meal`, `eat [item]`, `work`, `next [turns]`
- travel and recovery: `go <location>`, `rest [turns]`, `sleep [turns]`

`share [npc] <item> <qty>` is the default low-stakes social-transfer shortcut:

- if the player already has the item, it routes to `trade ... give ...`
- otherwise it routes to `trade ... ask ...`

`trade [npc] barter <give_item> <give_qty> for <get_item> <get_qty>` is the item-for-item exchange form:

- it stays on the same reserve-floor and acceptance path as the other exchange modes
- it is not limited to cash vendors

`trade [npc] debt <item> <qty>` is the credit-transfer form:

- it stays on the same stock, reserve-floor, relationship, urgency, and debt-ceiling path as the rest of exchange
- the resulting player-visible gold balance owed is exposed through `player.debts`

`repay [npc] [amount]` settles outstanding player debt:

- omitting `amount` repays the full remaining balance
- repayment is location-bound and still uses the raw command surface

## Error Contract

Errors return HTTP `400` for currently understood client mistakes.

Current cases:

- empty command
- invalid JSON body
- dialogue command while dialogue backend is still loading
- invalid prompt update such as empty prompt text

Error responses should keep a `state` field when the failure came from `/api/command`.

## Backend Notes

Dialogue backend selection is a runtime concern, not a client concern.

However, backend behavior has contract implications:

- `heuristic` must still obey the shared output contract such as language and format rules
- `openai_compat` and `local_peft` consume the full system prompt directly
- frontend clients must not branch on adapter type to decide basic NPC rendering behavior

## Versioning Rule

Whenever any endpoint, field name, response shape, or command meaning changes:

1. update this document
2. update `docs/context/frontend-api-handoff.md`
3. update `docs_kr/roadmap/23-web-client-api-spec.md`
4. update tests that lock the contract
5. update the current frontend implementation if it consumes the changed field

## Non-Goals

- documenting private in-process Python helpers as if they were API
- defining omniscient debug payloads here
- freezing renderer layout or CSS as part of the protocol
