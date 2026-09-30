# PreWash-Cell — 경기장 다회용기 예비세척 · 식기세척기 팔레트 적재 자동화 셀
> **조 이름:** ROKEY 9기 협동1 D-2 · 디투 (D2)
> **팀원:** 한석형(팀장) · 민범진 · 박진용 · 황인재

협동로봇이 반납된 다회용 그릇과 컵을 집어 **잔반을 털고, 안쪽을 힘 제어로 닦고, 헹군 뒤 식기세척기 팔레트에 꽂는다.**
카메라 없이 **파지 폭 · 무게 · 힘**만으로 판단한다. 본세척은 식기세척기가 맡는다.

| 항목 | 내용 |
|---|---|
| 로봇 · 그리퍼 | Doosan **M0609**(6축 협동로봇) + OnRobot **RG2** |
| 소프트웨어 | Ubuntu 24.04 · **ROS 2 Jazzy** · Python 3.12 · FastAPI + Next.js(운영 화면) · SQLite |
| 처리 대상 | 그릇 2개 + 컵 2개 → 팔레트 4칸 |
| 판단 수단 | 파지 폭 · 하중 측정 · 툴 힘센서 — **비전 없음** |
| 결과 | 시작 1번으로 그릇 2 · 컵 2 완주(배속 1.0 · 약 13분 · 사람 개입 0) · 예외 6종 복구 실기 통과 · 자동 시험 616개 통과 |
| 기간 | 2026-09-18 ~ 09-30 |

### 시연 영상 (58초 · 배속 1.0 · 그릇 2 → 컵 2)

https://github.com/user-attachments/assets/39b6fed5-1fb4-4138-8bd3-99d8b640b0f6

## 목차

1. [🎨 시스템 설계 및 플로우 차트](#1--시스템-설계-및-플로우-차트)
   - [1-1. 시스템 설계도 (System Architecture)](#1-1-시스템-설계도-system-architecture)
   - [1-2. 플로우 차트 (Flow Chart)](#1-2-플로우-차트-flow-chart)
   - [1-3. 핵심 설계 · 예외 처리](#1-3-핵심-설계--예외-처리)
2. [🖥️ 운영체제 환경 (OS Environment)](#2-️-운영체제-환경-os-environment)
3. [🛠️ 사용 장비 목록 (Hardware List)](#3-️-사용-장비-목록-hardware-list)
4. [📦 의존성 (Dependencies)](#4--의존성-dependencies)
5. [▶️ 실행 순서 (Usage Guide)](#5-️-실행-순서-usage-guide)
   - [Step 1. 설치 · 빌드 · 자동 시험 (처음 한 번)](#step-1-설치--빌드--자동-시험-처음-한-번)
   - [Step 2. 로봇 없이 실행](#step-2-로봇-없이-실행)
   - [Step 3. 두산 드라이버 (처음 한 번)](#step-3-두산-드라이버-처음-한-번)
   - [Step 4. 가상 로봇](#step-4-가상-로봇)
   - [Step 5. 실제 로봇 — PC 1대](#step-5-실제-로봇--pc-1대)
   - [Step 6. 실제 로봇 — PC 2대](#step-6-실제-로봇--pc-2대)
   - [Step 7. 문제가 생기면](#step-7-문제가-생기면)
6. [결과](#6-결과)
7. [저장소 구조 · 문서 지도](#7-저장소-구조--문서-지도)
8. [팀](#8-팀)
9. [라이선스](#9-라이선스)

---

## 1. 🎨 시스템 설계 및 플로우 차트
프로젝트의 전체 구조와 소프트웨어 흐름도다.

### 1-1. 시스템 설계도 (System Architecture)
<p align="center">
  <img src="docs/images/system_architecture_pc.png" width="900" alt="시스템 설계도"><br>
  <sub>시스템 설계도 — 대화형 판은 <a href="docs/images/system_architecture_pc.html">docs/images/system_architecture_pc.html</a></sub>
</p>

* *설명: PC 2대 · 프로그램(노드) 2개. GPU PC 의 `flow_node` 가 로봇을 움직이고, 화면 PC 의 `hmi_bridge` 가 ROS 토픽 3개를 받아 브라우저에 보여 주며 버튼 4개를 서비스로 보낸다. 기능(집기 · 무게 · 닦기 …)은 노드가 아니라 파이썬 함수다.*

**PC 2대 · 프로그램(노드) 2개.** 기능은 노드가 아니라 **파이썬 함수**이고, 메인 프로그램이 순서대로 부른다.

| 어디 | 프로그램 | 하는 일 |
|---|---|---|
| **GPU PC** (로봇과 유선) | `flow_node` | 메인 프로그램. 기능 함수를 순서대로 부르고, 실패 처리 · 정지/재개/중단 · 용기별 기록(`records.csv`)을 맡는다 |
| **화면 PC** (무선) | `hmi_bridge` + 웹 화면 | 운영 화면(버튼 · 단계 · 멈춤 안내 · 팔레트 · 소모품 · 누적 통계 · 이력)과 기록 DB(`prewash.db`) |

로봇에 명령을 내는 PC 는 GPU PC 하나뿐이다. PC 1대로도 돌릴 수 있다([Step 5](#step-5-실제-로봇--pc-1대)).

#### 패키지 8개

| 패키지 | 담당 | 내용 |
|---|---|---|
| `f1_handling` | 한석형 | 집기 · 놓기 · 이동 · 툴 집기/반납 · 팔레트 꽂기 (함수 6개) |
| `f2_sense_flow` | 민범진 · 황인재 | 무게 · 잔반 털기 · 헹굼 · 물 털기 (함수 4개) + **흐름(상태 머신)** `flow_node` |
| `f3_wipe` | 박진용 | 세제 · 그릇 닦기 · 컵 닦기 (함수 3개) |
| `f4_hmi` | 황인재 | 운영 화면 `hmi_bridge` · 웹(Next.js) · 기록 DB · 가짜 흐름(로봇 없이 화면 시험) |
| `cobot_common` | 4명 분담 | 두산 API 와 그리퍼를 감싼 **공용 로봇 함수**(이동 · 그리퍼 · 힘 · 무게) |
| `cobot_api` | 황인재 | 기능 함수 13개의 **약속**(이름 · 인자 · 결과 · 실패 코드) |
| `cobot_msgs` | 황인재 | **메시지 3개**(`FlowState` · `FlowEvent` · `WeighLive`) |
| `prewash_bringup` | 황인재 | 실행 묶음(실기용 · 로봇 없이) |

#### 두 프로그램 사이의 통신

| 이름 | 종류 | 방향 | 내용 |
|---|---|---|---|
| `/flow/state` | 토픽 · 1초에 2번 | `flow_node` → `hmi_bridge` | 지금 단계 · 진행 수 · 멈춤 원인 |
| `/flow/event` | 토픽 · 용기마다 1건 | `flow_node` → `hmi_bridge` | 용기 1개의 결과(무게 · 걸린 시간 · 완료/격리) |
| `/flow/weigh` | 토픽 · 무게 재는 동안 | `flow_node` → `hmi_bridge` | 재고 있는 무게 값 |
| `/flow/start` · `stop` · `resume` · `abort` | 서비스 | `hmi_bridge` → `flow_node` | 화면 버튼(시작 · 일시 정지 · 재개 · 중단) |

좌표 · 힘 · 횟수 · 시간 같은 숫자는 코드가 아니라 설정 파일 두 개에 있다.

| 설정 파일 | 내용 |
|---|---|
| `src/cobot_common/config/cell.yaml` | 좌표 · 그리퍼 프리셋 · 팔레트 칸 · 반납 슬롯 |
| `src/cobot_common/config/params.yaml` | 기능별 값 · 빈 용기 기준값 · 시간 상한 · 실패 정책 |

### 1-2. 플로우 차트 (Flow Chart)
<p align="center">
  <img src="docs/images/flow_chart.png" width="900" alt="플로우 차트"><br>
  <sub>플로우 차트 — 왼쪽: 용기 1개의 정상 흐름 · 오른쪽: 어느 단계에서든 걸리는 예외 처리 (원본 <a href="docs/images/flow_chart.svg">SVG</a>)</sub>
</p>

* *설명: 화면에서 시작을 한 번 누르면 용기마다 ① 집기 → ② 무게 → ③ 안착 → ④ 닦기 → ⑤ 헹굼 → ⑥ 적재를 돌고, 멈춤 · 중단 · 격리는 오른쪽 띠의 규칙대로 처리한다. 상태 머신 전체는 [설계 문서 §5.1](docs/03_설계_SDD.md)에 있다.*

용기 1개는 아래 순서로 돈다.

```
① 집기      반납 구역에서 용기를 집는다
② 무게      저울 자세에서 무게를 잰다 → 잔반이 50 g 이상이면 잔반통 위에서 털고 다시 잰다
③ 안착      스펀지 홈에 용기를 놓는다
④ 닦기      툴 집기(그릇 = 수세미 · 컵 = 솔) → 세제 → 안쪽 닦기(힘 제어) → 툴 반납
⑤ 헹굼      용기를 다시 집어 헹굼물에 2회 담근 뒤 물을 턴다
⑥ 적재      식기세척기 팔레트 칸에 꽂는다(컵은 뒤집어서) → HOME → 다음 용기
```

- 운영자는 화면에서 **시작을 한 번** 누른다. 그릇 2개 → 컵 2개를 순서대로 처리하고 용기마다 기록을 남긴다.
- 반납 구역은 구역마다 고정 슬롯이 2개다. 슬롯 1부터 집고, 비어 있으면 슬롯 2로 간다.
- 뒷면과 바깥면은 닦지 않는다. "닦임"은 공정 완료를 뜻하며 위생 판정이 아니다.

<p align="center">
  <img src="docs/images/layout_workcell.png" width="700" alt="워크셀 배치도(위에서 본 그림)"><br>
  <sub>워크셀 배치(위에서 본 그림) — 위: 헹굼 구역 · 왼쪽: 반납 구역 · 가운데: 툴 홀더 · 스펀지 홈 · 로봇 · 오른쪽: 잔반통 · 격리 구역 · 아래: 팔레트 4칸</sub>
</p>

### 1-3. 핵심 설계 · 예외 처리

| 설계 | 내용 |
|---|---|
| **비전 없는 판단** | 집었는지는 파지 폭으로, 잔반은 무게(30번 읽은 값의 중앙값)로, 닦기는 툴 힘센서로 판단한다 |
| **힘 제어 닦기** | 그릇 바닥은 접촉으로 찾고 벽은 치수로 계산한다. 컵은 솔을 회전시켜 닦는다. 힘 · 시간 상한을 넘으면 즉시 멈추고 위로 빠진다 |
| **지정 좌표 하강은 곧게** | 놓기 · 적재 · 툴 반납은 높은 접근점에서 자세를 맞춘 뒤 Z 만 곧게 내린다 |
| **바로 멈추는 이동** | 이동 명령을 비동기로 보내고 0.05초마다 완료와 정지 신호를 확인한다. 이동 중에도 일시 정지가 바로 걸린다 |
| **로봇 명령은 한 곳에서만** | 두산 API 는 `cobot_common` 안에서만, 메인 스레드에서만 부른다. 통신은 별도 스레드가 맡는다 |
| **안전** | 접촉 동작마다 힘 상한 · 후퇴 · 시간 상한. 로봇 위치를 모르면 자동으로 움직이지 않는다. 실행 전에 툴 · TCP 설정을 확인한다 |
| **운영 화면 · 기록** | 상태와 결과를 화면에 실시간으로 보여 주고, SQLite 표 5개에 기록한다. 누적 통계와 소모품 교체는 화면에서 관리한다 |

#### 예외 처리

| 상황 | 로봇이 하는 일 | 사람이 하는 일 |
|---|---|---|
| 반납 구역이 비어 있다 | 그 구역을 건너뛴다 | 없음 |
| 털어도 잔반이 남는다 | 그 용기를 격리 구역으로 보낸다 | 없음 |
| 툴을 집지 못했다 | 멈춘다 | 홀더를 확인하고 로봇을 가볍게 밀거나 화면에서 재개 → 다시 집는다 |
| 닦는 중에 툴을 놓쳤다 | 그 자리에서 멈춘다 | 툴을 홀더에 꽂고 밀기 · 재개 → 툴 집기부터 다시 한다 |
| 케이블이 당겨진다(무게 떨림) | 멈춘다 | 케이블을 풀고 밀기 · 재개 → 무게 단계를 처음부터 다시 한다 |
| 닦기 힘 · 시간 상한을 넘었다 | 즉시 멈추고 위로 빠진 뒤 한 번 더 닦는다. 또 실패하면 격리한다 | 없음 |
| 운영자가 일시 정지했다 | 하던 동작을 멈춘다 | 재개를 누르면 하던 동작부터 이어 간다 |
| 운영자가 중단했다 | 툴을 반납하고 용기를 격리 구역으로 보낸 뒤 다음 용기로 간다 | 없음 (이력에 "관리자 격리"로 남는다) |
| 로봇 오류(보호 정지 등) | 그 자리에서 멈추고 스스로 움직이지 않는다 | 원인을 확인하고 신호를 주면 쥔 것을 넘기고 HOME 으로 간다 |

<p align="center">
  <img src="docs/images/hmi_running.png" width="46%" alt="운영 화면 — 진행 중">
  <img src="docs/images/hmi_kpi.png" width="46%" alt="운영 화면 — 완료 · 통계"><br>
  <sub>운영 화면(가짜 흐름으로 찍은 예시) — 진행 중 / 완료 · 소모품 · 누적 통계</sub>
</p>

---

## 2. 🖥️ 운영체제 환경 (OS Environment)
이 프로젝트는 다음 환경에서 개발하고 실제 로봇으로 검증했다.

* **OS:** Ubuntu 24.04 LTS (GPU PC · 화면 PC 모두)
* **ROS Version:** ROS 2 Jazzy
* **Language:** Python 3.12 (로봇 프로그램 · 화면 서버) · JavaScript (웹 화면 — Next.js 15 · React 19)
* **IDE:** VS Code (권장 확장은 [환경 설정 문서](docs/setup/M0609_환경설정.md))
* **로봇 드라이버:** 교육 과정 배포본 `doosan-robot2`(ROS 2 Jazzy) · `onrobot_rg2` · `m0609_rg2_bringup` — 이 저장소에는 포함하지 않는다
* **PC 구성:** GPU PC(로봇 제어기와 유선 · 로봇을 움직이는 유일한 PC) + 화면 PC(무선 · 운영 화면과 기록 DB). PC 1대로도 돌아간다([Step 5](#step-5-실제-로봇--pc-1대)).

---

## 3. 🛠️ 사용 장비 목록 (Hardware List)
프로젝트에 사용한 주요 하드웨어다. 워크셀 배치는 [1-2 의 배치도](#1-2-플로우-차트-flow-chart), 자리 이름은 `cell.yaml` 에 있다.

| 장비명 (Model) | 수량 | 비고 |
|:---:|:---:|:---|
| Doosan **M0609** 협동로봇 (제어기 · 티치 펜던트 포함) | 1 | 6축 · 관절 토크로 툴 힘 · 무게를 추정한다 · 비상정지는 펜던트 E-Stop |
| OnRobot **RG2** 그리퍼 | 1 | 파지 폭을 되읽어 "집었나 · 툴이 있나"를 판단한다 · 케이블 여유 필요 |
| PC (Ubuntu 24.04 · ROS 2 Jazzy) | 2 | GPU PC = 로봇 제어(유선) · 화면 PC = 운영 화면(무선) · PC 1대로도 가능 |
| 수세미 툴 (그릇용) | 1 | 그리퍼가 집는 툴 · 툴 홀더에 보관 |
| 수세미 솔 (컵용) | 1 | 그리퍼가 집는 툴 · 회전 · 상하 왕복으로 닦는다 |
| 툴 홀더 | 2 | 툴 2종 자리 · 세제(비눗물) 컵을 겸한다 |
| 스펀지 고정틀 (그릇 홈 · 컵 홈) | 1 | 닦는 동안 용기를 고정 · 5 N 에서 1 mm 이상 밀리지 않게 고정 |
| 헹굼 수조 | 1 | 물 없이 담금 · 물 털기 모션만(과정 안전 규정) |
| 잔반통 | 1 | 잔반 털기 자세 아래 |
| 식기세척기 팔레트 모형 (그릇 2칸 · 컵 2칸) | 1 | 정해진 칸 · 각도로 적재 · 컵은 뒤집어 꽂는다 |
| 다회용 그릇 · 컵 | 각 2 | 반납 구역의 고정 슬롯 2개씩에 놓는다 |
| 잔반 대용품 (약 94~98 g) | 1~2 | 잔반 판정(50 g) 시험용 |
| 격리 구역 (트레이) | 1 | 처리하지 못한 용기를 옮겨 두는 자리 · 그릇 · 컵 공용 |

---

## 4. 📦 의존성 (Dependencies)
프로젝트 실행에 필요한 라이브러리다. 설치 명령은 [Step 1](#step-1-설치--빌드--자동-시험-처음-한-번)에 있다.

| 구분 | 이름 · 버전 | 용도 |
|---|---|---|
| ROS 2 | **Jazzy** — `rclpy` · `std_msgs` · `std_srvs` · `builtin_interfaces` · `launch` · `launch_ros` · `ament_cmake` · `rosidl_default_generators` | 노드 · 메시지 3개 · launch |
| apt | `git` · `python3-colcon-common-extensions` · `python3-pytest` · `python3-venv` · `python3-yaml` · `python3-pymodbus` · `nodejs`(18.18 이상) · `npm` | 빌드 · 자동 시험 616개 · 설정 파일 · 그리퍼 안전 스위치(Modbus) · 웹 빌드 |
| Python (venv · 화면 PC) | `fastapi` 0.141 · `uvicorn[standard]` 0.53 · `websockets` 17 (`pydantic` 2 는 fastapi 가 함께 설치) | 화면 서버 `hmi_bridge` — HTTP 버튼 · WebSocket 상태 |
| Node ([`package.json`](src/f4_hmi/web/package.json)) | `next` 15.5.25 · `react` 19.3.0 · `react-dom` 19.3.0 | 웹 화면(정적 빌드 → `hmi_bridge` 가 서빙) |
| Python 표준 라이브러리 | `sqlite3` · `csv` · `threading` · `json` | 기록 DB `prewash.db`(표 5개) · `records.csv` |
| 로봇 드라이버 (저장소 밖) | `doosan-robot2`(`DSR_ROBOT2` · `DR_init`) · `onrobot_rg2` · `m0609_rg2_bringup` — `~/ws_cobot_pjt/ws_dsr` | 두산 API · RG2 · 브링업 ([Step 3](#step-3-두산-드라이버-처음-한-번)) |

---

## 5. ▶️ 실행 순서 (Usage Guide)
명령은 위에서 아래로 **그대로 복사해 치면 된다.**

- 저장소는 홈 폴더의 `~/rokey_pjt01_ws` 에 받는다고 적었다. 다른 곳에 받았으면 명령의 `~/rokey_pjt01_ws` 만 바꾼다.
- 새 터미널을 열 때마다 그 절의 **터미널 준비** 줄부터 친다.

| 하고 싶은 것 | 더 필요한 것 | 따라갈 절 |
|---|---|---|
| **로봇 없이** 화면과 흐름 보기 | 없음 | Step 1 → Step 2 |
| 가상 로봇(RViz) | 두산 드라이버 | Step 1 → Step 3 → Step 4 |
| 실제 로봇 — PC 1대 | 두산 드라이버 · 로봇 · 워크셀 | Step 1 → Step 3 → Step 5 |
| 실제 로봇 — PC 2대 | 위 + 같은 망의 PC 1대 | Step 1 → Step 3 → Step 6 |

> **Step 2 · Step 4 · Step 5 · Step 6 은 이어서 하는 순서가 아니다. 하나만 골라 실행한다.**
> 갈래를 바꿀 때는 켜 둔 프로그램을 모두 끄고 새 터미널에서 시작한다.
>
> **브링업은 한 번에 하나만 켠다.** 이미 켜져 있으면 다시 켜지 않는다.

### Step 1. 설치 · 빌드 · 자동 시험 (처음 한 번)

처음 한 번만 한다. Ubuntu 24.04 와 **ROS 2 Jazzy** 가 필요하다. ROS 가 없으면 [공식 설치 안내](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html)대로 먼저 설치한다.

**① 도구 설치**

```bash
sudo apt update && sudo apt install -y git python3-colcon-common-extensions python3-pytest python3-venv python3-pymodbus nodejs npm
```

**② 받기 · 빌드 · 자동 시험**

```bash
cd ~ && git clone https://github.com/hwang-injae/rokey_9_pjt1_D2.git rokey_pjt01_ws
cd ~/rokey_pjt01_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
python3 -m pytest -q src
```

| 볼 것 | 통과 기준 |
|---|---|
| 빌드 마지막 줄 | `Summary: 8 packages finished` |
| 시험 마지막 줄 | `616 passed, 8 skipped, 1 xfailed` 이고 `failed` 가 없다 |

건너뛴 8개는 ③의 화면 부품이 있어야 도는 시험이다.

**③ 운영 화면 부품** (화면을 띄울 PC 에서)

```bash
python3 -m venv --system-site-packages ~/venvs/hmi
~/venvs/hmi/bin/pip install fastapi "uvicorn[standard]" websockets
cd ~/rokey_pjt01_ws/src/f4_hmi/web && npm install && npm run build && cd ~/rokey_pjt01_ws
```

| 볼 것 | 통과 기준 |
|---|---|
| `npm run build` 끝 | `(Static)  prerendered as static content` |
| 생긴 파일 | `src/f4_hmi/web/out/index.html` |

코드를 새로 받았으면(`git pull`) `colcon build --symlink-install` 과 `npm run build` 를 다시 한다.

### Step 2. 로봇 없이 실행

로봇과 드라이버 없이 화면과 흐름을 본다. 기능은 가짜로 돈다.

```bash
cd ~/rokey_pjt01_ws
source /opt/ros/jazzy/setup.bash && source install/setup.bash
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ros2 launch prewash_bringup prewash_mock.launch.py
```

| 볼 것 | 통과 기준 |
|---|---|
| 터미널 | `IDLE — /flow/start 를 기다린다` 와 `HMI 서버를 연다 → http://localhost:8000` |
| 브라우저 <http://localhost:8000> | 화면이 뜨고 연결 점이 초록이다 |
| **시작** 버튼 | 약 20초 뒤 그릇 2 · 컵 2 완료 |

- `setup_io 를 건너뛴다` 경고 두 줄은 두산 드라이버가 없을 때 나오는 정상 안내다.
- 끌 때는 터미널에서 Ctrl+C 를 누른다.

<details>
<summary>멈춤 화면을 골라서 보기</summary>

launch 대신 터미널 2개로 돌린다. 두 터미널 모두 위 첫 세 줄(`cd` · `source` · `export`)을 먼저 친다. launch 와 같은 포트를 쓰므로 한 번에 하나만 켠다.

```bash
ros2 run f4_hmi hmi_bridge
```

```bash
ros2 run f4_hmi fake_state_pub tool_lost
```

`tool_lost` 자리에 넣을 수 있는 이름: `normal` · `paused` · `isolate` · `error` · `empty_zone` · `tool_lost` · `leftover_remain` · `cable` · `tool_fail`

기록 DB 는 아래로 본다.

```bash
ros2 run f4_hmi hmi_db kpi
```

</details>

### Step 3. 두산 드라이버 (처음 한 번)

가상 로봇과 실제 로봇에만 필요하다. 드라이버는 이 저장소에 없다.

교육 과정 배포본(`doosan-robot2` · `onrobot_rg2` · `m0609_rg2_bringup`)을 `~/ws_cobot_pjt/ws_dsr` 에 받아 빌드한다. 절차는 [환경 설정 문서 §8](docs/setup/M0609_환경설정.md)에 있다.

**확인**

```bash
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
ros2 pkg prefix m0609_rg2_bringup && python3 -c "import DR_init; print('DR_init OK')"
```

통과 기준은 설치 경로 한 줄과 `DR_init OK` 다. `DR_init` 을 못 찾으면 아래 줄을 `~/.bashrc` 맨 아래에 넣고 터미널을 새로 연다.

```bash
export PYTHONPATH=$PYTHONPATH:~/ws_cobot_pjt/ws_dsr/install/dsr_common2/lib/dsr_common2/imp
```

**터미널 준비(로봇용)** — Step 4 와 Step 5 의 모든 터미널에서 먼저 친다.

```bash
cd ~/rokey_pjt01_ws
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash && source install/setup.bash
export ROS_DOMAIN_ID=60 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
```

### Step 4. 가상 로봇

**터미널 1 — 가상 브링업**

```bash
ros2 launch m0609_rg2_bringup bringup.launch.py mode:=virtual host:=127.0.0.1 port:=12345 model:=m0609
```

**터미널 2 — 좌표 순회**

```bash
python3 src/cobot_common/test/rig_coords.py --from 1
```

RViz 에 로봇이 뜨고, 터미널 2 를 켜면 로봇이 셀 좌표를 차례로 돈다. 가상 로봇에는 힘 · 무게 · 접촉이 없다.

### Step 5. 실제 로봇 — PC 1대

PC 한 대에서 브링업 · 메인 프로그램 · 화면을 모두 돌린다. **Step 6 의 명령은 치지 않는다.**

> **주의**
> - `cell.yaml` 의 좌표는 우리 워크셀 배치 기준이다. 배치가 다른 셀에서는 좌표를 다시 티칭한 뒤에 돌린다.
> - 처음 켜는 셀과 다시 티칭한 뒤의 첫 실행은 `vel_scale:=0.3` 을 붙여 천천히 돌린다.
> - 급할 때는 Ctrl+C 가 아니라 **E-Stop** 을 누른다.

**전제**

| 항목 | 값 |
|---|---|
| PC 유선 주소 | `192.168.1.x/24` 로 고정 |
| 로봇 제어기 · 그리퍼 | `192.168.1.100` · `192.168.1.1` |
| 티치펜던트 | 툴 무게와 TCP `GripperDA_v1` 등록 |

**① 터미널 1 — 브링업**

```bash
ping -c 3 192.168.1.100
ros2 launch m0609_rg2_bringup bringup.launch.py mode:=real host:=192.168.1.100 port:=12345 model:=m0609
```

**② 터미널 2 — TCP 확인**

```bash
ros2 service call /dsr01/dsr_controller2/tcp/get_current_tcp dsr_msgs2/srv/GetCurrentTcp
```

통과 기준은 `GripperDA_v1` 이다. 다르면 로봇이 움직이지 않는다.

**③ 터미널 2 — 빈 용기 기준값** (실행 직전에 한 번)

손을 연다.

```bash
python3 src/f2_sense_flow/test/rig_f2.py release
```

빈 그릇을 그리퍼 사이에 대 주고 쥔다.

```bash
python3 src/f2_sense_flow/test/rig_f2.py grip --kind BOWL
```

잰다. 로봇이 HOME 을 거쳐 저울 자세로 움직인다(약 1분 30초).

```bash
PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_f2.py empty --kind BOWL -n 3
```

| 볼 것 | 통과 기준 |
|---|---|
| `중앙값 X g (폭 Y g)` | 폭이 20 g 이하 |

중앙값을 `src/cobot_common/config/params.yaml` 의 `f2.empty_weight_g.BOWL` 에 넣는다.

그릇을 **손으로 받친 채** 손을 연다.

```bash
python3 src/f2_sense_flow/test/rig_f2.py release
```

컵도 `--kind CUP` 으로 같은 순서를 한다.

**④ 터미널 2 — 메인 프로그램과 화면**

팔레트와 격리 구역을 비우고, 반납 구역에 그릇 2개와 컵 2개를 놓는다.

```bash
ros2 launch prewash_bringup prewash.launch.py hmi:=true
```

| 볼 것 | 통과 기준 |
|---|---|
| 터미널 | 문지기 통과 → 케이블 확인 → `IDLE` |
| 브라우저 <http://localhost:8000> | 연결 점이 초록이다 |
| **시작** 버튼 | 그릇 2 → 컵 2 를 처리하고 `IDLE` 로 돌아온다 |

**⑤ 끝낼 때**

로봇이 멈춘 뒤 터미널 2 → 터미널 1 순서로 Ctrl+C 를 누른다.

### Step 6. 실제 로봇 — PC 2대

PC 두 대가 같은 망에 있을 때 쓴다. **Step 5 의 명령은 치지 않는다.**

| PC | 맡는 일 | 설치 |
|---|---|---|
| **GPU PC** | Discovery Server · 브링업 · `flow_node` | Step 1 의 ① ② 와 Step 3 |
| **화면 PC** | `hmi_bridge` · 브라우저 · 기록 DB | Step 1 의 ① ② ③ |

무선망이 ROS 2 의 기본 탐색(멀티캐스트)을 막으면 두 PC 가 서로를 찾지 못한다. 그래서 GPU PC 에 **Fast DDS Discovery Server** 를 띄우고 두 PC 가 거기에 붙는다.

**① GPU PC 의 주소 확인**

```bash
hostname -I
```

무선 쪽 주소를 적어 둔다(예: `172.18.0.101`). 아래 명령의 `GPU_IP=172.18.0.101` 을 **이 값으로 바꿔서** 친다.

| 확인 | 명령 |
|---|---|
| GPU PC → 로봇 제어기 | `ping -c 3 192.168.1.100` |
| 화면 PC → GPU PC | `ping -c 3 172.18.0.101` |

**② GPU PC 터미널 A — Discovery Server** (끝까지 켜 둔다)

```bash
export GPU_IP=172.18.0.101
source /opt/ros/jazzy/setup.bash
fastdds discovery --server-id 0 --udp-address $GPU_IP --udp-port 11811
```

**③ GPU PC 터미널 B — 브링업**

```bash
export GPU_IP=172.18.0.101
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp ROS_DISCOVERY_SERVER=$GPU_IP:11811 ROS_SUPER_CLIENT=TRUE ROS_DOMAIN_ID=60 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET && unset ROS_STATIC_PEERS
ros2 daemon stop && ros2 daemon start
ros2 launch m0609_rg2_bringup bringup.launch.py mode:=real host:=192.168.1.100 port:=12345 model:=m0609
```

**④ GPU PC 터미널 C — 메인 프로그램**

```bash
export GPU_IP=172.18.0.101
cd ~/rokey_pjt01_ws
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash && source install/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp ROS_DISCOVERY_SERVER=$GPU_IP:11811 ROS_SUPER_CLIENT=TRUE ROS_DOMAIN_ID=60 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET && unset ROS_STATIC_PEERS
ros2 launch prewash_bringup prewash.launch.py
```

| 볼 것 | 통과 기준 |
|---|---|
| launch 첫 줄 | `vel_scale=1 · hmi=False` |
| 그다음 | 문지기 통과 → 케이블 확인 → `IDLE` |

GPU PC 에는 `hmi:=true` 를 붙이지 않는다. 붙이면 화면 서버와 기록 DB 가 두 곳에 생긴다.

**⑤ 화면 PC 터미널 — 화면 서버** (GPU PC 의 A · B · C 가 모두 켜진 뒤)

```bash
export GPU_IP=172.18.0.101
cd ~/rokey_pjt01_ws
source /opt/ros/jazzy/setup.bash && source install/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp ROS_DISCOVERY_SERVER=$GPU_IP:11811 ROS_SUPER_CLIENT=TRUE ROS_DOMAIN_ID=60 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET && unset ROS_STATIC_PEERS
ros2 daemon stop && ros2 daemon start
ros2 run f4_hmi hmi_bridge
```

화면 PC 에서는 브링업과 launch 를 켜지 않는다. 두산 드라이버도 필요 없다.

**⑥ 연결 확인** (화면 PC 에서, ⑤의 환경변수 줄을 넣은 새 터미널)

```bash
ros2 node list | grep -E 'flow_node|dsr_controller2'
ros2 topic hz /flow/state
```

| 볼 것 | 통과 기준 |
|---|---|
| 노드 | `/flow_node` · `/dsr01/flow_node_dsr` · `/dsr01/dsr_controller2` 가 보인다 |
| `/flow/state` | 약 2 Hz |
| 브라우저 <http://localhost:8000> | 연결 점이 초록이고 버튼이 1초 안에 응답한다 |

**⑦ 끝낼 때**

화면 PC 의 화면 서버 → GPU PC 의 C(로봇이 멈춘 뒤) → B → A 순서로 Ctrl+C 를 누른다.

<details>
<summary>터미널에서 버튼 누르기(서비스 호출)</summary>

환경변수 줄을 넣은 터미널에서 친다.

```bash
ros2 service call /flow/start  std_srvs/srv/Trigger
ros2 service call /flow/stop   std_srvs/srv/Trigger
ros2 service call /flow/resume std_srvs/srv/Trigger
ros2 service call /flow/abort  std_srvs/srv/Trigger
```

| 서비스 | 동작 |
|---|---|
| `start` | 그릇 2 → 컵 2 를 처리하고 `IDLE` 로 돌아온다 |
| `stop` | 일시 정지한다(닦기 동작 중이면 그 동작이 끝난 뒤) |
| `resume` | 재개한다. 실패로 멈췄으면 그 단계부터 다시 한다 |
| `abort` | 멈춰 있을 때만 된다. 이 용기를 격리하고 다음 용기로 간다 |

</details>

### Step 7. 문제가 생기면

<details>
<summary>설치 · 실행</summary>

| 증상 | 원인 | 대처 |
|---|---|---|
| `ros2: command not found` · `colcon: command not found` | 그 터미널에서 `source` 줄을 치지 않았다 | 그 절의 터미널 준비 줄부터 다시 친다 |
| `Package 'prewash_bringup' not found` | `source install/setup.bash` 를 빼먹었거나 빌드 전이다 | Step 1 ② 의 빌드와 `source` 를 다시 한다 |
| 화면 주소에 시험 페이지만 나온다 | 화면을 빌드하지 않았다 | Step 1 ③ 의 `npm install && npm run build` |
| 8000 포트가 이미 쓰이고 있다 | 먼저 켠 화면 서버가 남아 있다 | 남은 `hmi_bridge` 를 끄고 다시 켠다 |
| 브링업이 바로 꺼진다 | 앞서 켠 브링업이나 에뮬레이터가 남아 있다 | `ss -tlnp \| grep 12345` 로 확인하고 남은 것을 끈다 |
| 브링업을 켰더니 10초쯤 뒤 꺼진다 | 브링업이 이미 켜져 있는데 하나 더 켰다 | 먼저 켠 브링업을 그대로 쓴다 |

</details>

<details>
<summary>PC 1대 실행</summary>

| 증상 | 원인 | 대처 |
|---|---|---|
| 화면이 "연결 끊김"이다 | Step 6 의 환경변수 줄을 넣은 터미널에서 화면 서버를 켰다 | 화면 서버를 끄고, 새 터미널에서 Step 3 의 터미널 준비 줄만 친 뒤 다시 켠다 |

</details>

<details>
<summary>PC 2대 실행</summary>

| 증상 | 원인 | 대처 |
|---|---|---|
| 화면이 "연결 끊김"인데 토픽은 보인다 | 화면 서버를 환경변수 없는 새 터미널에서 켰다 | 환경변수 줄을 넣은 터미널에서 다시 켠다 |
| `ros2 topic list` 가 비어 있다 | 옛 ros2 데몬이 옛 설정으로 남아 있다 | `ros2 daemon stop && ros2 daemon start` |
| PC 끼리 `ping` 이 안 된다 | 기기 사이 통신을 막는 망(손님용 무선 등)에 붙어 있다 | 두 PC 를 서로 통신이 되는 같은 망에 붙인다 |
| "두산 드라이버가 안 보인다" | 터미널 B · C 에 환경변수 줄이 빠졌거나 서버(A)가 꺼졌다 | 서버 → 브링업 → 메인 프로그램 순서로 다시 켠다 |
| 새로 켠 노드끼리 서로 못 찾는다 | 서버 터미널(A)을 닫았다 | 서버 → 브링업 → 메인 프로그램 순서로 다시 켠다 |
| 기록이 두 곳에 나뉜다 | GPU PC 에 `hmi:=true` 를 붙였다 | GPU PC 에는 붙이지 않는다 |
| 화면만 끊기고 로봇은 계속 돈다 | 무선이 끊겼다 | 멈춰야 하면 E-Stop 을 누른다 |

두 PC 가 같은 유선 스위치에 있으면 Discovery Server 없이도 된다. 방법은 [환경 설정 문서 10-5](docs/setup/M0609_환경설정.md)에 있다.

</details>

---

## 6. 결과
자세한 수치와 근거는 [결과표](docs/04_결과_결과표.md)에 있다.

| 수락 기준 | 결과 | 확인 |
|---|---|---|
| 완전성 — 시작 1번으로 4개 처리 | 배속 0.5 에서 3회 완주 · 배속 1.0 에서 무정지 완주(약 13분) | 실기 ✅ |
| 잔반 판정 | 대용품 98 g 4/4 감지 · 빈 용기 오판 0/8 | 실기 ✅ |
| 파지 · 안착 90 % 이상 | 슬롯 집기 12/12 · 홈 놓기 12/12 · 컵 재파지 6/6 | 실기 ✅ |
| 힘 안정성 | 그릇 평균 2.6 N · 최대 6.9 N(상한 10 N) · 컵 최대 3.4 N | 실기 ✅ |
| 적재 | 팔레트 12/12 · 낙하 0 | 실기 ✅ |
| 예외 복구 | 예외 6종과 빈 시작 모두 정의대로 복구 | 실기 ✅ |
| 화면 · 기록 | 기록 누락 0 · 두 PC 사이 버튼 응답 7~96 ms | 실기 ✅ |
| 자동 시험 | 616개 통과(로봇 없이) | 자동 ✅ |

| 용기별 걸린 시간(초) | 그릇 1 | 그릇 2 | 컵 1 | 컵 2 |
|---|---|---|---|---|
| 배속 0.5 | 204 | 297(잔반 털기 1회) | 274 | 283 |
| 배속 1.0 | 153 | 219(잔반 털기 1회) | 182 | 192 |

**9/30 최종 실기(발표 당일)**: 전체 흐름과 예외 처리 모두 정상 동작(세부 수치는 기록하지 않음).

실기 사고와 그 교훈은 [결과표 §6](docs/04_결과_결과표.md)과 [트러블슈팅 문서](docs/troubleshooting/)에 정리했다.

### 알려진 제한

- 닦기 동작 중에 일시 정지를 누르면 그 동작이 끝난 뒤에 멈춘다(컵 약 13초 · 그릇 약 3초).
- 격리 구역은 한 곳이다. 격리가 생기면 다음 격리 전에 사람이 치운다.
- 새로 시작하면 완료 수를 0부터 센다. 시작 전에 팔레트와 격리 구역을 비운다.
- 아래 세 가지는 자동 시험으로 확인한 뒤 9/30 최종 실기에서 정상 동작을 확인했다(세부 수치는 기록하지 않음).
  - 닦기 힘 · 시간 상한을 넘었을 때 즉시 멈추는 동작
  - 중단한 용기를 이력에 "관리자 격리"로 남기는 것
  - 밀어서 재개할 때 손을 뗄 시간(1.5초)을 기다리는 것

### 향후 개선

- 닦기 동작 중에도 일시 정지가 바로 걸리게 한다.
- 세제 펌프로 세제를 자동 보충한다. 이번에는 툴 홀더의 비눗물에 담그는 방식을 썼다.

---

## 7. 저장소 구조 · 문서 지도
```
rokey_pjt01_ws/                 받은 폴더 = ROS 2 워크스페이스
├── README.md
├── LICENSE
├── docs/
│   ├── 01_요구사항_BR-SR.md     요구사항 · 수락 기준
│   ├── 02_인터페이스_IRD.md     함수 약속 · 메시지 · 실패 코드
│   ├── 03_설계_SDD.md           구조 · 상태 머신 · 안전 · 화면 · 시험 계획
│   ├── 04_결과_결과표.md        수락 기준 현황 · 걸린 시간 · 사고와 교훈
│   ├── meetings/                결정 기록
│   ├── test_logs/               시험 기록
│   ├── troubleshooting/         트러블슈팅
│   ├── setup/                   PC 환경 설정
│   └── images/                  설계도 · 플로우 차트 · 배치도 · 화면 캡처
└── src/                         ROS 2 패키지 8개
    └── */test/                  자동 시험(test_*.py) · 단독 시험대(rig_*.py)
```

| 궁금한 것 | 문서 |
|---|---|
| 요구사항 · 수락 기준 | [01_요구사항](docs/01_요구사항_BR-SR.md) |
| 함수 · 메시지 약속 | [02_인터페이스](docs/02_인터페이스_IRD.md) · [`contracts.py`](src/cobot_api/cobot_api/contracts.py) |
| 설계 · 상태 머신 · 안전 | [03_설계](docs/03_설계_SDD.md) |
| 결과 · 수치 · 교훈 | [04_결과표](docs/04_결과_결과표.md) |
| 왜 그렇게 정했나 | [결정 기록](docs/meetings/20260919_결정기록_DSN-03.md) · [구조 결정](docs/meetings/20260918_결정기록_구조_인터페이스.md) |
| 시험 기록 · 트러블슈팅 | [test_logs](docs/test_logs/) · [troubleshooting](docs/troubleshooting/) |
| PC 환경 설정 | [M0609_환경설정](docs/setup/M0609_환경설정.md) |

---

## 8. 팀
| 이름 | 역할 |
|---|---|
| 한석형(팀장) | 파지 · 이송 · 적재 · 좌표 티칭 · 기구 · 영상 |
| 민범진 | 무게 · 잔반 털기 · 헹굼 · 흐름(상태 머신) · 케이블 이상 감지 |
| 박진용 | 세제 · 접촉 닦기(힘 제어) · 공용 힘 함수 · 안전 파라미터 |
| 황인재 | PM · 운영 화면 · 기록 DB · 인터페이스 · 통합 · 문서 |

개발 6일(9/18 ~ 9/23) 동안 4명이 로봇 1대를 나눠 쓰며 단위 기능 → 단위 통합 → 전체 통합 순서로 올렸다. 9/23 에 기능을 동결한 뒤 예외 처리와 운영 화면을 다듬었다.

---

## 9. 라이선스
[Apache-2.0](LICENSE). 두산 · OnRobot 드라이버는 이 저장소에 포함하지 않는다.
