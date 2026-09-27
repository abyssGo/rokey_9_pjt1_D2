# -*- coding: utf-8 -*-
"""힘 함수 — 담당 박진용 (INF-02b). 함수 표는 docs/03_설계_SDD.md §3.1.

    import cobot_common as cc
    depth, f = cc.contact_down(max_depth=40, limit=cfg['cell']['limits']['contact_limit_n'])
    cc.force_on('z', target=4.0, limit=10.0) → (닦기) → cc.force_off() → cc.safe_retreat()
    cc.move_spiral(rev=2.8, rmax_mm=14, time_s=3) → while not cc.motion_done(): (힘 확인)   # 바닥 나선 (비동기)
    cc.move_arc(mid, end, vel_mm_s=180, vel_deg_s=400, radius_mm=3)                        # 벽면 원호 (이어 붙임)
    cc.move_periodic([0,0,20,0,0,180], [0,0,6.3,0,0,6.3], repeat=3, ref='TOOL', scale=False)   # 컵: 위아래 + 6번 조인트 (TOOL rz)

약속
- 좌표계는 BASE. axis 는 'x'·'y'·'z'. target·limit·min·max 는 양수 크기(N) 이고, 누르는 방향(−axis)은 여기서 붙인다.
- 숫자는 인자로 받거나 cfg()['cell'] 에서 읽는다(AGENTS 규칙 6). 키가 없거나 비어 있으면(null) 로봇을 움직이지 않고 KeyError.
    cell.limits : safe_z_mm · timeout_s
    cell.force  : compliance_stx · contact_step_mm · contact_vel_mm_s · contact_acc_mm_s2 ·
                  retreat_vel_mm_s · retreat_acc_mm_s2 · force_max_n · search_y_period_ratio
    cell.motion : 이동 속도 상한 — move_rel · move_arc 가 읽는다
- 실행 인자 cfg()['run']['vel_scale'](0 초과 1 이하, 첫 실기 0.3)를 이동 속도에 곱한다 — 하강·후퇴 속도, 탐색은 주기를 나눠 느리게.
- 실패는 예외다: ForceLimitError(힘 상한) · MotionTimeout(시간 초과) · RuntimeError(두산 함수가 -1).
  기능 함수(f1·f3)가 받아서 FORCE_LIMIT · TIMEOUT · ROBOT_ERROR 코드로 바꾸고, 후퇴는 safe_retreat().
- 두산 함수는 함수 안에서 dsr() 로 얻는다(메인 스레드 검사 포함). 모듈 맨 위에서 DSR_ROBOT2 를 import 하지 않는다.
- check_force_condition 은 만족 0 / 아니면 -1 이다(DRL 매뉴얼과 다름, TS-01 증상 D) → force_reached() 만 쓴다.
- 순응 중에는 관절 이동(movej) 금지 · 비동기 이동 중 순응 ON 금지(오류 2.1903, 중급교육2) → 켜기 전에 mwait().
- 이동(contact_down 의 한 단계 하강, safe_retreat 의 상승)은 motion.move_rel(속도 선택 인자) 을 쓴다.
  그 속도도 cell.motion 의 100 % 기준 × vel_scale 을 넘지 못한다. 순응·힘제어·move_periodic 처럼 힘 함수 자체의 두산 호출만
  dsr() 로 직접 한다.
- 닦기 접촉 모션(move_spiral · move_arc)과 where · motion_done 도 여기 둔다 — 순응·힘제어를 켠 채 도는 동작이라
  힘 상한·해제와 같이 봐야 하고, 기능 함수(f3)는 두산 함수를 직접 부르지 않는다(AGENTS §3 규칙 4).
  이 둘에는 일시정지 폴링이 없다(move_periodic 과 같다) → 일시정지는 구간이 끝난 뒤 다음 이동에서 먹는다.

표기 — E-nn: 팀 결정 번호(docs/meetings/20260919_결정기록_DSN-03.md) · V-nn/INT-nn: 검증 항목(docs/test_logs/) · TS-nn: 트러블슈팅(docs/troubleshooting/)
"""
import time

from .bootstrap import cfg, dsr
from . import motion as _motion
from .motion import is_paused, move_rel

__all__ = ['force_on', 'force_off', 'force_release', 'force_reached', 'compliance_on', 'compliance_off',
           'contact_down', 'periodic_search', 'safe_retreat', 'read_force', 'start_nudge_watch', 'check_nudge',
           'robot_state', 'wait_robot_ready', 'recover_robot_if_needed',
           'where', 'joints', 'stop_now', 'motion_done', 'wait_done', 'move_joints', 'move_line_rel', 'move_spiral', 'move_arc', 'move_pose', 'move_periodic',
           'ForceLimitError', 'MotionTimeout']

_AXES = ('x', 'y', 'z')
# 비동기 모션이 시작하기를 기다리는 한도(s). 2.0(V-03 rig 와 같음)이던 것을 나선 재실패(soap 뒤 spiral 이 알람 없이
# 2 s 안에 시작하지 않음 · 실기)로 늘렸다
_START_WAIT_S = 5.0
_state = {'compliance': False, 'force': False, 'limit': None}   # 지금 켜져 있는 것 (safe_retreat 가 본다)


class ForceLimitError(RuntimeError):
    """접촉 힘이 상한을 넘었다 → 기능 함수는 FORCE_LIMIT."""


class MotionTimeout(RuntimeError):
    """접촉 동작이 cell.limits.timeout_s 안에 끝나지 않았다 → 기능 함수는 TIMEOUT."""


# ------------------------------------------------------------------ 공개 함수
def force_on(axis, target, limit):
    """순응 ON(강성 cell.force.compliance_stx) → 목표 힘 ON(−axis 방향으로 target N 누름).

    목표 힘은 절대값(DR_FC_MOD_ABS) — target = 실제로 누르는 힘. 보통 contact_down 으로 닿은 뒤 켠다.
    (상대값 REL 은 켜는 순간의 힘에 target 을 더한다 → 닿은 채 켜면 그만큼 더 누른다. V-03 에서 닿은 채 ABS 로 확인)
    """
    i = _axis_index(axis)
    _check_force_args(target=target, limit=limit)
    if target >= limit:
        raise ValueError(f'force_on: target {target} N 이 limit {limit} N 보다 작아야 한다')
    d = dsr()
    stx = _force_cfg('compliance_stx')
    d.mwait()                                              # 비동기 이동 중 순응 ON 은 2.1903
    _ok(d.task_compliance_ctrl(stx), 'task_compliance_ctrl')
    _state['compliance'] = True
    fd = [0.0] * 6
    direction = [0] * 6
    fd[i] = -float(target)
    direction[i] = 1
    try:
        _ok(d.set_desired_force(fd, direction, mod=d.DR_FC_MOD_ABS), 'set_desired_force')
    except BaseException:
        force_off()
        raise
    _state['force'] = True
    _state['limit'] = float(limit)


def compliance_on(stx=None):
    """순응제어만 켠다(힘제어는 켜지 않는다) — 닦기의 나선 구간처럼 힘 방향과 같은 축으로 움직이는 동작에 쓴다.

    중급2: 힘제어는 힘 방향과 같은 방향의 모션을 막는다 · 순응제어 중에는 Task 모션만 가능(Move J 계열 2.1903) ·
    비동기·블렌딩 모션이 도는 중에 켜면 2.1903 → 켜기 전 mwait · 목표 자리 근처에서 켜는 것을 권장.
    stx 를 안 주면 cell.force.compliance_stx 를 쓴다.
    """
    d = dsr()
    stx = _force_cfg('compliance_stx') if stx is None else stx
    d.mwait()
    _ok(d.task_compliance_ctrl(stx), 'task_compliance_ctrl')
    _state['compliance'] = True


def compliance_off():
    """순응제어를 끈다(힘제어가 켜져 있으면 함께 끝난다 — 중급2). 켜져 있지 않아도 부를 수 있다."""
    force_off()


def force_off():
    """힘 해제 → 순응 해제 (이 순서). 켜져 있지 않아도 부를 수 있다.

    주의: 하나가 실패해도 둘 다 시도한 뒤에 예외를 낸다 — 첫 줄이 force_off() 인 safe_retreat() 의 후퇴까지 막히면 안 된다.
    """
    d = dsr()
    failed = []
    if _state['force']:
        try:
            _ok(d.release_force(), 'release_force')
        except BaseException as e:                       # 순응 해제는 반드시 시도한다
            failed.append(e)
    if _state['compliance']:
        try:
            _ok(d.release_compliance_ctrl(), 'release_compliance_ctrl')
        except BaseException as e:
            failed.append(e)
    _state.update(compliance=False, force=False, limit=None)
    if failed:
        raise failed[0]


def force_release():
    """힘제어만 끈다 — 순응은 켜 둔 채로. 켜져 있지 않아도 부를 수 있다.

    닦기에서 벽면 구간이 끝난 뒤, 순응을 유지한 채 중심으로 돌아올 때 쓴다(V-03 확정 절차).
    둘 다 끄려면 force_off()/compliance_off(). 중급2: 순응을 끄면 힘제어도 같이 끝난다.
    """
    if not _state['force']:
        return
    d = dsr()
    d.mwait()
    _ok(d.release_force(), 'release_force')
    _state['force'] = False
    _state['limit'] = None


def force_reached(axis, min=None, max=None):
    """BASE 기준 axis 의 힘 크기가 [min, max] 안이면 True. check_force_condition(...) == 0 을 감싼 것."""
    if min is None and max is None:
        raise ValueError('force_reached: min 과 max 중 하나는 준다')
    for name, v in (('min', min), ('max', max)):
        if v is not None and v < 0:
            raise ValueError(f'force_reached: {name}={v} — 힘 크기(0 이상)로 준다')
    d = dsr()
    ret = d.check_force_condition(_axis_const(d, axis),
                                  min=d.DR_COND_NONE if min is None else float(min),
                                  max=d.DR_COND_NONE if max is None else float(max),
                                  ref=d.DR_BASE)
    return ret == 0


def read_force():
    """툴에 걸린 외력 [fx, fy, fz, mx, my, mz] (힘은 BASE 기준 N, 모멘트는 TOOL 기준 Nm)."""
    d = dsr()
    f = d.get_tool_force(ref=d.DR_BASE)
    if not isinstance(f, (list, tuple)) or len(f) != 6:
        raise RuntimeError(f'get_tool_force 실패: {f!r}')
    return [float(x) for x in f]


def robot_state():
    """지금 로봇 상태 번호(motion.py 의 코드 체계와 같다) — 1 = STANDBY(정상, 새 명령을 받을 수 있다).

    넛지(RS1) 뒤 컨트롤러 쪽 SOS 해제가 끝났는지 보려고 만들었다(고정 시간만 기다리면
    MoveIncomplete 가 났다). motion.py 를 고치지 않고 여기서 직접 두산 API 를 읽는다(읽기 전용).
    """
    return int(dsr().get_robot_state())


def wait_robot_ready(timeout_s):
    """robot_state() 가 STANDBY(1)가 될 때까지 기다린다 — 최대 timeout_s. 됐으면 True, 시간 초과면 False."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        try:
            if robot_state() == 1:                       # 1 = STANDBY
                return True
        except Exception:
            return False
        time.sleep(0.05)
    return False


# 상태 번호 → set_robot_control 코드(dsr_msgs2/srv/SetRobotControl.srv) — motion.py 의 상태 번호와 같다
_RECOVER_CODE = {5: 2, 3: 3, 9: 4, 10: 5, 8: 7}   # SAFE_STOP·SAFE_OFF·SAFE_STOP2·SAFE_OFF2·RECOVERY → STANDBY


def recover_robot_if_needed(timeout_s=5.0):
    """로봇 상태가 STANDBY(1)가 아니면 set_robot_control 서비스로 자동 복구를 시도한다.

    - SAFE_STOP(5) → robot_control=2
    - SAFE_OFF(3) → robot_control=3
    - SAFE_STOP2(9) → robot_control=4
    - SAFE_OFF2(10) → robot_control=5
    - RECOVERY(8) → robot_control=7

    이미 STANDBY(1)이면 즉시 True.
    Mock 환경이거나 DSR이 준비되지 않아 상태를 읽을 수 없으면 False 반환(예외 없이 안전 통과).
    timeout_s 안에 STANDBY 로 복귀하면 True, 아니면 False.
    """
    try:
        s = robot_state()
    except Exception:
        return False

    if s == 1:                                           # 1 = STANDBY
        return True

    code = _RECOVER_CODE.get(s)
    if code is None:
        return False

    try:
        from .bootstrap import ROBOT_ID, io_node
        from dsr_msgs2.srv import SetRobotControl
        node = io_node()
        if node is None:
            return False
        client = node.create_client(SetRobotControl, f"/{ROBOT_ID}/dsr_controller2/system/set_robot_control")
        if not client.wait_for_service(timeout_sec=1.0):
            return False
        req = SetRobotControl.Request()
        req.robot_control = code
        res = client.call(req)
        if res is None or not res.success:
            return False
    except Exception:
        return False

    return wait_robot_ready(timeout_s)


# ------------------------------------------------------------------ 넛지 감지 (NEW-02a·NEW-02b · E37 재개 신호)
# 로봇이 멈춰(PAUSED) 있는 동안 사람이 살짝 밀거나 톡 치는 것을 힘으로 본다 — HMI 버튼 없이도 재개할 수 있게.
#    이동 중이 아니라 정지 상태에서만 쓴다 — 그래서 순수 힘 감시(모션 없음)만으로 충분하다.
_nudge_baseline = None                                   # start_nudge_watch() 가 기록한 정지 시점 힘
_nudge_above_since = None                                # threshold_n 을 넘기 시작한 시각(모노토닉) — 끊기면 None
_nudge_counted = False                                   # E48: 이번 접촉을 이미 한 번으로 셌나 — 손을 떼기 전엔 다시 안 센다
_nudge_taps = []                                         # E48: 지금까지 센 두드림 시각들(첫 두드림부터 window_s 안)


def start_nudge_watch():
    """넛지 감시 시작 — 지금(멈춘 자리) 힘을 기준으로 삼는다. PAUSED 들어갈 때 한 번 부른다. 두드림 횟수도 처음부터."""
    global _nudge_baseline, _nudge_above_since, _nudge_counted, _nudge_taps
    _nudge_baseline = read_force()
    _nudge_above_since = None
    _nudge_counted = False
    _nudge_taps = []


def check_nudge(threshold_n, hold_s, taps=1, window_s=2.0):
    """기준보다 threshold_n 넘게 벗어난 상태가 hold_s 동안 이어지면 한 번 친 것으로 센다. taps 번(기본 1)이 window_s 안에 모이면 True.
    호출부(flow)가 대기 루프에서 반복해서 부른다.

    한 번 튄 값(순간 노이즈)에 오검출하지 않으려고 유지 시간을 본다(hold_s). 벗어났다가 곧 가라앉으면 다시 None 부터.
    E48: 케이블 이상·툴 놓침 모두 15 N 으로 통일 — 한 접촉은 손을 떼(기준 아래로 내려가)야 다음 번으로 센다.
       첫 두드림 뒤 window_s(cell.limits.nudge_tap_window_s) 안에 taps(cell.limits.nudge_taps)번째가 오면 True 이고 상태를 비운다.
       window 가 지나면 처음부터 다시 센다(우연한 접촉 한 번으로는 재개되지 않게).
    start_nudge_watch() 를 먼저 불러야 한다 — 안 불렀으면 RuntimeError.
    """
    global _nudge_above_since, _nudge_counted, _nudge_taps
    if _nudge_baseline is None:
        raise RuntimeError('check_nudge: start_nudge_watch() 를 먼저 불러 기준을 잡는다')
    f = read_force()
    mag = sum((f[i] - _nudge_baseline[i]) ** 2 for i in range(3)) ** 0.5   # xyz 크기, 정지 시점 대비
    now = time.monotonic()
    if _nudge_taps and now - _nudge_taps[0] > float(window_s):        # 첫 두드림 뒤 너무 오래 지났다 → 처음부터
        _nudge_taps = []
    if mag >= threshold_n:
        if _nudge_above_since is None:
            _nudge_above_since = now
        elif not _nudge_counted and now - _nudge_above_since >= hold_s:
            _nudge_counted = True                                        # 이 접촉은 한 번
            _nudge_taps.append(now)
            if len(_nudge_taps) >= max(1, int(taps)):
                _nudge_taps = []
                _nudge_above_since = None
                _nudge_counted = False
                return True
    else:
        _nudge_above_since = None
        _nudge_counted = False                                           # 손을 뗐다 → 다음 두드림을 받을 수 있다
    return False


def contact_down(max_depth, limit, timeout_s=None, keep_compliance=False, step_mm=None):
    """순응 ON 상태로 contact_step_mm 씩 내려가며 Z 힘이 limit 에 닿을 때까지 → (depth_mm, force_n).

    멈추는 조건: 시작할 때보다 Z 힘이 limit 만큼 커짐(접촉) · 깊이 ≥ max_depth(바닥 못 찾음) —
    둘을 가르는 건 부르는 쪽(depth < max_depth 면 접촉). 돌려주는 force_n 도 시작 대비 변화량이다.
    주의: 절대값으로 보면 안 된다: 툴 무게 설정에 없는 무게(솔·수세미)가 있으면 공중에서도 Fz 가 2 N 쯤 나와서
    내려가기도 전에 "바닥"이 된다(실기: 깊이 0.1 mm 에서 접촉 오판).
    순응을 켜 두어 단단한 작업대에 닿아도 한 단계만큼의 힘만 걸린다. 끝나면 순응을 끄고 그 자리에 선다 —
    단 `keep_compliance=True`면 끄지 않는다(바로 이어서 순응 상태로 다른 동작을 할 때:
    그릇 나선 진입 직전에 순응을 껐다 바로 다시 켜는 게 비동기 나선이 시작 안 하는 것과 관련 있어 보여서 없앰).
    힘이 cell.force.force_max_n 을 넘으면 ForceLimitError, cell.limits.timeout_s 를 넘으면 MotionTimeout.
    step_mm — 한 걸음 크기를 부르는 쪽이 정할 수 있다(없으면 cell.force.contact_step_mm 3). 순응 걸음 하나가 ≈3 s 라
       마지막 5 mm 만 감시하는 툴 반납·팔레트 삽입(f1.watch_step_mm)은 5 mm 한 걸음으로 간다.
       닿으면 순응이 그 걸음만큼만 눌리므로 걸음이 클수록 눌리는 힘도 커진다 — Z 강성 200 N/m × 5 mm = 1 N 이라 여유 있다.
    """
    if max_depth <= 0:
        raise ValueError(f'contact_down: max_depth={max_depth} mm — 0 보다 커야 한다')
    _check_force_args(limit=limit)
    d = dsr()
    step = _force_cfg('contact_step_mm') if step_mm is None else float(step_mm)
    if step <= 0:
        raise ValueError(f'contact_down: step_mm={step} mm — 0 보다 커야 한다')
    vel = _force_cfg('contact_vel_mm_s') * _vel_scale()
    acc = _force_cfg('contact_acc_mm_s2')
    stx = _force_cfg('compliance_stx')
    f_max = _force_cfg('force_max_n')
    timeout = _limits_cfg('timeout_s') if timeout_s is None else float(timeout_s)   # 부르는 쪽이 줄 수 있다(그릇 닦기 40 s · V-03)

    d.mwait()
    z0 = _current_z(d)
    f0 = read_force()[2]                                # 내려가기 전 Z 힘 = 기준(툴 무게·옵셋 포함)
    _ok(d.task_compliance_ctrl(stx), 'task_compliance_ctrl')
    _state['compliance'] = True
    waited = 0.0                                        # 주의: 일시정지한 시간은 세지 않는다 — 사람이 멈춰 둔 동안 TIMEOUT 나면 안 된다
    last = time.monotonic()
    try:
        while True:
            now = time.monotonic()
            if not is_paused():
                waited += now - last
            last = now
            depth = z0 - _current_z(d)
            f = abs(read_force()[2] - f0)               # 시작 대비 변화량 (누르는 힘)
            if f > f_max:
                raise ForceLimitError(f'contact_down: 누르는 힘 {f:.1f} N > force_max_n {f_max} N (깊이 {depth:.1f} mm)')
            if f >= limit or depth >= max_depth:
                return depth, f
            if waited > timeout:
                raise MotionTimeout(f'contact_down: {timeout} s 안에 접촉·최대 깊이에 닿지 않았다 (깊이 {depth:.1f} mm)')
            dz = min(step, max_depth - depth)
            move_rel(0.0, 0.0, -dz, 'BASE', vel_mm_s=vel, acc_mm_s2=acc)
    finally:
        if not keep_compliance:
            force_off()


def periodic_search(amp, period, duration):
    """Move Periodic 으로 TOOL 기준 X·Y 왕복 탐색(홈 안착). X 주기 period, Y 주기 period × search_y_period_ratio.

    두 축의 주기를 다르게 해서 한 선이 아니라 면을 훑는다(중급교육1 Move Periodic 실습 3). duration(s) 이 시간 한도.
    동기 동작이라 도는 도중에는 멈추지 않는다 — 들어갔는지는 끝난 뒤 부르는 쪽이 깊이·힘으로 판정한다.
    vel_scale < 1 이면 주기를 그만큼 늘려 느리게 한다(진폭·시간 한도는 그대로).
    """
    if amp <= 0 or period <= 0 or duration <= 0:
        raise ValueError(f'periodic_search: amp={amp} mm, period={period} s, duration={duration} s — 모두 0 보다 커야 한다')
    d = dsr()
    ratio = _force_cfg('search_y_period_ratio')
    period = period / _vel_scale()
    period_y = period * ratio
    repeat = max(1, int(duration // period_y))
    d.mwait()
    _ok(d.move_periodic(amp=[float(amp), float(amp), 0.0, 0.0, 0.0, 0.0],
                        period=[float(period), float(period_y), 0.0, 0.0, 0.0, 0.0],
                        repeat=repeat, ref=d.DR_TOOL), 'move_periodic')


def safe_retreat():
    """켜져 있는 힘·순응을 끄고 → X·Y 는 그대로 Z 만 cell.limits.safe_z_mm(BASE) 까지 올린다. 이미 위면 움직이지 않는다.

    주의: force_off() 가 실패해도 후퇴는 반드시 시도한다 — 힘이 안 꺼졌다고 툴을 용기 안에 두고 오면 더 위험하다.
       (끄기 실패는 후퇴한 뒤에 올린다)
    """
    d = dsr()
    safe_z = _limits_cfg('safe_z_mm')
    vel = _force_cfg('retreat_vel_mm_s') * _vel_scale()
    acc = _force_cfg('retreat_acc_mm_s2')
    off_error = None
    try:
        force_off()
    except BaseException as e:                       # noqa: BLE001 — 후퇴가 먼저다
        off_error = e
    z = _current_z(d)
    if z < safe_z:
        move_rel(0.0, 0.0, float(safe_z) - z, 'BASE', vel_mm_s=vel, acc_mm_s2=acc)
    if off_error is not None:
        raise off_error


# ------------------------------------------------------------------ 닦기 이동 (나선 · 원호) — 접촉 동작 전용
# 여기 두는 이유: 순응·힘제어를 켠 채 도는 접촉 모션이라 힘 함수와 같이 봐야 한다(AGENTS §3 규칙 4 — f3 는 cc.* 만 부른다).
#    자유 공간 이동은 motion.py 몫이다. 두 함수 모두 일시정지 폴링이 없다 — move_periodic 과 같은 취급이라
#    일시정지는 이 구간이 끝난 뒤 다음 이동에서 먹는다. 부르는 쪽이 구간 사이에서 is_halted() 를 본다.
def where():
    """지금 TCP 자세 [x, y, z, a, b, c] (BASE). 닦는 높이·나선이 실제로 돌았는지 확인에 쓴다."""
    d = dsr()
    pos, _ = d.get_current_posx(ref=d.DR_BASE)
    return [float(v) for v in pos]


def joints():
    """지금 관절 각도 [j1 … j6] (deg). 컵 닦기가 6번 축 360° 회전 전에 한계(±360°)를 확인하는 데 쓴다."""
    return [float(v) for v in dsr().get_current_posj()]


def stop_now():
    """지금 하던 동작을 즉시 정지(QSTOP · Stop Category 2 — 서보 전원 유지). 멈출 때까지 최대 3 s 기다린다.
    비동기 모션(Periodic 등)이 도는 중에 감시하다 이상을 보면 부른다. 정지는 통신 노드가 보낸다.
    제한: motion.py 의 내부 함수 _call('stop') 을 직접 쓴다(공개 함수 cc.stop() 과 같은 동작)."""
    _motion._call('stop')
    t0 = time.monotonic()
    while not motion_done() and time.monotonic() - t0 < 3.0:
        time.sleep(0.01)


def motion_done():
    """비동기 이동이 끝났나 (check_motion() == 0). move_spiral 이 도는 동안 힘을 보려고 쓴다."""
    return dsr().check_motion() == 0


def move_spiral(rev, rmax_mm, time_s, axis='z', ref='TOOL'):
    """나선(Move Spiral)을 비동기로 시작한다 — 끝을 기다리지 않는다(부르는 쪽이 motion_done() 으로 본다).

    주의: 속도(vel)로 부르면 드라이버(dsr_controller2)가 통째로 멈춘다(브링업 재시작). vel·acc 0 + time 으로만 부른다
       — 중급교육1 p.69 "[속도] → [시간] 지정 옵션을 이용하여 속도 설정", 실기로 확인.
    주의: 최대 반경에 비해 회전 수가 많으면 시작조차 하지 않는다(같은 쪽 경고) — 반경 14 mm 에 7바퀴·1.5 s 는 안 돌고
       2.8바퀴·3 s 는 돈다. 돌았는지는 부르는 쪽이 where() 로 확인한다.
    비동기라 순응이 이미 켜져 있어야 하고(중급1 p.69 "순응제어 및 비동기 제어를 활용하는 경우가 많다"),
    켤 때는 도는 중이 아니어야 한다(2.1903) → 여기서 먼저 mwait 한다.
    시간은 vel_scale 로 나누지 않는다: V-03 실기에서 돈 호출은 3 s 그대로였고,
       ÷ 0.3 = 10 s 로 준 제품 호출은 실기에서 명령은 받고 움직이지 않았다(알람 없음, 2회).
    접수는 되는데 조용히 실행 큐에 안 들어갈 때가 있다(알람 없음·check_motion 계속 0).
       원인을 컨트롤러 밖에서 못 찾아서, 시작을 못 잡으면 같은 명령을 최대 3번까지 다시 보낸다.
    """
    if rev <= 0 or rmax_mm <= 0 or time_s <= 0:
        raise ValueError(f'move_spiral: rev={rev} · rmax={rmax_mm} mm · time={time_s} s — 모두 0 보다 커야 한다')
    d = dsr()
    axis_c = _axis_const(d, axis)
    ref_c = {'BASE': d.DR_BASE, 'TOOL': d.DR_TOOL}[ref]
    max_tries = 3
    for attempt in range(1, max_tries + 1):
        d.mwait()
        _ok(d.amove_spiral(rev=float(rev), rmax=float(rmax_mm), lmax=0.0, vel=[0.0, 0.0], acc=[0.0, 0.0],
                           time=float(time_s), axis=axis_c, ref=ref_c), 'amove_spiral')       # vel_scale 로 나누지 않는다(위 설명)
        try:
            _wait_start(d, 'amove_spiral')
            return
        except RuntimeError:
            if attempt == max_tries:
                raise
            d.mwait()                                                    # 안 돈 채로 그 자리 — 다음 시도 전에 한 번 더 확인


def move_periodic(amp, period, repeat, ref='TOOL', atime=None, scale=True):
    """Move Periodic 을 비동기로 시작한다 — 끝을 기다리지 않는다(부르는 쪽이 motion_done() 으로 본다).

    amp · period 는 [x, y, z, rx, ry, rz] 6개. 길이 mm · 회전 deg · 주기 s.
    한 명령으로 이동과 회전을 같이 왕복한다(중급교육1 p.71 "일정한 진폭과 주기로 왕복 이동/회전 모션",
    p.73~75 실습 50 mm/2 s · 15°/2 s · 축마다 다른 주기).
    주의: ref=TOOL 의 회전 칸은 TCP 설정에 따라 도는 조인트가 달라진다 — 실기(TCP GripperDA_v1)에서 TOOL rx 가
       4번 조인트를 돌렸다 — 두산 정의대로다(rx 는 옆으로 누운 축). 그리퍼 축 회전 = TOOL rz = 6번 조인트.
       주의: Virtual 은 rx ↔ rz 를 뒤바꿔 움직이고, BASE rz 는 1·4번 조인트를 돌렸다 → Periodic 회전은 Virtual 결과를 믿지 않는다.
       부르는 쪽이 도는 동안 조인트를 감시한다(wipe_cup).
    주의: 어떤 축에 진폭을 주면 같은 축의 주기도 줘야 한다(반대도 마찬가지) — 빠지면 두산 오류 2.1218 (p.71~72).
    repeat = 왕복 횟수. 한 번 왕복하면 출발한 자리로 돌아온다(진폭은 편진폭 — 총 이동거리는 2배, p.71 그림).
    vel_scale < 1 이면 주기를 그만큼 늘려 느리게 한다(진폭은 그대로 — periodic_search 와 같은 방식).
    scale=False 면 주기를 그대로 쓴다 — 컵 세척은 vel_scale 예외(결정 E17).
    """
    if len(amp) != 6 or len(period) != 6:
        raise ValueError('move_periodic: amp · period 는 [x, y, z, rx, ry, rz] 6개로 준다')
    for i, (a, t) in enumerate(zip(amp, period)):
        if (a != 0) != (t != 0):                           # 한쪽만 준 축 → 2.1218
            raise ValueError(f'move_periodic: {i}번 축은 진폭({a})과 주기({t}) 중 하나만 있다 — '
                             '같은 축의 둘을 함께 준다(중급1 p.71, 두산 오류 2.1218)')
    if repeat < 1:
        raise ValueError(f'move_periodic: repeat={repeat} — 1 이상')
    d = dsr()
    slow = 1.0 / _vel_scale() if scale else 1.0
    d.mwait()
    _ok(d.amove_periodic(amp=[float(v) for v in amp], period=[float(v) * slow for v in period],
                         atime=0.0 if atime is None else float(atime),
                         repeat=int(repeat), ref={'BASE': d.DR_BASE, 'TOOL': d.DR_TOOL}[ref]), 'amove_periodic')


def move_arc(mid, end, vel_mm_s, vel_deg_s, radius_mm=0.0, acc_mm_s2=None, acc_deg_s2=None):
    """원호(Move C) — BASE 절대 자세 두 개(가운데·끝)를 지나는 호. 회전(a·b·c)도 같이 간다.

    radius_mm > 0 이면 다음 모션으로 이어 붙는다(중첩 가능한 모션은 Move L·C·J·JX 뿐 — 중급교육1 p.79).
    0 이면 그 자리에서 멈춘다 — 0 으로 이어 붙이면 원호마다 서서 작업대가 울린다(실기).
    속도에는 vel_scale 을 곱한다.
    가속도를 안 주면 cell.motion 100 % 기준 × vel_scale, 속도도 그 기준 × vel_scale 을 넘지 못한다.
    가속도를 주면(그릇 닦기 — V-03 rig_v03 값) 가속도는 그대로, 속도는 cell.motion 100 % 기준(vel_scale 안 곱함)까지만.
    """
    d = dsr()
    vel, acc = _line_vel_acc(vel_mm_s, vel_deg_s, acc_mm_s2, acc_deg_s2)
    _ok(d.movec([float(v) for v in mid], [float(v) for v in end], vel=vel, acc=acc,
                radius=float(radius_mm), ref=d.DR_BASE, mod=d.DR_MV_MOD_ABS), 'movec')


def move_pose(pose, vel_mm_s, vel_deg_s, acc_mm_s2, acc_deg_s2, radius_mm=0.0):
    """직선(Move L) — BASE 절대 자세로(회전 포함). 닦기 접촉 중 벽으로 붙기·중심 복귀에 쓴다(V-03 rig_v03 과 같은 명령).
    속도는 × vel_scale, cell.motion 100 % 기준(vel_scale 안 곱함)까지만 · 가속도는 준 값 그대로. 끝날 때까지 기다린다."""
    d = dsr()
    vel, acc = _line_vel_acc(vel_mm_s, vel_deg_s, acc_mm_s2, acc_deg_s2)
    _ok(d.movel([float(v) for v in pose], vel=vel, acc=acc, radius=float(radius_mm),
                ref=d.DR_BASE, mod=d.DR_MV_MOD_ABS), 'movel')


def move_joints(q, vel_deg_s, acc_deg_s2):
    """관절 이동(Move J) — 관절 6개 절대값으로, 속도 × vel_scale · 가속도 그대로. 끝날 때까지 기다린다.
    그릇 닦기의 HOME 이동을 V-03 rig_v03 과 같은 값(40 °/s × vel_scale · 40 °/s²)으로 하려고 둔다."""
    d = dsr()
    _ok(d.movej([float(v) for v in q], vel=_positive('vel_deg_s', vel_deg_s) * _vel_scale(),
                acc=_positive('acc_deg_s2', acc_deg_s2)), 'movej')


def move_line_rel(dx, dy, dz, vel_mm_s, acc_mm_s2):
    """직선 상대 이동(Move L, BASE) — 끝날 때까지 기다리는 동기 movel. 속도 × vel_scale · 가속도 그대로.
    그릇 닦기를 V-03 rig_v03 과 같은 명령(d.movel 동기)으로 하려고 둔다. 속도는 cell.motion 100 % × vel_scale 까지만."""
    d = dsr()
    top_v = float(_cell_key('motion', 'vel_tcp_max_mm_s')) * _vel_scale()
    _ok(d.movel([float(dx), float(dy), float(dz), 0.0, 0.0, 0.0],
                vel=min(_positive('vel_mm_s', vel_mm_s) * _vel_scale(), top_v), acc=_positive('acc_mm_s2', acc_mm_s2),
                ref=d.DR_BASE, mod=d.DR_MV_MOD_REL), 'movel')


def wait_done():
    """보낸 모션(이어 붙인 원호 포함)이 모두 끝날 때까지 기다린다(mwait)."""
    dsr().mwait()


def _line_vel_acc(vel_mm_s, vel_deg_s, acc_mm_s2, acc_deg_s2):
    s = _vel_scale()
    top_v, top_a = float(_cell_key('motion', 'vel_tcp_max_mm_s')), float(_cell_key('motion', 'acc_tcp_max_mm_s2'))
    if acc_mm_s2 is None or acc_deg_s2 is None:
        vel = [min(_positive('vel_mm_s', vel_mm_s) * s, top_v * s), _positive('vel_deg_s', vel_deg_s) * s]
        return vel, [top_a * s, top_a * s]
    vel = [min(_positive('vel_mm_s', vel_mm_s) * s, top_v), _positive('vel_deg_s', vel_deg_s) * s]
    return vel, [_positive('acc_mm_s2', acc_mm_s2), _positive('acc_deg_s2', acc_deg_s2)]


# ------------------------------------------------------------------ 내부
def _wait_start(d, what, limit_s=None):
    """비동기 모션이 실제로 시작할 때까지(check_motion ≠ 0) 기다린다. limit_s 안에 시작 안 하면 RuntimeError.

    주의: 실기에서 amove_spiral 이 0 을 돌려준 직후 check_motion 은 아직 0(멈춤)이다 → 부르는 쪽의
       `while not motion_done()` 이 한 번도 안 돌고 끝나 "나선이 돌지 않았다" 로 멈췄다(35 ms 만에).
       V-03 rig 는 wait_start 로 시작을 기다려서 돌았다 — 그 단계가 공용 함수로 옮길 때 빠졌다.
    """
    limit_s = _START_WAIT_S if limit_s is None else limit_s
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit_s:
        if d.check_motion() != 0:
            return
        time.sleep(0.02)
    raise RuntimeError(f'{what}: 명령은 받았는데 {limit_s:g} s 안에 움직이지 않았다 — 설정(회전 수·반경·시간)을 확인 '
                       f'· 그때 컨트롤러 {_controller_snapshot(d)}')


def _controller_snapshot(d):
    """출발을 안 했을 때 원인을 보려고 그 순간의 컨트롤러 상태를 글로 — 읽다 실패해도 멈추지 않는다."""
    out = []
    for name, fn in (('check_motion', 'check_motion'), ('robot_state', 'get_robot_state'),
                     ('robot_mode', 'get_robot_mode'), ('last_alarm', 'get_last_alarm')):
        try:
            out.append(f'{name}={getattr(d, fn)()!r}')
        except Exception as e:                                  # noqa: BLE001 — 진단만
            out.append(f'{name}=읽기 실패({type(e).__name__})')
    try:
        out.append(f'z={float(d.get_current_posx(ref=d.DR_BASE)[0][2]):.2f}')
    except Exception:                                           # noqa: BLE001
        pass
    return ' · '.join(out)


def _ok(ret, what):
    if ret != 0:
        raise RuntimeError(f'{what} 실패 (반환 {ret!r})')


def _axis_index(axis):
    if axis not in _AXES:
        raise ValueError(f"axis={axis!r} — 'x'·'y'·'z' 중 하나")
    return _AXES.index(axis)


def _axis_const(d, axis):
    return (d.DR_AXIS_X, d.DR_AXIS_Y, d.DR_AXIS_Z)[_axis_index(axis)]


def _check_force_args(**kw):
    f_max = _force_cfg('force_max_n')
    for name, v in kw.items():
        if not 0 < v <= f_max:
            raise ValueError(f'{name}={v} N — 0 보다 크고 cell.force.force_max_n({f_max} N) 이하여야 한다')


def _positive(name, v):
    if v is None or float(v) <= 0:
        raise ValueError(f'{name}={v} — 0 보다 커야 한다')
    return float(v)


def _current_z(d):
    pos, _ = d.get_current_posx(ref=d.DR_BASE)
    return float(pos[2])


def _force_cfg(key):
    return _cell_key('force', key)


def _limits_cfg(key):
    return _cell_key('limits', key)


def _vel_scale():
    """실행 인자 vel_scale (config.load 가 0 초과 1 이하로 검사한다). 없으면 1.0."""
    return float(cfg().get('run', {}).get('vel_scale', 1.0))


def _cell_key(section, key):
    try:
        value = cfg()['cell'][section][key]
    except (KeyError, TypeError):
        value = None
    if value is None:                   # 키가 없거나 INF-04 골격처럼 비어 있음(null)
        raise KeyError(f'cell.yaml 의 cell.{section}.{key} 가 없거나 비어 있다 — 한석형(cell.yaml) 에 요청. '
                       '값이 없으면 로봇을 움직이지 않는다')
    return value
