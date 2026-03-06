# Current Execution Roadmap

## Purpose

Turn the current design convergence into an implementation sequence that can be executed without drifting back into ad hoc UI work.

This roadmap assumes `docs/roadmap/00-execution-checklist.md` remains the top-level priority document.

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

### Phase 2: Travel and Recovery

- convert `go <location>` into multi-turn travel
- add fatigue growth from time, work, and travel
- add `rest` and `sleep`
- make shelter quality affect sleep quality
- expose route progress in terminal and web

### Phase 3: Exchange Unification

- replace vendor-only trade assumptions with one exchange path
- support gift, barter, debt, and cash without fragmenting the rules
- use reserve floors and urgency checks to keep altruism stable

### Phase 4: Goal Monkeys

- replace random monkeying with role-driven proxy-PC runs
- add explicit goals, allowed commands, and rule-based scoring
- make monkeys a standard observation harness for travel, exchange, and shock behavior
- role-driven runner, scoring, and failure reporting are now in place
- `shock_observer` now tracks field stress and active shock events from the player side
- next work is richer exploit-oriented evaluation and multi-settlement observation roles

### Phase 5: External Shocks and Recovery Loops

- add one controllable state-dependent shock chain
- make shocks visible in rumors, logs, and world state
- make every destructive chain include a plausible recovery path
- the first weather -> field stress -> harvest shortfall -> rain recovery chain is now in place

### Phase 5.5: Entropy Sinks

- add internal sinks so inventories and production do not stay perfectly stable forever
- keep sinks legible and recoverable instead of punitive noise
- food spoilage and repeated tool wear are now in place; next work is storage pressure, delayed production, and monkey validation of exploit resistance

### Phase 6: Multi-Settlement Scaling

- add summarized regional nodes
- keep local simulation high-resolution only near the player or tracked actors
- make travel cost and information flow matter across settlements

## Immediate Next Work

The current immediate queue is:

1. backend parity audit: heuristic vs openai-compatible vs local-peft
2. complete `20G` with one more economy sink or buffer rule
3. extend goal monkeys for shock and exploit observation
4. continue toward `20H` summarized regional scaling

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
