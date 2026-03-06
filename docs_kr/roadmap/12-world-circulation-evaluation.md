# 월드 순환성 평가

## 목적

월드는 한 장소로 붕괴하거나, 영구 starvation 상태로 빠지거나, 경제가 얼어붙지 않고 계속 돌아야 한다. 이 하네스는 모델 변경 전에 반복 가능한 headless 검사를 제공한다.

## 진입점

- `src/acidnet/eval/circulation.py`
- `run_circulation_eval.py`

## 측정 항목

- run 전체의 평균 active location 수
- 어떤 턴에서든 최소 active location 수
- 한 location 에 몰린 최대 NPC 수
- 모든 NPC 기준 peak hunger
- 최종 starvation NPC 수
- 돈이 0 이하인 NPC 수
- `move`, `buy`, `eat`, `work`, `share_rumor` 액션 비율
- 최종 scarcity index
- 파생 circulation score

## 실행 예시

```bash
python run_circulation_eval.py --turns 120
```

## 기본 출력

```text
data/eval/circulation_report.json
```

## 현재 해석 기준

- `average_active_locations >= 4.0` 이면 village 가 공간적으로 아직 살아 있다고 본다
- `starving_npc_count <= 1` 이면 food loop 가 NPC 를 버리지 않고 회복시키고 있다고 본다
- circulation score 는 높을수록 좋지만, raw number 보다 flag 를 더 중요하게 본다

## 이 하네스로 검증한 최근 수정

- hungry NPC 가 가장 비싼 음식에 실패하지 않고 실제로 살 수 있는 음식을 고른다
- 돈이 없는 service NPC 가 다시 food loop 로 복귀할 수 있다
- player 도 돈을 벌거나 food 를 모을 수 있어서 지출만 하다 끝나지 않는다

## 다음 작업

- `240`, `480` turn 장기 run 검사 추가
- rumor 정체와 price collapse 에 대한 failure budget 추가
- heuristic, prompt-only 4B, fine-tuned 4B 를 같은 report 형태로 비교
