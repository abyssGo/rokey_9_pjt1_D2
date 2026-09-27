# TS-03 `reset_workpiece_weight` 호출 후 컨트롤러 서비스가 모두 멈춤

| 항목 | 내용 |
|---|---|
| 날짜 | 2026-09-18 |
| 발견 | 민범진 (V-02 하중 측정 준비 중) |
| 영향 | **F2 `weigh`·`leftover_loop`.** 한 번 걸리면 브링업 재시작 전까지 모든 서비스 응답이 없다 |
| 관련 | [TS-01](TS-01_두산API_초기화_실행기_교착.md) 과 **다른 건** — TS-01은 우리 파이썬 노드 쪽 실행기, 이건 `dsr_controller2`(드라이버) 쪽 |
| 상태 | 회피책 확인. **근본 원인은 추정 단계** — 제어권 가설 재확인 필요 |

## 1. 증상
```
File "tools/...", line ..., in reset
    return bool(self._call(self._reset, self._ResetReq()).success)
RuntimeError: 서비스 응답 시간 초과
```
그리고 **그 뒤로는 되던 것까지 안 된다.**
```bash
ros2 service call /dsr01/dsr_controller2/system/get_robot_mode ...   # 응답 없음
ros2 service call /dsr01/dsr_controller2/force/get_workpiece_weight ...  # 응답 없음 (전에는 됐다)
```

## 2. 관찰된 사실
| 확인 | 결과 |
|---|---|
| `get_workpiece_weight` (조회) — reset 호출 **전** | ✅ 정상 (빈 그리퍼에서 값 반환) |
| `get_current_posj` (조회) — reset 호출 **전** | ✅ 정상 |
| `reset_workpiece_weight` (명령) | ❌ 응답 없음 |
| 그 뒤 모든 컨트롤러 서비스 | ❌ 응답 없음 |
| `ros2_control_node` 프로세스 | 살아 있음 (CPU 200%대) |
| 로봇 TCP 연결 `192.168.1.100:12345` | ESTABLISHED 유지 |
| 실시간 제어 루프 | 계속 동작 (`dsr_hw_interface2` 로그 갱신 중) |
| 컨트롤러 로그 | reset 호출 뒤 `[dsr_controller2]: Access control granted` 가 찍힘 |

즉 **로봇 연결과 제어 루프는 멀쩡한데 서비스 처리만 막혔다.**

## 3. 원인 (추정)
`reset_workpiece_weight` 는 조회가 아니라 **로봇에 내리는 명령**이다. 컨트롤러는 명령을 받으면 로봇 제어권(access control)을 요구하는데, **제어권이 ROS 쪽에 없으면 그 호출이 반환되지 않고**, 컨트롤러의 서비스 처리 경로가 그 한 건에 물려 뒤따르는 요청이 전부 대기한다.

근거: 로그의 `Access control granted` 가 **reset 호출보다 뒤**에 찍혔다 = 호출 시점에는 제어권이 없었다.

> 🟡 **확정이 아니다.** "제어권이 없어서"가 유력하지만, 제어권을 확실히 확보한 상태에서 reset 이 정상 반환되는지 아직 확인하지 못했다.

## 4. 회피책 (현재 적용)
**`reset` 없이 측정한다.** 조회(`get_workpiece_weight`)는 제어권이 없어 보이는 상태에서도 값을 돌려줬다(§2 관찰). 다만 "제어권과 무관하다"까지 확인한 것은 아니다.

`reset` 은 0점 재설정이므로, 생략하면 측정값에 **고정 옵셋**이 남는다. 그러나 우리 판정식은

```
측정값 − 빈 용기 무게 ≥ 임계  →  잔반
```

이고 **양쪽에 같은 옵셋이 실려 상쇄**되므로, 잔반 판정에는 영향이 없다.
실제로 옵셋이 일정하다는 것을 측정으로 확인했다 → V-02 기록(과정 기록 · git 이력)

## 5. 재발 방지
1. **`reset` 을 반복 호출하지 않는다.** 실패하면 그 뒤로는 부르지 않는다 — 반복하면 컨트롤러가 계속 막힌다.
2. `f2_sense_flow/sense.py` 의 `weigh()` 구현 시 `reset` 은 **선택 동작**으로 두고, 응답 시간 상한(3초 권장)과 실패 시 계속 진행 경로를 반드시 넣는다.
3. 막혔을 때 복구: 브링업 `Ctrl+C` → `killdrcf` → `sodreal`.
4. 명령성 서비스(`set_*`, `reset_*`, `move*`)는 제어권이 필요할 수 있다. 조회성(`get_*`)과 구분해서 다룬다.

## 6. 남은 확인
- [ ] 제어권을 ROS 가 확실히 가진 상태에서 `reset_workpiece_weight` 가 정상 반환되는가
- [ ] 제어권이 ROS 에 있을 때 **직접교시가 되는가** (안 되면 자세를 바꿔가며 측정하는 절차 자체를 바꿔야 한다)
- [x] SDD §3.1 `weigh` 정의 → **`weigh(n, reset=False)`: reset 은 선택 동작(응답 상한 3 s, 실패 시 반복 금지)** 으로 반영(9/18 PM, IRD v3.0 §4 · SDD v3.0 §3.1·§5.3). 인터페이스(함수 서명 `weigh(kind)`)는 그대로
