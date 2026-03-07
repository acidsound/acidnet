# AcidNet Handoff

## Read First
- Start with `docs/context/current-state.md`.
- Then read `docs/context/project-map.md`.
- Then read `docs/context/frontend-api-handoff.md`.
- Then read `docs/roadmap/00-execution-checklist.md`.
- Then read `docs/roadmap/20-spatial-time-exchange-model.md`, `docs/roadmap/23-web-client-api-spec.md`, and `docs/roadmap/24-execution-roadmap.md`.

## Context Layout
- `docs/context/*.md` is the fast re-entry layer for new conversations. Keep it short, current, and tied to the live code path.
- `docs/context/frontend-api-handoff.md` is the frontend-facing summary of queryable and controllable HTTP contract only. Keep it aligned with the live web API.
- `docs/roadmap/*.md` is the durable design and execution record. Keep `docs_kr/roadmap/*.md` mirrored when those roadmap docs change.
- Prefer updating these existing context docs over adding generic `handoff.md` files or extra subtree `AGENTS.md` files.

## Non-Negotiables
- Keep the project `simulation-first`. Frontends render simulation state and send intents; they do not invent world logic.
- The web client is the primary frontend. Treat Tk as legacy/dead-path unless a task explicitly says otherwise.
- Do not leave dead prompt paths or unused feature branches in place after refactors. If a contract changes, audit its call sites.

## Current World Direction
- Travel is not teleportation. Movement should consume time and actor resources such as fatigue/risk.
- `fatigue` must stay coupled to `rest/sleep/shelter`; otherwise it is just a duplicate hunger meter.
- Exchange should support asymmetric, non-monetary sharing by default. Money is optional, not foundational.
- External shocks should be state-dependent and include recovery loops, not only one-way destruction.

## Dialogue Contract
- `system_prompt` is a real runtime contract for all dialogue backends, including heuristic mode.
- Global output rules belong in `system_prompt`; NPC-specific behavior belongs in structured context/persona.

## Change Discipline
- When changing simulation or API contracts, update docs and tests in the same slice.
- When changing player-visible query or control API behavior, update `docs/context/frontend-api-handoff.md` in the same slice.
- Always check: backend parity, API compatibility, dead paths, and frontend/simulation contract drift.
