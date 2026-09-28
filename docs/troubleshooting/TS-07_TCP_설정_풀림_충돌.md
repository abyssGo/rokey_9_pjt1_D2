# TS-07 · 툴·TCP 선택이 풀려 좌표 전체가 208 mm 아래로 — 그릇 바닥 충돌 (9/22)

| | |
|---|---|
| 날짜 | 2026-09-22 11:22 · 실기 · 민범진 세션 |
| 증상 | `rig_f2.py empty` 로 저울 자세(`WEIGH.BOWL`)에 가던 중 **그릇이 바닥에 닿음** → `MoveIncomplete: 목표까지 46.6 mm 남았다` → 정지 명령 응답 없음(2 s) |
| 코드·좌표 | 아침에 같은 자세로 **6회 성공**한 것과 바이트 단위로 같음 (좌표 z 235 · 같은 `cc.move_to` 두 줄) |
| 원인 | 컨트롤러의 **툴·TCP 선택이 빈 값**이 된 상태(11:10 rig_v03 실행 뒤~11:17 사이 · 풀린 원인은 미확인 · E26). cell.yaml 의 posx 는 전부 TCP `GripperDA_v1`(Z 208 mm) 기준 → TCP 가 없으면 컨트롤러가 손목 플랜지를 "손끝"으로 보고 같은 명령을 **208 mm 아래**로 보낸다. z 235 − 208 ≈ 27 → 그릇 바닥이 닿는 높이 |
| 복구 | 펜던트에서 알람 리셋 → 조그로 떼어냄 → TCP 다시 선택 → 브링업 재시작 |
| 피해 | 없음(저속 아니었으나 충돌 감지로 정지). 로봇 슬롯 약 20분 |

## 왜 위험한가
여러 사람이 한 로봇·한 펜던트를 쓴다. **내 코드·내 좌표가 그대로여도** 남이 컨트롤러 설정을 바꾸면 내 실기가 깨진다. 좌표가 "맞다"는 것은 언제나 **"그 TCP 기준으로"** 맞다는 뜻이다(cell.yaml 머리말 🚨).

## 재발 방지 — 코드가 막는다
`f2_sense_flow/preflight.py` — **움직이기 전에** `get_current_tool` · `get_current_tcp` 로 이름을 읽어 `params.yaml flow.preflight` 의 기대값과 비교, 다르면 `PreflightError` 로 **시작 거부**(로봇은 안 움직임).
- 연결된 곳: `flow_node`(robot=True) · `rig_f2` · `rig_int12` · `rig_weigh_probe` — cc.init 직후, 첫 이동 전
- 기대 이름의 정본: `cell.yaml` 머리말(ENV-05 · 황인재). 툴·TCP 이름을 바꾸면 `flow.preflight` 도 같이
- 사람 쪽: 세션 시작 때 `robottool`(환경설정 문서 별칭) 로 두 이름 확인 · 남이 펜던트를 만졌으면 다시 확인

## 확인 명령 (로봇 안 움직임)
```bash
ros2 service call /dsr01/dsr_controller2/tool/get_current_tool dsr_msgs2/srv/GetCurrentTool   # info='Tool Weight'
ros2 service call /dsr01/dsr_controller2/tcp/get_current_tcp   dsr_msgs2/srv/GetCurrentTcp    # info='GripperDA_v1'
```
