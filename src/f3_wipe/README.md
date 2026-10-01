# f3_wipe — 접촉 닦기(세제 · 그릇 · 컵)

설계: SDD §3.2(함수 모듈 · 노드 아님) · 인터페이스: IRD §8 · 약속: `cobot_api.F3Api`

| 함수 | 하는 일 | 돌려주는 것 |
|---|---|---|
| `soap(count, kind=None)` | 쥔 툴(수세미·컵솔)을 비틀고 위아래로 흔들어 세제를 묻힌 뒤 작업 위치(수세미 = HOME 좌표 · 컵솔 = HOME 에서 위 40 mm · 옆 140 mm 인 컵 위)로 데려간다. kind 는 안 쓰고 쥔 위치로 판정 | `Result(ok, code)` |
| `wipe_bowl()` | 호출된 자리에서 곧게 내려가 바닥을 접촉으로 찾고, 바닥 나선 → 벽면 원호(힘 제어)로 안쪽을 닦은 뒤 호출 높이로 복귀 | `WipeBowlResult(힘 로그 경로 · 소요 · 평균 힘)` |
| `wipe_cup()` | 호출된 자리에서 곧게 내려가 바닥을 접촉으로 찾고, 위아래 왕복 + 6번 조인트 회전으로 안을 문지른 뒤 호출 높이로 복귀 | `WipeCupResult(힘 로그 경로 · 소요 · 삽입 깊이)` |

부르는 곳: `f2_sense_flow/flow.py`(flow_node) — 용기마다 SOAP 단계에서 `soap(count, kind)`, WIPE 단계에서 `wipe_bowl()` 또는 `wipe_cup()`. 툴 집기는 flow(f1.tool)가, 그릇·컵 위 작업 위치로 옮기기는 soap 이 하고, wipe_* 는 그 자리에서 하강·세척·복귀만 한다(로봇 없는 시험은 `mock/mock_f3.py` 로 바꿔 끼운다).
설정: `src/cobot_common/config/params.yaml` 의 `f3` 절(`soap` · `wipe_bowl` · `wipe_cup`) — 시간 상한 · 힘 · 치수 · 속도가 전부 여기에 있다.

## 힘 제어 원칙
- 바닥은 접촉으로 찾는다(`contact_down` · `find_limit_n`) — 그릇·컵 높이가 조금 달라도 된다. 벽은 치수로 간다(안지름 − 툴 지름 + 밀어 넣는 양 `wall_press_mm`) — 힘으로 벽을 찾지 않는다.
- 누르는 힘 상한 `limit_n` · 옆 힘 상한 `lateral_max_n` 을 넘으면 남은 나선·주기 운동을 즉시 정지(`stop_now`) → 힘·순응 끄기 → 호출 높이로 곧게(E60) → `FORCE_LIMIT`. 전체 시간 `duration_s` 를 넘어도 같은 순서로 → `TIMEOUT`. 재시도 여부는 flow 가 정한다(툴을 쥐고 있을 때만 · E61).
- 닦는 중 쥔 폭이 기준(`f2.slip_tol_mm`)보다 벗어나면 즉시 정지 → `TOOL_LOST`(그 자리에 둔다 · 사람이 툴을 다시 넣고 재개).
- 위치를 모르는 상태(강제정지 · 이동 미완)면 힘만 끄고 움직이지 않는다 — 티치펜던트로 확인한 뒤 사람이 복구.

## 시험
```bash
# 최상위 README 설치 및 실행 Step 3 의 '로봇용 터미널 준비' 줄을 먼저 친 터미널에서
python3 src/f3_wipe/test/rig_f3.py bowl -n 3            # 실기 시험대 — soap | bowl | cup 을 같은 함수로 연속 3회 이상
python3 -m pytest -q src/f3_wipe                          # 자동 시험(로봇 없이)
```
