# PreWash-Cell — 경기장 다회용기 예비세척 · 식기세척기 팔레트 적재 자동화 셀

> 경기장에서 반납된 **다회용 그릇·컵**을 협동로봇이 집어 **잔반을 털고, 안쪽을 힘 제어로 닦고, 헹군 뒤 식기세척기 팔레트에 꽂는다.**
> 카메라 없이 **파지 폭 · 무게 · 힘**만으로 판단한다. 본세척은 식기세척기가 맡는다.

| 항목 | 내용 |
|---|---|
| 로봇 · 그리퍼 | Doosan **M0609** (6축 협동로봇) + OnRobot **RG2** (0~110 mm · 3~40 N) |
| 소프트웨어 | Ubuntu 24.04 · **ROS 2 Jazzy** · Python 3.12 · FastAPI + Next.js(운영 화면) · SQLite |
| 처리 대상 | 그릇 1규격 2개 + 컵 1규격 2개 → 팔레트 4칸(그릇 2 · 컵 2) |
| 판단 수단 | 파지 폭(빈손/용기/툴 구분) · 하중 측정(잔반 ≥ 50 g) · 툴 힘센서(닦기 힘 제어 · 넛지 재개) — **비전 없음** |
| 결과 | 시작 1회로 **그릇 2 → 컵 2 완주 3회**(9/23 실기 · 배속 0.5 · 사람 개입 0 · 튜닝 뒤 3회차 무정지 17분 39초) · 9/29 오전 1회차(배속 1.0) 무정지(DONE 4 · 멈춤 0 · 약 13분) · 9/29 예외 6종 + 빈 시작 실기 통과 · 9/29 리허설(배속 1.0 · 약 9분) 그릇 1 · 컵 2 · 격리 0 완료(그릇은 1개만 놓아 B2 칸 건너뜀 · 새 컵 칸 C1·C2 자세로 곧게 적재 ✅) · 자동 시험 **606개** 통과(`pytest src` · 로봇 없이) · 수락 기준 7개 모두 ✅(AC-4 의 닦기 힘 상한 즉시 정지 E60 은 자동 시험만 · 실기 미실시) |
| 팀 | ROKEY 9기 협동1 · D그룹 2조 — 한석형(팀장 · 파지·이송·적재) · 민범진(무게·털기·헹굼 · 흐름) · 박진용(접촉 닦기 · 공용 로봇 함수) · 황인재(PM · 운영 화면 · 통합) |
| 기간 | 2026-09-18 ~ 09-30 (개발 6일 · 기능 동결 9/23 · 최종 시연 9/29 · 제출 9/30) |

<p align="center">
  <img src="docs/images/system_architecture_pc.png" width="900" alt="시스템 아키텍처"><br>
  <sub>시스템 아키텍처 — 시연은 PC 2대: GPU PC(로봇 제어 · Discovery Server · 브링업 · flow) + 화면 PC(hmi_bridge · 브라우저 · 기록 DB) · 대화형 판은 <a href="docs/images/system_architecture_pc.html">docs/images/system_architecture_pc.html</a></sub>
</p>

---

## 1. 무엇을 하는가 — 용기 1개가 도는 길

```
반납 구역 ──집기──▶ HOME 을 거쳐 저울 자세 ──무게──▶ (잔반 ≥ 50 g 이면 잔반통 위에서 기울여 털고 다시 잰다)
        ──▶ 스펀지 홈에 놓기 ──▶ 툴 집기(그릇 수세미 · 컵 솔) → 세제 → 안쪽 닦기(힘 제어) → 툴 반납
        ──▶ 다시 집기(컵은 옆면으로) ──▶ 헹굼 담금 2회 → 곧게 위로 → 털기 자세에서 손목 좌우 3회
        ──▶ 식기세척기 팔레트 칸에 꽂기(컵은 뒤집어) ──▶ HOME → 다음 용기
```

- 운영자는 화면에서 **시작 1번**만 누른다. 그릇 2개 → 컵 2개를 계획 순서대로 처리하고 용기마다 기록을 남긴다.
- 반납 구역은 구역마다 고정 슬롯 2개다 — 슬롯 1부터 집고, 비어 있으면 슬롯 2(E41). 그릇은 옆면(벽)을 세로로, 컵은 테두리를 위에서 집고 파지 폭으로 성공을 판정한다.
- 뒷면·바깥면은 닦지 않는다. "닦임"은 공정 완료이지 위생 판정이 아니다.

<p align="center">
  <img src="docs/images/layout_workcell.png" width="700" alt="워크셀 배치도(위에서 본 그림)"><br>
  <sub>워크셀 배치(위에서 본 그림 · 9/28 실제 배치 기준) — 맨 위 헹굼 구역(흐르는 물) · 왼쪽 반납 구역(그릇·컵 슬롯 1·2) · 가운데 툴 홀더(세제 = 홀더 비눗물)·스펀지 홈과 로봇(앞 +X 는 스펀지 홈 쪽) · 오른쪽 잔반통·격리 구역 · 아래 팔레트 4칸</sub>
</p>

## 2. 시스템 구성

**PC 2대 · 프로그램 2개.** 기능은 노드가 아니라 **파이썬 함수 모듈**이고, 메인 프로그램이 순서대로 부른다. 로봇 명령은 메인 프로그램의 메인 스레드에서만 나간다.

| 어디 | 프로그램 | 하는 일 |
|---|---|---|
| **GPU PC** (로봇 제어 · 로봇과 유선) | `flow_node` (`f2_sense_flow`) | 메인 프로그램. 상태 머신으로 기능 함수를 차례로 부르고 실패 정책 · 정지/재개/중단 · 용기별 기록(`records.csv`)을 맡는다. 같은 PC 에서 두산 드라이버 브링업과 Fast DDS Discovery Server 도 돈다 |
| **화면 PC** (강의실 무선) | `hmi_bridge` (`f4_hmi`) + 웹 화면 | 브라우저 운영 화면(시작·일시 정지·재개·중단 · 단계 카드 · 멈춤 원인별 안내 · 팔레트 · 소모품 · 누적 KPI · 이력) · 기록 DB(SQLite `prewash.db`) |

로봇에 명령을 내는 PC 는 GPU PC 하나뿐이다. 두 PC 는 강의실 무선의 같은 망에 있는데, 이 무선이 ROS 2 기본 탐색(멀티캐스트)을 막아 GPU PC 의 **Fast DDS Discovery Server** 로 서로를 찾는다(실행 순서는 §5-6). PC 1대로 돌릴 수도 있다(`hmi:=true`).

| 패키지 | 담당 | 함수 | 한 줄 |
|---|---|---|---|
| `f1_handling` | 한석형 | `pick` `regrip_top` `place` `move_to` `tool` `rack_place` | 집기 · 격리 정리 때 홈의 용기 위에서 다시 잡기 · 놓기 · 이동 · 툴 집기/반납 · 팔레트 꽂기 |
| `f2_sense_flow` | 민범진 · 황인재(통합) | `weigh` `leftover_loop` `shake` `dip` + `flow.py` `flow_node.py` | 무게 · 잔반 버리기 · 헹굼 담금 · 물 털기 + **흐름(상태 머신)** |
| `f3_wipe` | 박진용 | `soap` `wipe_bowl` `wipe_cup` | 세제 · 그릇 닦기(나선 + 벽면 힘 제어) · 컵 닦기(솔 회전) |
| `f4_hmi` | 황인재 | `hmi_bridge` · `web/`(Next.js) · `hmi_db` · `fake_state_pub` | 운영 화면 · 기록 DB · KPI · 가짜 흐름(로봇 없이 화면 시험) |
| `cobot_common` | 4명 분담 | `bootstrap` `motion` `gripper` `weigh` `force` | 두산 API·그리퍼를 감싼 **공용 로봇 함수** — 두산 함수는 여기서만 부른다 |
| `cobot_api` · `cobot_msgs` | 황인재 | `contracts.py` · `FlowState` `FlowEvent` | 함수 약속과 메시지(팀 계약) |
| `prewash_bringup` | 황인재 | `prewash.launch.py` · `prewash_mock.launch.py` | 실행 묶음(실기 · 로봇 없이) |

좌표·힘·횟수·시간 같은 숫자는 코드가 아니라 `src/cobot_common/config/cell.yaml`(좌표 · 프리셋 · 팔레트 칸 · 반납 슬롯)과 `params.yaml`(기능별 값 · 빈 용기 기준값 · 시간 상한 · 실패 정책)에 있다.

## 3. 핵심 설계

- **비전 없는 판단**: 집었는지는 파지 폭(그릇 벽 ≈ 2 mm · 컵 테두리 · 툴 25.6/18.9 mm)으로, 잔반은 하중 측정(항상 HOME 을 거쳐 같은 자세에서 · 빈 용기 기준값은 실행 직전 1회)으로, 닦기는 툴 힘센서로 판단한다.
- **힘 제어 닦기**: 그릇 바닥은 접촉 하강으로 찾고(수세미가 물러 깊이가 매번 다름) 벽은 치수로 계산한다. 누르는 힘 상한 · 옆 힘 상한 · 시간 상한을 넘으면 남은 동작을 즉시 멈추고 후퇴한다. 컵은 솔을 회전시켜 닦는다.
- **지정 좌표 하강은 곧게**: 물체가 항상 지정 좌표에 있으므로 놓기 · 팔레트 적재 · 툴 반납 · 재파지는 높은 접근점에서 자세를 맞춘 뒤 Z 만 곧게 내린다(마지막 15 mm 완충). 힘 감시는 접촉 동작(닦기 · 바닥 찾기)에만 쓴다.
- **예외 처리**: 빈 구역 → 건너뜀 / 잔반이 계속 남음 → 자동 격리 / 툴 집기 실패 → 멈춤 → 홀더 확인 → 로봇을 가볍게 밀거나 화면 재개 → 다시 집기 / 툴 놓침 → 멈춤 → 홀더에 꽂고 가볍게 밀기·재개 → 곧게 위로 → 툴 집기 → 세제 → 닦기(E62) / 케이블 당김(무게 떨림) → 멈춤 → 가볍게 밀거나 화면 재개 → 바로 재개(밀기였으면 손 뗄 시간 1.5 s → 보호정지 복구 · 풀었으면 2 s 더) → 무게 단계를 처음부터 다시 재며 케이블을 다시 봄 → 아직 떨리면 같은 케이블 멈춤이 다시 걸리고 새 신호를 기다림(E64 · 리허설 실기 ✅ — 떨림 156 g → 밀기 1번 → 무게 다시 통과 · 멈춤 약 8 s) / 힘 상한 · 시간 초과 → 남은 나선·주기 운동 즉시 정지 → 힘 끄고 곧게 위로(E60 · 자동 시험만 — 실기 미실시) → 툴을 쥐고 있으면 그 자리에서 한 번 더 닦기, 없으면 툴 놓침 멈춤(E61) → 또 실패하면 중단과 같은 순서로 정리 후 격리 / 운영자 일시 정지 → 재개 한 번이면 하던 동작부터 이어 감(9/29 수정 · 실기 ✅ — 닦기 중 정지 → 재개 한 번 → 다시 안 멈춤) / 운영자 중단 → 곧게 위로 → HOME → 툴 반납 → 스펀지 홈의 용기는 놓았던 자세에서 위로 다시 잡기 → HOME → 격리 → HOME(정리 순서 하나로 통일 · 다시 못 잡으면 용기는 홈에 두고 빈손으로 HOME · E65) / 로봇 오류 → 그 자리 멈춤, 쥔 것이 있으면 사람 신호 뒤 손만 열어 넘기고 HOME(안전망). 격리 자리는 그릇·컵 한 곳이라 시작 전에 격리 구역을 비우고, 격리가 생기면 다음 격리 전에 사람이 치운다(E65).
- **안전**: 접촉 동작마다 힘 상한 · 후퇴 · 타임아웃. 로봇 위치를 모르는 상태에서는 자동으로 움직이지 않는다. 수조 안에서는 먼저 곧게 위로. 빈손이면 털기·담금을 거부. 실행 전 툴·TCP 이름을 문지기가 확인.
- **공용 로봇 함수 · 메인 스레드**: 두산 API 는 `cobot_common` 안에서만, 로봇 함수는 메인 스레드에서만 부른다(콜백·타이머에서 부르면 실행기가 교착 — `docs/troubleshooting/TS-01`).
- **운영 화면 · 기록**: 상태 2 Hz · 이벤트를 WebSocket 으로 화면에, SQLite 5개 표(용기 · 실행 · 멈춤 · 명령 · 소모품 교체)에 기록. 누적 KPI(처리량 · 처리율 · 용기당 평균 · 멈춤 · 잔반)와 소모품(수세미 · 솔 · 세제 · 잔반통) 교체 관리는 로봇 코드를 바꾸지 않고 화면 쪽에서 한다.

<p align="center">
  <img src="docs/images/hmi_running.png" width="46%" alt="운영 화면 — 진행 중">
  <img src="docs/images/hmi_kpi.png" width="46%" alt="운영 화면 — 완료 · KPI"><br>
  <sub>운영 화면(가짜 흐름으로 찍은 예시) — 진행 중 / 완료 · 소모품 · 누적 KPI</sub>
</p>

## 4. 결과

검증 수준: **자동** = pytest(로봇 없이) · **가상** = RViz 가상 로봇 · **실기** = 실제 로봇. 자세한 수치·근거는 [docs/04_결과_결과표.md](docs/04_결과_결과표.md).

| 수락 기준 | 현황 |
|---|---|
| AC-1 완전성 — 시작 1회로 그릇 2 · 컵 2 처리 → 팔레트 | ✅ 실기 3회 완주(9/23 · 배속 0.5 · 개입 0 · 앞 2회는 자동 재시도 1회 · 3회차 무정지 17분 39초) · 9/29 오전 1회차(배속 1.0) 무정지(09:26 → 09:39 · DONE 4 · 멈춤 0 · 약 13분) |
| AC-2 잔반 판정 — 대용품 감지 · 빈 용기 오판 0 | ✅ 98 g 대용품 4/4 감지 · 빈 용기 8/8 통과 · 9/29 1회차 대용품 94 g 감지(85.5 g → 털기 1회 → 15.8 g) |
| AC-3 파지·안착 ≥ 90 % | ✅ 슬롯 집기 12/12 · 스펀지 홈 놓기 12/12 · 컵 옆면 재파지 6/6 |
| AC-4 힘 안정성 — 닦기 힘 유지 · 상한 초과 후퇴 · 힘 로그 | ✅ 그릇 평균 2.6 N · 최대 6.9 N(상한 10 N) · 컵 최대 3.4 N · CSV 힘 로그 · 상한 초과 때 남은 동작 즉시 정지 → 곧게 위로(E60)는 자동 시험만(실기 미실시) |
| AC-5 적재 — 낙하 0 · 칸·각도 | ✅ 팔레트 12/12 · 낙하 0 · 컵은 뒤집어 적재 |
| AC-6 지속성 — 실패 주입 뒤 정의대로 복구 | ✅ 9/29 실기(흐름 안 예외 6종 + 빈 시작 · 번호는 결과표 §7-1) — 2회차: ② 정지·재개 ✅(재개를 두 번 눌러야 했음 → 한 번이면 이어 가게 고침 → 11:44 닦기 중 정지 → 재개 한 번 → 다시 안 멈춤 ✅) · ④ 잔반 남음 → 사람 없이 자동 격리 ✅ · ① 케이블(떨림 103 g) → 멈춤 → 밀어 재개 → 무게 다시 통과 ✅(옛 방식) · 밀면 바로 재개하는 새 방식 E64 ✅(리허설 12:26 · 떨림 156 g → 밀기 1번 → 2 s 대기 → 무게 다시 −3.9 g 통과 · 멈춤 약 8 s) · ③ 툴 놓침(세제 중 솔 뽑기) → 밀기 → 곧게 위로 → 툴 집기부터 다시 → 닦기 ✅(E62) · ⑨ 툴 집기 실패 → 솔 꽂고 밀기 → 다시 집기 ✅ / ⑤ 중단(따로 확인): 닦기 중 → 솔 반납 → 홈의 컵을 위에서 다시 잡아 격리 ✅(E65) · 헹굼 중 → 쥔 채 격리 ✅ / 3회차 빈 시작 → 두 구역 건너뜀 ✅ / ⑩ 로봇 오류 2단은 시험·발표 제외(E55 · 코드는 안전망) |
| AC-7 입출력 — 화면 표시 · 기록 누락 0 | ✅ 화면 · 용기별 기록 · 이벤트 4/4 · 실제 flow 연결·DB 기록(9/29 1회차 DB events) ✅ · 소리(멈춤 1번 · 재개 2번) ✅(9/29) · 두 PC(와이파이 경유) 버튼 응답 7~96 ms ✅ |

| 용기별 사이클 타임(초) | 그릇 1 | 그릇 2 | 컵 1 | 컵 2 |
|---|---|---|---|---|
| 배속 0.5(9/23) — 집기 → 무게(잔반 루프 포함) → 안착 → 세제 → 닦기 → 헹굼 → 적재 | 204 | 297(잔반 루프 1회) | 274 | 283 |
| 용기 합계(배속 1.0 · 9/29) | 153 | 219(털기 1회) | 182 | 192 |

배속 1.0 은 용기별 합계만 기록했다(단계별 값은 기록하지 않음 · 총 약 13분). 배속 0.5 의 단계별 값은 결과표 §3 에 있다.

사고에서 배운 것(주요 실기 사고 4건 — TCP 선택 풀림 · 수조 안에서 HOME 이동 충돌 · 재파지 관절 이동 동선 · 1.0 배속 반납 하강 — 과 소프트웨어 크래시 1건)은 결과표 §6 과 [docs/troubleshooting/](docs/troubleshooting/)에 정리했다.

### 알려진 제한
- 닦기 동작 중에 일시 정지를 누르면 그 동작이 끝난 뒤에 멈춘다(컵 주기 운동 ≈ 13 s · 그릇 나선 ≈ 3 s — 동작이 끝나기를 기다리는 동안 정지 신호를 보지 않는다).
- 격리 구역은 그릇·컵 한 곳이다. 한 실행에서 격리가 두 번 생기면 두 번째가 첫 번째 위로 내려가므로, 시작 전에 격리 구역을 비우고 격리가 생기면 다음 격리 전에 사람이 치운다(E65).
- 닦기 힘 상한·시간 초과 때 남은 동작을 즉시 멈추는 갈래(E60)는 자동 시험으로만 확인했다(실기 미실시).
- 중단으로 격리한 용기는 이력에 '관리자 격리'(`OPERATOR_ABORT` · E68)로 기록된다 — 9/29 오후에 고친 것이라 실기 확인 전이다.

### 향후 개선
- 닦기 동작 중 일시 정지도 바로 멈추기 — 남은 동작을 즉시 멈추고(E60 과 같은 방식) 재개 때 닦기를 처음부터 한다.
- 세제 펌프(세제 자동 보충) — 이번에는 툴 홀더의 비눗물에 담그는 방식으로 충분해 쓰지 않았다(E66).

## 5. 실행 방법

명령은 위에서 아래로 **그대로 복사해 치면 된다.** 저장소는 홈 폴더의 `~/rokey_pjt01_ws` 에 받는다고 적었다(다른 곳에 받았으면 명령의 `~/rokey_pjt01_ws` 만 그 경로로 바꾼다). 새 터미널을 열 때마다 그 절의 "터미널 준비" 줄부터 친다.

| 하고 싶은 것 | 더 필요한 것 | 따라갈 절 |
|---|---|---|
| **로봇 없이** 화면과 흐름 보기 | 없음(ROS 2 Jazzy 만) | 5-1 → 5-2 |
| 가상 로봇(RViz) | 두산 드라이버 워크스페이스 | 5-1 → 5-3 → 5-4 |
| 실제 로봇 — PC 1대 | + M0609 · RG2 · 워크셀 | 5-1 → 5-3 → 5-5 |
| 실제 로봇 — 시연(PC 2대) | + 같은 망의 두 번째 PC | 5-1(두 PC) → 5-3(GPU PC) → 5-6 |

### 5-1. 설치 · 빌드 · 자동 시험 (처음 한 번)

준비물은 Ubuntu 24.04 와 **ROS 2 Jazzy**(`ros-jazzy-desktop`)다. ROS 가 없으면 [ROS 2 Jazzy 공식 설치 안내](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html)나 [환경 설정 문서 §4~5](docs/setup/M0609_환경설정.md)대로 먼저 설치한다.

```bash
# ① 도구 설치
sudo apt update && sudo apt install -y git python3-colcon-common-extensions python3-pytest python3-venv python3-pymodbus nodejs npm
```
```bash
# ② 받기 · 빌드 · 자동 시험
cd ~ && git clone https://github.com/hwang-injae/rokey_9_pjt1_D2.git rokey_pjt01_ws
cd ~/rokey_pjt01_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
python3 -m pytest -q src
```
- 통과 기준: 빌드는 `Summary: 8 packages finished`, 시험은 `606 passed, 8 skipped, 1 xfailed` 이고 `failed` 가 없다. 건너뛴 8개는 아래 ③의 웹 부품이 있어야 도는 화면 시험이다(`~/venvs/hmi/bin/python -m pytest -q src/f4_hmi` 로 돌리면 48개 모두 실행).

```bash
# ③ 운영 화면 부품 — 화면을 띄울 PC 에서
python3 -m venv --system-site-packages ~/venvs/hmi
~/venvs/hmi/bin/pip install fastapi "uvicorn[standard]" websockets
cd ~/rokey_pjt01_ws/src/f4_hmi/web && npm install && npm run build && cd ~/rokey_pjt01_ws
```
- 통과 기준: `npm run build` 끝에 `(Static)  prerendered as static content` 가 나오고 `src/f4_hmi/web/out/index.html` 이 생긴다. Node.js 는 18.18 이상이면 된다(Ubuntu 24.04 기본 18.19 로 확인).
- 코드를 새로 받았으면(`git pull`) `colcon build --symlink-install` 을 다시 한다 — 새로 생긴 파일은 다시 빌드해야 설치된다. 화면(`web/`)이 바뀌었으면 `npm run build` 도 다시 한다.

### 5-2. 로봇 없이 — 화면과 흐름

```bash
# 터미널 준비 + 실행
cd ~/rokey_pjt01_ws
source /opt/ros/jazzy/setup.bash && source install/setup.bash
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST          # 이 PC 밖으로 토픽이 나가지 않게
ros2 launch prewash_bringup prewash_mock.launch.py      # 메인 프로그램 + 화면을 가짜 기능으로
```
- 볼 것: 터미널에 `IDLE — /flow/start 를 기다린다` 와 `HMI 서버를 연다 → http://localhost:8000` 이 나온다.
- 브라우저에서 <http://localhost:8000> 을 열고 **시작**을 누른다 → 약 20초 뒤 그릇 2 · 컵 2 완료(가짜 기능이라 빨리 끝난다).
- `motion.setup_io 를 건너뛴다` · `gripper.setup_io 를 건너뛴다` 경고는 두산 드라이버가 없을 때 나오는 정상 안내다.
- 끄기: 터미널에서 Ctrl+C.

멈춤 화면(툴 놓침 · 케이블 …)을 골라 보려면 launch 대신 터미널 2개로 돌린다. 두 터미널 모두 위 첫 세 줄(`cd` · `source` · `export`)을 먼저 친다. launch 와 이 방법은 같은 포트·토픽을 쓰므로 한 번에 하나만 켠다.
```bash
ros2 run f4_hmi hmi_bridge                              # 터미널 1: 화면 서버 → http://localhost:8000
```
```bash
ros2 run f4_hmi fake_state_pub tool_lost                # 터미널 2: 가짜 흐름 대본(normal · paused · isolate · error · empty_zone · tool_lost · leftover_remain · cable · tool_fail)
```
```bash
ros2 run f4_hmi hmi_db kpi                              # 기록 DB 조회(tables · dump · usage · kpi · replace · export)
```

### 5-3. 두산 드라이버 워크스페이스 (가상 · 실제 로봇에만)

두산 · OnRobot 드라이버는 이 저장소에 없다. 교육 과정 배포본(`doosan-robot2` · `onrobot_rg2` · `m0609_rg2_bringup`)을 `~/ws_cobot_pjt/ws_dsr` 에 받아 빌드한다 — 의존성 · 에뮬레이터 · 빌드 절차는 [환경 설정 문서 §8](docs/setup/M0609_환경설정.md)에 있다.

```bash
# 확인
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
ros2 pkg prefix m0609_rg2_bringup && python3 -c "import DR_init; print('DR_init OK')"
```
- 통과 기준: 설치 경로 한 줄과 `DR_init OK` 가 나온다. `DR_init` 을 못 찾으면 아래 줄을 `~/.bashrc` 맨 아래에 넣고 터미널을 새로 연다.
```bash
export PYTHONPATH=$PYTHONPATH:~/ws_cobot_pjt/ws_dsr/install/dsr_common2/lib/dsr_common2/imp
```

**로봇용 터미널 준비** — 5-4 · 5-5 의 모든 터미널에서 먼저 친다.
```bash
cd ~/rokey_pjt01_ws
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash && source install/setup.bash
export ROS_DOMAIN_ID=60 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
```

### 5-4. 가상 로봇(RViz)

```bash
# 터미널 1 — 가상 브링업
ros2 launch m0609_rg2_bringup bringup.launch.py mode:=virtual host:=127.0.0.1 port:=12345 model:=m0609
```
```bash
# 터미널 2 — 전 좌표 순회
python3 src/cobot_common/test/rig_coords.py --from 1
```
- 볼 것: RViz 에 M0609 + RG2 가 뜨고, 터미널 2 를 켜면 로봇이 셀 좌표를 차례로 돈다.
- 가상 로봇에는 힘 · 무게 · 접촉이 없다. 로직은 가상/가짜 기능으로, 임계값은 실기로 맞춘다.

### 5-5. 실제 로봇 — PC 1대 · 담당자만 · 로봇 프로그램은 한 번에 하나

🚨 `src/cobot_common/config/cell.yaml` 의 좌표는 **우리 워크셀 배치**(§1 그림) 기준이다. 배치가 다른 셀에서는 좌표를 다시 티칭하기 전에 돌리지 않는다. 처음 켜는 셀 · 다시 티칭한 뒤 첫 실행은 `vel_scale:=0.3` 으로 낮춘다.

- 전제: PC 유선 주소를 `192.168.1.x/24` 로 고정(제어기 `192.168.1.100` · RG2 `192.168.1.1`) · 티치펜던트에 툴 무게와 TCP `GripperDA_v1` 등록([환경 설정 문서 10-4](docs/setup/M0609_환경설정.md)).

```bash
# 터미널 1 — 제어기 응답 확인 뒤 실기 브링업
ping -c 3 192.168.1.100
ros2 launch m0609_rg2_bringup bringup.launch.py mode:=real host:=192.168.1.100 port:=12345 model:=m0609
```
```bash
# 터미널 2 — 점검 · 빈 용기 기준값(실행 직전 1회)
ros2 service call /dsr01/dsr_controller2/tcp/get_current_tcp dsr_msgs2/srv/GetCurrentTcp      # 통과 기준: GripperDA_v1 (아니면 움직이지 않는다)
PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_f2.py empty --kind BOWL -n 1        # 빈 그릇 기준값 → params.yaml f2.empty_weight_g (컵은 --kind CUP)
```
```bash
# 터미널 2 — 메인 프로그램 + 화면
ros2 launch prewash_bringup prewash.launch.py hmi:=true     # 볼 것: 문지기 통과 → 케이블 확인 ✅ → IDLE · 화면 http://localhost:8000
```
- 시작 전에 팔레트와 격리 구역을 비우고, 반납 구역 슬롯에 그릇 · 컵을 놓는다. 화면에서 **시작**을 누른다.
- 끝낼 때: 로봇이 멈춘 뒤 터미널 2 Ctrl+C → 터미널 1 Ctrl+C. 급하면 Ctrl+C 가 아니라 E-Stop.
- 단독 기능 시험대(`src/*/test/rig_*.py`)는 용기를 손으로 시작 자리에 놓고 기능 하나만 돌린다. 볼 것과 통과 기준은 각 파일 머리말에 있다.

### 5-6. 운영(시연) 실행 — PC 2대

| PC | 맡는 일 | 네트워크 |
|---|---|---|
| **GPU PC** | 로봇 제어 · Fast DDS Discovery Server · 두산 브링업 · `flow_node`(메인 프로그램) | 로봇 제어기와 유선(고정 192.168.1.60/24 → 제어기 192.168.1.100) + 강의실 무선(Rokey_B · 받은 주소 172.18.0.101 = Discovery Server 주소) |
| **화면 PC** | `hmi_bridge` · 브라우저 · 기록 DB(`prewash.db`) | 같은 강의실 무선(Rokey_B · 172.18.0.x) · 로봇에는 붙지 않는다 |

- **왜 Discovery Server**: 강의실 무선은 ROS 2 기본 탐색(멀티캐스트)을 막는다. 그래서 두 PC 가 GPU PC 에 띄운 Discovery Server 에 붙어 서로를 찾는다. 손님망(Rokey_Guest)은 PC 끼리 ping 도 되지 않아 두 PC 모두 Rokey_B 를 쓴다(9/29 · ping 약 6 ms).
- **실기 제어 PC 는 GPU PC 하나뿐**이다. 화면 PC 에서 브링업 · launch 를 하지 않는다.
- 설치: GPU PC 는 5-1 의 ① ② 와 5-3, 화면 PC 는 5-1 의 ① ② ③.

**먼저 — GPU PC 의 무선 주소 확인**
```bash
hostname -I                  # GPU PC 에서. 무선 쪽 주소(예: 172.18.0.101)를 적어 둔다
```
아래 모든 터미널의 첫 줄 `export GPU_IP=172.18.0.101` 은 9/29 에 받은 주소다. 다르게 나왔으면 **그 값으로 바꿔서** 친다. 그다음 GPU PC 에서 `ping -c 3 192.168.1.100`(로봇 제어기), 화면 PC 에서 `ping -c 3 172.18.0.101`(GPU PC)이 응답하는지 본다.

**GPU PC — 터미널 3개 · 순서 A(서버) → B(브링업) → C(flow)**

```bash
# 터미널 A — Discovery Server (시연 끝까지 켜 둔다)
export GPU_IP=172.18.0.101
source /opt/ros/jazzy/setup.bash
fastdds discovery --server-id 0 --udp-address $GPU_IP --udp-port 11811
```
`fastdds` 명령은 ROS Jazzy 에 들어 있다(`ros-jazzy-fastrtps`). 없을 때만 `sudo apt install fastdds-tools`.

```bash
# 터미널 B — 실기 브링업 (환경변수 줄을 브링업에도 꼭 넣는다 — flow 만 서버를 쓰면 같은 PC 안에서도 드라이버를 못 찾는다)
export GPU_IP=172.18.0.101
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp ROS_DISCOVERY_SERVER=$GPU_IP:11811 ROS_SUPER_CLIENT=TRUE ROS_DOMAIN_ID=60 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET && unset ROS_STATIC_PEERS
ros2 daemon stop && ros2 daemon start
ros2 launch m0609_rg2_bringup bringup.launch.py mode:=real host:=192.168.1.100 port:=12345 model:=m0609
```
```bash
# 터미널 C — 메인 프로그램
export GPU_IP=172.18.0.101
cd ~/rokey_pjt01_ws
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash && source install/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp ROS_DISCOVERY_SERVER=$GPU_IP:11811 ROS_SUPER_CLIENT=TRUE ROS_DOMAIN_ID=60 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET && unset ROS_STATIC_PEERS
ros2 launch prewash_bringup prewash.launch.py      # 볼 것: 문지기 통과 → 케이블 확인 ✅ → IDLE
```
- 실기 기본 배속은 1.0 이라(E67) `vel_scale:=1.0` 은 생략해도 된다. 처음 켜는 셀 · 좌표를 다시 티칭한 뒤 첫 실행은 `vel_scale:=0.3` 을 붙인다.
- 두 PC 로 돌릴 때 GPU PC 에는 `hmi:=true` 를 붙이지 않는다 — 붙이면 웹 서버가 두 개, 기록 DB 가 두 곳이 된다. launch 첫 줄 `[prewash] … vel_scale=1 · hmi=False` 로 확인한다.
- GPU PC 워크스페이스는 `colcon build --symlink-install` 로 빌드한다(복사 빌드면 코드를 새로 받아도 옛 코드로 돈다).
- 환경변수 줄을 `~/.bashrc` 에 넣어 두면 매번 치지 않아도 되지만, 그러면 서버(A)가 켜져 있어야만 ROS 가 동작한다.

**화면 PC — 터미널 1개**

```bash
export GPU_IP=172.18.0.101
cd ~/rokey_pjt01_ws
source /opt/ros/jazzy/setup.bash && source install/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp ROS_DISCOVERY_SERVER=$GPU_IP:11811 ROS_SUPER_CLIENT=TRUE ROS_DOMAIN_ID=60 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET && unset ROS_STATIC_PEERS
ros2 daemon stop && ros2 daemon start
ros2 run f4_hmi hmi_bridge                         # 브라우저 http://localhost:8000 — 버튼이 아래 서비스를 부른다
```
- 기록 DB(`prewash.db`)는 화면 PC 의 `~/rokey_pjt01_ws` 에 쌓인다. 웹 부품(`~/venvs/hmi` · `npm run build`)은 화면 PC 에만 설치한다. 화면 PC 에는 두산 드라이버 워크스페이스가 없어도 된다.
- 이 설정은 그 터미널에만 적용된다. 새 터미널은 기본으로 돌아가므로, 화면 PC 의 ROS 명령은 위 줄들을 넣은 터미널에서 친다.

화면 버튼과 같은 서비스(환경변수 줄을 넣은 터미널에서):
```bash
ros2 service call /flow/start  std_srvs/srv/Trigger      # 시작 — 계획대로 그릇 2 → 컵 2 · 끝나면 IDLE
ros2 service call /flow/stop   std_srvs/srv/Trigger      # 즉시 일시 정지(이동 중에도 · 닦기 동작 중이면 그 동작이 끝난 뒤)
ros2 service call /flow/resume std_srvs/srv/Trigger      # 재개 — 실패로 멈췄으면 그 단계부터
ros2 service call /flow/abort  std_srvs/srv/Trigger      # 멈춤 중에만: 이 용기를 격리하고 다음 용기로(로봇 오류로 멈췄을 때는 거부)
```

**연결 확인 · 통과 기준**(화면 PC 에서 환경변수 줄을 넣은 터미널)

```bash
ros2 topic list | grep -E '/flow/state|/flow/event|/dsr01/joint_states'
ros2 node list  | grep -E 'flow_node|dsr_controller2|hmi_bridge'
ros2 topic hz /flow/state                          # 또는 ros2 topic echo /flow/state --once
```
- 토픽 `/flow/state` · `/flow/event` · `/dsr01/joint_states` 와 노드 `/flow_node` · `/dsr01/flow_node_dsr` · `/dsr01/dsr_controller2` 가 모두 보인다. `/hmi_bridge` 는 화면 PC 에서만 돈다(GPU PC 쪽에는 없어야 한다).
- `/flow/state` 가 약 2 Hz 로 들어온다.
- 브라우저의 연결 점이 초록 · 시작/정지/재개가 1 s 안에 응답 · 멈춤 비프 1번 / 재개 비프 2번이 화면 PC 에서 울린다(9/29 확인).

**끝낼 때**: 화면 PC `hmi_bridge` Ctrl+C → GPU PC 터미널 C(flow · 로봇이 멈춘 뒤) Ctrl+C → B(브링업) Ctrl+C → A(서버) Ctrl+C. 급하면 E-Stop.

**흔한 실패와 대처**(★ = 9/29 실제로 겪음)

| 증상 | 원인 | 대처 |
|---|---|---|
| `ros2: command not found` · `colcon: command not found` | 그 터미널에서 `source` 줄을 치지 않았다 · 5-1 ① 을 건너뛰었다 | 그 절의 "터미널 준비" 줄부터 다시 친다 |
| `Package 'prewash_bringup' not found` | `source install/setup.bash` 를 빼먹었거나 빌드 전이다 | `cd ~/rokey_pjt01_ws` 뒤 5-1 ② 의 빌드 · source |
| 화면 주소에 시험 페이지만 나온다 | 화면을 빌드하지 않았다 | 5-1 ③ 의 `npm install && npm run build` |
| 화면 서버가 `cannot import name … from 'pydantic…'` 로 죽는다 | 시스템에 옛 pydantic(apt `python3-pydantic` 1.x)이 깔려 있어 HMI 상자(`~/venvs/hmi`)의 새 판보다 먼저 잡힌다 | 그 터미널에서 `export PYTHONPATH=~/venvs/hmi/lib/python3.12/site-packages:$PYTHONPATH` 를 친 뒤 다시 켠다 |
| 브링업이 바로 죽는다(포트 12345) | 앞서 켠 브링업 · 에뮬레이터가 남아 있다 | `ss -tlnp \| grep 12345` 로 확인하고 남은 브링업을 끈 뒤 다시 |
| ★ 화면이 '연결 끊김'인데 토픽은 보인다 | `hmi_bridge` 를 환경변수 없는 새 터미널에서 켰다 | Ctrl+C 뒤 환경변수 줄을 넣은 터미널에서 다시 켠다 |
| ★ `ros2 topic list` 가 비어 있다 · 설정을 바꿨는데 그대로다 | 옛 ros2 데몬이 옛 설정으로 남아 있다 | `ros2 daemon stop && ros2 daemon start` · `ROS_SUPER_CLIENT=TRUE` 인지 확인 |
| ★ PC 끼리 ping 이 안 된다 | 손님망(Rokey_Guest)에 붙어 있다 | 두 PC 모두 Rokey_B 로 |
| flow 가 '두산 드라이버가 안 보인다'고 한다 | 터미널 B·C 중 환경변수 줄이 빠졌거나 서버(A)가 꺼졌다 | 서버 → 브링업 → flow 순서로 다시 켠다 |
| 새로 켠 노드끼리 서로 못 찾는다 | 서버 터미널(A)을 닫았다 | A 는 시연 끝까지 켜 둔다 · 닫았으면 서버 → 브링업 → flow 순서로 다시 |
| 8000 포트가 이미 쓰이고 있다 | 먼저 켠 `hmi_bridge` 가 남아 있다 | 남은 `hmi_bridge` 를 끄고 다시 켠다 |
| 웹 서버가 두 개 · 기록이 두 곳에 나뉜다 | GPU PC 의 flow 에 `hmi:=true` 를 붙였다 | GPU PC 에는 `hmi:=true` 를 붙이지 않는다 |
| 화면만 끊기고 로봇은 계속 돈다 | 와이파이가 끊겼다(로봇은 GPU PC 에서 계속 돈다) | 멈춰야 하면 E-Stop 또는 GPU PC 터미널 C 에서 Ctrl+C |

두 PC 가 같은 유선 스위치에 있어 멀티캐스트가 통하면 Discovery Server 없이 양쪽 터미널에서 `export ROS_DOMAIN_ID=60 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET` 만으로도 된다([환경 설정 10-5](docs/setup/M0609_환경설정.md)).

## 6. 저장소 구조 · 문서 지도

```
rokey_pjt01_ws/                ← clone 폴더 = ROS 2 워크스페이스
├── README.md
├── LICENSE                     Apache-2.0
├── docs/
│   ├── 01_요구사항_BR-SR.md    요구사항 · 수락 기준(BR · FR · NFR · SR)
│   ├── 02_인터페이스_IRD.md    함수 약속 · 메시지 · 실패 코드 · 실패 정책
│   ├── 03_설계_SDD.md          아키텍처 · 상태 머신 · 설정 양식 · 오류·안전 · 화면 · 테스트 계획
│   ├── 04_결과_결과표.md       수락 기준 현황 · 사이클 타임 · 무게·힘 · 사고와 교훈
│   ├── meetings/               결정 기록(E1~E68 · 왜 그렇게 했나)
│   ├── test_logs/              실기·가상 시험 기록(날짜_ID_내용_이름.md)
│   ├── troubleshooting/        TS-01 ~ TS-08(두산 API 초기화 · 정지 처리 · 수조 안 충돌 …)
│   ├── setup/                  PC 환경 설정
│   └── images/                 아키텍처(대화형 HTML · PNG) · 배치도(SVG · PNG) · 화면 캡처
├── src/                        ROS 2 패키지 8개 — cobot_api cobot_msgs cobot_common f1_handling f2_sense_flow f3_wipe f4_hmi prewash_bringup
│   └── */test/                 pytest(test_*.py) + 실기·가상 시험대(rig_*.py)
└── build/ install/ log/        (.gitignore)
```

| 무엇이 궁금하면 | 여기 |
|---|---|
| 요구사항 · 수락 기준 | [docs/01_요구사항_BR-SR.md](docs/01_요구사항_BR-SR.md) |
| 함수 · 메시지 약속(계약) | [docs/02_인터페이스_IRD.md](docs/02_인터페이스_IRD.md) · [`src/cobot_api/cobot_api/contracts.py`](src/cobot_api/cobot_api/contracts.py) |
| 설계 · 상태 머신 · 안전 · 화면 | [docs/03_설계_SDD.md](docs/03_설계_SDD.md) |
| 결과 · 수치 · 교훈 | [docs/04_결과_결과표.md](docs/04_결과_결과표.md) |
| 결정 기록(왜 그렇게 했나) | [docs/meetings/20260919_결정기록_DSN-03.md](docs/meetings/20260919_결정기록_DSN-03.md) · [구조·인터페이스 결정](docs/meetings/20260918_결정기록_구조_인터페이스.md) |
| 시험 기록 · 트러블슈팅 · 환경 설정 | [docs/test_logs/](docs/test_logs/) · [docs/troubleshooting/](docs/troubleshooting/) · [docs/setup/M0609_환경설정.md](docs/setup/M0609_환경설정.md) |

## 7. 팀 · 진행

| 이름 | 역할 |
|---|---|
| 한석형(팀장) | F1 파지 · 이송 · 적재 · 좌표 티칭 · 기구 · 영상 |
| 민범진 | F2 무게 · 잔반 털기 · 헹굼 · 흐름(상태 머신) · 케이블 이상 감지 |
| 박진용 | F3 세제 · 접촉 닦기(힘 제어) · 공용 힘 함수 · 안전 파라미터 |
| 황인재 | PM · F4 운영 화면 · 기록 DB · 인터페이스 정본 · 통합 · 문서 |

개발 6일(9/18~9/23) 동안 4명이 로봇 1대를 나눠 쓰며 단위 기능 → 단위 통합 → 셀 통합 → 전체 통합 순으로 올렸고, 9/23 저녁 기능을 동결한 뒤 예외 처리와 운영 화면을 다듬어 9/29 최종 시연, 9/30 제출했다. 결정은 모두 [결정 기록](docs/meetings/20260919_결정기록_DSN-03.md)에 번호(E1~E68)로 남겼다.

## 8. 라이선스

[Apache-2.0](LICENSE) — 두산·OnRobot 드라이버는 이 저장소에 포함하지 않는다(실행 방법의 두산 드라이버 워크스페이스는 따로 설치).
