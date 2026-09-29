# 인터페이스 요구사항 문서 (IRD)
## PreWash-Cell — 기능 함수·메시지 약속 정본

| 항목 | 내용 |
|---|---|
| 문서 ID | IRD-PREWASH-001 · **v3.2 제출판** (2026-09-29) — v3.0(9/18) + 실패 정책 §8 갱신(E42 · E52 · E54 · E55 · E60~E62 · E64 케이블 멈춤 바로 재개 · E65 격리 한 자리) · 코드 `TOOL_LOST` 추가(E37) · F1 함수 `regrip_top` 추가(E65) · `/flow/resume` 재개 한 번 |
| 구조 | **스크립트형(9/18 저녁 결정)**: `flow_node`(메인 프로그램)가 f1·f2·f3의 **파이썬 함수**를 차례로 부른다. 기능 사이에 ROS 서비스는 없다. ROS 통신은 flow ↔ HMI와 그리퍼·두산 드라이버뿐이다. 배경은 [TS-01](troubleshooting/TS-01_두산API_초기화_실행기_교착.md), 결정은 [회의록 DSN-02b](meetings/20260918_결정기록_구조_인터페이스.md) |
| 확정 상태 | ✅ 확정: PC 2대(GPU PC 로봇 제어 · 화면 PC — Discovery Server · §6) · **노드 2개(`flow_node`·`hmi_bridge`)** · F1↔F3 경계(툴 픽업 F1 / 세제 담금 F3) · 닦기 분리(`wipe_bowl`/`wipe_cup`) · `place`가 안착 놓기 · 복귀는 `move_to('HOME')` · 파지 힘 2단계 · 설정 파일 2개 |
| 상위 | [01_요구사항_BR-SR.md](01_요구사항_BR-SR.md) §5.4 |
| 정본 파일 | **함수 약속** [`src/cobot_api/cobot_api/contracts.py`](../src/cobot_api/cobot_api/contracts.py) · **메시지** `src/cobot_msgs/msg/*.msg`. 이 문서와 파일이 다르면 **파일이 정본** |
| 변경 규칙 | 함수 이름·인자·반환 필드·코드, 메시지 필드의 추가·삭제·타입 변경은 이슈 → 4명 확인 → PR. 혼자 바꾸지 않는다. |

🚨 **이 문서가 4명 동시 개발의 약속이다.** 이 약속이 있어서 남의 코드가 없어도 내 함수를 만들고 시험할 수 있다. v2.1의 서비스 12개가 **같은 이름·같은 인자·같은 반환 필드의 함수 12개**로 바뀌었을 뿐 내용은 같다(9/29 E65 로 F1 `regrip_top` 이 더해져 지금은 13개).

---

## 1. 원칙
1. 기능 패키지(f1·f2·f3)는 **함수 제공자**다. 부르는 쪽은 `flow_node` 하나뿐이다. 기능 패키지끼리는 서로의 함수를 부르지 않는다(import 금지).
2. 모든 기능 함수는 `cobot_api`의 **`Result`(또는 하위 타입)** 를 돌려준다: `ok(bool)` + `code(str)` + 기능별 필드. **실패는 예외가 아니라 `ok=False` + `code`.** 예외가 새어 나오면 flow가 `ROBOT_ERROR`로 바꾸고 안전 자세로 간다(SDD §5.1).
3. 물리 인계는 **정해진 스테이션 위치**로만 한다. F1이 놓은 자리에서 F3가 시작한다. 그래서 각자 용기를 손으로 놓아 두고 자기 함수를 단독으로 시험할 수 있다.
4. 로봇 API는 `cobot_common`(두산 API를 감싼 공용 로봇 함수 모음)만 쓴다. 기능 패키지가 `DSR_ROBOT2`를 직접 import하지 않는다.
5. 🚨 **두산 함수(=`cobot_common`의 로봇 함수)는 메인 스레드에서만 부른다.** 콜백·타이머·다른 스레드에서 부르지 않는다. 기능 함수 안에서 노드를 만들거나 `rclpy.spin*`을 부르지 않는다(SDD §3.2).
6. 모든 ID는 아래 §2 문자열을 그대로 쓴다(대문자, 코드·YAML·기록·메시지·HMI 동일). 코드에서는 `cobot_api`의 상수를 쓴다(`from cobot_api import BOWL, EMPTY_ZONE`).

## 2. 공통 ID (IR-05)
| 분류 | 값 | 설명 |
|---|---|---|
| 용기 종류 `kind` | `BOWL` `CUP` | |
| 툴 `tool` | `SPONGE`(그릇용 수세미 툴) `BRUSH`(컵용 수세미 솔) | |
| 반납 구역 `zone_id` | `RET_B` `RET_C` | 공정 입구. **구역마다 고정 슬롯 2개**(트레이에 자리 표시) — 용기는 슬롯에 겹치지 않게 하나씩 놓는다(9/19 결정: 구역 + 탐색 파지 → 고정 슬롯). ID·함수 서명은 그대로 ✅ **9/20 변경(결정기록 E9)**: 반납 구역은 **내리막 공급 구조** — 용기를 꺼내면 뒤 용기가 같은 자리로 내려온다 → 구역마다 집는 자리는 **1개**이고 같은 자리에서 차례로 집는다(슬롯 2개 안은 폐기). 🔄 **E41 로 시연은 다시 자리 2개** — 슬롯 1부터 집고 비면 슬롯 2(E9 대체) |
| 팔레트 칸 `rack_slot` | `RACK_B1` `RACK_B2` / `RACK_C1` `RACK_C2` | 공정 출구. 그릇 2칸·컵 2칸 (✅ 황인재 9/20: 컵 칸 4 → 2 — `RACK_C3`·`RACK_C4` 삭제. 코드(`cobot_api.RACK_SLOTS`·`cell.yaml`·`params.yaml`)도 2칸으로 맞췄다) |
| 스테이션 `station` | `HOME` `WEIGH` `WASTE` `SPONGE_BED_B` `SPONGE_BED_C` `TOOL_SPONGE` `TOOL_BRUSH` `SOAP` `RINSE` `ISOLATE` | 작업대 위 고정 위치 |
| 실패 코드 `code` | `OK` `GRIP_FAIL` `EMPTY_ZONE` `LEFTOVER` `LEFTOVER_REMAIN` `SEAT_FAIL` `TOOL_FAIL` `TOOL_LOST`(🆕 9/23 E37 · 닦는 중 툴 놓침) `FORCE_LIMIT` `TIMEOUT` `RACK_JAM` `RACK_FULL` `ROBOT_ERROR` `STOPPED` `OPERATOR_ABORT`(E68 · 관리자가 중단해 격리 — 실패 원인이 아니라 사람의 결정 · 화면 '관리자 격리') | |
| 흐름 상태 `step` | `IDLE` `PICK` `WEIGH` `SHAKE` `SEAT` `SOAP` `WIPE` `RINSE` `RACK` `ISOLATE` `DONE` `ERROR` `PAUSED` | `PICK` 안에 탐색 포함 |

## 3. F1 파지·이송·적재 (IR-01) · 한석형 · 모듈 `f1_handling.handling`
| 함수 | 인자 | 반환 | 비고 |
|---|---|---|---|
| `pick(zone_id, kind)` | `RET_B`/`RET_C`/`SPONGE_BED_*`, `BOWL`/`CUP` | `PickResult`: `ok, code, width_mm, attempts, offset_x_mm, offset_y_mm` (재파지가 빈손이면 `GRIP_FAIL` — `EMPTY_ZONE` 이면 홈의 용기를 잃는다) | **고정 슬롯 파지**: 구역의 슬롯을 정해진 순서로 — 슬롯 접근점 → 곧게 하강 → 파지 → 폭 판정(영점 뺀 폭). 폭 범위 밖(빈 슬롯·헛잡음)이면 놓고 다음 슬롯. 슬롯을 다 돌면 `EMPTY_ZONE`. `attempts` = 시도한 슬롯 수, `offset_*` = 집은 슬롯의 오프셋. **그릇은 벽을 세로로, 컵은 테두리 벽을 위에서 파지**(E29) · 홈 C 재파지만 옆면(`CUP_SIDE`). `SPONGE_BED_*`면 고정 위치 재파지(슬롯 1개) |
| `regrip_top(bed, kind)` | `SPONGE_BED_B`/`SPONGE_BED_C`, `BOWL`/`CUP` | `PickResult` — 코드 `OK` · `GRIP_FAIL` · `ROBOT_ERROR` | 🆕 E65(9/29) **격리 정리용**: 스펀지 홈의 용기를 **놓았던 자세에서 위로** 다시 잡는다 — 반납 구역에서 집을 때와 같은 파지(그릇은 벽 · 컵은 테두리 벽). 헹굼 앞 재파지(`pick('SPONGE_BED_C', 'CUP')`)의 옆면 잡기는 격리 구역에 옆으로 놓여 쓰지 않는다. 다시 잡지 못하면 `GRIP_FAIL` |
| `place(station, kind=None)` | 스테이션, (선택) `BOWL`/`CUP` | `PlaceResult`: `ok, code, offset_mm` | 상공 → 하강 → 놓기 → 후퇴. **항상 놓기(release)까지 한다.** **`SPONGE_BED_B/C`면 안착 놓기**: 쥔 채 순응 하강 → 깊이+힘으로 홈에 들어갔는지 판정 → 안 들어가면 Move Periodic 탐색 → 들어가면 놓기 / 한도 초과 → 들고 후퇴 + `SEAT_FAIL` · ✅ 9/20 추가: **`kind`** = 종류별 자리(`ISOLATE` 등)에 놓을 때 준다(좌표가 종류별이 됐다). 스펀지 홈처럼 이름에 종류가 들어 있는 자리는 생략 · 🔄 E65(9/29): `ISOLATE` 는 그릇·컵 **한 자리**(같은 관절값으로 곧장 가서 놓는다 · 인자 `kind` 는 그대로 받는다) · 🔄 as-built(E44): 스펀지 홈·칸 모두 접근점에서 **곧게 내려 놓는다**(마지막 15 mm 완충) — 순응 탐색·`SEAT_FAIL`·`RACK_JAM` 은 나지 않는다 · 마지막 보호는 컨트롤러 충돌 감지 |
| `move_to(station, carrying, kind=None)` | 스테이션, `bool`, (선택) `BOWL`/`CUP` | `Result` | 티칭한 자세로 이동, 들고 있으면 저속. 안전 자세 복귀 = `move_to('HOME', False)`. ✅ 9/20 추가: **`kind`** = 종류별 자리(`WEIGH`·`WASTE`·`SOAP`·`RINSE`·`ISOLATE`)로 갈 때 준다 — 그릇은 위에서·컵은 옆에서 잡아 같은 자리라도 자세가 다르다. `HOME` 은 생략. ("안전 높이 경유"는 9/20 결정 E7 로 삭제) |
| `tool(tool, action)` | `SPONGE`/`BRUSH`, `PICK`/`RETURN` | `ToolResult`: `ok, code, width_mm` | 홀더에서 툴 픽업·반납. 폭 범위 밖 → `TOOL_FAIL` |
| `rack_place(rack_slot, kind)` | 칸, 종류 | `Result` | 지정 각도 삽입, 순응 + 삽입력 감시, 걸림 → `RACK_JAM` · 🔄 as-built(E44): 스펀지 홈·칸 모두 접근점에서 **곧게 내려 놓는다**(마지막 15 mm 완충) — 순응 탐색·`SEAT_FAIL`·`RACK_JAM` 은 나지 않는다 · 마지막 보호는 컨트롤러 충돌 감지 |

반납 구역 `pick`의 헛잡음은 내부 재탐색(다음 슬롯)으로 소화되고, flow가 받는 코드는 `OK` · `EMPTY_ZONE` · `ROBOT_ERROR`다. 스펀지 홈 재파지가 빈손이면 `GRIP_FAIL`(정책 pause). 격리 정리의 `regrip_top` 이 `GRIP_FAIL` 이면 멈추지 않고 용기를 홈에 남긴 채 정리를 마친다(§8 · E65).

## 4. F2 무게·털기·헹굼 (IR-02) · 민범진 · 모듈 `f2_sense_flow.sense`
| 함수 | 인자 | 반환 | 비고 |
|---|---|---|---|
| `weigh(kind)` | 종류 | `WeighResult`: `ok, code, weight_g` | WEIGH 자세 정지 후 N회 평균. 0점 재설정(`reset`)은 **선택 동작**(응답 상한 3 s, 실패해도 계속 — [TS-03](troubleshooting/TS-03_하중_reset_제어권_교착.md)). 판정은 `측정값 − 빈 용기 기준값`이라 고정 옵셋은 상쇄된다 |
| `leftover_loop(kind, max_rounds)` | 종류, 최대 반복 | `LeftoverResult`: `ok, code, weight_before_g, weight_after_g, rounds` | 판정→털기→재측정 반복. 초과 지속 → `LEFTOVER_REMAIN`. 임계 미만은 `OK` |
| `shake(mode, count, kind)` | `WASTE`/`RINSE`, 횟수, 종류 | `Result` | 🔄 **E24: `WASTE` = 잔반 버리기(쏟기) · `RINSE` = 물기 털기 — 서명은 같고 동작이 다르다.** 진폭·속도는 `params.yaml`의 `f2` 절. **시작 시 강한 파지(HOLD) → 끝나면 보통 파지(NORMAL)**. 털다가 폭이 변하면(미끄러짐) `GRIP_FAIL` |
| `dip(station, count, kind)` | `RINSE`, 횟수, 종류 | `Result` | 담금 모션. 담그는 동안 **강한 파지(HOLD)** |

### 파지 힘 2단계 (9/18 V-17 검증 결과)
컵 옆면 파지는 들고 옮길 때는 충분하지만, **털기·헹굼·물 털기처럼 흔드는 동작에서는 더 꽉 잡아야 한다.** 파지 힘을 두 단계로 둔다: `NORMAL`(집기·이송·놓기) / `HOLD`(털기·담금·물 털기). 값은 `cell.yaml`의 `presets.<kind>.grip_force_n`·`hold_force_n`. 전환은 `cobot_common.grip_level(kind, 'HOLD'|'NORMAL')`. **흔드는 함수(F2 `shake`·`dip`·`leftover_loop`)가 시작할 때 HOLD, 끝날 때 NORMAL**로 되돌린다. 그래서 이 함수들은 `kind`를 받는다.

## 5. F3 접촉 닦기 (IR-03) · 박진용 · 모듈 `f3_wipe.wipe`
| 함수 | 인자 | 반환 | 비고 |
|---|---|---|---|
| `soap(count, kind=None)` | 횟수(🔄 9/22: 지금은 **무시** — 횟수는 `f3.soap` 설정), (선택) `BOWL`/`CUP` | `Result` | 툴 든 채 세제 담금(🔄 9/21 E18: 세제 수조를 따로 두지 않고 **툴 홀더의 비눗물 컵**에서 담근다 — 서명·반환은 그대로). ✅ 9/20 추가: **`kind`** — `SOAP` 이 종류별 자리가 됐다(`BOWL` = 수세미를 쥔 자세 · `CUP` = 솔을 쥔 자세) |
| `wipe_bowl()` | — | `WipeBowlResult`: `ok, code, force_log_path, duration_s, force_mean_n` | **그릇**: 수세미 툴로 힘제어(목표 힘 유지) 나선 닦기. 상한 초과 → `FORCE_LIMIT` |
| `wipe_cup()` | — | `WipeCupResult`: `ok, code, force_log_path, duration_s, insert_depth_mm` | **컵**: 수세미 솔을 컵 안에 삽입(힘 감시) → J6 회전 + Z 상하 스트로크. 동작이 그릇과 달라 함수를 분리(9/18 팀 결정) |

툴 픽업·반납과 **스펀지 홈 안착 놓기**는 F1(`tool`, `place`)을 flow가 부른다. F3는 "용기는 홈에 안착돼 있고 툴을 쥔 상태"에서 시작한다.

## 6. flow ↔ HMI (IR-04) · 민범진(flow) · 황인재(HMI) — **ROS 통신은 여기뿐**
| 인터페이스 | 형식 | 내용 |
|---|---|---|
| `/flow/start` | srv `std_srvs/Trigger` | 구역 계획대로 전부 처리 시작 (IDLE에서만). **즉시 응답**하고 실행은 메인 스레드가 한다 |
| `/flow/stop` | srv `std_srvs/Trigger` | ✅ **즉시 일시 정지**(황인재 9/20): 로봇이 **하던 이동을 그 자리에서 멈추고** `PAUSED` — 두산 `move_pause`(이동 함수는 비동기 + 폴링, V-24). 구현은 `cobot_common`의 `cc.pause()`·`cc.resume()`. 🚨 먹는 범위: 이동 함수를 거치는 모든 이동(접촉 하강·닦기의 걸음 포함 — 순응·힘제어는 켜진 채 선다). **안착 탐색(`move_periodic`)·그리퍼·무게 대기는 그 동작을 마친 뒤** 멈춘다. ⚠️ 알려진 제한(9/29): 닦기의 나선(그릇 ≈3 s)·주기 운동(컵 ≈13 s)도 그 동작이 끝난 뒤 멈춘다 — 대기 루프가 정지 깃발을 보지 않는다(향후 개선: 즉시 정지 + 재개 때 닦기 처음부터 · SDD §14). 실기는 V-24 빈손 통과(9/22) · 툴 든 채 세제 단계 정지 → 재개 ✅(9/29). 이동 중이 아니면 다음 단계로 가기 전에 멈춘다. HMI의 **일시 정지** 버튼("E-STOP"이라 부르지 않는다). 이름·타입은 그대로 → `cobot_msgs` 변경 없음 |
| `/flow/resume` | srv `std_srvs/Trigger` | `PAUSED`일 때만 받는다. ✅ 사람이 확인하고 **문제없으면 마저 한다**(황인재 9/20): 일시 정지였으면 **하던 이동을 이어서**(`move_resume`), 실패로 멈춘 경우(`RACK_FULL` 등)는 **실패한 그 단계부터 다시** · 🔄 9/29: 재개 때 **stop 깃발도 내린다(재개 한 번)** — 전에는 이동 도중 멈춘 것을 이어 간 뒤 다음 단계 앞에서 또 멈춰 재개를 두 번 눌러야 했다(9/29 2회차 ② · ✅ 실기 11:44: 닦기 중 정지 → 재개 한 번 → 다시 안 멈춤) |
| `/flow/abort` | srv `std_srvs/Trigger` | 🆕 ✅ 신설(황인재 9/20) — `PAUSED`일 때만. 사람이 **문제가 있다고 판단하면 지금 용기를 접는다**: **먼저 곧게 위로(safe_retreat) → `HOME` 자세로**(✅ 황인재 9/20 17:25 — 이동에서 안전 높이 경유를 없앴으므로 임의의 자세에서 다음 자리로 곧장 가지 않게) → 쥐고 있는 툴 반납 → 🔄 용기가 스펀지 홈에 있으면 `f1.regrip_top` 으로 위에서 다시 잡고 `HOME`(E52 · E65 — 못 잡으면 홈에 남기고 빈손으로 `HOME` · 사람이 치운다) → 용기를 격리 구역(`ISOLATE`)에 놓기(`f1.place('ISOLATE', kind)`) → `HOME` → **다음 용기**부터. 이벤트는 `ISOLATED`. 🚨 `ROBOT_ERROR`로 멈춘 경우는 **거부**한다(로봇 위치를 모른다 — 사람이 복구, SDD §7) |
| `/flow/state` | msg `cobot_msgs/FlowState` @2 Hz | 아래 정의. HMI는 2 s 이상 안 오면 "연결 끊김" 표시 |
| `/flow/event` | msg `cobot_msgs/FlowEvent` | 용기 1개 완료·격리·오류마다 1건 → HMI가 SQLite에 저장 |
| ~~`/cell/force`~~ | ~~msg `std_msgs/Float32` @10 Hz(닦는 동안만)~~ | ❌ **삭제(황인재 9/21 결정 E21)** — main 어디에서도 발행하지 않았다(HMI 가짜 발행기만). F3 힘제어는 그릇 벽면을 도는 몇 초뿐이고 컵은 없어(E17), 실제 로봇에서는 HMI 그래프가 늘 "닦는 중 아님" 이었다 → **HMI 힘 그래프 삭제**. 힘 데이터는 F3 가 용기마다 CSV(`force_log_path`)로 남긴다 — 발표에 힘제어를 보이려면 그 파일로 그래프를 따로 그린다. (9/20 결정: 힘 그래프를 넣는다 → 철회) |
| ~~`/cell/gripping`~~ | ~~msg `std_msgs/Bool`~~ | ❌ **삭제(황인재 9/21 결정 E21)** — 발행 코드가 한 번도 안 들어왔고, 결정 E19 로 **컵은 쥐었는지 판정하지 않으므로** "파지 중" 을 정확히 낼 수도 없다 → **HMI 파지 표시 삭제**. 대신 HMI 는 **셀 평면도 위에 로봇이 지금 어디서 무엇을 하는지** 그린다(`cell.yaml` 좌표 + `/flow/state` 의 step — 새 인터페이스 없음). 민범진·박진용은 발행을 만들지 않는다 |
| HMI 브리지 | REST `POST /api/start` `/api/stop` `/api/resume` `/api/abort`, `GET /api/state`, `GET /api/history` · `/api/usage` · `/api/kpi?period=`(`run`·`today`·`all`) · `/api/db/{table}` · `POST /api/replace/{item}`, WS `/ws/state` | FastAPI가 rclpy로 중계 (화면 PC · `hmi.host` 127.0.0.1 → `http://localhost:8000`) |

이 서비스·토픽은 `flow_node`의 **통신 노드**(백그라운드 실행기)가 맡는다. 콜백은 값 저장·깃발 세우기만 하고 로봇 함수를 부르지 않는다(SDD §3.2). 하드웨어 비상정지는 로봇 E-Stop이다. HMI 버튼은 소프트 정지이며 화면에 항상 보이게 둔다.

**두 PC 사이 통신**: `flow_node`(GPU PC · 로봇 제어)와 `hmi_bridge`(화면 PC)는 강의실 무선망에서 위 토픽·서비스를 주고받으며, 무선망이 ROS 2 기본 탐색(멀티캐스트)을 막으므로 GPU PC 에 띄운 Fast DDS **Discovery Server**(`172.18.0.101:11811`)로 서로를 찾는다 — 두 PC 의 ROS 터미널 모두 `RMW_IMPLEMENTATION=rmw_fastrtps_cpp` · `ROS_DISCOVERY_SERVER=172.18.0.101:11811` · `ROS_SUPER_CLIENT=TRUE` · `ROS_DOMAIN_ID=60` · `ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET` · `ROS_STATIC_PEERS` 비움(정확한 명령은 SDD §10). 인터페이스의 이름·타입은 그대로다(구성·실행 순서는 SDD §1.2 · §10).

외부 ROS 인터페이스(우리가 정의하지 않음, `cobot_common`만 사용): 두산 드라이버 `/dsr01/dsr_controller2/*`(DSR_ROBOT2 API 경유), 그리퍼 드라이버 `/onrobot/sendCommand`(srv) + 현재 폭을 읽는 `/onrobot_joint_states`(구독). 드라이버(`OnRobotRGControllerServer`)는 `OnRobotRGInput`을 **발행하지 않는다**(9/19 소스 확인: 나가는 것은 `/joint_states`→`/onrobot_joint_states` remap의 `JointState`뿐, 서비스는 `/onrobot/sendCommand`·`/onrobot/pose`·`/onrobot/restartPower`). 그래서 `cobot_common` 이 `/onrobot_joint_states` 의 `finger_joint` 관절각을 드라이버와 같은 식으로 폭(mm)으로 환산해 읽는다(SDD §3.1 `grip`).

## 7. 메시지 정의 (정본: [src/cobot_msgs/msg/](../src/cobot_msgs/msg/))
```
# FlowState.msg
string step            # §2 흐름 상태
string kind            # 현재 용기 BOWL/CUP/""
string zone_id         # 현재 반납 구역
uint16 done_bowl
uint16 done_cup
uint16 isolated
uint16 target_bowl     # 계획 수량 (진행률 계산용)
uint16 target_cup
uint16 sponge_uses
uint16 soap_dips
uint16 rinse_dips
string last_code
string message
builtin_interfaces/Time stamp

# FlowEvent.msg
builtin_interfaces/Time stamp
string kind
string zone_id
string rack_slot
uint8 attempts          # 시도한 슬롯 수 (고정 슬롯 파지)
float32 weight_before_g
float32 weight_after_g
string result           # DONE / ISOLATED / ERROR / SKIPPED
string code
float32 duration_s
string force_log_path
```
`cobot_msgs` v3.0은 이 메시지 2개만 담는다(서비스 12개 삭제). `/flow/*` 서비스는 `std_srvs/Trigger`.

## 8. 호출 순서 (flow_node)
```python
from f1_handling import handling as f1          # mock 이면 f2_sense_flow.mock.mock_f1
from f2_sense_flow import sense as f2
from f3_wipe import wipe as f3                  # mock 이면 f2_sense_flow.mock.mock_f3

# plan (params.yaml flow 절): [{zone: RET_B, kind: BOWL, count: 2}, {zone: RET_C, kind: CUP, count: 2}]
# 구역마다 count 회 또는 EMPTY_ZONE 까지 반복:
# BOWL
f1.pick('RET_B', 'BOWL') → f1.move_to('WEIGH', True, 'BOWL') → f2.leftover_loop('BOWL', 2)   # kind: 9/20 추가(종류별 자리)
→ f1.place('SPONGE_BED_B')                      # 안착 놓기(순응 하강·탐색, 실패 SEAT_FAIL)
→ f1.tool('SPONGE', 'PICK') → f3.soap(3, 'BOWL') → f3.wipe_bowl() → f1.tool('SPONGE', 'RETURN')
→ f1.pick('SPONGE_BED_B', 'BOWL')               # 홈에 놓인 그릇 재파지(고정 위치, 탐색점 1개)
→ f2.dip('RINSE', 2, 'BOWL') → f2.shake('RINSE', 3, 'BOWL')   # 🔄 9/22 담금 1 → 2 · 🔄 9/23 E36: shake(RINSE) 는 곧게 위로 빠져나와 **접근 높이(수조 위)에서 J4 좌우 3회** · 끝나면 높은 자세(dip 은 수조 안에서 끝)
→ f1.rack_place('RACK_Bn', 'BOWL') → f1.move_to('HOME', False)
# CUP: 🔄 E30(9/22 19:0x · E25 되돌림) — **그릇과 같은 흐름**(move_to WEIGH · leftover_loop 도 한다 · `flow.weigh_kinds [BOWL, CUP]`) · 파지는 E29 벽 집기(폭 판정) · 나머지 동일, SPONGE_BED_C · tool('BRUSH') · wipe_cup() · dip·shake('RINSE') 는 한다 · RACK_Cn
```

**실패 정책 (`params.yaml` flow 절 `policy`)**
| 코드 | 처리 |
|---|---|
| `EMPTY_ZONE` | 구역 종료 → 다음 구역 (기록 SKIPPED) |
| `LEFTOVER_REMAIN` | 🔄 E52(황인재 9/25 · ✅ 9/29 실기): **ISOLATE** — 사람 없이 위로 → HOME → ISOLATE → HOME → 다음 용기(정리 함수 통일 · E42 의 "기록만" 빈틈 닫힘 · E42 의 임시 PAUSED 를 대체) |
| `SEAT_FAIL` | ISOLATE 후 다음 용기 (🟡 위와 같은 빈틈 · 시연 범위 밖 E28) |
| `FORCE_LIMIT` `TIMEOUT` `RACK_JAM` | 공통: 곧게 위로(`safe_retreat`) 뒤 재시도 1회 → 또 실패하면 ISOLATE — 🔄 E52: 격리 = 정리 함수 통일(위로 → HOME → 툴 반납 → 홈 용기를 위에서 다시 잡기(`regrip_top` · E65) → HOME → ISOLATE → HOME · abort 와 같은 길). 🔄 닦기에서는 먼저 남은 나선·주기 운동을 즉시 정지하고, 힘·순응을 끈 뒤 호출 높이로 곧게 올라온다(E60). 재시도 전에 툴 쥠을 확인해 없으면 `TOOL_LOST` 멈춤으로 가고(E61), 재시도는 HOME 이동 없이 곧게 올라온 자리(safe_z)에서 한다(E61 정정). `RACK_JAM`은 E44(감시 없이 곧게 내려가 놓기) 이후 시연 설정에서는 나지 않는다 |
| `TOOL_FAIL` | 🔄 E52(황인재 9/25): **PAUSED** → 홀더 확인 → 넛지/resume → 툴 집기부터 다시(ISOLATE 안 함 · 전에는 retry:1 → ISOLATE) · ✅ 9/29 실기(빈 홀더 → `TOOL_FAIL` → 툴을 꽂고 밀기 → 다시 집기 · 격리 0) |
| `TOOL_LOST` | 🆕 9/23 E37(9/22 회의 합의 · 황인재 승인): F3 가 닦는 중 폭 재확인으로 툴(수세미·솔) 놓침을 감지해 돌려준다 → flow 는 **정지(PAUSED)** → 사람이 홀더에 다시 넣고 넛지·재개 → 곧게 위로 → 🔄 **툴 집기 단계부터 다시**(툴 집기 → 세제 → 닦기 · E62) · 다시 집기 실패는 `TOOL_FAIL` 정책을 따른다 · 후퇴 실패는 로봇 오류 절차 · 격리 아님 · ✅ 9/29 실기(세제 중 솔을 뽑음 → 밀기 → 툴 집기부터 다시 → 완료 · 닦기 중 놓침은 자동 시험만) |
| `GRIP_FAIL` (f2: 털기·담금 중 미끄러짐 · 무게로 본 빈손) | ✅ **PAUSED + HMI 알림 → 사람이 확인**(황인재 9/20 17:25). 놓쳤다면 용기가 손에 없을 수 있어 격리 동작이 의미 없고, 떨어진 용기를 다음 동작이 칠 수 있다. 확인 뒤 `resume` = 그 단계부터 다시 / `abort` = 그 용기를 접고 다음 용기 |
| `RACK_FULL` | PAUSED + HMI 알림 → 팔레트 교체 후 **resume = 실패한 단계(적재)부터 다시** / **abort = 그 용기를 격리**하고 다음 용기 |
| `ROBOT_ERROR` (기능 함수에서 새어 나온 예외 포함) | 그 자리 정지 → PAUSED + 알림 → **사람이 복구**(SDD §7). `abort`는 거부, 복구 뒤 `resume`하면 다음 용기부터(그 용기는 `ERROR`로 기록) 🔄 E52(9/25): 격리 이동 없음 · 쥔 것이 있으면 2단(신호 1 → release 만 → 사람 수거 → 화면 재개 버튼(E54 · 가볍게 밀기 X) → 위로 → HOME → ERROR 기록 → 다음 용기) · 첫 신호만 넛지 허용 · 2단 절차는 실기 시험·발표에서 제외(E55 · 코드는 안전망) |
| 케이블 이상(무게 재기 중 떨림 > 80 g) | 🔄 E64(9/29 · E63 정정): 후퇴 없이 그 자리 **PAUSED** + 알림 → 사람이 케이블 확인 → 가볍게 밀기(또는 화면 재개)면 **바로 재개** — 제자리 재측정은 하지 않는다 → 밀기였으면 손 뗄 시간(`f2.nudge.settle_s` 1.5 s) → 보호정지 복구·STANDBY 확인(복구 전 STANDBY 가 아니었으면 이동 전 2 s 더 · `cell.limits.nudge_after_reset_s`) → **무게 단계를 처음부터 다시**(HOME 경유) — 그 무게 재기가 케이블을 다시 본다 → 아직 떨리면 같은 케이블 멈춤이 다시 걸려(알림창·소리) 새 신호를 기다린다 · 멈춘 동안 `last_code` 는 `ROBOT_ERROR` 라 `abort` 는 거부된다 · ✅ 새 방식 실기(리허설 12:26): 떨림 156 g → 멈춤 → 밀기 1번 → 2 s 더 대기 → 무게 다시 −3.9 g 통과 · 멈춤 약 8 s |
| 일시 정지 버튼 | **즉시** 그 자리에서 멈춤 → PAUSED (안착 탐색·그리퍼·무게 대기·닦기 나선·주기 운동은 그 동작을 마친 뒤 — §6 알려진 제한) → **재개**(하던 동작을 이어서 · 재개 한 번이면 이어 간다 · ✅ 실기 11:44) 또는 **중단**(`abort` — 격리 후 다음 용기) |

**격리 구역 운영(E65 · 9/29)**: 격리 자리는 그릇·컵 **한 곳**이다(그릇 전용 경로 없음). 한 실행에서 격리가 두 번 생기면 두 번째가 첫 번째 위로 내려간다 → **시작 전 격리 구역을 비우고, 격리가 생기면 다음 격리 전에 사람이 치운다.** 격리 정리(중단 · 재시도 소진)에서 스펀지 홈의 용기는 `f1.regrip_top` 으로 놓았던 자세에서 위로 다시 잡는다 → HOME → 격리 → HOME. 다시 잡지 못하면 용기는 홈에 남기고 격리 구역에 가지 않는다(빈손) → HOME · 사람이 치운다.

## 9. 설정 파일 (IR-07) — 파일 2개
설정은 `src/cobot_common/config/`의 **파일 2개**로 둔다(9/18 최종 결정).

| 파일 | 주인 | 내용 | 읽는 쪽 |
|---|---|---|---|
| **`cell.yaml`** (공용) | **한석형 혼자** | 속도·안전 높이·공통 힘 상한·타임아웃, 프리셋(종류별 폭·`grip_force_n`·`hold_force_n`), 스테이션·반납 구역(탐색점)·스펀지 홈(안착 파라미터)·팔레트 칸 좌표 | 전부 (읽기만) |
| **`params.yaml`** (기능별 절) | 절마다 주인 | `f1:` 한석형 · `f2:` 민범진(기준 무게·잔반 임계·털기·담금) · `f3:` 박진용(세제 담금·`wipe_bowl`·`wipe_cup`) · `flow:` 민범진(구역 계획·실패 정책·칸 배정·소모품·`use_mock`) · `hmi:` 황인재(포트·갱신 주기·끊김 판정·DB 경로) | 각 패키지는 자기 절 + `cell.yaml` |

왜 2개인가: ① 공용 값(좌표·속도·프리셋)은 한 곳, 주인 한 명 — F1의 `place`와 F3의 `wipe_bowl`이 같은 `cell.yaml`을 읽으므로 값이 갈라질 수 없다. ② 나머지는 한 파일에서 한눈에 — 절이 떨어져 있어 git이 자동으로 합친다. 규칙은 하나, **자기 절만 고친다.** ③ 코드는 `cobot_common.config.load()`가 두 파일을 읽어 하나의 설정(`cfg['cell']`, `cfg['f3']` …)으로 합쳐 준다. 키 이름 규칙은 SDD §4.3.

## 10. 시험용 가짜 구현
- **`f2_sense_flow.mock.mock_f1` · `mock_f2` · `mock_f3`**(✅ `mock_f2` 추가 — 황인재 9/20, 코드는 그 전부터 있었다): 실제 모듈과 **같은 함수 이름·같은 인자**로 즉시 `Result(ok=True)`를 돌려주고, 설정으로 실패 코드를 주입한다(`flow.mock.fail_on: ["place:SEAT_FAIL"]`). flow는 `params.yaml`의 `flow.use_mock: [f1, f3]`로 어느 쪽을 import할지 고른다. 전부 mock이면 두산 드라이버 없이 돈다 — flow·HMI 개발용, 민범진 제공. 서명 일치는 `cobot_api.check_api(mock_f1, F1Api)`로 검사한다.
- **`fake_state_pub`**: `/flow/state`·`/flow/event`를 시나리오대로 발행 — HMI 개발용, 황인재 제작.
- **단독 시험 스크립트** `rig_f1.py`·`rig_f2.py`·`rig_f3.py`: `cobot_common.init('rig_f1')` 뒤 자기 함수만 직접 부른다(SDD §3.2). 용기·툴은 손으로 놓아 준다.
