# 키보드 GUI 프런트엔드

## 현재 상태

상태 메모:

- 이 문서는 이제 역사적 참고용이다
- Tk 프런트엔드는 active runtime surface 에서 제거됐다
- 새 시뮬레이션 작업은 terminal/raw-command 흐름과 공유 가능한 web probe 를 먼저 대상으로 삼는다

구현됨:

- Tk 기반 맵 뷰
- 키보드 이동
- 인접한 맵 노드 클릭 이동
- 현재 위치 기반 work 액션
- NPC 선택 리스트
- 선택된 NPC를 보여주는 target 패널
- talk, inspect, direct-speech, rumor, dynamic trade, eat, next 액션
- GUI 내부 monkey mode 토글
- event log panel
- 선택된 NPC 전용 direct-speech 입력창
- `focus`, `inspect`, optional-NPC `trade` 를 포함한 target-aware raw command
- 터미널 런타임과 공유되는 SQLite persistence
- 전역 dialogue system prompt 를 조회/수정하는 `Settings` modal
- read-only `prompt_presets` 와 editable `runtime_settings` 로 나뉜 DB-backed prompt storage

진입점:

- `run_monkey_world.py`
- `run_tail_event_log.ps1`

## 실행 방법

The old `run_acidnet_gui.py`, `run_dev_world.ps1`, and `acidnet-gui` launcher paths have been removed from the repo.
Keep this document as historical UI reference only.

또는 editable install 이후:

기존 `acidnet-gui` 엔트리포인트는 제거됐다.

관찰 중심 개발용 launcher:

이제 dev launcher 는 기본적으로 GUI monkey mode 를 켠 채 실행하므로, 수동 입력이 없어도 월드가 계속 흐른다.

별도 창에서 plain-text event log tail:

```powershell
powershell -ExecutionPolicy Bypass -File run_tail_event_log.ps1 -Path data/logs/dev-world.log
```

GUI 와 tail 을 함께 실행:

prompt-only local model 관찰:

HTTP bridge 없이 direct local adapter 관찰:

headless monkey regression run:

```bash
python run_monkey_world.py --steps 240 --dialogue-backend heuristic
```

## 조작

- 방향키 또는 `WASD`: 이동
- 인접한 맵 노드 클릭: 해당 location 으로 바로 이동
- NPC 리스트 클릭: 현재 interaction target 설정
- `T`: 선택된 NPC 와 대화
- `I`: 선택된 NPC inspect
- `Y`: 선택된 NPC 기준 direct-speech 입력창으로 포커스 이동
- `R`: 선택된 NPC 에게 rumor 질문
- `X`: 현재 location 에서 local work 수행
- `B`: trade section 에 설정된 현재 거래 실행
- `E`: 인벤토리에서 가장 좋은 음식 먹기
- `M`: monkey mode on/off
- `Space`: 한 턴 대기
- `L`: 현재 location 정보 다시 보기
- `Dialogue` 영역의 `Settings` 버튼: system prompt modal 열기
- direct-speech 입력창에서 `Enter`: `say <npc> <message>` 전송
- command 입력창에서 `Enter`: raw command 실행
- `Run (Enter)` 버튼: raw command 실행

## UI 구조

- 왼쪽: world map, rumors, event log
- 오른쪽: status, dialogue 상태, location text, NPC list, target detail panel, action buttons, trade controls, direct-speech input, raw command input
- dialogue status 영역은 model readiness 와 shared system prompt `Settings` 버튼을 함께 보여준다
- trade section 은 `buy` 와 `sell` 을 전환하고, 현재 target 에게 유효한 item 만 노출하며, 수량/가격 요약을 같이 표시한다

## 다음 작업

- multi-turn conversation 이 event log 를 넘어설 때 dialogue transcript UX 확장
- SQLite snapshot log 위에 save/load slot 처리 추가
- 현재 node map 이 한계에 닿으면 proper tile renderer 추가
