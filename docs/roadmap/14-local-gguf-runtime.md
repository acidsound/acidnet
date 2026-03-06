# Local GGUF Runtime

## Purpose

The project needs a simple path from a local GGUF file to a live OpenAI-compatible endpoint that ACIDNET can talk to.

## Entry Points

- `run_llama_server.ps1`
- `run_local_qwen_dev_loop.ps1`
- `run_dev_world.ps1`

## Expected Runtime Shape

1. Start a local GGUF server.
2. Point ACIDNET at `/v1/chat/completions`.
3. Run the model gate.
4. Launch the GUI and observe the world.

## Example Commands

Start a local server for the 4B GGUF:

```powershell
powershell -ExecutionPolicy Bypass -File run_llama_server.ps1 `
  -ModelPath .\models\Qwen3.5-4B-Q4_K_M.gguf `
  -Port 8000 `
  -ContextSize 4096 `
  -GpuLayers 99 `
  -Detached
```

Run the gate and launch the GUI against the same endpoint:

```powershell
powershell -ExecutionPolicy Bypass -File run_dev_world.ps1 `
  -DialogueBackend openai_compat `
  -DialogueModel qwen3.5-4b `
  -DialogueEndpoint http://127.0.0.1:8000/v1/chat/completions `
  -RunModelGate `
  -Detached
```

One-command startup for `server + gate + GUI`:

```powershell
powershell -ExecutionPolicy Bypass -File run_local_qwen_dev_loop.ps1 `
  -ModelPath .\models\Qwen3.5-4B-Q4_K_M.gguf `
  -Port 8000 `
  -ModelGateTurns 120
```

## Notes

- `run_llama_server.ps1` assumes `llama-server` is on `PATH` unless `-ServerPath` is given
- the endpoint ACIDNET expects is `http://127.0.0.1:<port>/v1/chat/completions`
- this path is for runtime validation before any fine-tuning job starts

## Next Work

- add a ready-made preset for the final exported fine-tuned GGUF
- capture latency and token throughput in the model gate report
- add cleanup helpers for stopping the local server and GUI together
