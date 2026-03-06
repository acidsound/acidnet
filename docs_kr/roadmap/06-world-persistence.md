# 월드 영속화

## 현재 상태

구현 완료:

- JSON 직렬화 가능한 `Simulation.snapshot()`
- SQLite snapshot store
- CLI 와 GUI 세션에서 event log 저장

진입점:

- `src/acidnet/engine/simulation.py`
- `src/acidnet/storage/sqlite_store.py`
- `src/acidnet/cli.py`
- `src/acidnet/frontend/tk_app.py`

## 저장되는 것

- world snapshot payload
- player state
- NPC states
- rumors
- episodic memories
- user command 와 session 기반 event log

SQLite 테이블:

- `snapshots`
- `memories`
- `rumors`
- `event_log`

## 기본 경로

```text
data/acidnet.sqlite
```

## 왜 SQLite 부터 가는가

- 추가 인프라가 없다
- 현재 prototype 규모에서는 충분히 빠르다
- 디버깅과 데이터셋 큐레이션 시 직접 확인하기 쉽다
- Windows 에서 바로 동작한다

## Vector Search 경계

- `zvec` 는 optional 로 유지한다
- 현재 코드는 Windows 에서 SQLite-only 모드를 기본으로 둔다
- long-term memory retrieval 이 필요해질 때 Linux/macOS 배포 경로에서 `zvec` 를 검토한다

참고:

- [zvec repository](https://github.com/alibaba/zvec)

## 다음 작업

- retrieval 지향 memory index 추가
- long-term memory retrieval 에 SQLite FTS, zvec, 혹은 둘 다 필요한지 결정
- runtime transcript 와 curated training data 의 보존 정책 정의
