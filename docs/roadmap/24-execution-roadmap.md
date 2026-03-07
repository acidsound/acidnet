# Current Execution Roadmap

## Purpose

Turn the current design convergence into an implementation sequence that can be executed without drifting back into ad hoc UI work.

This roadmap assumes `docs/roadmap/00-execution-checklist.md` remains the durable product-priority document.

## Priority Interpretation

- Use `docs/context/current-state.md` as the live next-slice queue when documents disagree.
- Use this file for the ordered sequence inside the active simulation and world-expansion track.
- Use `docs/roadmap/21-frontend-world-expansion-checklist.md` for step exit criteria and remaining gaps, not for live queue order.
- Structural repo-split work and the later realtime-transition refactor are tracked from `docs/context/current-state.md` as a parallel boundary-hardening track.

## Baseline

The current project baseline is:

- simulation-first
- web client as the main frontend feedback surface
- terminal/raw-command flow as the debugging control surface
- Tk treated as legacy and removable
- graph travel, fatigue, load, recovery, and unified exchange as the next core simulation work
- bounded monkey evaluation as a future world-observation tool, not random noise

## Active Roadmap

### Phase 1: Contract Lock

- write and maintain the full web client API spec
- remove ambiguity between system prompt, shared output contract, and persona context
- make all dialogue backends honor the shared output contract, including language rules
- `active_events` and route disruption state now flow through player-visible filtering instead of the raw omniscient event list
- runtime and eval parser policy now also separate promoted runtime backends from `local_peft` dev/eval-only paths
- shared dialogue cleanup now strips common hidden-reasoning wrappers plus code-fenced or JSON-wrapped reply shells across `heuristic`, `openai_compat`, and `local_peft`

### Phase 2: Travel and Recovery

- convert `go <location>` into multi-turn travel
- add fatigue growth from time, work, and travel
- add `rest` and `sleep`
- make shelter quality affect sleep quality
- expose route progress in terminal and web
- baseline travel, ETA, fatigue, and recovery behavior are now in place
- sleep now bottoms out at a shelter-sensitive fatigue floor, so poor cover only gives shallow recovery while shrine or tavern shelter supports deeper recovery
- travel now explicitly blocks the old location-bound command surface until arrival, so dead instant-move assumptions stay locked out in regression
- `20B` is now closed enough to leave the immediate queue

### Phase 3: Exchange Unification

- replace vendor-only trade assumptions with one exchange path
- support gift, barter, debt, and cash without fragmenting the rules
- use reserve floors and urgency checks to keep altruism stable
- cash buys, asks, and gifts now share most of the current rule path; remaining work is barter, debt, and clearer gift-default semantics

### Phase 4: Goal Monkeys

- replace random monkeying with role-driven proxy-PC runs
- add explicit goals, allowed commands, and rule-based scoring
- make monkeys a standard observation harness for travel, exchange, and shock behavior
- role-driven runner, scoring, and failure reporting are now in place
- `shock_observer` now tracks field stress and active shock events from the player side
- `hoarder` now probes storage-pressure behavior from the player side
- `exploit_observer` now probes reserve-constrained vendor exposure and buy-floor refusals from the player side
- `regional_observer` now fast-forwards long route completion during deterministic runs and verifies actual cross-settlement observation instead of stalling mid-route
- `downstream_observer` now records summarized regional stock shifts together with downstream market-price reactions from the player side
- `downstream_observer` scoring now also distinguishes a coarse route-delay -> transit -> regional-stock -> market-pressure response chain and item overlap instead of only counting separate downstream signals
- next work is richer downstream-economy scoring beyond the current summarized response-chain and item-overlap checks

### Phase 5: External Shocks and Recovery Loops

- add one controllable state-dependent shock chain
- make shocks visible in rumors, logs, and world state
- make every destructive chain include a plausible recovery path
- the first weather -> field stress -> harvest shortfall -> rain recovery chain is now in place

### Phase 5.5: Entropy Sinks

- add internal sinks so inventories and production do not stay perfectly stable forever
- keep sinks legible and recoverable instead of punitive noise
- food spoilage, player-side tool wear, storage pressure, and one-turn bakery or tavern production delays are now in place
- repeated food `ask` requests to the same NPC now hit a recent-help buffer before they turn into a zero-cash farm loop
- `exploit_observer` now probes repeated gift-request refusal as well as reserve-constrained cash buys
- the current entropy-sink closure path is now covered by simulation, monkey, and circulation regressions

### Phase 6: Multi-Settlement Scaling

- add summarized regional nodes
- keep local simulation high-resolution only near the player or tracked actors
- make travel cost and information flow matter across settlements
- summarized regional nodes and route metadata now exist in the world model and web state
- low-cost offscreen regional stock drift now runs each turn for summarized neighboring regions
- `travel-region <region>` now uses summarized route travel and region anchors
- route-aware delay events now surface in world state, regional command output, and web route metadata
- route pressure now slows inter-region travel and dampens summarized route throughput
- regional shortage or delay rumors now propagate into the local rumor layer from offscreen summaries
- summarized regional transit pulses now move goods across routes without instantiating full offscreen NPCs
- web route payloads now surface player-visible route transit counts
- `regional_observer` and `downstream_observer` now cover route, transit, stock-shift, and market-shift observation from the player side
- next work is deciding whether summarized transit should produce richer downstream economy effects and how to score those effects in observation runs

## Immediate Next Work

This section is the immediate queue for the active simulation and world-expansion track only.
Use `docs/context/current-state.md` when choosing between this track and the parallel structural boundary track.

The current simulation-track queue is:

1. continue `20C` exchange unification until barter, debt, and clearer gift-default behavior are closed
2. tighten the remaining `20D` frontend state contract gaps before reopening later-phase tuning as the main slice
3. after the earlier checklist closures are tighter, resume deeper downstream-economy scoring and `20H` summarized regional scaling

The backend parity audit is now closed enough to leave the immediate queue.
Keep parity locked through regression coverage when prompt shaping, output cleanup, runtime parser policy, or fallback behavior changes.
`20G` is now also closed enough to leave the immediate queue.
`20B` is now also closed enough to leave the immediate queue.

Open but not first in this thin-slice queue:

- extend the later `20E` downstream-economy monkey scoring beyond the current response-chain and item-overlap checks
- continue the later `20H` summarized regional scaling work

## Removal Work

The following paths should not keep accumulating hidden maintenance cost:

- Tk-specific parity work
- backend-specific prompt behavior that silently diverges from the contract
- frontend-only action logic that should come from simulation state

## Review Discipline

For every logic change, explicitly check:

- API contract impact
- backend parity impact
- test coverage impact
- dead-path or legacy-client impact
- documentation impact

## Done Definition For A Roadmap Slice

A slice is not complete until:

- code is implemented
- tests pass
- docs are updated
- the browser path is verified if the change affects player-visible state
- hidden legacy drift was checked, not ignored
