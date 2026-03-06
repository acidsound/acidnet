# World Circulation Evaluation

## Purpose

The world must stay active without collapsing into one location, permanent starvation, or a frozen economy. This harness gives a repeatable headless check before model changes land.

## Entry Points

- `src/acidnet/eval/circulation.py`
- `run_circulation_eval.py`

## What It Measures

- average active locations across the run
- minimum active locations in any turn
- peak single-location occupancy
- peak hunger seen across all NPCs
- final starvation count
- zero-money NPC count
- action mix: `move`, `buy`, `eat`, `work`, `share_rumor`
- final scarcity index
- derived circulation score

## Example Command

```bash
python run_circulation_eval.py --turns 120
```

## Default Output

```text
data/eval/circulation_report.json
```

## Current Interpretation

- `average_active_locations >= 4.0` means the village is still spatially alive
- `starving_npc_count <= 1` means the food loop is recovering NPCs instead of abandoning them
- a higher circulation score is better, but the flags matter more than the raw number

## Recent Fixes Validated By This Harness

- hungry NPCs now buy food they can actually afford instead of failing on the most expensive meal
- broke service NPCs can work back into the food loop
- the player can now earn gold or gather food instead of only spending down

## Next Work

- include longer-run checks at `240` and `480` turns
- add failure budgets for rumor stagnation and price collapse
- compare heuristic, prompt-only 4B, and fine-tuned 4B on the same report shape
