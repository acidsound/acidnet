# 플레이 가능한 월드 MVP

## 현재 구현된 것

이 저장소에는 플레이어가 실제로 village world 안에서 NPC와 상호작용할 수 있는 터미널 시뮬레이션이 들어 있다.

현재 가능한 상호작용:

- village location 사이 이동
- 현재 장면 확인
- NPC와 대화
- NPC에게 rumor 질문
- vendor NPC와 아이템 매매
- world가 진행되도록 대기

## 런타임 기능

- deterministic turn loop
- NPC hunger progression
- 단순 production job
- 근처 NPC 간 rumor propagation
- relationship를 반영한 rumor sharing
- heuristic planner 기반 NPC intent
- aggregate stock 기반 market price refresh

## 실행 방법

```bash
python run_acidnet.py
```

또는 editable install 이후:

```bash
python -m pip install -e .
acidnet
```

## 유용한 명령

- `look`
- `go tavern`
- `talk mara`
- `ask neri rumor`
- `trade mara buy bread 1`
- `status`
- `rumors`
- `wait 3`

## 이 MVP의 한계

- dialogue는 persona template 기반이며 아직 local fine-tuned model 생성은 아니다
- NPC planning은 heuristic이며 아직 local-model inference가 아니다
- memory는 외부 저장되지만 아직 장기 summary reflection까지는 가지 않는다
- economy는 realism보다 playability를 우선한 단순 버전이다
