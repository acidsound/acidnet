# Rumor Diversity Handoff

## What Just Landed

Recent milestone commits:

- `1c02f31` `Add DB-backed system prompt settings modal`
- `fc015f5` `Diversify seeded and dynamic village rumors`

The current playable build now has:

- a full `Qwen/Qwen3.5-4B` WSL-trained local adapter wired into the GUI through `local_peft`
- startup-time dialogue model loading with visible `loading -> ready` state in the GUI and event log
- a GUI `Settings` modal for the shared dialogue system prompt
- SQLite-backed prompt storage with:
  - read-only baseline prompt in `prompt_presets`
  - active editable prompt in `runtime_settings`
- NPC/world/player log separation in the event log
- seeded rumor diversity plus dynamic rumor spawning during runtime
- signature-based rumor deduplication so repeated dynamic content refreshes one rumor instead of stacking clones
- dynamic-rumor decay and expiry so stale runtime chatter leaves the world instead of accumulating forever

## Why The Rumor Fix Was Needed

The previous rumor loop looked alive but was effectively narrow:

- the demo world started with one dominant rumor
- rumor sharing picked from `known_rumor_ids` in list order
- player-facing rumor collection therefore kept surfacing the same wheat-shortage line

That meant the world was circulating, but the information layer was not.

## What Changed

Relevant files:

- `src/acidnet/world/demo.py`
- `src/acidnet/engine/simulation.py`
- `tests/test_simulation.py`

Implemented changes:

- the demo world now starts with multiple distinct rumors across economy, shortage, social, danger, and event categories
- several NPCs start with overlapping but non-identical rumor sets
- the simulation now spawns additional dynamic rumors from:
  - weather phase changes
  - market scarcity pressure
  - bakery and riverside supply pressure
- rumor selection for sharing is now ranked by value, recency, confidence, and hop count instead of raw insertion order
- the player rumor panel now shows rumors using the same ranked ordering
- repeated dynamic rumors with the same content now refresh an existing rumor instead of creating a new duplicate entry
- rumor sharing to NPCs and the player now treats already-known rumor content as known even if a later rumor ID differs
- stale dynamic rumors now decay and expire instead of living in the world forever

## Current Expected Behavior

When you ask different NPCs for rumors, you should now see different content instead of only:

- `The south field yield is down after the dry wind. Grain will be tight this week.`

For example, the player can now learn distinct rumors from `Neri`, `Hobb`, `Mara`, `Toma`, and `Serin`, more rumor entries appear as the world advances, and repeated weather/supply beats should no longer flood the player rumor list with the same sentence under different IDs.

## Verified State

Code checks at the time of this handoff:

- `python -m pytest -q` -> `58 passed`
- `python -m compileall src/acidnet/engine/simulation.py src/acidnet/world/demo.py tests/test_simulation.py` passed

The rumor-specific tests now cover:

- multiple seeded rumors at startup
- multiple distinct rumors collected by the player
- dynamic rumor spawning after world advancement
- repeated dynamic rumor content reusing an existing rumor
- player rumor knowledge deduped by rumor content
- stale dynamic rumor expiry

## What To Read First In A New Chat

- `docs/roadmap/00-execution-checklist.md`
- `docs/roadmap/07-keyboard-gui-frontend.md`
- `docs/roadmap/18-wsl2-unsloth-train-path.md`
- `docs/roadmap/19-rumor-diversity-handoff.md`

## Recommended Next Steps

The most sensible next moves are:

1. Add rumor distortion and paraphrase drift so hop count changes wording, not only confidence.
2. Add stronger event-driven rumor creation from trade shocks, starvation, shrine relief, and guard incidents.
3. Add UI affordances for rumor history:
   - latest learned
   - source NPC
   - age
   - confidence trend
4. Add evaluation that measures rumor diversity over time, not only circulation and starvation.

## Continuation Prompt

If a new conversation starts, the quickest continuation is:

`Read docs/roadmap/19-rumor-diversity-handoff.md and continue from the current playable GUI build. Keep the 4B local model path, keep SQLite prompt settings, and focus next on rumor distortion, event-driven rumor generation, and information-layer observability.`
