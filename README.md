# PreWash-Cell — 협동로봇 다회용기 예비세척 · 식기세척기 팔레트 적재 자동화

반납된 다회용 그릇과 컵을 협동로봇이 집어 **잔반을 털고, 안쪽을 수세미 · 솔로 닦고, 헹군 뒤 식기세척기 팔레트에 꽂는다.** 카메라 없이 **파지 폭 · 무게 · 힘** 세 신호만으로 판단하고, 운영자는 웹 화면에서 시작 버튼 하나만 누른다.

<p align="center">
  <img src="docs/images/hmi_running.png" width="900" alt="운영 화면 — 그릇 닦기 단계"><br>
  <sub>운영 화면 — 단계 · 팔레트 · 진행 수 · 사이클 타임 · 소모품을 한 화면에 보여 준다 (로봇 없이 가짜 흐름으로 찍은 화면)</sub>
</p>

> 두산 ROKEY Boot Camp 9기 · 협동-1 프로젝트 "ROS2를 활용한 로봇 자동화 공정 시스템 구현" · D-2조 **디투(D2)** (한석형 · 민범진 · 박진용 · 황인재, 멘토 이일주) · 2026-09-18 ~ 09-30

**결과 한눈에** ([자세히](#결과))

- 시작 1번으로 그릇 2 · 컵 2 를 사람 개입 없이 끝까지 처리 — 배속 1.0 무정지 완주 약 13분(실기)
- 잔반 대용품 4/4 감지 · 빈 용기 오판 0/8, 예외 6종과 빈 시작 모두 정의대로 복구(실기)
- 용기당 사이클 타임은 목표 90 s 에 미달 — 배속 1.0 평균 186.5 s

## 주요 기능

- **비전 없는 3신호 판단**: 집었는지 · 툴이 있는지는 그리퍼가 되읽는 파지 폭(빈손 영점을 뺀 값: 그릇 벽 약 2 mm · 수세미 약 15 mm · 솔 약 8.3 mm)으로, 잔반은 무게로, 닦을 때의 접촉은 관절 토크로 추정한 툴 힘으로 본다.
- **그릇 · 컵에 맞춘 닦기**: 그릇은 접촉 하강으로 바닥을 찾은 뒤 바닥 나선 → 1.5 N 힘 제어로 벽면 원호를 돈다(벽 반지름은 치수로 계산). 컵은 솔을 위아래 ±15 mm · 손목 ±90° 주기 운동(2.6 s × 5회)으로 닦고, 힘은 상한(10 N)만 감시한다.
- **잔반 판정과 자동 털기**: 저울 자세에서 30번(0.5 s 간격) 읽은 무게의 중앙값에서 빈 용기 기준값을 뺀다. 50 g 을 넘으면 잔반통 위에서 털고 다시 재며, 털어도 남으면 사람 없이 격리 구역으로 보낸다.
- **바로 멈추고 이어 가는 운전**: 이동 명령을 비동기로 보내고 0.05 s 마다 완료와 정지 신호를 확인해, 일시 정지를 누르면 이동 도중 그 자리에서 선다. 케이블 이상(무게 떨림 80 g 초과) · 툴 놓침 · 툴 집기 실패로 멈추면 사람이 원인을 치운 뒤 로봇팔을 한 번 가볍게(15 N) 밀거나 화면에서 재개한다. 밀어서 재개했으면 손 뗄 시간 1.5 s 를 기다린 뒤 멈춘 단계부터(툴 놓침은 툴 집기부터) 다시 한다.
- **운영 화면과 기록 DB**: Next.js + FastAPI 웹 화면에서 시작 · 일시 정지 · 재개 · 중단을 누른다. 무게를 재는 동안 표본이 한 칸씩 실시간으로 쌓이고, 누적 KPI · 소모품 교체 · 이력을 보여 준다. 기록은 SQLite 표 5개와 용기별 `records.csv` 에 남는다.
- **로봇 없이 도는 개발 · 시험**: 기능 함수 13개의 약속(`cobot_api`)과 서명이 같은 가짜 기능, 대본대로 상태를 내는 가짜 발행기로 로봇 · 드라이버 없이 흐름과 화면을 돌린다. 자동 시험은 `pytest`(로봇 없이)와 화면 계산 `node --test` 다.

## 시스템 구성

### 아키텍처

<p align="center">
  <a href="https://hwang-injae.github.io/rokey_9_pjt1_D2/images/system_architecture_pc.html"><img src="docs/images/system_architecture_pc.png" width="900" alt="시스템 아키텍처"></a><br>
  <sub><a href="https://hwang-injae.github.io/rokey_9_pjt1_D2/images/system_architecture_pc.html">시스템 아키텍처 HTML</a> · <a href="docs/images/system_architecture_pc.png">PNG</a></sub>
</p>

**PC 2대 · 프로그램(노드) 2개.** 기능(집기 · 무게 · 닦기 …)은 노드가 아니라 **파이썬 함수**이고, 메인 프로그램 `flow_node` 가 순서대로 부른다. 로봇 명령은 `flow_node` 메인 스레드 한 곳에서만 낸다([배운 점 1](#배운-점--회고)). 강의실 무선망이 ROS 2 기본 탐색(멀티캐스트)을 막아, GPU PC 의 Fast DDS Discovery Server 로 두 PC 가 서로를 찾는다.

| 위치 | 구성 | 역할 |
|---|---|---|
| GPU PC (로봇과 유선) | Fast DDS Discovery Server · 두산 · RG2 드라이버 · `flow_node` | 메인 프로그램. 기능 함수를 순서대로 부르고 실패 처리 · 정지/재개/중단 · 용기별 기록(`records.csv`)을 맡는다. 로봇에 명령하는 유일한 PC |
| 화면 PC (무선) | `hmi_bridge`(FastAPI · WebSocket) · 웹 화면(Next.js) · SQLite | 운영 화면(버튼 · 단계 · 멈춤 안내 · 팔레트 · 소모품 · 누적 통계 · 이력)과 기록 DB(`prewash.db`) |
| 로봇 셀 | Doosan M0609 + OnRobot RG2 · 툴 2종 · 스펀지 고정틀 · 팔레트 모형 | 교육 과정 배포 드라이버(`ws_dsr`)는 저장소에 포함하지 않고 수정하지 않는다 |

| 통신 | 종류 | 방향 | 내용 |
|---|---|---|---|
| `/flow/state` | 토픽 · 1초에 2번 | `flow_node` → `hmi_bridge` | 지금 단계 · 진행 수 · 멈춤 원인 |
| `/flow/event` | 토픽 · 용기마다 1건 | `flow_node` → `hmi_bridge` | 용기 1개의 결과(무게 · 걸린 시간 · 완료/격리) |
| `/flow/weigh` | 토픽 · 무게 재는 동안 | `flow_node` → `hmi_bridge` | 재고 있는 무게 표본 |
| `/flow/start` · `stop` · `resume` · `abort` | 서비스 | `hmi_bridge` → `flow_node` | 화면 버튼(시작 · 일시 정지 · 재개 · 중단) |

좌표 · 힘 · 횟수 · 시간은 코드가 아니라 설정 파일 두 개(`src/cobot_common/config/cell.yaml` · `params.yaml`)에 있다. 패키지별 역할은 [src/README.md](src/README.md), 함수 · 메시지 약속은 [인터페이스 문서](docs/02_인터페이스_IRD.md)에 있다.

<p align="center">
  <img src="docs/images/hmi_kpi.png" width="700" alt="운영 화면 — 완료 · 통계"><br>
  <sub>운영 화면 — 완료 · 소모품 · 누적 통계 (로봇 없이 가짜 흐름으로 찍은 화면)</sub>
</p>

### 동작 흐름

<p align="center">
  <img src="docs/images/flow_chart.png" width="900" alt="플로우 차트"><br>
  <sub>왼쪽: 용기 1개의 정상 흐름 · 오른쪽: 예외 처리 · <a href="docs/images/flow_chart.svg">플로우 차트 SVG</a></sub>
</p>

```
① 집기   반납 구역의 고정 슬롯에서 용기를 집는다 (슬롯 1 → 비면 슬롯 2)
② 무게   HOME 을 거쳐 저울 자세에서 잰다 → 잔반이 50 g 을 넘으면 잔반통 위에서 털고 다시 잰다
③ 안착   스펀지 홈에 용기를 놓는다
④ 닦기   툴 집기(그릇 = 수세미 · 컵 = 솔) → 세제 → 안쪽 닦기(그릇 = 바닥 나선 뒤 1.5 N 힘 제어로 벽면 · 컵 = 위아래 + 손목 주기 운동) → 툴 반납
⑤ 헹굼   용기를 다시 집어 헹굼 구역에 2회 담근 뒤 물을 턴다
⑥ 적재   식기세척기 팔레트 칸에 꽂는다(컵은 뒤집어서) → HOME → 다음 용기
```

그릇 2개 → 컵 2개를 순서대로 처리하고 용기마다 기록을 남긴다. 상태 머신 전체는 [설계 문서 §5.1](docs/03_설계_SDD.md)에 있다.

### 예외 처리

원칙: 사람을 부르는 멈춤에서는 쥔 것을 그대로 두고 그 자리에 선다. 격리할 때는 곧게 위로 빠져 툴을 홀더에 반납한 뒤 옮긴다. 로봇 위치를 모르면 스스로 움직이지 않는다.

| 상황 | 로봇 | 사람 |
|---|---|---|
| 반납 구역이 비어 있다 | 그 구역을 건너뛴다 | — |
| 털어도 잔반이 남는다 · 닦기 힘/시간 상한을 넘었다 | 닦기는 즉시 멈추고 위로 빠진 뒤 한 번 더 닦는다. 그래도 실패하거나 잔반이 남으면 사람 없이 격리 구역으로 보내고 다음 용기로 간다 | — |
| 케이블 이상 · 툴 놓침 · 툴 집기 실패 | 그 자리에서 멈춘다 | 케이블을 풀거나 툴을 홀더에 꽂고, 팔을 가볍게 밀거나 화면에서 재개 → 케이블은 무게 단계부터, 툴은 툴 집기부터 다시 한다 |
| 운영자 일시 정지 · 중단 | 이동 도중에도 그 자리에서 멈춘다(닦기 동작 중이면 그 동작이 끝난 뒤). 멈춘 상태에서 중단하면 툴을 반납하고 용기를 격리한 뒤 다음 용기로 간다 | 재개하면 하던 동작부터 이어 간다. 중단한 용기는 이력에 "관리자 격리"로 남는다 |
| 로봇 오류(보호 정지 등) | 그 자리에서 멈춘다(예외였으면 곧게 위로 한 번만 시도 · 위치를 모르면 그것도 안 함). 사람 신호 전까지 움직이지 않는다 | 신호 1(밀기 · 재개) → 그리퍼만 열려 쥔 것을 받는다 → 신호 2(화면 재개) → 곧게 위로 → HOME → 다음 용기 (실기 시험 제외 · 자동 시험으로 확인) |

전체 예외 · 오류 목록은 [설계 문서 §7](docs/03_설계_SDD.md)에 있다.

## 개발 환경

| 항목 | 값 |
|---|---|
| OS · ROS | Ubuntu 24.04 LTS (GPU PC · 화면 PC) · ROS 2 Jazzy · Fast DDS(`rmw_fastrtps_cpp`) + Discovery Server |
| 로봇 드라이버 | 교육 과정 배포본 `doosan-robot2`(`DSR_ROBOT2` · `DR_init`) · `onrobot_rg2` · `m0609_rg2_bringup` — 저장소 밖 `~/ws_cobot_pjt/ws_dsr` · 제어기 Dart Platform 2.12.1 |
| 시뮬레이션 | 두산 에뮬레이터 + RViz(Virtual) — 경로 · 순서 확인용(힘 · 무게 · 접촉은 없음) · 로봇 없이는 가짜 기능(`use_mock`) · 가짜 상태 발행기(`fake_state_pub`) |
| 화면 | FastAPI · uvicorn · WebSocket(`hmi_bridge`, 포트 8000) · Next.js 15 · React 19(정적 빌드) · SQLite |
| 언어 · 도구 | Python 3.12 · JavaScript · colcon · pytest · `node --test` · VS Code |

검증은 세 단계로 했다: 로봇 없이(자동 시험 · 가짜 기능) → 가상 로봇(RViz) → 실기. 결과마다 어느 단계로 확인했는지 적었다.

## 사용 장비

| 장비 | 모델명 · 사양 | 수량 | 용도 |
|---|---|---|---|
| 협동로봇 | Doosan M0609 (6축 · 가반하중 6 kg · 도달 거리 900 mm) + 제어기 · 티치 펜던트 | 1 | 용기 · 툴 이송, 닦기. 관절 토크로 추정한 툴 힘을 무게 · 접촉 판정에 쓴다. 비상정지는 펜던트 E-Stop |
| 그리퍼 | OnRobot RG2 (스트로크 0~110 mm · 파지 힘 3~40 N · 폭 피드백) | 1 | 파지 폭으로 집기 성공과 툴 유무를 판정 |
| 툴 | 수세미 툴(그릇용 · 지름 90 mm) · 수세미 솔(컵용 · 길이 95 mm) | 각 1 | 그릇 · 컵 안쪽 닦기. 툴 홀더 2개에 보관하고 홀더의 비눗물에 담가 세제를 묻힌다 |
| 스펀지 고정틀 | 그릇 홈 · 컵 홈 (홈 여유 1~2 mm) | 1 | 닦는 동안 용기 고정 |
| 셀 구성품 | 반납 구역 2곳(구역마다 고정 슬롯 2개) · 잔반통 · 헹굼 구역 · 격리 구역 · 식기세척기 팔레트 모형(그릇 2칸 · 컵 2칸) | — | 공정의 입구 · 중간 · 출구. 헹굼은 물 없이 모션만(과정 안전 규정) |
| 처리 대상 | 다회용 그릇 (외경 114 mm) · 컵 (내부 높이 95 mm) · 잔반 대용품 94~98 g | 각 2 | 시연 · 시험 |
| PC | Ubuntu 24.04 · ROS 2 Jazzy | 2 | GPU PC(로봇 제어 · 유선) · 화면 PC(운영 화면 · 무선). PC 1대로도 돌아간다 |

<p align="center">
  <img src="docs/images/layout_workcell.png" width="700" alt="워크셀 배치도"><br>
  <sub>워크셀 배치(위에서 본 그림) · <a href="docs/images/layout_workcell.svg">배치도 SVG</a></sub>
</p>

티치 펜던트 등록값: TCP `GripperDA_v1`(Z 208 mm) · 툴 무게 1.440 kg. 좌표는 모두 이 TCP 기준이며, 프로그램은 시작 전에 툴 · TCP 이름을 확인하고 다르면 움직이지 않는다. 설치 절차는 [환경 설정 문서](docs/env/M0609_환경설정.md)에 있다.

## 설치 및 실행

### 빠른 시작

**로봇 없이** (Ubuntu 24.04 + ROS 2 Jazzy)

```bash
# 1. 도구 · 받기 · 빌드 · 자동 시험
sudo apt update && sudo apt install -y git python3-colcon-common-extensions python3-pytest python3-venv python3-pymodbus nodejs npm
cd ~ && git clone https://github.com/hwang-injae/rokey_9_pjt1_D2.git rokey_pjt01_ws && cd ~/rokey_pjt01_ws
source /opt/ros/jazzy/setup.bash && colcon build --symlink-install && source install/setup.bash
python3 -m pytest -q src                      # 616 passed, 8 skipped, 1 xfailed

# 2. 운영 화면 부품
python3 -m venv --system-site-packages ~/venvs/hmi && ~/venvs/hmi/bin/pip install fastapi "uvicorn[standard]" websockets
cd src/f4_hmi/web && npm install && npm run build && cd ~/rokey_pjt01_ws

# 3. 로봇 없이 실행 → 브라우저 http://localhost:8000 에서 시작 (기능이 가짜라 그릇 2 · 컵 2 가 곧바로 완료)
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ros2 launch prewash_bringup prewash_mock.launch.py
```

**실제 로봇 (PC 1대)** — 두산 드라이버(저장소 밖)를 설치한 뒤 두 터미널 모두 터미널 준비 줄을 먼저 실행한다. 실행 직전의 빈 용기 기준값 측정과 TCP 확인은 Step 5 에 있다.

```bash
# 터미널 준비 (두 터미널 모두)
cd ~/rokey_pjt01_ws && source ~/ws_cobot_pjt/ws_dsr/install/setup.bash && source install/setup.bash
export ROS_DOMAIN_ID=60 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
# 터미널 1 — 브링업
ros2 launch m0609_rg2_bringup bringup.launch.py mode:=real host:=192.168.1.100 port:=12345 model:=m0609
# 터미널 2 — 메인 프로그램 + 운영 화면 → http://localhost:8000
ros2 launch prewash_bringup prewash.launch.py hmi:=true
```

### 단계별 실행 절차

| 하고 싶은 것 | 더 필요한 것 | 순서 |
|---|---|---|
| 로봇 없이 화면과 흐름 보기 | 없음 | Step 1 → Step 2 |
| 가상 로봇(RViz) | 두산 드라이버 | Step 1 → Step 3 → Step 4 |
| 실제 로봇 — PC 1대 | 두산 드라이버 · 로봇 · 워크셀 | Step 1 → Step 3 → Step 5 |
| 실제 로봇 — PC 2대 | 위 + 같은 망의 PC 1대 | Step 1 → Step 3 → Step 6 |

- 저장소는 `~/rokey_pjt01_ws` 에 받는 것으로 적었다. 다른 곳에 받았으면 명령의 `~/rokey_pjt01_ws` 만 바꾼다.
- 새 터미널을 열 때마다 그 단계의 **터미널 준비** 줄부터 실행한다.
- Step 2 · 4 · 5 · 6 은 이어서 하는 순서가 아니라 **하나만 골라** 실행한다. 갈래를 바꿀 때는 켜 둔 프로그램을 모두 끄고 새 터미널에서 시작한다. **브링업은 한 번에 하나만** 켠다.

<details>
<summary><b>Step 1. 설치 · 빌드 · 자동 시험 (처음 한 번)</b></summary>

Ubuntu 24.04 와 **ROS 2 Jazzy** 가 필요하다. ROS 가 없으면 [공식 설치 안내](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html)대로 먼저 설치한다.

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

| 확인 | 통과 기준 |
|---|---|
| 빌드 마지막 줄 | `Summary: 8 packages finished` |
| 시험 마지막 줄 | `616 passed, 8 skipped, 1 xfailed` · `failed` 없음 |

건너뛴 8개는 운영 화면 부품(fastapi 등)이 있어야 도는 시험이다. ③을 마친 뒤 `~/venvs/hmi/bin/python3 -m pytest -q src/f4_hmi` 로 돌리면 함께 실행된다(50 passed).

**③ 운영 화면 부품** (화면을 띄울 PC 에서)

```bash
python3 -m venv --system-site-packages ~/venvs/hmi
~/venvs/hmi/bin/pip install fastapi "uvicorn[standard]" websockets
cd ~/rokey_pjt01_ws/src/f4_hmi/web && npm install && npm run build && cd ~/rokey_pjt01_ws
```

| 확인 | 통과 기준 |
|---|---|
| `npm run build` 끝 | `(Static)  prerendered as static content` |
| 생긴 파일 | `src/f4_hmi/web/out/index.html` |

코드를 새로 받았으면(`git pull`) `colcon build --symlink-install` 과 `npm run build` 를 다시 한다.

</details>

<details>
<summary><b>Step 2. 로봇 없이 실행</b></summary>

로봇과 드라이버 없이 화면과 흐름을 본다. 기능은 가짜로 돈다.

```bash
cd ~/rokey_pjt01_ws
source /opt/ros/jazzy/setup.bash && source install/setup.bash
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ros2 launch prewash_bringup prewash_mock.launch.py
```

| 확인 | 통과 기준 |
|---|---|
| 터미널 | `IDLE — /flow/start 를 기다린다` 와 `HMI 서버를 연다 → http://localhost:8000` |
| 브라우저 <http://localhost:8000> | 화면이 뜨고 연결 점이 초록이다 |
| **시작** 버튼 | 곧바로 그릇 2 · 컵 2 완료(기능이 가짜라 로봇 동작 시간이 없다) |

- `setup_io 를 건너뛴다` 경고 두 줄은 두산 드라이버가 없을 때 나오는 정상 안내다.
- 끌 때는 터미널에서 Ctrl+C.

**멈춤 화면을 골라서 보기**

launch 대신 터미널 2개로 돌린다. 두 터미널 모두 위 첫 세 줄(`cd` · `source` · `export`)을 먼저 실행한다. launch 와 같은 포트를 쓰므로 한 번에 하나만 켠다.

```bash
ros2 run f4_hmi hmi_bridge
```

```bash
ros2 run f4_hmi fake_state_pub tool_lost
```

`tool_lost` 자리에 넣을 수 있는 이름: `normal` · `paused` · `isolate` · `error` · `empty_zone` · `tool_lost` · `leftover_remain` · `cable` · `tool_fail`

기록 DB 조회:

```bash
ros2 run f4_hmi hmi_db kpi
```

</details>

<details>
<summary><b>Step 3. 두산 드라이버 (처음 한 번)</b></summary>

가상 로봇과 실제 로봇에만 필요하다. 드라이버는 이 저장소에 없다.

교육 과정 배포본(`doosan-robot2` · `onrobot_rg2` · `m0609_rg2_bringup`)을 `~/ws_cobot_pjt/ws_dsr` 에 받아 빌드한다. 절차는 [환경 설정 문서 §8](docs/env/M0609_환경설정.md)에 있다.

**확인**

```bash
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
ros2 pkg prefix m0609_rg2_bringup && python3 -c "import DR_init; print('DR_init OK')"
```

통과 기준은 설치 경로 한 줄과 `DR_init OK`. `DR_init` 을 못 찾으면 아래 줄을 `~/.bashrc` 맨 아래에 넣고 터미널을 새로 연다.

```bash
export PYTHONPATH=$PYTHONPATH:~/ws_cobot_pjt/ws_dsr/install/dsr_common2/lib/dsr_common2/imp
```

**터미널 준비(로봇용)** — Step 4 와 Step 5 의 모든 터미널에서 먼저 실행한다.

```bash
cd ~/rokey_pjt01_ws
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash && source install/setup.bash
export ROS_DOMAIN_ID=60 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
```

</details>

<details>
<summary><b>Step 4. 가상 로봇</b></summary>

**터미널 1 — 가상 브링업**

```bash
ros2 launch m0609_rg2_bringup bringup.launch.py mode:=virtual host:=127.0.0.1 port:=12345 model:=m0609
```

**터미널 2 — 좌표 순회**

```bash
python3 src/cobot_common/test/rig_coords.py --from 1
```

RViz 에 로봇이 뜨고, 터미널 2 를 켜면 로봇이 셀 좌표를 차례로 돈다. 가상 로봇에는 힘 · 무게 · 접촉이 없다.

</details>

<details>
<summary><b>Step 5. 실제 로봇 — PC 1대</b></summary>

PC 한 대에서 브링업 · 메인 프로그램 · 화면을 모두 돌린다. Step 6 의 명령은 실행하지 않는다.

> **주의**
> - `cell.yaml` 의 좌표는 우리 워크셀 배치 기준이다. 배치가 다른 셀에서는 좌표를 다시 티칭한 뒤에 돌린다.
> - 처음 켜는 셀과 다시 티칭한 뒤의 첫 실행은 `vel_scale:=0.3` 을 붙여 천천히 돌린다.
> - 급할 때는 Ctrl+C 가 아니라 **E-Stop**.

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

통과 기준은 `GripperDA_v1`. 다르면 로봇이 움직이지 않는다.

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

| 확인 | 통과 기준 |
|---|---|
| `중앙값 X g (폭 Y g)` | 폭이 20 g 이하 |

중앙값을 `src/cobot_common/config/params.yaml` 의 `f2.empty_weight_g.BOWL` 에 넣는다. 그릇을 **손으로 받친 채** 손을 연다.

```bash
python3 src/f2_sense_flow/test/rig_f2.py release
```

컵도 `--kind CUP` 으로 같은 순서를 한다.

**④ 터미널 2 — 메인 프로그램과 화면**

팔레트와 격리 구역을 비우고, 반납 구역에 그릇 2개와 컵 2개를 놓는다.

```bash
ros2 launch prewash_bringup prewash.launch.py hmi:=true
```

| 확인 | 통과 기준 |
|---|---|
| 터미널 | 문지기 통과 → 케이블 확인 → `IDLE` |
| 브라우저 <http://localhost:8000> | 연결 점이 초록이다 |
| **시작** 버튼 | 그릇 2 → 컵 2 를 처리하고 `IDLE` 로 돌아온다 |

**⑤ 끝낼 때** — 로봇이 멈춘 뒤 터미널 2 → 터미널 1 순서로 Ctrl+C.

</details>

<details>
<summary><b>Step 6. 실제 로봇 — PC 2대</b></summary>

PC 두 대가 같은 망에 있을 때 쓴다. Step 5 의 명령은 실행하지 않는다.

| PC | 맡는 일 | 설치 |
|---|---|---|
| **GPU PC** | Discovery Server · 브링업 · `flow_node` | Step 1 의 ① ② 와 Step 3 |
| **화면 PC** | `hmi_bridge` · 브라우저 · 기록 DB | Step 1 의 ① ② ③ |

무선망이 ROS 2 의 기본 탐색(멀티캐스트)을 막으면 두 PC 가 서로를 찾지 못한다. 그래서 GPU PC 에 **Fast DDS Discovery Server** 를 띄우고 두 PC 가 거기에 붙는다.

**① GPU PC 의 주소 확인**

```bash
hostname -I
```

무선 쪽 주소를 적어 둔다(예: `172.18.0.101`). 아래 명령의 `GPU_IP=172.18.0.101` 을 **이 값으로 바꿔서** 실행한다.

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

| 확인 | 통과 기준 |
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

| 확인 | 통과 기준 |
|---|---|
| 노드 | `/flow_node` · `/dsr01/flow_node_dsr` · `/dsr01/dsr_controller2` 가 보인다 |
| `/flow/state` | 약 2 Hz |
| 브라우저 <http://localhost:8000> | 연결 점이 초록이고 버튼이 1초 안에 응답한다 |

**⑦ 끝낼 때** — 화면 PC 의 화면 서버 → GPU PC 의 C(로봇이 멈춘 뒤) → B → A 순서로 Ctrl+C.

**터미널에서 버튼 누르기(서비스 호출)**

환경변수 줄을 넣은 터미널에서 실행한다.

```bash
ros2 service call /flow/start  std_srvs/srv/Trigger
ros2 service call /flow/stop   std_srvs/srv/Trigger
ros2 service call /flow/resume std_srvs/srv/Trigger
ros2 service call /flow/abort  std_srvs/srv/Trigger
```

| 서비스 | 동작 |
|---|---|
| `start` | 그릇 2 → 컵 2 를 처리하고 `IDLE` 로 돌아온다 |
| `stop` | 일시 정지(닦기 동작 중이면 그 동작이 끝난 뒤) |
| `resume` | 재개. 실패로 멈췄으면 그 단계부터 다시 |
| `abort` | 멈춰 있을 때만. 이 용기를 격리하고 다음 용기로 |

</details>

<details>
<summary><b>Step 7. 문제가 생기면</b></summary>

| 언제 | 증상 | 원인 | 대처 |
|---|---|---|---|
| 설치 · 실행 | `ros2: command not found` | 그 터미널에서 `source` 줄을 실행하지 않았다 | 그 단계의 터미널 준비 줄부터 다시 |
| 설치 · 실행 | `colcon: command not found` | colcon 을 설치하지 않았다 | Step 1 ① 의 apt 설치를 다시 |
| 설치 · 실행 | `Package 'prewash_bringup' not found` | `source install/setup.bash` 를 빼먹었거나 빌드 전이다 | Step 1 ② 의 빌드와 `source` 를 다시 |
| 설치 · 실행 | 화면 주소에 시험 페이지만 나온다 | 화면을 빌드하지 않았다 | Step 1 ③ 의 `npm install && npm run build` |
| 설치 · 실행 | 8000 포트가 이미 쓰이고 있다 | 먼저 켠 화면 서버가 남아 있다 | 남은 `hmi_bridge` 를 끄고 다시 켠다 |
| 설치 · 실행 | 브링업이 바로 꺼진다 | 앞서 켠 브링업이나 에뮬레이터가 남아 있다 | `ss -tlnp \| grep 12345` 로 확인하고 남은 것을 끈다 |
| 설치 · 실행 | 브링업을 켰는데 곧 꺼지거나 먼저 켠 브링업이 멈춘다 | 브링업이 이미 켜져 있는데 하나 더 켰다 | 새로 켜지 말고 먼저 켠 브링업을 그대로 쓴다 |
| PC 1대 | 화면이 "연결 끊김"이다 | Step 6 의 환경변수 줄을 넣은 터미널에서 화면 서버를 켰다 | 화면 서버를 끄고, 새 터미널에서 Step 3 의 터미널 준비 줄만 실행한 뒤 다시 켠다 |
| PC 2대 | 화면이 "연결 끊김"인데 토픽은 보인다 | 화면 서버를 환경변수 없는 새 터미널에서 켰다 | 환경변수 줄을 넣은 터미널에서 다시 켠다 |
| PC 2대 | `ros2 topic list` 가 비어 있다 | 옛 ros2 데몬이 옛 설정으로 남아 있다 | `ros2 daemon stop && ros2 daemon start` |
| PC 2대 | PC 끼리 `ping` 이 안 된다 | 기기 사이 통신을 막는 망(손님용 무선 등)에 붙어 있다 | 두 PC 를 서로 통신이 되는 같은 망에 붙인다 |
| PC 2대 | "두산 드라이버가 안 보인다" | 터미널 B · C 에 환경변수 줄이 빠졌거나 서버(A)가 꺼졌다 | 서버 → 브링업 → 메인 프로그램 순서로 다시 켠다 |
| PC 2대 | 새로 켠 노드끼리 서로 못 찾는다 | 서버 터미널(A)을 닫았다 | 서버 → 브링업 → 메인 프로그램 순서로 다시 켠다 |
| PC 2대 | 기록이 두 곳에 나뉜다 | GPU PC 에 `hmi:=true` 를 붙였다 | GPU PC 에는 붙이지 않는다 |
| PC 2대 | 화면만 끊기고 로봇은 계속 돈다 | 무선이 끊겼다 | 멈춰야 하면 E-Stop |

두 PC 가 같은 유선 스위치에 있으면 Discovery Server 없이도 된다. 방법은 [환경 설정 문서 10-5](docs/env/M0609_환경설정.md)에 있다.

</details>

## 프로젝트 구조

```text
rokey_pjt01_ws/                ROS 2 워크스페이스 (저장소 루트)
├── src/                       ROS 2 패키지 8개 · 패키지 지도는 src/README.md
│   ├── cobot_api/             기능 함수 13개의 약속(이름 · 인자 · 결과 · 실패 코드) — 로봇 코드 없음
│   ├── cobot_common/          두산 API · 그리퍼를 감싼 공용 로봇 함수 + 설정 파일 config/*.yaml
│   ├── cobot_msgs/            메시지 3개 — FlowState · FlowEvent · WeighLive
│   ├── f1_handling/           집기 · 다시 집기 · 놓기 · 이동 · 툴 집기/반납 · 팔레트 꽂기 (함수 6개)
│   ├── f2_sense_flow/         무게 · 잔반 털기 · 헹굼 · 물 털기 (함수 4개) + 메인 프로그램 flow_node (상태 머신)
│   ├── f3_wipe/               세제 · 그릇 닦기 · 컵 닦기 (함수 3개)
│   ├── f4_hmi/                운영 화면 hmi_bridge · 웹(Next.js) · 기록 DB(SQLite) · 가짜 흐름
│   ├── prewash_bringup/       launch 2개 — 실기용 · 로봇 없이(mock)
│   └── */test/                자동 시험 test_*.py · 단독 시험대 rig_*.py
├── docs/                      문서 지도는 docs/README.md
│   ├── 01_요구사항_BR-SR.md   요구사항 · 수락 기준 · KPI
│   ├── 02_인터페이스_IRD.md   함수 약속 · 메시지 · 실패 코드
│   ├── 03_설계_SDD.md         구조 · 상태 머신 · 예외 처리 · 안전 · 화면 · 시험 계획
│   ├── 04_결과_결과표.md      수락 기준 결과 · 걸린 시간 · 사고와 교훈
│   ├── decisions/             결정 기록 — 구조 · 인터페이스(9/18) · 결정 E1~E71
│   ├── test-reports/          실기 · 가상 시험 기록 (설계 · 결과의 근거만 선별)
│   ├── troubleshooting/       트러블슈팅 TS-01~08 (증상 → 원인 → 해결 → 재발 방지)
│   ├── env/                   PC 환경 설정 (Ubuntu 24.04 · ROS 2 Jazzy · M0609 + RG2)
│   ├── research/              주제 조사 — 법규 · 산업 조사 · 브리핑 자료
│   └── images/                아키텍처 · 플로우 차트 · 배치도 · 화면 캡처
├── LICENSE                    Apache-2.0
└── README.md
```

두산 · OnRobot 드라이버(`ws_dsr`)는 저장소 밖에 따로 빌드한다.

## 결과

9/22 · 9/23 · 9/29 실기(Doosan M0609)와 로봇 없는 자동 시험에서 확인한 값이다. 목표는 [요구사항 문서](docs/01_요구사항_BR-SR.md)의 수락 기준(AC) · KPI · 시스템 요구(SR) · 검증 항목(TR), 근거는 [결과표](docs/04_결과_결과표.md)와 [시험 기록](docs/test-reports/)에 있다.

| 항목 | 결과 | 목표 | 판정 | 검증 |
|---|---|---|---|---|
| 완전성 — 시작 1번으로 그릇 2 · 컵 2 처리 | 배속 0.5 완주 3회(9/23) · 배속 1.0 무정지 완주 1회(9/29 · 약 13분) · 사람 개입 0 | 시작 1회로 4개를 팔레트까지 | 달성 | 실기 |
| 잔반 판정 | 98 g 대용품 4/4 감지 · 빈 용기 오판 0/8 | 대용품 100 % · 오판 0 (임계 50 g) | 달성 | 실기 |
| 무게 정확도 | 96 g 물건 오차 +3 g (9/22) | ±20 g | 달성 | 실기 |
| 파지 · 안착 | 슬롯 집기 12/12 · 스펀지 홈 놓기 12/12 · 컵 재파지 6/6 | 90 % 이상 | 달성 | 실기 |
| 툴 집기 · 반납 | 수세미 10/10 · 솔 10/10 · 낙하 0 (9/22) | 10회 중 9회 이상 · 낙하 0 | 달성 | 실기 |
| 닦기 힘 | 그릇 평균 2.64 / 2.06 N · 최대 6.91 / 6.34 N(그릇 1 / 2) · 컵 최대 3.39 N · 힘 로그 기록 · 상한 초과 0 | 목표 범위 유지 · 힘 로그 기록 · 상한(10 N) 초과 시 즉시 후퇴 | 달성 | 실기 |
| 팔레트 적재 | 12/12 · 낙하 0 · 컵은 뒤집어 적재 | 90 % 이상 · 낙하 0 | 달성 | 실기 |
| 예외 복구 | 예외 6종과 빈 시작 모두 정의대로 복구(두 PC 구성에서도 같음) | 실패마다 재시도 · 격리 · 정지 · 재개가 정의대로 | 달성 | 실기 |
| 운영 화면 · 기록 | 기록 누락 0 · 두 PC 사이 버튼 응답 7~96 ms(무선) | 누락 0 · 응답 1 s 이내 | 달성 | 실기 |
| 용기당 사이클 타임 | 배속 1.0 에서 153 ~ 219 s (평균 186.5 s) | 90 s 이내 | **미달** | 실기 |
| 자동 시험 | `pytest` 616 passed · 8 skipped · 1 xfailed · 화면 계산 15 pass | 로봇 없이 실패 0 | 달성 | 자동 |

| 용기별 걸린 시간(초) | 그릇 1 | 그릇 2 | 컵 1 | 컵 2 |
|---|---|---|---|---|
| 배속 0.5 (9/23) | 204 | 297 (잔반 털기 1회) | 274 | 283 |
| 배속 1.0 (9/29) | 153 | 219 (잔반 털기 1회) | 182 | 192 |

사이클 타임은 배속을 0.5 → 1.0 으로 올려도 용기당 25~34 % 줄어드는 데 그쳤다(두 실행 사이에 컵 재파지 동선 등 코드 차이도 있다). 무게 측정(8 s 안정 · 약 21 s 측정 — 당시 30 × 0.7 s)과 닦기(배속 예외)처럼 배속과 무관한 구간이 크기 때문으로 본다.

발표 당일(9/30) 최종 실기에서도 전체 흐름과 예외 처리가 모두 정상 동작했다.

### 알려진 제한 · 향후 개선

- 닦기 동작 중에 일시 정지를 누르면 그 동작이 끝난 뒤에 멈춘다(컵 주기 운동 약 13초 · 그릇은 나선 · 원호 동작이 끝날 때까지). → 남은 동작을 즉시 멈추고 재개할 때 닦기를 처음부터 하도록 바꿀 계획이다.
- 잔반 임계(50 g)와의 여유가 작아 빈 용기 기준값을 실행 직전에 다시 잰다.
- 격리 구역은 그릇 · 컵 공용 한 곳이라, 격리가 생기면 다음 격리 전에 사람이 치운다. → 화면에 격리 구역 비움 확인 버튼을 둘 계획이다.
- `cell.yaml` 좌표는 우리 워크셀 배치 기준이다. 다른 셀에서는 다시 티칭하고 첫 실행은 배속 0.3 으로 돌린다.
- 세제는 툴 홀더의 비눗물에 담그는 방식으로 했다. → 세제 펌프로 자동 보충하는 것이 향후 개선이다.

## 배운 점 / 회고

실기와 가상 시험에서 생각대로 움직이지 않은 것을 기록으로 좁혀 고치면서 남긴 것이다.

1. **로봇 명령은 한 곳, 한 스레드에서만 내린다.** 첫 설계는 기능 노드 3개가 서비스 콜백 안에서 로봇을 움직였는데, 두산 API 가 명령마다 실행기를 직접 돌려 교착이 생겼고 다른 프로세스의 명령은 조용히 덮어써졌다. "기능은 함수, 메인 스레드가 차례로 부르고 통신만 별도 스레드"로 바꾸자 연속 6회 성공 · 모션 중 상태 2 Hz 가 나왔다(가상 로봇 비교 시험). ([TS-01](docs/troubleshooting/TS-01_두산API_초기화_실행기_교착.md))
2. **좌표는 TCP 기준이니, 움직이기 전에 툴 · TCP 이름부터 확인한다.** 컨트롤러의 툴 · TCP 선택이 빈 값으로 풀려(원인 미확인) 같은 좌표 명령이 208 mm 아래로 갔고 그릇 바닥이 닿았다(충돌 감지로 정지 · 피해 없음). 시작 전에 이름을 읽어 기대값과 다르면 움직이지 않는 문지기를 넣었다. ([TS-07](docs/troubleshooting/TS-07_TCP_설정_풀림_충돌.md))
3. **무게는 늘 같은 길로 와서, 실행 직전에 잰 기준값과 비교한다.** 같은 저울 자세라도 집은 자리에서 곧장 오면 −113 g, HOME 을 거쳐 오면 −23 g 으로 90 g 이 달랐고, 같은 길에서도 기준값이 6~20분 사이 ±45 g 움직였다. 그래서 무게는 항상 HOME 을 거쳐 재고 기준값은 실행 직전에 다시 잰다. 98 g 대용품은 4/4 감지됐지만 읽은 값이 50.1~91.4 g 으로 임계와의 여유가 작아 이 절차를 계속 지킨다. ([결과표 §4](docs/04_결과_결과표.md))
4. **사람이 밀어서 재개할 때는 손을 뗄 시간을 준다.** 케이블 멈춤에서 제자리 재측정 중 손이 닿아 값이 튀었고, 다섯 번 밀어야 재개됐다. 제자리 재측정을 없애고 손 뗄 시간 1.5 s 와 (보호정지를 풀었으면) 이동 전 2 s 대기를 둔 뒤에는 밀기 1번 · 약 8 s 만에 멈춤이 풀리고 HOME 을 거쳐 무게 단계를 다시 통과했다. 같은 대기를 툴 놓침 · 툴 집기 실패 재개에도 넣었다. ([결정 기록 E64 · E69](docs/decisions/20260919_결정기록_DSN-03.md))
5. **정지는 "다음 동작 전"이 아니라 "움직이는 도중"에 걸리게 만든다.** 처음에는 동기 이동이 끝난 뒤에야 일시 정지가 처리됐다. 이동을 비동기 + 0.05 s 확인으로 바꾸자 가상 가능성 시험(V-24a)에서 0.13 s 에 멈추고 재개하면 같은 동작을 이어 갔고, 실기에서도 툴을 든 채 정지 → 재개가 됐다. ([설계 문서 §5.1](docs/03_설계_SDD.md) · [V-24 시험 기록](docs/test-reports/20260921_V-24_실기_일시정지_황인재.md))
6. **정해진 좌표로는 접근점에서 자세를 맞춘 뒤 Z 만 곧게 내린다.** 수조 안 자세에서 HOME 으로 관절 이동을 하자 그리퍼가 테이블을 쓸어, 복귀 · 중단은 Z 만 먼저 올린 뒤 HOME 으로 가게 했다. 9/23 재파지 · 툴 반납 동선에서 멈춘 일 뒤에는 놓기 · 적재 · 툴 반납 · 재파지를 접근점에서 자세를 맞춘 뒤 Z 만 곧게 내리는 동선 규칙으로 정했다. 힘 감시는 닦기 · 바닥 찾기 같은 접촉 동작에만 쓴다. ([TS-08](docs/troubleshooting/TS-08_수조안에서_HOME이동_테이블충돌.md) · [결정 기록 E44 · E50](docs/decisions/20260919_결정기록_DSN-03.md))
7. **결과마다 검증 수준을 밝힌다.** 로봇 없는 검증만 거친 수정이 실기까지 확인된 것처럼 읽힌 일이 있은 뒤로, 바뀐 것마다 자동 시험 / 가상 / 실기를 적고 실기 전인 것은 따로 표시해 두었다가 확인한 뒤 닫았다. ([결정 기록 E20](docs/decisions/20260919_결정기록_DSN-03.md))

## 팀

| 이름 | 역할 |
|---|---|
| 한석형(팀장) | 파지 · 이송 · 적재 · 좌표 티칭 · 기구 · 영상 |
| 민범진 | 무게 · 잔반 털기 · 헹굼 · 흐름(상태 머신) · 케이블 이상 감지 |
| 박진용 | 세제 · 접촉 닦기(힘 제어) · 공용 힘 함수 · 안전 파라미터 |
| 황인재 | PM · 운영 화면 · 기록 DB · 인터페이스 · 통합 · 문서 |

개발 6일(9/18 ~ 9/23) 동안 4명이 로봇 1대를 나눠 쓰며 단위 기능 → 단위 통합 → 전체 통합 순서로 올렸다. 9/23 에 기능을 동결한 뒤 예외 처리와 운영 화면을 다듬었다.

## 라이선스

[Apache License 2.0](LICENSE) — Copyright 2026 Team D2 (ROKEY 9기 협동1 D그룹 2조). ROS 2 패키지 8개의 `package.xml` 도 같은 라이선스를 선언한다. 두산 · OnRobot 드라이버(`ws_dsr`, 저장소 밖)는 각 제공자의 라이선스를 따른다.
