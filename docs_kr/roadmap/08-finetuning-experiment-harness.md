# 파인튜닝 실험 하네스

## 현재 상태

구현 완료:

- baseline/challenger 실험 manifest 생성기
- 고정된 dataset path 계약
- 고정된 train row / eval row target
- 재현 가능한 experiment JSON export 스크립트

진입점:

- `src/acidnet/training/finetune_manifest.py`
- `run_finetune_manifest_export.py`

## Manifest 의 목적

manifest 는 다음을 고정하기 위해 존재한다:

- 어떤 모델이 baseline 인가
- 어떤 모델이 challenger 인가
- 각 run 이 어떤 dataset artifact 를 먹는가
- 긴 학습을 시작하기 전에 어떤 LoRA 와 batch 설정을 기준으로 삼는가

## 현재 기본 계획

Baseline:

- `Qwen3.5-4B`
- `bf16 LoRA`
- `max_seq_length = 4096`
- `batch_size = 2`
- `grad_accum = 8`

Challenger:

- `Qwen3.5-9B`
- `bf16 LoRA`
- `max_seq_length = 3072`
- `batch_size = 1`
- `grad_accum = 16`

## 실행 명령

```bash
python run_finetune_manifest_export.py --vram 24 --train-rows 50000 --eval-rows 4000
```

## 출력 경로

```text
data/training/finetune_manifest.json
```

## 아직 하지 않는 것

- Unsloth training 을 직접 실행하지는 않는다
- distributed job 을 띄우지 않는다
- checkpoint 를 자동 평가하지 않는다

이 부분이 다음 구현 단계다.
