# PreWash-Cell — 경기장 다회용기 예비세척 · 식기세척기 팔레트 적재 자동화 셀

> ROKEY 9기 협동1 · **D그룹 2조** (한석형 팀장 · 민범진 · 박진용 · 황인재 PM)
> 두산 **M0609** + OnRobot **RG2** · ROS 2 Jazzy · Ubuntu 24.04 · **비전 없음**(판단은 파지 폭 · 하중 · 힘)
> 기능 동결 **9/23(수) 저녁** · 최종 시연 **9/29(화) 14:00**(강사 입회) · 제출·발표 **9/30(화)**

경기장에서 반납된 **다회용 그릇·컵**을 로봇이 집어 **잔반을 털고, 안쪽을 닦고, 헹군 뒤 식기세척기 팔레트에 꽂는다.** 본세척은 식기세척기가 한다.

---

## 1. 무엇을 하는가 — 용기 1개가 도는 길

```
반납 구역 ──집기──▶ HOME 을 거쳐 저울 자세 ──무게──▶ (잔반 ≥ 50 g 이면 잔반통 위에서 기울여 털고 다시 잰다)
        ──▶ 스펀지 홈에 놓기 ──▶ 툴 집기(그릇 수세미 · 컵 솔) → 세제 → 안쪽 닦기(힘 제어) → 툴 반납
        ──▶ 다시 집기(컵은 옆면으로) ──▶ 헹굼 담금 2회 → 곧게 위로 → 털기 자세에서 손목(J4) 좌우 3회
        ──▶ 식기세척기 팔레트 칸에 꽂기(컵은 뒤집어) ──▶ HOME
```
- **그릇·컵 모두** 위 순서 전부(컵도 무게·잔반 버리기 — 결정 E30). 컵은 반납 자리에서 테두리를 집고(E29), 스펀지 홈에서 **옆면 몸통**으로 다시 잡아(70 mm · 10 N · E38) 헹군 뒤 뒤집어 꽂는다.
- 시연 시나리오(강사 피드백 · E41): **그릇 2 · 컵 2 를 처음부터 다 놓아 두고** 그릇1 → 그릇2 → 컵1 → 컵2 순으로 **정상 흐름을 끝까지**(예외 처리는 시연 목표에서 제외 · E28). 배속 0.5(E40) · 잔반 대용품은 2개(≈190 g) 기준.
- 실패하면(예외 처리 · **9/29 오전 실기로 확인한 것만 시연 대본에** · E45): 빈 구역 → 건너뛰고 HOME(#98) / **잔반이 계속 남음 → 멈춤 → 사람이 재개(다시 잼) 또는 중단(HOME → 격리 → 다음 용기)**(E42) / 안착 실패 → 격리 / **닦는 중 툴 놓침 → 그 자리 정지 → 홀더에 넣고 톡톡(15 N · 1번) 또는 화면 재개 → 다시 집고 이어감**(E37 · E48) / **무게 떨림 > 80 g(케이블 당김) → 멈춤 → 케이블 정리 → 톡톡 → 재검증 → 안전정지 자동 해제 → 이어감**(E43 · E47) / 용기 놓침·로봇 오류 → 멈추고 사람이 확인. 놓기·적재·툴 반납은 힘 감시 없이 곧게 내려가 놓는다(E44 · 걸림은 충돌 감지). 화면 버튼: 정지(즉시) · 재개 · 중단(HOME → 툴 반납 → 격리 → HOME · E11).

## 2. 구조 한눈에 (PC 2대 · 프로그램 2개)

| 어디 | 프로그램 | 하는 일 |
|---|---|---|
| **PC-A** (로봇 옆) | `flow_node` (`f2_sense_flow`) | 메인 프로그램. 위 순서대로 기능 함수를 차례로 부르고, 실패 정책·정지/재개/중단·기록(`records.csv`)을 맡는다. 로봇 명령은 이 프로그램의 메인 스레드에서만 나간다 |
| **PC-B** (화면) | `hmi_bridge` (`f4_hmi`) + 웹 화면 | 브라우저에서 시작·일시 정지·재개·중단 버튼, 단계 그림 카드, 팔레트 그림, 숫자 패널, 이력 |

기능은 **파이썬 함수 모듈**로 나뉘어 있고(노드가 아니다), `flow_node`가 순서대로 부른다.

| 모듈 | 담당 | 함수 | 한 줄 |
|---|---|---|---|
| `f1_handling` | 한석형 | `pick` `place` `move_to` `tool` `rack_place` | 집기 · 놓기 · 이동 · 툴 집기/반납 · 팔레트 꽂기 |
| `f2_sense_flow` | 민범진(9/23 통합은 황인재) | `weigh` `leftover_loop` `shake` `dip` + `flow.py`/`flow_node.py` | 무게(항상 HOME 경유) · 잔반 버리기 · 헹굼 담금 · 물 털기(E36 · 털기 자세 `RINSE_SHAKE`) + **흐름** |
| `f3_wipe` | 박진용 | `soap` `wipe_bowl` `wipe_cup` | 세제 · 그릇 닦기(나선 + 벽면 힘 제어) · 컵 닦기(솔 회전) |
| `f4_hmi` | 황인재 | `hmi_bridge` · `web/`(Next.js) · `fake_state_pub`(가짜 flow) | 운영 화면 |
| `cobot_common` | 4명 분담 | `bootstrap` `motion` `gripper` `weigh` `force` | 두산 API·그리퍼를 감싼 **공용 로봇 함수** — 두산 함수는 여기서만 부른다. 이동 상한·접촉 타임아웃은 배속(`PREWASH_VEL_SCALE`)에 맞춰 늘어난다 |
| `cobot_api` · `cobot_msgs` | 황인재(정본) | 함수 약속(`contracts.py`) · 메시지 2개(`FlowState` `FlowEvent`) | 팀 계약 — 혼자 바꾸지 않는다 |
| `prewash_bringup` | 황인재 | `prewash.launch.py` · `prewash_mock.launch.py` | 실행 묶음 |

좌표·힘·횟수 같은 숫자는 코드가 아니라 `src/cobot_common/config/cell.yaml`(좌표·프리셋 · 스테이션 12 · 프리셋 5 · 팔레트 4칸 · 반납 구역 2×2 슬롯) · `params.yaml`(기능별 값 · 빈 용기 기준값 · 시간 상한)에 있다.

## 3. 지금까지 된 것 (9/23 동결 · `v1.0-demo` = main 8874dfc)

검증 수준 표기: **자동** = pytest(로봇 없이) · **가상** = RViz 가상 로봇 · **실기** = 실제 로봇 · 🟡 = 아직 실기로 못 봄

| 영역 | 상태 | 확인 수준 | 근거 |
|---|---|---|---|
| **시연 경로 리허설** | 메인 프로그램(`flow_node`) 한 번 시작 → **그릇 2 → 컵 2 연속 완주 3회**(배속 0.5 · 19분 34초 / 19분 39초 / 튜닝 뒤 **17분 39초** · 격리 0 · 잔반 루프 1회 · ros bag) — 2번째 슬롯 집기 · 팔레트 B1·B2·C1·C2 · 잔반 감지 → 털기 → 재측정 통과 | 실기 | `docs/test_logs/20260923_VER-0923_*` §17~18 · PR #96 #97 |
| 그릇 한 바퀴 | 빈 그릇 · 96 g 잔반(감지 → 털기 → 통과) 각 1회 + 리허설 4회 | 실기 | 같은 기록 §2~5 |
| 컵 한 바퀴 | 빈 컵 2회 · 98 g 잔반 2회(옆면 재파지 → 담금 → 뒤집은 자세 물털기 → 팔레트) + 리허설 4회 | 실기 | 같은 기록 §12~16 · PR #92 #94 |
| 환경·좌표 | 4대 PC 환경 · 전 스테이션 좌표(HOME·저울·잔반통·반납 구역 2×2·스펀지 홈·툴 홀더·팔레트 4칸·격리·털기 자세) · 툴 무게·TCP 등록 | 실기 | `20260922_ENV-05_*` · `20260921_V-22_*` |
| 공용 로봇 함수 | 이동(비동기 + 즉시 정지 · 배속에 맞춘 시간 상한) · 그리퍼(폭 판정 · 쥔 프리셋 기억 · 빈손 거부) · 무게(힘센서 Fz · 떨림·흐름 분리) · 힘 제어·접촉 하강·순응 · 관절 스플라인(물털기) | 자동 + 실기 | `20260922_V-26_*` · PR #89 #92 #94 #97 |
| F1 집기·이송 | `pick`(슬롯 2개 순회) · `place`(그릇 격리 J1 경로 #90) · `tool`(수세미·솔 · 반납 감시 하강) · `rack_place`(경유점 · 그릇 손목 반전 · 컵 뒤집기) · 옆면 재파지(접근점 + 힘 감시) | 실기 | `20260922_V-08_*` · 9/23 기록 |
| F2 무게·털기·헹굼 | 무게는 항상 HOME 경유(오는 길 차 90 g 발견) · 기준값은 **실행 직전 1회**(드리프트 ±45 g) · 잔반 털기(그릇 35 N · 컵 25 N) · 담금 2회 → 새 물털기(J4 ±30°/±15° 스플라인 · 배속 예외로 빠르게) | 실기 | 9/23 기록 · PR #89 #95 #96 |
| F2 흐름(flow) | 상태 머신 · 실패 정책(재시도 · 격리 · 정지) · 정지/재개/중단 · 기록 · 툴·TCP 문지기 · 계획(구역마다 2개) | 자동 + **실기(flow_node 리허설 2회)** | `20260921_UT-FLOW_*` · 9/23 기록 §17~18 |
| F3 닦기 | 세제 → 그릇 닦기(바닥 힘으로 찾기 → 나선 → 벽면) · 컵 닦기(솔) → 반납 — 흐름 안에서 그릇·컵 모두 | 실기 | `20260920_V-03_*` · `20260921_V-10_*` · 9/23 기록 |
| F4 화면 | 운영 화면(단계 카드 · 팔레트 그림 · 숫자 · 이력) · 버튼 · 가짜 flow 대본 5개 | 가짜 flow · 실제 flow 연결 🟡(추석) | PR #66 · `src/f4_hmi/README.md` |
| 새 기능(9/23) | 그릇 격리 경로(#90 · 중단 정리에서 씀 · #103 흐름 갈래는 E42 로 미사용) · 세제 펌프(#100 · 제품 함수 · **기본 꺼짐** · 9/29 구매 뒤 결정) · 케이블 이상 → 멈춤 → 톡톡 재개(#93) + 안전정지 자동 해제(#102 · E43) · 툴 놓침 TOOL_LOST → 정지 → 넛지 → 재PICK(#99 · E37) · 넛지 힘 15 N 통일 · 1번(E48 · 9/24 22:1x 2번 철회) | 실기(케이블 1회 · 툴 놓침 rig) · 🟡 **흐름 안 예외 5종은 9/29 오전 INT-4b** | PR #90 #93 #99 #100 #102 #103 · 대본 `docs/test_logs/20260929_INT-4b_*`(PR 대기) |
| 안전 | 접촉 동작마다 힘 상한·후퇴·타임아웃(배속·거리에 맞춰 늘림 · 최소 30 s) · 놓기·적재·툴 반납은 감시 없이 곧게 + 마지막 15 mm 완충(E44 · 황인재 결정) · 로봇 위치를 모르면 자동으로 안 움직임 · 수조 안에서는 먼저 곧게 위로 · 빈손이면 털기·담금 거부 · 툴·TCP 이름 확인 · 실기 끝나면 Ctrl+C 뒤 랜선 | 규칙 + 코드 | `AGENTS.md` §3 · `docs/00_현재상황_리마인드.md` §6 · `docs/troubleshooting/` |

**동결 뒤(9/24~)**: 추석(9/24~28)은 로봇 없이 화면(HMI)·문서만. **9/29(화) 오전** 브링업 → 좌표 재현 10분 → 리허설 1회(0.5) → 대용품 94 g 무게 확인 → 예외 시나리오 5종 실기(INT-4b 대본) → 기준값 2종 → **14:00 최종 시연**(정상 흐름 + 오전 통과한 시나리오만 · E28 · E45). 동결 뒤 코드는 시연 경로 무영향 안전장치만, 실기 확인 뒤 반영.
자동 시험은 **532개**(9/23 동결 · 두 환경에서 통과). 시험 기록은 `docs/test_logs/`, 결정은 `docs/meetings/20260919_결정기록_DSN-03.md`(E1~E48). 9/23 merge 된 PR: #89~#105(튜닝 #105 까지 = `v1.0-demo`).

## 4. 실행 방법 — 무엇을 치면 무엇이 도는가

별칭(`sod` `soc` `cbc` `sodvir` `sodreal` `rosinfo` `solo`/`team60`)은 `docs/setup/M0609_환경설정.md`대로 `.bashrc`에 있다.
`sod` = 두산 드라이버 워크스페이스 source · `soc` = 두산 + 우리 워크스페이스 source · `cbc` = 우리 워크스페이스 빌드 + source. 실기 명령은 배속 `PREWASH_VEL_SCALE`(0.3 = 첫 실기 · 0.5 = 시연)을 앞에 붙인다.

### 4-1. 준비 (한 번) — 빌드와 자동 시험
```bash
git clone https://github.com/hwang-injae/rokey_9_pjt1_D2.git rokey_pjt01_ws && cd rokey_pjt01_ws
cbc                                              # 빌드 — "8 packages finished"
python3 -m pytest -q src                          # 자동 시험 476개 통과 (로봇 없이 · 빌드한 뒤)
python3 src/f2_sense_flow/test/rig_flow_once.py check   # 메인 흐름 설정(계획 그릇 2 → 컵 2 · 팔레트 순서) 점검
```

### 4-2. 로봇 없이 — 화면과 흐름만 (아무 PC)
```bash
soc && ros2 launch prewash_bringup prewash_mock.launch.py     # 메인 프로그램 + 화면을 가짜 기능으로 → http://localhost:8000 에서 시작·정지·재개·중단
```
```bash
soc && ros2 run f4_hmi hmi_bridge                  # 터미널 1: 화면 서버 → http://localhost:8000
soc && ros2 run f4_hmi fake_state_pub normal       # 터미널 2: 가짜 flow 대본(normal · paused · isolate · error · empty_zone)으로 화면 반응 보기
```
화면(`web/out`)이 없으면 `/`에 시험 페이지가 뜬다 — 화면 PC(PC-B)에서 한 번 `cd src/f4_hmi/web && npm install && npm run build`.

### 4-3. 가상 로봇 (RViz · 팔 동작·흐름만 — 그리퍼·무게·힘은 없음)
```bash
sod && sodvir                                                    # 터미널 1: 가상 브링업 (이미 떠 있으면 다시 띄우지 않는다)
soc && python3 src/cobot_common/test/rig_coords.py --from 1      # 터미널 2: 전 좌표를 순서대로 방문
soc && python3 src/f2_sense_flow/test/rig_int12.py a --virtual --kind BOWL -n 3   # 집기 → 저울 → 잔반 처리 구간
```

### 4-4. 실제 로봇 🚨 담당자만 · 팀 확인 뒤 · 로봇 프로그램은 한 번에 하나
```bash
rosinfo                                          # RANGE=LOCALHOST(격리)인지 — PC 2대 통합 때만 team60, 끝나면 solo
sod && sodreal                                   # 터미널 1: 실기 브링업 (컨트롤러 192.168.1.100)
ros2 service call /dsr01/dsr_controller2/tcp/get_current_tcp  dsr_msgs2/srv/GetCurrentTcp    # → GripperDA_v1  (아니면 움직이지 말고 펜던트에서 다시 고른다)
ros2 service call /dsr01/dsr_controller2/tool/get_current_tool dsr_msgs2/srv/GetCurrentTool  # → Tool Weight
```
브링업 뒤 힘센서가 안정되는 데 약 50분이 걸린다. **빈 용기 기준값은 실행 직전에 1회** 재고 `params.yaml`의 `f2.empty_weight_g`에 넣는다(몇 분 사이에도 수십 g 움직인다):
```bash
soc && PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_f2.py empty --kind BOWL -n 1   # 빈 그릇 기준값 (HOME 경유 · 21 s 창)
soc && PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_f2.py empty --kind CUP  -n 1   # 빈 컵 기준값
```

**단독 기능 시험(rig)** — 용기를 손으로 시작 자리에 놓고 기능 하나만 돌린다. 볼 것과 통과 기준은 각 파일 머리말에 있다.
| 명령 | 무엇이 도는가 |
|---|---|
| `PREWASH_VEL_SCALE=0.3 python3 src/f1_handling/test/rig_f1.py pick --zone RET_C --kind CUP -n 1` | 반납 구역 집기(슬롯 1 → 2 순회 · 폭 판정) |
| `… rig_f1.py place --station SPONGE_BED_C --kind CUP -n 1` | 스펀지 홈에 놓기 |
| `… rig_f1.py pick --zone SPONGE_BED_C --kind CUP -n 1` | 홈에서 다시 집기(컵은 옆면 · 접근점 + 마지막 60 mm 힘 감시) |
| `… rig_f1.py tool --action CYCLE -n 3` | 툴 집기 → 반납 |
| `… rig_f1.py rack_place --slot RACK_C1 --kind CUP -n 1` | 팔레트 칸에 꽂기(수조 안에서 출발해도 됨) |
| `… src/f2_sense_flow/test/rig_f2.py dip --kind CUP --count 2 -n 1 --no-home` | 헹굼 담금 2회 |
| `… rig_f2.py shake --mode RINSE --kind BOWL --count 3 -n 1 --no-home` | 새 물털기(곧게 위로 → 털기 자세 → J4 3회) |
| `… rig_f2.py shake --mode WASTE --kind BOWL --count 4 -n 1` | 잔반통 위 털기 |
| `… src/f3_wipe/test/rig_f3.py` | 세제 → 그릇 닦기 |
| `… src/cobot_common/test/rig_goto.py RINSE_SHAKE --kind CUP --carrying --via RINSE` | 자리 한 곳으로 가서 멈춤(티칭 확인) |
🚨 단계별 rig 는 프로그램마다 그리퍼 힘·프리셋 기억이 이어지지 않는다 — 담금·털기는 한 프로그램(흐름) 안에서 본다.

**한 바퀴(흐름 한 번 · 프로그램 하나)**:
```bash
soc && PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_flow_once.py --kind CUP  --mock "" -n 1   # 컵 1개 · 모든 기능 실제
soc && PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_flow_once.py --kind BOWL --mock f3 -n 1   # 그릇 1개 · F3(세제·닦기)만 가짜
```
멈추면(PAUSED) 터미널에서 Enter = 그 단계부터 다시 · a = 이 용기를 접고 격리 · q = 끝(안 움직임).

### 4-5. 시연 실행 — 메인 프로그램으로 그릇 2 → 컵 2 연속 (9/23 리허설 2회 완주한 절차)
준비: 그릇 2·컵 2 를 반납 구역에 **처음부터 다 배치**(E41) · 잔반 대용품 2개(≈190 g) · 새 컵 · 기준값 2종 실행 직전 1회(4-4).
```bash
# PC-A
soc && ros2 launch prewash_bringup prewash.launch.py vel_scale:=0.5      # 터미널 2: 메인 프로그램(flow_node) — IDLE 로 대기
ros2 service call /flow/start  std_srvs/srv/Trigger                    # 터미널 3: 시작 → 계획대로 4개 연속 · 끝나면 DONE → IDLE
ros2 service call /flow/stop   std_srvs/srv/Trigger                    # 즉시 일시 정지 (이동 도중에도)
ros2 service call /flow/resume std_srvs/srv/Trigger                    # 재개 — 실패로 멈췄으면 그 단계부터 다시
ros2 service call /flow/abort  std_srvs/srv/Trigger                    # PAUSED 에서만: 이 용기를 격리하고 다음 용기로
ros2 topic echo /flow/state                                            # 지금 단계·용기·잔반·메시지 (2 Hz)
```
```bash
# PC-B (화면 · 선택 — 두 PC 모두 team60 · 같은 스위치)
soc && ros2 run f4_hmi hmi_bridge                # http://<PC-B>:8000 — 시작·정지·재개·중단 버튼이 위 서비스를 부른다
```
볼 것: 용기마다 `/flow/event`(DONE·ISOLATED) · `records.csv`(PC-A) 1행 · 사이클 타임(리허설: 그릇 ≈4분 · 컵 ≈5~6분 · 4개 ≈19분 30초).
실기가 끝나면 **프로그램 터미널 Ctrl+C → 브링업 터미널 Ctrl+C → 그다음 랜선**. 급하면 Ctrl+C 가 아니라 E-Stop.

## 5. 문서 지도

| 무엇이 궁금하면 | 여기 |
|---|---|
| 지금 무엇이 참인가(시나리오 · 분담 · 유효한 결정 · 안전 · 좌표 상태) | **[docs/00_현재상황_리마인드.md](docs/00_현재상황_리마인드.md)** |
| 요구사항 (BR · FR · NFR · SR · 추적표) | [docs/01_요구사항_BR-SR.md](docs/01_요구사항_BR-SR.md) |
| 함수·메시지 약속 (계약 정본) | [docs/02_인터페이스_IRD.md](docs/02_인터페이스_IRD.md) · [`src/cobot_api/cobot_api/contracts.py`](src/cobot_api/cobot_api/contracts.py) · [docs/interfaces/](docs/interfaces/) |
| 설계 (아키텍처 · 상태 머신 · YAML 양식 · 오류·안전 · §9 테스트 계획) | [docs/03_설계_SDD.md](docs/03_설계_SDD.md) |
| 결정 기록 (E1~E41 · 왜 그렇게 했나) | [docs/meetings/20260919_결정기록_DSN-03.md](docs/meetings/20260919_결정기록_DSN-03.md) |
| 시험 기록 (날짜_ID_내용_이름.md) | [docs/test_logs/](docs/test_logs/) |
| 트러블슈팅 (TS-01 두산 API 초기화 … TS-08 수조 안에서 HOME 으로 가다 충돌) | [docs/troubleshooting/](docs/troubleshooting/) |
| PC 환경 설정 · 별칭 | [docs/setup/M0609_환경설정.md](docs/setup/M0609_환경설정.md) |
| 팀 규칙 (에이전트 공통) · 기여 규칙 (브랜치 · PR · 검토) | [AGENTS.md](AGENTS.md) · [CONTRIBUTING.md](CONTRIBUTING.md) |
| 일정표 (구글 시트 · 실시간 정본) | [일정표](https://docs.google.com/spreadsheets/d/1ikTAYTa8bgZofF_3RgP5jDoOipSZBPB1/edit?usp=sharing) · 터미널 `python3 tools/sched.py [담당\|taskID]` |
| 그림 — **시스템 아키텍처(대화형)** · 워크셀 · 셀 평면도 | [docs/images/system_architecture_pc.html](docs/images/system_architecture_pc.html)(브라우저로 열기 · 보기 전환 · Present) · [docs/images/](docs/images/) · 그리는 법은 `tools/gen/README.md` |
| 팀원 온보딩 · 에이전트 프롬프트 | [docs/00_팀원_시작가이드.md](docs/00_팀원_시작가이드.md) · [docs/prompts/](docs/prompts/) |

## 6. 팀이 지키는 규칙 (요약)
1. `main` 직접 push 금지 — 브랜치 → PR → 자동 검사 + PM 검토(자동 시험 두 환경) → merge. PR 승인 코멘트에 **검증 수준(자동/가상/실기)** 을 항상 적는다.
2. 접촉 동작에는 힘 상한 · 후퇴 · 타임아웃. 로봇 위치를 모르면(정지 · 이동 미완) **자동으로 움직이지 않는다** — 사람이 복구.
3. 숫자는 YAML, 코드에 하드코딩 금지 · 두산 API는 `cobot_common` 안에서만.
4. 인터페이스(IRD)는 계약 — 혼자 바꾸지 않는다(4명 확인).
5. 단위 기능 테스트 먼저, 통합은 일정표의 통합 슬롯에서. 실기 시작 전 툴·TCP 이름 확인, 끝나면 Ctrl+C 뒤 랜선.

## 저장소 구조
```
rokey_pjt01_ws/            ← clone 폴더 = ROS 2 워크스페이스
├── README.md AGENTS.md CLAUDE.md CONTRIBUTING.md
├── docs/                  문서 · 인터페이스 정본 · 결정 기록 · 시험 기록 · 트러블슈팅 · 그림 · 프롬프트
├── src/                   ROS 2 패키지 8개 (cobot_api cobot_msgs cobot_common f1_handling f2_sense_flow f3_wipe f4_hmi prewash_bringup)
│   └── */test/            pytest(test_*.py) + 실기·가상 시험대(rig_*.py — pytest 는 모으지 않음)
├── tools/                 PR 자동 검사(pr_check.sh · pr_open.py) · 일정표 조회(sched.py) · 일정표 패치·구글 시트 반영(gen/)
└── build/ install/ log/   (.gitignore)
```
