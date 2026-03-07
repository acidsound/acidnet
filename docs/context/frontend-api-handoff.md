# Frontend API Handoff

## Purpose

This is the short frontend-facing handoff for engineers building on the web client.
Keep it limited to the player-visible HTTP contract:

- what the client can query
- what the client can control
- which files and tests define that contract

Do not duplicate simulation design notes here.
Do not document raw persistence or private Python helpers here.

Updated: 2026-03-07

## Canonical Ownership

- HTTP runtime: `src/acidnet/frontend/web_app.py`
- Full protocol spec: `docs/roadmap/23-web-client-api-spec.md`
- Contract tests: `tests/test_web_frontend.py`
- Current browser probe: `src/acidnet/frontend/client/index.html`

The web client should consume the server payloads above as authoritative.
It must not recompute economy, travel, rumor, or exchange rules client-side.

## Queryable API

### `GET /api/state`

Primary player-view snapshot for the browser.

Frontend-safe top-level sections:

- `dialogue`
- `world`
- `player`
- `actions`
- `scene`
- `target`
- `recent_events`
- `help`

Current `world` fields that are explicitly safe to render:

- `day`
- `tick`
- `weather`
- `field_stress`
- `scarcity_index`
- `market_prices`
- `location_id`
- `location_name`
- `region_id`
- `region_name`
- `active_events`

Current `scene` fields that are explicitly safe to render:

- `description`
- `people`
- `rumors`
- `route_preview`
- `map_nodes`
- `map_edges`
- `regional_nodes`
- `regional_routes`

Notes:

- `scarcity_index` and `market_prices` are server-authoritative derived values.
- `active_events` entries currently expose `event_id`, `event_type`, and `summary`.
- `active_events` may now include item-aware `market_support` or `market_pressure` summaries when visible regional transits are actively steadying or tightening the local market.
- `player.debts` entries currently expose `npc_id`, `name`, and `amount` for outstanding player-visible debt.
- `scene.route_preview` is the server-authored route preview DTO for local and regional travel options.
- `regional_nodes` is summarized regional context, including `stock_signals`; it is not raw offscreen NPC state.
- `regional_nodes[].risk_level` is now a dynamic summarized pressure signal driven by offscreen stock, route throughput, and local scarcity context.
- `scene.people` cards now also expose `debt_options` alongside `buy_options`, `sell_options`, `ask_options`, and `give_options`.
- `actions.travel` is the server-authored travel action catalog aligned with `scene.route_preview`.
- `actions` is the allowed action catalog for the current state, not a hint to rebuild rules in the browser.
- `recent_events` is the append-only player-visible feed, not a full simulation log.

### `GET /api/dialogue-prompt`

Read-only prompt editor state.

Safe fields:

- `current_prompt`
- `default_prompt`
- `current_lines`
- `current_chars`

## Controllable API

### `POST /api/command`

Primary write surface for gameplay.

Request:

```json
{
  "command": "focus npc.mara"
}
```

Frontend responsibility:

- send the server-authored command string
- render returned `entries`
- refresh local UI from returned `state` or the next `GET /api/state`

The client must not synthesize new command grammar from UI assumptions.

Current exchange and debt command note:

- `share [npc] <item> <qty>` is now a supported low-stakes social-transfer shortcut.
- it routes to `give` when the player already holds the item, and otherwise routes to `ask`.
- `trade [npc] barter <give_item> <give_qty> for <get_item> <get_qty>` is now supported as the raw item-for-item exchange command.
- `trade [npc] debt <item> <qty>` is now supported as the raw credit-transfer command.
- `repay [npc] [amount]` repays player debt to a local NPC; omitting `amount` repays the full remaining balance.

### `POST /api/dialogue-prompt`

Prompt editor write surface.

Supported write modes:

- save with `prompt`
- reset with `reset_default`

This endpoint is for runtime prompt control only.
It is not a general configuration API.

## What Frontend Engineers Should Ignore

- raw simulation persistence
- hidden NPC state not exposed in `GET /api/state`
- in-process helper methods
- Tk UI behavior
- adapter-specific dialogue branching

If the browser needs a new player-visible field, add it to the web API and lock it in tests instead of deriving it locally.

## Update Rule

Update this file in the same slice whenever a change affects any of these:

- `GET /api/state` response shape
- `POST /api/command` command meaning or returned player-visible behavior
- `GET /api/dialogue-prompt` or `POST /api/dialogue-prompt`
- frontend-visible travel, exchange, rumor, event, market, or dialogue fields

If the full protocol changes, also update `docs/roadmap/23-web-client-api-spec.md` and `tests/test_web_frontend.py`.
