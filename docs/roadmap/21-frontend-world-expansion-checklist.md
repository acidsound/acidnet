# Frontend and World Expansion Checklist

## Goal

Use the spatial-time-exchange model as the execution baseline and add new systems one at a time without losing control of world stability.

Reference:

- `docs/roadmap/20-spatial-time-exchange-model.md`
- `docs/roadmap/23-web-client-api-spec.md`
- `docs/roadmap/24-execution-roadmap.md`

## Execution Rules

- land one system at a time
- require tests and observation hooks for every new system
- prefer simple, tuneable rules over broad realism
- keep offscreen simulation summarized
- do not let frontend needs redefine simulation truth

## How To Read This Checklist

- use `docs/context/current-state.md` for the live next-slice queue
- use `docs/roadmap/24-execution-roadmap.md` for the active simulation-track order
- use this file for exit criteria, landed progress, and remaining gaps
- `[x]` means the step's exit criteria are complete enough to close the phase
- `[ ]` means the step is still open even if substantial slices under it have already landed

## Checklist

- [x] Step 20A: Add actor cost schema for travel.
  Exit criteria:
  - player and NPC state include `fatigue`, `carried_weight`, `carry_capacity`, and `travel_state`
  - tests cover bounds and serialization
  - snapshots and storage handle the new fields cleanly

- [x] Step 20B: Convert movement into multi-turn travel.
  Exit criteria:
  - `go <location>` becomes a travel action with ETA
  - travel consumes time and cost before arrival
  - travel can be blocked or slowed by route modifiers
  - `rest` and `sleep` exist as the recovery side of movement cost
  - fatigue matters because sleep quality and shelter quality matter
  - the raw-command client and the web frontend both show travel progress
  Progress:
  - `go <location>` now starts multi-turn travel with ETA instead of immediate teleport
  - travel already consumes time, hunger, fatigue, load, and weather-sensitive route cost before arrival
  - `rest` and `sleep` are already live in the command surface and browser action catalog
  - player `status` now surfaces current shelter quality, and sleep now bottoms out at a shelter-sensitive fatigue floor so poor cover only gives shallow recovery
  - terminal and web state both expose travel progress through `player.travel_state` and scene text
  - travel now explicitly blocks the old location-bound command surface until arrival, so dead instant-move assumptions stay locked out in regression

- [x] Step 20C: Unify exchange modes.
  Exit criteria:
  - buy, sell, gift, barter, and debt use one rule path
  - reserve-floor logic prevents self-destructive generosity
  - gifting is the default low-stakes exchange mode when reserve floors are safe
  - the survival loop still works without a money-first economy
  - relationship and urgency influence acceptance
  - tests cover free transfer, refusal, and asymmetric exchange
  Progress:
  - cash buys, asks, and gifts now share most of the current rule path and reserve-floor logic
  - reserve floors already protect both vendor stock and player-side gifting from self-destructive depletion
  - `share [npc] <item> <qty>` now defaults low-stakes social transfer to `give` when the player has the item and to `ask` otherwise, while staying on the same exchange path
  - `trade [npc] barter <give_item> <give_qty> for <get_item> <get_qty>` now keeps item-for-item exchange on the same reserve-floor and acceptance path, including non-vendor barter
  - `trade [npc] debt <item> <qty>` now keeps credit exchange on the same stock, reserve-floor, relationship, urgency, and debt-ceiling path
  - `repay [npc] [amount]` now closes the player-visible debt leg on the same live command surface, and web state exposes `player.debts` plus per-NPC `debt_options`

- [x] Step 20D: Define the frontend state contract.
  Exit criteria:
  - add derived scene DTOs separate from raw persistence snapshots
  - expose player-visible state, not omniscient world state, by default
  - include route preview, target details, and valid action catalogs
  - document the contract before a larger frontend rewrite

Current note:

- the web probe now lives in `src/acidnet/frontend/web_app.py` and `src/acidnet/frontend/client/index.html`
- the browser already consumes derived player-view state plus command POSTs instead of raw persistence snapshots
- the HTTP contract is now documented in `docs/context/frontend-api-handoff.md` and `docs/roadmap/23-web-client-api-spec.md`
- `scene.route_preview` now exposes server-authored local and regional route preview DTOs instead of leaving route preview to client reconstruction
- `actions.travel` now exposes server-authored travel commands aligned with that route preview DTO

- [ ] Step 20E: Replace random monkeying with goal monkeys.
  Exit criteria:
  - add bounded monkey roles such as survivor, trader, rumor verifier, and altruist
  - use tight action prompts with explicit goals and allowed commands
  - treat monkey runs as proxy-PC observation runs, not as random noise
  - keep scoring rule-based
  - emit failure reasons that are actionable during tuning
  Progress:
  - initial role-driven runner landed with `wanderer`, `survivor`, `trader`, `rumor_verifier`, and `altruist`
  - observation roles now also include `shock_observer`, `hoarder`, `exploit_observer`, `regional_observer`, and `downstream_observer`
  - each step now records a goal label alongside the chosen command
  - rule-based scoring and actionable failure summaries now land in the monkey report
  - `downstream_observer` now distinguishes a coarse route-delay -> transit -> stock-shift -> market-pressure response chain and item overlap instead of only counting separate downstream signals
  - Remaining gap: richer downstream-economy scoring beyond the current summarized response-chain and item-overlap checks

- [ ] Step 20F: Add the first controllable external shock.
  Exit criteria:
  - choose one chain such as weather -> harvest shortfall -> scarcity
  - define trigger, duration, blast radius, and recovery path
  - include both downside and regenerative or recovery-side effects
  - expose the shock in logs and rumor generation
  - verify that the world can recover without manual reset
  Progress:
  - the first chain now exists as `dry_wind/dusty_heat -> field_stress -> harvest_shortfall -> cool_rain recovery`
  - `field_stress` and `active_events` are exposed through simulation status and web state
  - the remaining gap is broader blast radius and longer economic knock-on effects

- [x] Step 20G: Add entropy sinks to the economy loop.
  Exit criteria:
  - introduce at least two of spoilage, storage pressure, tool wear, reserve floors, or delayed production
  - verify that work and trade are still worth doing
  - confirm that the player cannot trivially farm infinite stability
  Progress:
  - first sinks are now in place as food spoilage over time and player-side tool wear on repeated field or riverside work
  - player resource work now loses some yield under storage pressure when the carried load is already near capacity
  - baker and cook output now complete one turn after work starts instead of appearing instantly
  - repeated food `ask` requests to the same NPC now hit a recent-help buffer before they turn into a zero-cash farm loop
  - `exploit_observer` now probes repeated gift-request refusal as well as reserve-constrained cash buys
  - circulation and monkey regressions now cover the closure path for the current entropy slice

- [ ] Step 20H: Add regional scaling.
  Exit criteria:
  - support multiple settlements through summarized regional nodes
  - keep local areas high-resolution only when needed
  - route travel between settlements consumes meaningful time and risk
  - confirm acceptable runtime cost in observation runs
  Progress:
  - world state now includes summarized `regions` and `regional_routes`
  - the demo world exposes Greenfall as the high-resolution home region plus two offscreen summarized neighbors
  - offscreen summarized regions now drift their stock signals over time at low cost
  - `travel-region <region>` now follows summarized regional routes and lands at region anchor locations
  - web state now surfaces current region and summarized regional route metadata
  - route-aware delay events now surface in world state, `regions`, and web regional route payloads
  - route pressure now raises inter-region ETA and weakens summarized throughput under bad weather
  - offscreen regional shortages and route delays now seed local regional rumors
  - summarized `regional_transits` now move goods between settlements without spawning full offscreen NPC loops
  - web regional route payloads now expose summarized `transit_count`
  - `regional_observer` and `downstream_observer` now cover cross-settlement route, transit, stock-shift, and market-shift observation from the player side
  - the remaining gap is deciding how much richer downstream economy impact summarized transit should have and how to score it in observation runs

## Dependency Order Of Steps

1. `20A`
2. `20B`
3. `20C`
4. `20D`
5. `20E`
6. `20F`
7. `20G`
8. `20H`

This is the original dependency order, not the live next-slice queue once later steps have partially landed.

## What Not To Do Yet

- do not commit to a heavy renderer before `20D`
- do not add many disaster systems before `20F` is stable
- do not add many villages before route cost and offscreen summarization exist
- do not let monkey tests become open-ended chat without rule-based evaluation
- do not spend time keeping the Tk prototype in feature parity with simulation changes
