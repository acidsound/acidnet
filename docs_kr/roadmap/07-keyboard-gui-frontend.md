# 키보드 GUI 프론트엔드

## 현재 상태

구현 완료:

- Tk 기반 map view
- 키보드 이동
- 직접 연결된 map node 클릭 이동
- NPC selection list
- talk, rumor, buy, eat, wait 액션
- event log panel
- raw command 입력창
- 터미널 런타임과 공유되는 SQLite persistence

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

이 dev launcher 는 이제 기본적으로 GUI monkey mode 를 켜서, 수동 입력이 없어도 월드가 계속 움직이게 한다.

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
  -Detached
```

회귀 관찰용 headless monkey run:

```bash
python run_monkey_world.py --steps 240 --dialogue-backend heuristic
```

## 조작

- 방향키 또는 `WASD`: 이동
- 인접한 map node 클릭: 해당 location 으로 바로 이동
- `T`: 선택된 NPC 와 대화
- `R`: 선택된 NPC 에게 rumor 질문
- `B`: 선택된 NPC 에게 bread 구매
- `E`: 인벤토리에서 가장 좋은 음식 먹기
- `Space`: 한 턴 대기
- `L`: 현재 장면 다시 보기
- 명령창에서 `Enter`: raw command 실행

## UI 구조

- 왼쪽: location, 연결선, player marker 가 있는 world map
- 오른쪽: status, location text, NPC list, rumors, event log
- 오른쪽 아래: raw command 입력창

## 다음 작업

- 미래의 local persona/dialogue model 을 talk, rumor 응답에 연결
- 현재 node map 으로 부족해지면 tile renderer 추가
- SQLite snapshot log 위에 save/load slot 처리 추가
