# Teacher Output 에서 SFT Dataset 으로

## 현재 상태

구현 완료:

- teacher prompt-pack JSONL 생성
- teacher output JSONL 을 SFT-ready JSONL 로 병합하는 경로
- merged SFT dataset 에 대한 optional Parquet export

진입점:

- `run_teacher_prompt_export.py`
- `run_teacher_sft_merge.py`
- `src/acidnet/training/sft_dataset.py`

## 기대 흐름

1. teacher request prompt 를 JSONL 로 export 한다.
2. 외부에서 teacher model 을 돌리고 `custom_id` 기준의 JSONL output 을 수집한다.
3. prompt row 와 teacher output 을 병합해 SFT example 을 만든다.
4. merged SFT dataset 을 첫 4B baseline run 에 넣는다.

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

## 다음 작업

- 실제 teacher output 파일 생성
- 첫 SFT dataset split 정의
- merged dataset 을 4B baseline training runner 와 연결
