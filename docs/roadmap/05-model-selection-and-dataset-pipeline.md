# Model Selection And Dataset Pipeline

## Current Status

Implemented:

- model experiment registry for 4B vs 9B
- GPT-5.3 teacher prompt templates
- synthetic scenario generator
- JSONL export
- Parquet export with optional `pyarrow`
- teacher-output to SFT-dataset merge path

Code entrypoints:

- `run_teacher_prompt_export.py`
- `run_teacher_sft_merge.py`
- `src/acidnet/training/experiment_registry.py`
- `src/acidnet/training/dataset_builder.py`
- `src/acidnet/training/teacher_prompts.py`
- `src/acidnet/training/sft_dataset.py`

## Experiment Order

- baseline: `Qwen3.5-4B`
- challenger: `Qwen3.5-9B`
- decision rule: 9B only wins if it clearly beats 4B on persona fidelity and world consistency relative to cost

## Dataset Shape

Each rollout produces:

- planner supervision rows
- dialogue supervision rows
- player interaction context inside each dialogue sample
- scenario metadata for filtering and evaluation

Current synthetic dataset fields include:

- world tick, day, weather, scarcity, market prices
- location context
- player inventory, money, hunger, rumor knowledge
- NPC inventory, hunger, beliefs, relationships, memories, vendor flag
- nearby NPC summary
- interaction context with player prompt and expected focus

## Export Commands

Install Parquet support if needed:

```bash
python -m pip install -e .[training]
```

Create a small validation pack:

```bash
python run_teacher_prompt_export.py --mode synthetic --scenarios 32 --turns 4 --format both
```

Create roughly 50k rows with the current 9-NPC village:

```bash
python run_teacher_prompt_export.py --mode synthetic --scenarios 704 --turns 4 --format both
```

Create roughly 147k rows with the current 9-NPC village:

```bash
python run_teacher_prompt_export.py --mode synthetic --scenarios 2048 --turns 4 --format both
```

Row count formula with the current demo:

```text
rows = scenarios * turns * npc_count * 2
```

## Notes On Parquet

- JSONL is the easiest teacher-request artifact.
- Parquet is the better training preprocessing artifact for slicing, filtering, and batch analytics.
- Parquet export currently depends on `pyarrow`.

## Next Work

- collect actual GPT-5.3 teacher responses for the exported prompt packs
- curate an evaluation split before long fine-tuning runs
- define the first 4B baseline run configuration
