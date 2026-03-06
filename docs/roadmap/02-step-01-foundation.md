# Step 01 Foundation

## Goal

Create the repository foundation needed before the simulation loop exists.

## Deliverables

- Python package scaffold
- core schemas for world, NPC, rumor, belief, intent, and persona
- planner protocol boundary
- minimal tests for schema validation

## Files Added In This Step

- `pyproject.toml`
- `src/acidnet/...`
- `tests/...`

## Acceptance Criteria

- core models can be imported without circular dependency issues
- intent, rumor, and persona fields are structured and validated
- planner can depend on a protocol instead of a concrete model implementation
- future engine code can consume the schemas without redesign

## Immediate Follow-Up

The next implementation step is Step 02:

- define tick duration config
- implement world clock
- implement deterministic scheduler
- introduce a simulation state container

