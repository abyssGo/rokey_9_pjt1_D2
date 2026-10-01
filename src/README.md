# src 패키지

ROS 2 Jazzy 패키지 8개. 노드는 `flow_node`(메인 프로그램)와 `hmi_bridge`(운영 화면) 둘뿐이고, f1 · f2 · f3 의 기능은 `flow_node` 가 차례로 부르는 **파이썬 함수**다. 구조는 [설계 문서 §1.4 · §3](../docs/03_설계_SDD.md), 함수 · 메시지 약속은 [인터페이스 문서](../docs/02_인터페이스_IRD.md)에 있다.

| 패키지 | 빌드 타입 | 담당 | 역할 | 시험 |
|---|---|---|---|---|
| [`cobot_api`](cobot_api/) | ament_python | 황인재 | 기능 함수 13개의 **약속** — 공통 ID · 실패 코드 · 결과 타입 · 함수 서명(`contracts.py`). 로봇 코드 없음 | 2 |
| [`cobot_common`](cobot_common/) | ament_python | 4명 분담 | 두산 API · RG2 를 감싼 **공용 로봇 함수** — 초기화 `bootstrap.py` · 설정 로더 `config.py` · 이동 `motion.py` · 그리퍼 `gripper.py` · 힘 `force.py` · 무게 `weigh.py` + 설정 파일 `config/cell.yaml` · `params.yaml` | 201 · 시험대 17 |
| [`cobot_msgs`](cobot_msgs/) | ament_cmake (rosidl) | 황인재 | 메시지 3개 — `FlowState` · `FlowEvent` · `WeighLive` (`flow_node` → `hmi_bridge`) | — |
| [`f1_handling`](f1_handling/) | ament_python | 한석형 | 집기 · 다시 집기 · 놓기 · 이동 · 툴 집기/반납 · 팔레트 꽂기 — `handling.py` 함수 6개 | 86 · 시험대 1 |
| [`f2_sense_flow`](f2_sense_flow/) | ament_python | 민범진 · 황인재 | 무게 · 잔반 털기 · 헹굼 · 물 털기 — `sense.py` 함수 4개 + 메인 프로그램 **`flow_node`**(상태 머신 `flow.py` · 움직이기 전 문지기 `preflight.py` · 용기별 기록 `logger.py` · 가짜 기능 `mock/`) | 217 · 시험대 7 |
| [`f3_wipe`](f3_wipe/) | ament_python | 박진용 | 세제 · 그릇 닦기 · 컵 닦기(힘 제어) — `wipe.py` 함수 3개 · [패키지 README](f3_wipe/README.md) | 63 · 시험대 8 |
| [`f4_hmi`](f4_hmi/) | ament_python | 황인재 | 운영 화면 서버 **`hmi_bridge`**(FastAPI · WebSocket) · 웹 `web/`(Next.js) · 기록 DB(SQLite 표 5개) · 가짜 흐름 `fake_state_pub` · DB 조회 `hmi_db` · [패키지 README](f4_hmi/README.md) | 50 · 화면 계산 15 |
| [`prewash_bringup`](prewash_bringup/) | ament_python | 황인재 | launch 2개 — `prewash.launch.py`(실기 · `flow_node`) · `prewash_mock.launch.py`(로봇 없이 · 기능 전부 가짜 + 화면) | 6 · 시험대 1 |

시험 열 — 숫자: `pytest` 가 모으는 자동 시험 수(로봇 없이 돈다) · 시험대: 로봇(실기 · 가상)에 붙여 손으로 돌리는 `test/rig_*.py` 수 · 화면 계산: `f4_hmi/web/test/` 의 Node 자동 시험 수.

## 구조 규칙

- **두산 API 는 `cobot_common` 안에서만.** 기능 패키지는 `import cobot_common as cc` 로 `cc.함수()` 만 부르고 `DSR_ROBOT2` 를 직접 import 하지 않는다. 초기화 순서와 반환값 함정을 한 곳에서 다루기 위해서다. 기능 코드 가운데서는 움직이기 전 툴 · TCP 를 확인하는 문지기(`f2_sense_flow/preflight.py`)만 `cobot_common` 의 `dsr()` 를 빌려 조회한다(시험대 `rig_*.py` 일부는 안전 확인 · 측정용으로 `dsr()` 를 직접 쓴다). — IRD §1 · SDD §3.2 ⑤
- **로봇 명령은 `flow_node` 메인 스레드에서만.** 두산 API 는 명령마다 자기 실행기를 돌리므로 콜백에서 부르면 교착한다([TS-01](../docs/troubleshooting/TS-01_두산API_초기화_실행기_교착.md)). 통신 스레드의 콜백은 값 저장 · 깃발 세우기만 한다. 시험대(`rig_*.py`)도 같은 뼈대(`cc.init()` → 메인 스레드에서 호출 → `cc.shutdown()`)를 쓴다. — SDD §3.2 ② ③ ⑦
- **기능은 노드가 아니라 함수.** f1 · f2 · f3 는 `cobot_api` 약속대로 `Result` 를 돌려주는 평범한 함수이고, 실패는 예외가 아니라 `ok=False` + 실패 코드다. 기능 함수 모듈(`handling` · `sense` · `wipe`)끼리는 서로 import 하지 않는다. 부르는 쪽은 `flow_node`(`f2_sense_flow/flow.py`) 하나뿐이다. — IRD §1 · SDD §1.5
- **숫자는 설정 파일에.** 좌표 · 힘 · 횟수 · 시간은 코드가 아니라 `cobot_common/config/cell.yaml`(공용 좌표 · 속도 · 프리셋)과 `params.yaml`(기능별 절)에 두고, 각자 자기 절만 고친다. 코드는 `cc.cfg()` 로 읽는다. — IRD §9 · SDD §4.3
- **로봇 없이 도는 가짜 모듈.** `f2_sense_flow/mock/` 의 `mock_f1` · `mock_f2` · `mock_f3` 는 실제 모듈과 서명이 같고(`cobot_api.check_api` 로 검사) `use_mock` 으로 바꿔 끼우며 실패 코드를 주입할 수 있다. 화면 쪽은 `fake_state_pub` 이 대본(`f4_hmi/scenarios/`)대로 `flow_node` 와 같은 토픽을 낸다. — IRD §10
- **약속은 파일이 정본.** `cobot_api/contracts.py` 와 `cobot_msgs/msg/` 가 인터페이스 문서와 다르면 파일이 정본이다. 바꿀 때는 이슈로 4명이 확인한 뒤 고친다. — IRD 머리말

## 빌드 · 시험

```bash
# 저장소 루트(rokey_pjt01_ws)에서
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install            # Summary: 8 packages finished
source install/setup.bash
python3 -m pytest -q src                  # 616 passed, 8 skipped, 1 xfailed

cd src/f4_hmi/web && node --test test/    # 화면 계산 시험(Node 18 내장) — 15 pass
```

- 건너뛴 8개는 운영 화면 부품(`fastapi` 등)이 있어야 도는 시험이다. 설치는 루트 [README](../README.md) '실행 방법' 3. 3 을 마친 뒤 `~/venvs/hmi/bin/python3 -m pytest -q src/f4_hmi` 로 돌리면 함께 실행된다(50 passed).
- xfailed 1개는 알려진 빈틈(닦기 재시도가 성공해도 기록의 닦기 시간 · 힘 로그 경로가 1회차 값으로 남는다)을 표시해 두는 시험이다 — `f2_sense_flow/test/test_f2_e60_flow.py`.
- 시험대(`rig_*.py`)는 로봇을 움직인다. 실행법은 각 파일 머리말과 루트 README '실행 방법' 5-2 · 5-3 에 있다.
