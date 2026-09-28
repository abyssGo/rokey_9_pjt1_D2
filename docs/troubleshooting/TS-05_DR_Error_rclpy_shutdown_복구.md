# TS-05 두산 `DR_Error` 가 나면 그 프로그램은 더 이상 로봇에 명령을 못 보낸다 (순응·힘제어가 켜진 채 남음)

| 항목 | 내용 |
|---|---|
| 날짜 | 2026-09-19 (V-03 1회차 실기) · 문서 2026-09-20 |
| 발견 | 박진용 (F3, V-03 힘제어 중 XY 이동 시험) |
| 영향 | **두산 API 를 부르는 모든 프로그램** — `flow_node` · `rig_f1` · `rig_f2` · `rig_f3` · `rig_v03`. 특히 순응·힘제어를 켠 구간 |
| 관련 | [TS-01](TS-01_두산API_초기화_실행기_교착.md)(초기화·교착)·[TS-04](TS-04_종료처리_실행기스레드_SIGINT.md)(종료 순서)와 **다른 건** — 이건 **인자 오류 하나가 프로세스의 ROS 를 꺼 버리는** 문제 |
| 상태 | **회피책 적용.** 복구 도구 `src/cobot_common/test/release_force.py` 가 공식 복구 수단(9/20 PM 확정, SDD §7 `ROBOT_ERROR` = 그 자리 정지 + 사람이 복구) |

> 설치본(강사 배포)을 고칠 수 없으므로 **우리 쪽에서 막고, 났을 때 복구**한다.

---

## 1. 증상

V-03 1회차(9/19 저녁). 나선 이동을 `amove_spiral` 로 부르면서 `vel` 을 빠뜨렸다.

```
[ERROR] <DSR_ROBOT.py> func_name = _spiral, line_no = 3325
...
rclpy.shutdown() 이후:
  [WARN] Service is not available, waiting for service to become available...
  (그 뒤 어떤 로봇 명령도 나가지 않음)
```

그리고 **로봇 팔을 손으로 밀면 스프링처럼 눌렸다** — 순응(`task_compliance_ctrl`)이 켜진 채 남은 것이다.
프로그램의 `finally` 에서 `force_off()` 를 부르도록 해 두었지만, 그 호출도 **서비스가 안 불려서 아무 일도 하지 못했다.**

---

## 2. 원인 — `DR_Error` 는 만들어지는 순간 `rclpy.shutdown()` 을 부른다

설치본 `DR_error2.py` (`~/ws_cobot_pjt/ws_dsr/install/dsr_common2/.../imp/DR_error2.py` 73번째 줄):

```python
class DR_Error(Exception):
    def __init__(self, type, msg="", back=False):
        ...
        print(err_msg)
        rclpy.shutdown()          # ← 예외를 만들기만 해도 ROS 컨텍스트가 죽는다
```

- 파이썬에서 `raise DR_Error(...)` 는 **예외 객체를 만들면서** 이 `__init__` 을 실행한다. 즉 `except` 로 잡든 말든 **ROS 는 이미 꺼진 뒤**다.
- 꺼지면 이 프로세스의 서비스 클라이언트가 전부 무효가 되어, 이후 `release_force()` · `movel()` 같은 명령이 컨트롤러에 **도달하지 못한다.**
- 설치본 `DSR_ROBOT2.py` 에 `raise DR_Error` 가 **896곳**이고, 확인해 보면 전부 **인자 타입·값 검사**다(황인재 확인). 즉 컨트롤러 고장이 아니라 **우리 코드가 잘못된 인자를 넘겼을 때** 난다.
  - 예: `vel` 없이 `amove_spiral`, `radius` 에 문자열, `ref` 에 없는 상수, `movej` 에 길이 5 리스트.
- 컨트롤러 쪽은 멀쩡하다. **그 프로세스만** 손이 잘린 상태가 된다. 그래서 새 프로세스로는 복구가 된다.

---

## 3. 해결 — 새 프로세스로 끈다 (`release_force.py`)

```bash
soc && python3 src/cobot_common/test/release_force.py            # 힘·순응 끄기만
soc && python3 src/cobot_common/test/release_force.py --home     # + 위로 올린 뒤 HOME (🚨 E-Stop 에 손)
```

- `release_force()` → `release_compliance_ctrl()` 을 부른다. 이미 꺼져 있으면 `-1` 이 돌아오지만 그대로 두면 된다.
- `--home` 은 **이미 HOME 이면 움직이지 않는다**(관절 1° 이내). 아니면 곧게 80 mm 올린 뒤 HOME 으로, 속도는 0.3배.
- 끈 뒤 팔을 손으로 밀어 **딱딱하면** 풀린 것이다. 그래도 물렁하면 E-Stop → 브링업 재시작.

### 프로그램이 스스로 알아차리는 법

`rclpy.ok()` 가 `False` 면 이 프로세스로는 아무것도 못 한다. `rig_v03.py` 의 마무리 처리:

```python
finally:
    import rclpy
    if not rclpy.ok():                 # DR_Error 가 rclpy.shutdown() 을 불렀다
        log.error('🚨 두산 오류로 ROS 가 꺼졌다 → 힘·순응이 켜진 채일 수 있다. 새 터미널에서 바로:\n'
                  '    soc && python3 src/cobot_common/test/release_force.py --home   (E-Stop 에 손)')
    else:
        force_off() → mwait() → safe_retreat() → HOME      # 한 단계가 실패해도 다음 단계를 시도
```

`flow` 는 이 경우 복구를 시도하지 않고 멈춘다 — `ROBOT_ERROR` = 그 자리 정지 + `PAUSED` + 사람이 복구(SDD §7, 9/20 확정).

---

## 4. 재발 방지

| 방법 | 어디에 |
|---|---|
| **두산 함수는 `cobot_common` 안에서만** 부르고, 인자는 부르기 전에 검사한다(값이 없으면 `KeyError` 로 멈추고 로봇을 움직이지 않는다) | `force.py` · `motion.py` · `gripper.py` · `weigh.py` |
| 선택 인자(`vel`·`acc`·`radius`·`ref`·`mod`)를 **빠짐없이** 넘긴다. 특히 `amove_*` 계열 | 모든 호출부 |
| 접촉 구간은 **짧게** 켜고 **`finally` 에서 반드시 끈다.** `force_off()` 는 하나가 실패해도 둘 다 시도한다 | `force.py`(9/20 수정) |
| 새 동작을 실기에서 처음 돌리기 전에 **Virtual 에서 같은 인자로** 한 번 돌린다 — 인자 오류는 Virtual 에서도 똑같이 난다 | 모든 rig |
| 실기 옆에 **복구 명령을 미리 띄워 둔다**(새 터미널에 명령을 쳐 놓고 엔터만 누르면 되게) | 실기 담당 |

---

## 5. 확인한 범위 · 남은 확인

- 확인: 설치본 `DR_error2.py` 73번째 줄 `rclpy.shutdown()` · `DSR_ROBOT2.py` 의 `raise DR_Error` 896곳이 인자 검사라는 점 · 9/19 V-03 1회차에서 실제로 순응이 남았고 `release_force.py` 로 풀린 것.
- 남은 확인: 컨트롤러 쪽 오류(예: 충돌 정지·안전 정지)일 때도 같은 경로인지 — 그때는 `DR_Error` 가 아니라 서비스가 실패값을 돌려줄 수 있다(그건 `RuntimeError` 로 올라와 프로세스는 살아 있다).
- 설치본은 **고치지 않는다**(강사 배포본).
