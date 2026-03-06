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
- `src/acidnet/frontend/web/index.html`
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
    "weather": "dry_wind",
    "location_id": "square",
    "location_name": "Market Square"
  },
  "player": {
    "name": "Jaeho",
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
      {"label": "Next", "command": "next 1"}
    ],
    "consume": [
      {"label": "Eat Bread", "command": "eat bread", "item": "bread", "quantity": 1}
    ],
    "target": [
      {"label": "Inspect", "command": "inspect", "requires_target": true, "enabled": false},
      {"label": "Talk", "command": "talk", "requires_target": true, "enabled": false},
      {"label": "Ask Rumor", "command": "ask rumor", "requires_target": true, "enabled": false}
    ]
  },
  "scene": {
    "description": "You are at Market Square [market].\nExits: ...",
    "people": [],
    "rumors": [],
    "map_nodes": []
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
  "prompt": "Respond in Korean only."
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
- `location_id`, `location_name`: current player anchor location
- when the player is traveling, the scene description and player travel state are the authoritative source for route progress

### `player`

- `focused_npc_id`: current interaction target or `null`
- `inventory`: positive-count visible inventory only
- `travel_state`: route progress and travel metadata
- `money`, `hunger`, `fatigue`, `carried_weight`, `carry_capacity`: player survival and load stats

### `actions`

This is a derived command catalog, not a second rules engine.

- `common`: globally available low-friction actions
- `consume`: item-specific consumption actions derived from current inventory
- `target`: actions that rely on the currently focused NPC

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
  ]
}
```

Notes:

- `stock` is visible stock, not necessarily the full hidden world state
- `buy_options` means what the player can buy from this NPC
- `sell_options` means what the player can sell to this NPC
- `ask_options` means what the player can request as a no-cash gift from this NPC
- `give_options` means what the player can give away without payment while staying above reserve

### `scene.rumors`

Player-known rumors only.

Per-rumor shape:

```json
{
  "content": "The south field yield is down after the dry wind.",
  "confidence": 0.82
}
```

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
  "occupant_count": 3
}
```

This is presentation guidance, not a physics system.

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
- economy: `trade [npc] buy <item> <qty>`, `trade [npc] sell <item> <qty>`, `trade [npc] ask <item> <qty>`, `trade [npc] give <item> <qty>`
- survival: `meal`, `eat [item]`, `work`, `next [turns]`
- travel and recovery: `go <location>`, `rest [turns]`, `sleep [turns]`

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
2. update `docs_kr/roadmap/23-web-client-api-spec.md`
3. update tests that lock the contract
4. update the current frontend implementation if it consumes the changed field

## Non-Goals

- documenting private in-process Python helpers as if they were API
- defining omniscient debug payloads here
- freezing renderer layout or CSS as part of the protocol
