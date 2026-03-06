# Teacher Output 에서 SFT Dataset 으로

## 현재 상태

구현 완료:

- teacher prompt-pack JSONL 생성
- teacher completion run 용 OpenAI batch request export
- teacher-output JSONL 로의 OpenAI batch output 정규화
- teacher output JSONL 을 SFT-ready JSONL 로 병합하는 경로
- merged SFT JSONL 을 deterministic train/eval artifact 로 split 하는 경로
- merged SFT dataset 에 대한 optional Parquet export

진입점:

- `run_teacher_prompt_export.py`
- `run_openai_teacher_batch_prepare.py`
- `run_openai_teacher_batch_normalize.py`
- `run_teacher_sft_merge.py`
- `run_teacher_sft_split.py`
- `src/acidnet/training/sft_dataset.py`

## 기대 흐름

1. teacher request prompt 를 JSONL 로 export 한다.
2. prompt pack 을 OpenAI batch request 로 변환한다.
3. 외부에서 teacher model 을 돌리고 `custom_id` 기준의 batch output JSONL 을 수집한다.
4. batch output 을 `teacher_outputs.jsonl` 로 정규화한다.
5. prompt row 와 teacher output 을 병합해 SFT example 을 만든다.
6. merged SFT dataset 을 deterministic train/eval artifact 로 split 한다.
7. split 된 SFT dataset 을 첫 4B baseline run 에 넣는다.

## 지원하는 teacher output 형태

현재 merger 는 다음 key 를 지원한다:

- `assistant_json`
- `output_json`
- `response_text`
- `output_text`
- `assistant_text`
- `response`

text payload 는 valid JSON 이어야 한다.

## 실행 예시

Prompt pack export:

```bash
python run_teacher_prompt_export.py --mode synthetic --scenarios 704 --turns 4 --format jsonl
```

OpenAI batch request 준비:

```bash
python run_openai_teacher_batch_prepare.py --model gpt-5.3
```

OpenAI batch output 정규화:

```bash
python run_openai_teacher_batch_normalize.py ^
  --batch-output data/prompt_packs/openai_batch_output.jsonl ^
  --output data/prompt_packs/teacher_outputs.jsonl
```

teacher output 을 SFT JSONL 로 병합:

```bash
python run_teacher_sft_merge.py ^
  --prompt-pack data/prompt_packs/teacher_requests.jsonl ^
  --teacher-output data/prompt_packs/teacher_outputs.jsonl ^
  --format jsonl
```

JSONL 과 Parquet 둘 다 병합:

```bash
python run_teacher_sft_merge.py ^
  --prompt-pack data/prompt_packs/teacher_requests.jsonl ^
  --teacher-output data/prompt_packs/teacher_outputs.jsonl ^
  --format both
```

merged SFT 를 train/eval JSONL 과 Parquet 로 split:

```bash
python run_teacher_sft_split.py ^
  --input data/sft/teacher_sft_dataset.jsonl ^
  --train-rows 50000 ^
  --eval-rows 4000 ^
  --format both
```

## 다음 작업

- 첫 실제 teacher batch output 파일 생성
- 첫 train/eval split 을 4B baseline run 으로 검증
- split dataset 을 첫 실제 4B training launch 와 연결
