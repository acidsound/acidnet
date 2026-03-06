# Spatial, Time, and Exchange Model

## Purpose

Lock the world model for distance, travel time, actor cost, and asymmetric exchange before larger frontend work begins.

This document treats space as a simulation problem, not a rendering problem.

## Why This Comes First

The next frontend should not be built around instant teleports, symmetric vendor-only trade, or a scene model that hides time cost.

If travel, cost, and exchange are wrong, a richer frontend will only make the wrong rules feel more polished.

## Core Principles

- distance must be represented as time, effort, and risk
- movement is a multi-turn action, not an immediate location swap
- world truth and player-visible state must be separated
- paid trade, gifting, barter, and debt should share one exchange rule path
- need-based gifting should be normal, not exceptional
- actors should be modeled as custodians of resources, not as absolute owners of all held goods
- money may exist later as a convenience or ledger, but the world loop should not depend on money-first survival
- offscreen simulation should stay summarized unless the player or a tracked actor gets close
- entropy must come from both internal sinks and external shocks
- destructive shocks should also open recovery paths instead of pushing the world in one direction forever

## Space Model

Use a layered graph.

### Layer 1: Local Settlement Graph

This is the current village-scale location graph.

Each node should keep:

- `location_id`
- `kind`
- `capacity`
- `shelter_rating`
- `resource_tags`
- `danger_tags`

Each edge should keep:

- `from_location`
- `to_location`
- `travel_ticks`
- `effort_cost`
- `exposure_risk`
- `load_modifier`
- `weather_modifier`
- `is_blockable`

### Layer 2: Regional Route Graph

Each village or major site becomes a region node.

Regional edges should keep:

- `route_id`
- `travel_ticks`
- `cargo_risk`
- `weather_sensitivity`
- `bandit_or_wildlife_risk`
- `seasonal_capacity`

The player and nearby NPCs may run high-resolution local simulation.
Far settlements should run as summarized state with periodic imports and exports.

## Actor Requirements

The current `location_id`, `inventory`, `money`, and `hunger` model is not enough.

Add at least:

- `fatigue`
- `carried_weight`
- `carry_capacity`
- `travel_state`
- `home_region_id` once multiple villages exist

Recommended `travel_state` fields:

- `is_traveling`
- `route`
- `origin_location_id`
- `destination_location_id`
- `ticks_remaining`
- `risk_budget`

Fatigue only earns its place if it creates a different recovery problem than hunger.
That implies `rest` and `sleep` must become first-class actions, not flavor text.

## Travel Resolution

`go <location>` should become a travel intent that resolves over time.

Recommended rule shape:

1. choose a route edge
2. spend `travel_ticks`
3. apply hunger and fatigue increase per segment
4. apply load and weather modifiers
5. roll any route event windows
6. arrive, fail, or retreat

Travel should pair with recovery.
The first implementation should treat `rest` as light local recovery and `sleep` as strong recovery that depends on shelter quality and safety.

### Cost Model

Keep the first version simple and readable.

- base hunger pressure comes from time
- extra hunger pressure comes from effort and carried load
- fatigue rises faster than hunger during long movement
- bad weather should increase travel time before it increases randomness

Example first-pass formula:

```text
effective_travel_ticks =
  base_travel_ticks
  * weather_modifier
  * load_modifier

hunger_delta =
  base_time_hunger
  + effort_cost * 0.15

fatigue_delta =
  effort_cost
  + carried_weight_ratio * 4
```

The exact constants can change.
The important part is that distance always implies opportunity cost.

## Exchange Model

Do not split gifting into a separate system.
Treat it as asymmetric exchange.

Also do not assume money is the natural default.
The world should remain stable even if most exchanges happen without money.

### Unified Exchange Concept

Every transfer should use the same underlying structure:

- `from_actor`
- `to_actor`
- `items_out`
- `items_in`
- `payment_mode`
- `money_amount`
- `debt_terms`
- `reason`

`payment_mode` can begin with:

- `gift`
- `cash`
- `barter`
- `debt`

The ordering matters.
`gift` should be the social default for low-stakes need-based transfers when reserve floors are safe.

### Validation Rules

All exchange modes should pass through the same rule engine checks:

- stock availability
- reserve floor
- relationship score
- desperation or urgency
- profession norms
- debt ceiling

This keeps altruism possible without making the world collapse into free infinite redistribution.

### Why Reserve Floors Matter

An actor should be allowed to gift food while still refusing to starve themselves.

That means each actor needs a soft or hard minimum stock rule such as:

- keep `N` meals for self and household
- do not gift critical production inputs below reserve
- emergency states may override normal refusal thresholds

### Money Boundary

Money should be treated cautiously.

If introduced or expanded later, it should be:

- optional for survival-critical exchange
- bounded by explicit issuance and sink rules
- secondary to stock, labor, trust, and need

The simulation should not require a capital-first economy to feel alive.

## External Shocks

External pressure should be state-dependent, not purely random.

Good early shocks:

- weather shift -> crop yield pressure
- supply delay -> market scarcity
- heat + neglect -> fire risk
- storm + poor route conditions -> travel delay

Bad early shocks:

- many unrelated disaster systems at once
- catastrophic randomness with no recovery path

Each shock should define:

- trigger conditions
- impact radius
- duration
- affected resources
- recovery path

The important addition is this:

- a shock should usually have both a loss channel and a recovery or regeneration channel

Example:

```text
fire damages shelter
-> ash and mineral pulse improve soil
-> crop growth improves
-> insects and pollination return
-> wood supply recovers
-> shelter can be rebuilt
```

This prevents destructive randomness from becoming meaningless one-way decay.

## Frontend Contract Implications

The frontend should not consume the full persistence snapshot as its main scene contract.
The frontend must be a presentation layer over simulation truth, not a second rules engine.

Introduce derived, frontend-facing frames such as:

- `SceneFrame`
- `PlayerFrame`
- `VisibleNPCFrame`
- `RoutePreview`
- `ActionCatalog`
- `EventFeed`

The frontend should show:

- where the player is
- what is visible
- what actions are valid
- what travel costs in time, fatigue, and risk
- what exchange options are valid for the current target

The frontend should not need to recompute simulation truth on its own.

## Monkey Implications

The monkey runner should evolve from random command sampling into bounded goal-play.
It should act as a proxy player-character that moves through the world and triggers meaningful situations.

Useful monkey roles:

- survivor
- trader
- rumor verifier
- altruist
- stress tester

These monkeys should reason over:

- current scene
- current goal
- valid actions
- recent events
- injected behavior policy or role prompt

The language model may choose the next action, but scoring must remain rule-based.

## Multi-Village Scaling

When multiple settlements are added:

- local play remains high-resolution
- distant settlements run summarized state
- routes carry time, risk, and supply cost
- news and rumors can move faster than goods

This is the right place to preserve performance without flattening the world into instant travel.

## Non-Goals

- committing to a 2D or 3D renderer
- full physics simulation
- continuous free-movement coordinates
- global always-high-resolution world updates

## Baseline Decision

Before the next major frontend push, the project should assume:

- graph-based space
- multi-turn travel
- hunger plus fatigue plus load-aware movement cost
- unified exchange instead of separate gift systems
- summarized offscreen regions
- state-dependent external shocks
