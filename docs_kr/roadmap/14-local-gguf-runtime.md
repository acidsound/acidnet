# Local GGUF Runtime

## 목적

로컬 GGUF 파일에서 바로 OpenAI-compatible endpoint 를 띄우고, ACIDNET 이 그 endpoint 와 대화할 수 있는 단순한 경로가 필요하다.

## 진입점

- `run_llama_server.ps1`
- `run_local_qwen_dev_loop.ps1`
- `run_dev_world.ps1`

## 기대하는 실행 형태

1. 로컬 GGUF 서버를 띄운다.
2. ACIDNET 을 `/v1/chat/completions` 에 연결한다.
3. model gate 를 실행한다.
4. GUI 를 띄워 실제 월드를 관찰한다.

## 실행 예시

4B GGUF 용 로컬 서버 시작:

```powershell
powershell -ExecutionPolicy Bypass -File run_llama_server.ps1 `
  -ModelPath .\models\Qwen3.5-4B-Q4_K_M.gguf `
  -Port 8000 `
  -ContextSize 4096 `
  -GpuLayers 99 `
  -Detached
```

같은 endpoint 에 대해 gate 실행 후 GUI 시작:

```powershell
powershell -ExecutionPolicy Bypass -File run_dev_world.ps1 `
  -DialogueBackend openai_compat `
  -DialogueModel qwen3.5-4b `
  -DialogueEndpoint http://127.0.0.1:8000/v1/chat/completions `
  -RunModelGate `
  -Detached
```

`server + gate + GUI` one-command startup:

```powershell
powershell -ExecutionPolicy Bypass -File run_local_qwen_dev_loop.ps1 `
  -ModelPath .\models\Qwen3.5-4B-Q4_K_M.gguf `
  -Port 8000 `
  -ModelGateTurns 120
```

## 메모

- `run_llama_server.ps1` 는 `-ServerPath` 를 주지 않으면 `llama-server` 가 `PATH` 에 있다고 가정한다
- ACIDNET 이 기대하는 endpoint 는 `http://127.0.0.1:<port>/v1/chat/completions` 이다
- 이 경로는 fine-tuning 전에 runtime validation 을 하기 위한 것이다

## 다음 작업

- 최종 fine-tuned GGUF 용 ready-made preset 추가
- model gate report 에 latency 와 token throughput 추가
- local server 와 GUI 를 함께 정리하는 cleanup helper 추가
