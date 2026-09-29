# TS-04 프로그램 종료 시 Abort · 종료 로그가 `/rosout`에 안 남음

| 항목 | 내용 |
|---|---|
| 날짜 | 2026-09-19 |
| 발견 | 민범진 (FLOW-01 `flow_node` 메인 뼈대 시험 중) |
| 영향 | `cobot_common.init`/`shutdown` 을 쓰는 모든 프로그램 — `flow_node`·`rig_f1`·`rig_f2`·`rig_f3` |
| 관련 | [TS-01](TS-01_두산API_초기화_실행기_교착.md) 과 **다른 건** — TS-01은 실행기 **교착**, 이건 **종료 순서**. 구조(SDD §3.2)는 그대로 유효하다 |
| 상태 | **종결.** 두 건 모두 `cobot_common`(황인재)에 반영돼 있다 — 아래 §5에서 실제 코드로 확인 |

> 이 문서는 **요청이 아니라 기록**이다. 증상을 겪었을 때 "왜 이렇게 돼 있는지" 를 알기 위한 것이고,
> 발표 자료의 "문제 해결 과정" 근거로도 쓴다.

---

## 1. 증상

### A — 프로세스가 정상 종료가 아니라 Abort
Ctrl+C(SIGINT)로 끝내면:
```
[INFO] [flow_node]: Ctrl+C — 정리하고 끝낸다
[INFO] [flow_node]: shutdown — 실행기 정리
terminate called without an active exception
[ros2run]: Aborted
```
종료 코드가 0이 아니다. 런치에서 돌리면 **비정상 종료로 잡힌다.**

### B — 종료 로그가 `/rosout`에 안 올라감
```
[INFO] [flow_node]: Ctrl+C — 정리하고 끝낸다
Failed to publish log message to rosout: publisher's context is invalid, at ./src/rcl/publisher.c:423
```
콘솔에는 찍히지만 **`/rosout` 토픽에는 안 나간다.** PC-B(HMI)에서 로그를 보는 쪽은 종료 과정을 못 본다.

---

## 2. 재현 방법 (로봇·브링업 불필요)

```bash
cbc
ros2 run f2_sense_flow flow_node      # 터미널 1
kill -INT $(pgrep -f "lib/f2_sense_flow/flow_node")
```

증상이 나는 구조(= SDD §3.1 의 설계를 그대로 옮겼을 때):
```python
def init(name, robot=True):
    rclpy.init()                                   # ← 기본 SIGINT 처리기가 설치된다
    _executor = MultiThreadedExecutor(); _executor.add_node(_io)
    _thread = threading.Thread(target=_executor.spin, daemon=True)
    _thread.start()

def shutdown():
    _executor.shutdown()
    _node.destroy_node()        # ← 스레드를 기다리지 않는다
    rclpy.shutdown()
```

---

## 3. 원인

### A — `spin()` 중인 스레드를 안 기다리고 끝낸다
`_executor.shutdown()` 은 "그만해라" 라고 **요청만** 한다. 백그라운드 스레드가 실제로 `spin()` 에서 빠져나오는 데는 시간이 걸린다.
그 사이에 `destroy_node()` → `rclpy.shutdown()` → 인터프리터 종료가 진행되면, **아직 돌고 있는 스레드를 C++ 쪽이 정리하지 못한다.**
C++ 표준에서 `joinable` 한 `std::thread` 가 파괴되면 `std::terminate()` 가 불린다 → `terminate called without an active exception`.

`daemon=True` 라 파이썬은 스레드를 기다려 주지 않는다. **그래서 명시적으로 `join` 해야 한다.**

### B — rclpy 기본 SIGINT 처리기가 컨텍스트를 먼저 닫는다
`rclpy.init()` 은 자기 SIGINT 처리기를 설치한다. Ctrl+C가 오면 **그 처리기가 먼저** ROS 컨텍스트를 무효화하고, 그다음에 파이썬 쪽으로 `KeyboardInterrupt` 가 올라온다.
`except KeyboardInterrupt:` 블록이 실행될 시점에는 **컨텍스트가 이미 죽어 있어서** `get_logger().info()` 가 `/rosout` 에 발행하지 못한다.

🚨 **실기에서 문제인 이유**: [SDD §5.1](../03_설계_SDD.md)은 *"`SIGINT` 처리기가 `cobot_common.shutdown()` 을 불러 **동작 정지 명령을 먼저 보낸다**"* 로 정해 두었다.
컨텍스트가 먼저 죽으면 **정지 명령 자체를 못 보낸다.** 팀 환경 함정 기록: *"움직이는 중에 그냥 죽이면 드라이버가 그 요청에 갇혀 브링업부터 다시"*.

---

## 4. 해결 — `cobot_common` 이 맡는다

두 건 모두 **프로그램 쪽이 아니라 `cobot_common`(황인재) 에서** 푼다. `flow_node`·`rig_f*.py` 는 아무것도 하지 않는다.

### 4-1. `shutdown()` 이 스레드를 기다린다
```python
_executor.shutdown(timeout_sec=_JOIN_WAIT_S)
if _thread is not None and _thread is not threading.current_thread():
    _thread.join(timeout=_JOIN_WAIT_S)          # 🚨 이것이 없으면 Abort
...
if rclpy.ok():                                   # 이미 닫혔을 수 있다
    rclpy.shutdown()
```
포인트: **무한 대기 금지**(상한을 둔다) · `rclpy.ok()` 로 두 번 닫기 방지 · `if not _started: return` 으로 두 번 불려도 안전.

### 4-2. SIGINT 처리기를 `init()` 이 단독으로 맡는다
```python
rclpy.init(signal_handler_options=SignalHandlerOptions.NO)   # 기본 처리기를 끈다
_install_signal_handling()
```
→ 컨텍스트가 살아 있는 상태에서 정리하므로 로그도 `/rosout` 에 정상으로 나가고, 실기에서는 정지 명령을 보낼 틈이 생긴다.

🚨 **그래서 `flow_node`·`rig_f*.py` 는 `signal.signal` 을 걸지 않는다.** `try/finally: cc.shutdown()` 만 쓴다(SDD §3.1).
두 곳에서 처리기를 걸면 서로 덮어써 정리가 꼬인다. 이 규칙은 [결정기록 S2](../meetings/20260918_결정기록_구조_인터페이스.md)(Ctrl+C 의 주인)로 정했다.

---

## 5. 현재 코드 확인 (2026-09-19)

`src/cobot_common/cobot_common/bootstrap.py` 에 둘 다 들어가 있다(줄 번호는 9/19 당시 값 — 코드가 바뀌면 움직이므로 내용 칸의 문구로 찾는다):

| 항목 | 줄(9/19 당시) | 내용 |
|---|---|---|
| 기본 처리기 끄기 | 73 | `rclpy.init(signal_handler_options=SignalHandlerOptions.NO)` |
| 두 번 불려도 안전 | 118 | `if not _started: return` |
| 정지 명령 먼저 | 128 | `if _robot and _stop_client is not None and rclpy.ok():` |
| 스레드 기다리기 | 136 | `_thread.join(timeout=_JOIN_WAIT_S)` |
| 두 번 닫기 방지 | 143 | `if rclpy.ok(): rclpy.shutdown()` |

검증(수정 전후, `flow_node` 를 mock 으로 띄워 SIGINT):

| 항목 | 전 | 후 |
|---|---|---|
| `publisher's context is invalid` | 2건 | **0건** |
| `terminate called` / `Aborted` | 발생 | **0건** |
| 종료 로그 `/rosout` 도달 | ❌ | ✅ |
| Ctrl+C **뒤 재실행** | — | ✅ 정상 |
| `/flow/state` 발행 | 2.000 Hz | 2.000 Hz (영향 없음) |

> 🔔 관련: 콜백에서 예외가 나면 통신 노드 **스레드가 끝나** 서비스가 영구 무응답이 되는 문제가 따로 있었고,
> `bootstrap.py` 의 `_spin_io()` 에서 잡아 계속 돌도록 고쳐졌다(PR #10).

---

## 6. 재발 방지

1. **`shutdown()` 에는 `join(timeout)` 을 넣는다.** 무한 대기는 금지.
2. **SIGINT 처리기는 `init()` 만 건다.** 프로그램 쪽은 `try/finally` 만.
3. `shutdown()` 은 **여러 번 불려도 안전**해야 한다 — `finally` 와 신호 처리기 양쪽에서 불릴 수 있다.
4. 종료 시험은 **두 상태 모두**에서: IDLE 대기 중 / 기능 함수 실행 중.
5. 종료 뒤 **재실행까지** 확인한다(TS-03 의 드라이버 교착처럼, 한 번 죽이면 다음이 안 되는 경우가 있다).
6. 움직이는 중의 Ctrl+C는 **정지를 최선으로 시도할 뿐**이다(V-24) — 급하면 **E-Stop**.

---

## 7. 곁들여 — 같은 날 겪은 환경 함정 3가지

TS 번호를 따로 붙일 만큼은 아니지만, 같은 벽에 부딪힐 수 있어 적어 둔다.

### ① `ros2 daemon stop` 을 해야 노드가 보인다 — 🔴 **전원 해당**

9/19 격리 설정(결정기록 S1)을 넣은 뒤, 노드를 띄웠는데 `ros2 topic list` 에 안 잡혔다.

**원인**: `ros2` 데몬이 **이전 discovery 설정을 물고 있다.** 환경변수만 바꾸면 이미 떠 있는 데몬에는 반영되지 않는다.
**해결**: `ros2 daemon stop` — `solo`·`team60` 별칭에 이미 들어 있다. 별칭을 쓰지 않고 손으로 `export` 했다면 직접 해야 한다.

> 9/19에 네 명 모두 격리 설정을 넣었으므로 전원이 겪을 수 있다.

### ② `pytest` 가 ROS 플러그인과 충돌 — 🟡 **venv 를 쓰는 환경만**

```
pluggy._manager.PluginValidationError: Plugin 'launch_testing' for hook 'pytest_pycollect_makemodule'
```

**원인**: ROS 2 Jazzy는 **pytest 7.4.4** 기준이다. venv 안의 새 pytest(9.x)와 `launch_testing` 플러그인의 훅 형식이 맞지 않는다.
**확인**: 시스템 pytest(`/usr/bin/python3 -m pytest`)로는 그냥 된다. 팀 표준은 **시스템 colcon·pytest**(*"colcon은 시스템 설치, venv는 HMI 전용"*).
**해결**: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest ...` 또는 시스템 python 사용.

> 민범진 PC는 venv 가 기본 활성화돼 있어 이 문제가 난다. 통합(L3·L4) 때 **PC-A 는 민범진 PC 를 쓰지 않기로** 했으므로(9/19 결정) 환경은 그대로 둔다.

### ③ 모듈 이름과 함수 이름이 같으면 모듈이 가려진다 — 🟡 `weigh.py` 한정

```python
from cobot_common import weigh       # → 모듈이 아니라 **함수**
```

**원인**: `__init__.py` 의 `from .weigh import *` 가 함수 이름을 패키지에 올려 같은 이름의 모듈을 가린다.
**해결**: 모듈이 필요하면 `importlib.import_module('cobot_common.weigh')`. 시험에서 내부를 바꿔 끼울 때 걸린다.
`motion.py`·`force.py`·`gripper.py` 는 함수 이름이 달라 해당 없다.
