@echo off
setlocal

cd /d G:\appWrk\acidsound\acidnet

if not exist data\logs mkdir data\logs

set "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True,max_split_size_mb:128"
set "LOG_PATH=data\logs\qwen3_5_4b_runtime_dialogue_full_train_low_vram.log"

echo [%date% %time%] Starting low-VRAM runtime-dialogue training... > "%LOG_PATH%"
python run_qwen4b_baseline_train.py ^
  --train-dataset data/sft/train_bootstrap_teacher_sft_dataset.jsonl ^
  --eval-dataset data/sft/eval_bootstrap_teacher_sft_dataset.jsonl ^
  --output-dir data/training/qwen3_5_4b_runtime_dialogue_full_adapter_low_vram ^
  --script-output data/training/train_qwen3_5_4b_runtime_dialogue_full_low_vram.py ^
  --spec-output data/training/qwen3_5_4b_runtime_dialogue_full_low_vram_run_spec.json ^
  --trainer-backend hf_peft ^
  --epochs 1 ^
  --eval-steps 1000 ^
  --save-steps 1000 ^
  --memory-profile low_vram >> "%LOG_PATH%" 2>&1

echo [%date% %time%] Training command exited with code %errorlevel% >> "%LOG_PATH%"
endlocal
