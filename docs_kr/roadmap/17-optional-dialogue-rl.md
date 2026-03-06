# Optional Dialogue RL

## 목적

RL은 계속 optional이고 dialogue 전용으로만 둔다.

이제 프로젝트에는, world mutation 권한을 모델에 주지 않으면서도 괜찮은 SFT checkpoint를 preference optimization으로 더 다듬을 수 있는 최소 scaffolding이 들어가 있다.

## 구현된 진입점

- `src/acidnet/eval/persona_reward.py`
- `src/acidnet/training/preference_dataset.py`
- `src/acidnet/training/dpo_runner.py`
- `run_dialogue_preference_export.py`
- `run_dialogue_rl_train.py`

## 현재 기본 흐름

preference pair 생성:

```bash
python run_dialogue_preference_export.py ^
  --prompt-pack data/prompt_packs/bootstrap_teacher_requests.jsonl ^
  --chosen-output data/prompt_packs/bootstrap_teacher_outputs.jsonl ^
  --format both
```

optional DPO run 준비:

```bash
python run_dialogue_rl_train.py ^
  --prepare-only ^
  --train-dataset data/preferences/bootstrap_dialogue_preferences.jsonl ^
  --eval-dataset data/preferences/bootstrap_dialogue_preferences.jsonl ^
  --sft-adapter-path data/test_artifacts/qwen3_5_4b_bootstrap_smoke_adapter
```

## 현재 preference dataset 스냅샷

- rows: `50700`
- chosen source: bootstrap teacher output
- rejected source: bootstrap low-signal dialogue output

artifact:

- `data/preferences/bootstrap_dialogue_preferences.jsonl`
- `data/preferences/bootstrap_dialogue_preferences.parquet`
- `data/preferences/bootstrap_dialogue_preferences_manifest.json`
- `data/training/qwen3_5_4b_dialogue_dpo_run_spec.json`
- `data/training/train_qwen3_5_4b_dialogue_dpo.py`

## 경계

- RL은 dialogue/persona consistency에만 쓴다
- planner/world mutation은 계속 rule-based로 유지한다
- RL은 SFT checkpoint가 이미 usable한 뒤에만 검토한다
- RL이 latency나 stability를 해치면 바로 비활성 상태로 둔다
