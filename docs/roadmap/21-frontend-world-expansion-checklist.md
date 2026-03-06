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

## Checklist

- [x] Step 20A: Add actor cost schema for travel.
  Exit criteria:
  - player and NPC state include `fatigue`, `carried_weight`, `carry_capacity`, and `travel_state`
  - tests cover bounds and serialization
  - snapshots and storage handle the new fields cleanly

- [ ] Step 20B: Convert movement into multi-turn travel.
  Exit criteria:
  - `go <location>` becomes a travel action with ETA
  - travel consumes time and cost before arrival
  - travel can be blocked or slowed by route modifiers
  - `rest` and `sleep` exist as the recovery side of movement cost
  - fatigue matters because sleep quality and shelter quality matter
  - the raw-command client and the web frontend both show travel progress

- [ ] Step 20C: Unify exchange modes.
  Exit criteria:
  - buy, sell, gift, barter, and debt use one rule path
  - reserve-floor logic prevents self-destructive generosity
  - gifting is the default low-stakes exchange mode when reserve floors are safe
  - the survival loop still works without a money-first economy
  - relationship and urgency influence acceptance
  - tests cover free transfer, refusal, and asymmetric exchange

- [ ] Step 20D: Define the frontend state contract.
  Exit criteria:
  - add derived scene DTOs separate from raw persistence snapshots
  - expose player-visible state, not omniscient world state, by default
  - include route preview, target details, and valid action catalogs
  - document the contract before a larger frontend rewrite

Current note:

- a provisional web probe now exists in `src/acidnet/frontend/web_app.py` and `src/acidnet/frontend/web/index.html`
- it already uses derived player-view state plus command POSTs
- formal DTO naming, route preview, and fuller action catalogs still remain before `20D` is complete

- [ ] Step 20E: Replace random monkeying with goal monkeys.
  Exit criteria:
  - add bounded monkey roles such as survivor, trader, rumor verifier, and altruist
  - use tight action prompts with explicit goals and allowed commands
  - treat monkey runs as proxy-PC observation runs, not as random noise
  - keep scoring rule-based
  - emit failure reasons that are actionable during tuning
  Progress:
  - initial role-driven runner landed with `wanderer`, `survivor`, `trader`, `rumor_verifier`, and `altruist`
  - each step now records a goal label alongside the chosen command
  - rule-based scoring and actionable failure summaries still remain

- [ ] Step 20F: Add the first controllable external shock.
  Exit criteria:
  - choose one chain such as weather -> harvest shortfall -> scarcity
  - define trigger, duration, blast radius, and recovery path
  - include both downside and regenerative or recovery-side effects
  - expose the shock in logs and rumor generation
  - verify that the world can recover without manual reset

- [ ] Step 20G: Add entropy sinks to the economy loop.
  Exit criteria:
  - introduce at least two of spoilage, storage pressure, tool wear, reserve floors, or delayed production
  - verify that work and trade are still worth doing
  - confirm that the player cannot trivially farm infinite stability

- [ ] Step 20H: Add regional scaling.
  Exit criteria:
  - support multiple settlements through summarized regional nodes
  - keep local areas high-resolution only when needed
  - route travel between settlements consumes meaningful time and risk
  - confirm acceptable runtime cost in observation runs

## Recommended Order After This

1. `20A`
2. `20B`
3. `20C`
4. `20D`
5. `20E`
6. `20F`
7. `20G`
8. `20H`

## What Not To Do Yet

- do not commit to a heavy renderer before `20D`
- do not add many disaster systems before `20F` is stable
- do not add many villages before route cost and offscreen summarization exist
- do not let monkey tests become open-ended chat without rule-based evaluation
- do not spend time keeping the Tk prototype in feature parity with simulation changes
