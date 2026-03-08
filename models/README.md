# Local Model Directory

This directory is the maintained local restore point for runtime GGUF files.

Keep large model weights here, but do not commit them to git.

Current promoted runtime expectation:

- base model: `Qwen3.5-4B-Q4_K_M.gguf`

Expected absolute path on this repo:

- `G:\appWrk\acidsound\acidnet\models\Qwen3.5-4B-Q4_K_M.gguf`

Notes:

- `acidsound/acidnet_model` stores the fine-tuned LoRA adapter bundle and adapter GGUF, not this base model file.
- `run_llama_server.ps1`, `run_local_qwen_dev_loop.ps1`, `run_acidnet.py`, and `run_acidnet_web.py` expect this base model path when using the promoted GGUF runtime.
- `models/*.gguf` is intentionally gitignored so local runtime weights do not enter source control.
- Maintained reference source:
  - `https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf`
