# 키보드 GUI 프론트엔드

## 현재 상태

구현 완료:

- Tk 기반 map view
- 키보드 이동
- 직접 연결된 map node 클릭 이동
- player 가 gold 를 벌거나 food 를 모을 수 있는 work 액션
- NPC selection list
- talk, direct-speech, rumor, buy, eat, wait 액션
- 관찰용 monkey mode 를 GUI 안에서 켜고 끌 수 있는 toggle
- event log panel
- 선택한 NPC 전용 direct-speech 입력창
- raw command 입력창
- 터미널 런타임과 공유되는 SQLite persistence
- 전역 dialogue system prompt 를 보고 수정할 수 있는 `Settings` modal
- 읽기 전용 `prompt_presets` 테이블과 수정 가능한 `runtime_settings` 테이블로 분리된 DB 기반 prompt 저장

진입점:

- `run_acidnet_gui.py`
- `run_dev_world.ps1`
- `run_monkey_world.py`
- `run_tail_event_log.ps1`

## 실행 방법

```bash
python run_acidnet_gui.py
```

또는 editable install 이후:

```bash
python -m pip install -e .
acidnet-gui
```

관찰 중심 개발용 launcher:

```powershell
powershell -ExecutionPolicy Bypass -File run_dev_world.ps1 -Detached
```

이 dev launcher 는 기본적으로 GUI monkey mode 를 켜서, 수동 입력이 없어도 월드가 계속 움직이게 한다.

별도 창에서 plain-text event log tail:

```powershell
powershell -ExecutionPolicy Bypass -File run_tail_event_log.ps1 -Path data/logs/dev-world.log
```

GUI 와 tail 을 같이 실행:

```powershell
powershell -ExecutionPolicy Bypass -File run_dev_world.ps1 -Detached -TailLog
```

prompt-only local model 관찰:

```powershell
powershell -ExecutionPolicy Bypass -File run_dev_world.ps1 `
  -DialogueBackend openai_compat `
  -DialogueModel qwen3.5-4b `
  -DialogueEndpoint http://127.0.0.1:8000/v1/chat/completions `
  -RunPromptOnlyEval `
  -RunModelGate `
  -Detached
```

HTTP bridge 없이 direct local adapter 관찰:

```powershell
powershell -ExecutionPolicy Bypass -File run_dev_world.ps1 `
  -DialogueBackend local_peft `
  -DialogueModel Qwen/Qwen3.5-4B `
  -DialogueAdapterPath data/training/qwen3_5_4b_runtime_dialogue_full_adapter `
  -RunModelGate `
  -Detached
```

회귀 관찰용 headless monkey run:

```bash
python run_monkey_world.py --steps 240 --dialogue-backend heuristic
```

## 조작

- 방향키 또는 `WASD`: 이동
- 인접한 map node 클릭: 해당 location 으로 바로 이동
- `T`: 선택한 NPC 와 대화
- `Y`: 선택한 NPC 용 direct-speech 입력창으로 포커스 이동
- `R`: 선택한 NPC 에게 rumor 질문
- `X`: 현재 location 에서 local work 수행
- `B`: 선택한 NPC 에게 bread 구매
- `E`: 인벤토리에서 가장 좋은 음식을 먹기
- `M`: monkey mode 켜기/끄기
- `Space`: 한 턴 대기
- `L`: 현재 화면 다시 보기
- `Dialogue` 영역의 `Settings` 버튼: system prompt modal 열기
- direct-speech 입력창에서 `Enter`: `say <npc> <message>` 전송
- 명령창에서 `Enter`: raw command 실행
- `Run (Enter)` 버튼: raw command 입력 실행

## UI 구조

- 왼쪽: location, 연결선, player marker 가 있는 world map
- 오른쪽: status, dialogue 상태, location text, NPC list, 액션 버튼, direct-speech 입력, raw command 입력
- map 아래: rumors, event log
- dialogue status 영역에는 모델 준비 상태와 전역 system prompt 용 `Settings` 버튼이 같이 표시됨

## 다음 작업

- multi-turn conversation 이 event log 를 넘어설 때 dialogue transcript UX 확장
- SQLite snapshot log 위에 save/load slot 처리 추가
- 현재 node map 으로 부족해지면 tile renderer 추가
