# Teacher Output To SFT Dataset

## Current Status

Implemented:

- teacher prompt-pack JSONL generation
- merge path from teacher output JSONL into SFT-ready JSONL
- optional Parquet export for the merged SFT dataset

Entry points:

- `run_teacher_prompt_export.py`
- `run_teacher_sft_merge.py`
- `src/acidnet/training/sft_dataset.py`

## Expected Flow

1. Export teacher request prompts as JSONL.
2. Run the teacher model externally and collect JSONL outputs keyed by `custom_id`.
3. Merge prompt rows and teacher outputs into SFT examples.
4. Feed the merged SFT dataset into the first 4B baseline run.

## Supported Teacher Output Shapes

The merger currently accepts rows containing:

- `assistant_json`
- `output_json`
- `response_text`
- `output_text`
- `assistant_text`
- `response`

Text payloads must contain valid JSON.

## Example Commands

Export prompt pack:

```bash
python run_teacher_prompt_export.py --mode synthetic --scenarios 704 --turns 4 --format jsonl
```

Merge teacher outputs into SFT JSONL:

```bash
python run_teacher_sft_merge.py ^
  --prompt-pack data/prompt_packs/teacher_requests.jsonl ^
  --teacher-output data/prompt_packs/teacher_outputs.jsonl ^
  --format jsonl
```

Merge into both JSONL and Parquet:

```bash
python run_teacher_sft_merge.py ^
  --prompt-pack data/prompt_packs/teacher_requests.jsonl ^
  --teacher-output data/prompt_packs/teacher_outputs.jsonl ^
  --format both
```

## Next Work

- produce real teacher output files
- define the first SFT dataset split
- connect the merged dataset to the 4B baseline training runner
