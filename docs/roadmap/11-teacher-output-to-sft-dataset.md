# Teacher Output To SFT Dataset

## Current Status

Implemented:

- teacher prompt-pack JSONL generation
- OpenAI batch request export for teacher completion runs
- OpenAI batch output normalization into teacher-output JSONL
- merge path from teacher output JSONL into SFT-ready JSONL
- optional Parquet export for the merged SFT dataset

Entry points:

- `run_teacher_prompt_export.py`
- `run_openai_teacher_batch_prepare.py`
- `run_openai_teacher_batch_normalize.py`
- `run_teacher_sft_merge.py`
- `src/acidnet/training/sft_dataset.py`

## Expected Flow

1. Export teacher request prompts as JSONL.
2. Convert the prompt pack into OpenAI batch requests.
3. Run the teacher model externally and collect batch output JSONL keyed by `custom_id`.
4. Normalize batch outputs into `teacher_outputs.jsonl`.
5. Merge prompt rows and teacher outputs into SFT examples.
6. Feed the merged SFT dataset into the first 4B baseline run.

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

Prepare OpenAI batch requests:

```bash
python run_openai_teacher_batch_prepare.py --model gpt-5.3
```

Normalize OpenAI batch output:

```bash
python run_openai_teacher_batch_normalize.py ^
  --batch-output data/prompt_packs/openai_batch_output.jsonl ^
  --output data/prompt_packs/teacher_outputs.jsonl
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

- produce the first real teacher batch output file
- define the first SFT dataset split
- connect the merged dataset to the 4B baseline training runner
