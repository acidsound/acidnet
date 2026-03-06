# Shareable Web Frontend Baseline

## Goal

Replace the current Tk-only presentation path with a shareable web probe that makes simulation feedback easy to collect through a URL.

This is not a renderer-first decision.
It is a simulation-observability decision.

## Rendering Direction

The minimum visual target is a NetHack-scale readable interface.
The maximum near-term target is an isometric 2D village view.

Both targets must remain downstream of simulation truth.
Do not let visual ambition redefine movement, exchange, or time rules.

## Why The Web Frontend Comes Next

The project now has enough simulation shape that feedback from other people matters more than polishing the local Tk shell.

The older Tk client should now be treated as a legacy exploratory tool, not as the standard that new systems must match.

A browser frontend helps with:

- sharing a live build by URL on a local network
- collecting fast feedback on targeting, trading, rumor readability, and travel cost
- separating simulation state from presentation state
- keeping the next frontend iteration closer to a real deployment surface

## Core Frontend Rules

- the Python simulation remains the only authority on world truth
- the frontend sends intents and renders derived player-view state
- no client-side world rules
- no renderer-specific shortcuts that bypass time, fatigue, exchange, or rumor rules
- debug or omniscient tools must stay explicit and separate from the player view

## First Web Slice

The first web frontend should stay deliberately small:

- stdlib HTTP server
- one shareable HTML client
- polling-based state refresh
- command POST endpoint
- simple 2D node map, not free movement
- scene, target, trade, rumor, and event-feed panels

This is enough to observe the simulation without locking the project into a heavy framework too early.

## Current State Contract

The provisional contract is a player-view payload exposed from the Python runtime.

Current sections:

- `dialogue`
- `world`
- `player`
- `actions`
- `scene`
- `target`
- `recent_events`
- `help`

Current command surface:

- `GET /api/state`
- `POST /api/command`

This contract is intentionally derived from simulation state rather than reusing raw persistence snapshots.

## What The Web Probe Must Show

- current location and nearby reachable places
- who is present and who is targeted
- visible stock and currently valid trade options
- player hunger, fatigue, load, money, and travel state
- recent events and rumor knowledge
- action buttons that stay aligned with valid simulation commands

## Near-Term Follow-Up

After this first web probe lands, the next frontend-facing work should be:

1. formalize the state contract into named DTOs
2. add route preview and travel-progress presentation for multi-turn movement
3. replace remaining hardcoded UI commands with action catalogs from simulation
4. prepare for a richer 2D presentation only after travel and exchange rules are stable

## Non-Goals

- committing to a large JS framework yet
- treating the browser as a second simulation engine
- adding graphical complexity before travel, rest, and exchange are correct
- using frontend convenience as a reason to simplify away world cost
