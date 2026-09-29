"""F3 접촉 닦기 — soap · wipe_bowl · wipe_cup.

soap 이 잡은 위치로 수세미/컵솔을 가려 작업 위치까지 데려가고(움직임), wipe_bowl·wipe_cup 은 호출된 자리에서
바로 하강해 세척한 뒤 그 높이로만 복귀한다. 숫자는 params.yaml f3 절 · cell.yaml 에서 읽는다.
"""
import csv
import math
import os
import threading
import time

import cobot_common as cc
from cobot_api import FORCE_LIMIT, OK, ROBOT_ERROR, TIMEOUT, TOOL_LOST, Result, WipeBowlResult, WipeCupResult


class JointGuardStop(RuntimeError):
    """컵 세척 중 1·4번 조인트가 움직여 즉시 정지했다."""


class ToolLostError(RuntimeError):
    """쥔 폭이 soap 시작 때 기준보다 크게 벗어났다 — 닦는 도중 놓쳤다 (TOOL_LOST)."""


START = 'HOME'                       # 닦기의 기준 자리 (cell.stations.HOME)

FORCE_LOG_HEADER = ('t', 'fx', 'fy', 'fz', 'target')   # 힘 로그 CSV 열

_tool_baseline_mm = None             # soap() 이 잡을 때 재는 기준 폭 — wipe_bowl/wipe_cup 도 이 값으로 본다


def _tool_lost_now():
    """기준 폭 대비 벗어났는지만 본다(예외 없음) — 기준 없으면(soap 안 거침) False. 감시 스레드가 반복 호출한다.

    허용오차는 새로 만들지 않고 f2.slip_tol_mm 을 그대로 쓴다(실기로 재현성 확인 — 놓치면
    변화량이 수세미 약 3 mm·솔 약 2 mm, 정상 흔들림은 0.1~0.2 mm 라 이 허용오차로 충분히 갈린다).
    """
    if _tool_baseline_mm is None:
        return False
    w = float(cc.grip_width())
    return abs(w - _tool_baseline_mm) > _tool_tol_mm()


def _tool_tol_mm():
    """툴 놓침 판정 허용오차(mm) = f2.slip_tol_mm. 종류별 dict({BOWL: 1.0, CUP: 1.5})면 가장 작은 값을 쓴다
    — 툴 손잡이는 단단해 작은 허용오차로 충분. 숫자 하나면 그대로."""
    tol = cc.cfg()['f2']['slip_tol_mm']
    if isinstance(tol, dict):
        return min(float(v) for v in tol.values())
    return float(tol)


def _check_tool(where):
    """벗어났으면 즉시 멈추고(stop_now) ToolLostError — move_periodic·move_spiral 은 이미 도는 중 반복 호출된다."""
    if not _tool_lost_now():
        return
    cc.stop_now()
    w = float(cc.grip_width())
    tol = _tool_tol_mm()
    raise ToolLostError(f'{where}: 폭 {w:.2f} mm (기준 {_tool_baseline_mm:.2f} mm · 허용 ±{tol:g}) — 놓침 의심')


def _set_baseline():
    """지금 쥔 폭을 놓침 판정 기준으로 삼는다 — soap()·wipe_bowl()·wipe_cup() 시작부에서 각자 부른다
    (wipe_bowl/wipe_cup 도 자기 것을 새로 잰다 — 닦기 재시도(E61 · 힘 상한·시간 초과)는 soap() 없이 그 함수만 다시 부른다)."""
    global _tool_baseline_mm
    _tool_baseline_mm = float(cc.grip_width())


def _on_tool_lost(e, where):
    """ToolLostError 처리 공통부 — 경고 남기고 기준을 지운다(뒤이은 후퇴 이동까지 다시 검사하지 않으려고). code 를 돌려준다."""
    global _tool_baseline_mm
    _warn(f'{where} 중단: {e}')
    _tool_baseline_mm = None
    return TOOL_LOST


def _finish_guard(moved, code):
    """정리 단계에서 움직이면 안 되는 상태면 경고만 남기고 True(호출부는 곧장 return) — 위치 불명 또는 TOOL_LOST."""
    if not moved:
        _warn('🚨 로봇이 어디 있는지 모른다 → 힘만 끄고 **움직이지 않았다**. '
              '티치펜던트로 상태를 확인하고 사람이 복구한다')
        return True
    if code == TOOL_LOST:
        _warn('TOOL_LOST — 그 자리에 그대로 둔다. 사람이 툴을 다시 넣고 넛지·재개할 때까지 안 움직인다')
        return True
    return False


def _stop_if_aborted(moved, code):
    """힘 상한·시간 초과로 끝났으면 남은 비동기 동작(나선·주기 운동)을 먼저 즉시 정지한다.
    정리 단계의 wait_done(mwait)이 남은 동작을 끝까지 기다리지 않게 — 정상 종료·TOOL_LOST·위치 불명은 여기서 건드리지 않는다.
    stop_now 는 멈춤을 최대 3 s 기다린다. 실패해도 경고만 남기고 정리를 계속한다."""
    if not moved or code not in (FORCE_LIMIT, TIMEOUT):
        return
    _warn(f'{code} — 하던 동작을 즉시 정지(stop_now) → 힘·순응 끄고 곧게 위로')
    try:
        cc.stop_now()
        if not cc.motion_done():
            _warn(f'{code} — 즉시 정지를 보냈는데 3 s 안에 멈추지 않았다 → 남은 동작이 끝나기를 기다린 뒤 올라간다 · 눈으로 확인')
    except Exception as e:                                    # noqa: BLE001
        _warn(f'정리 실패: 즉시 정지 — {e!r} · 눈으로 확인')


def _finish_rise(rise):
    """동작 끝 대기 → 곧게 호출 시점 높이로 상승 — 실패해도 예외를 삼키고 경고만 남긴다."""
    for what, fn in (('동작 끝 대기', cc.wait_done), ('곧게 올라오기', rise)):
        try:
            fn()
        except Exception as e:                                    # noqa: BLE001
            _warn(f'정리 실패: {what} — {e!r} · 눈으로 확인')


def _guarded_move_rel(dx, dy, dz, frame, vel_mm_s, acc_mm_s2):
    """move_rel 은 통짜 호출이라 도중에 검사할 틈이 없다 — 별도 스레드로 폭을 지켜보다 놓치면 cc.halt() 로 그 자리에서 멈춘다.

    cc.halt()/is_halted() 는 다른 스레드에서 불러도 안전하다(motion.py 명시). halt 로 멈추면 move_rel 이
    MotionHalted 를 던지는데, 우리가 건 halt 면 clear_halt() 로 직접 풀고 ToolLostError 로 바꿔서 올린다
    (안 풀면 다음 이동을 아무것도 못 보낸다 — 재개가 막힌다). 남이 건 halt(HMI 등)면 그대로 올린다.
    """
    lost = {'via_halt': False}
    stop_watch = threading.Event()

    def watch():
        while not stop_watch.is_set():
            if _tool_lost_now():
                lost['via_halt'] = True
                cc.halt()
                return
            time.sleep(0.02)                                   # 20 ms 주기로 폭을 본다

    def _lost_error():
        cc.clear_halt()
        w = float(cc.grip_width())
        tol = _tool_tol_mm()
        return ToolLostError(f'이동 중: 폭 {w:.2f} mm (기준 {_tool_baseline_mm:.2f} mm · 허용 ±{tol:g}) — 놓침 의심')

    t = threading.Thread(target=watch, daemon=True)
    t.start()
    try:
        cc.move_rel(dx, dy, dz, frame, vel_mm_s=vel_mm_s, acc_mm_s2=acc_mm_s2)
    except cc.MotionHalted:
        if not lost['via_halt']:
            raise
        raise _lost_error() from None
    else:
        # 주의: halt 가 걸린 바로 그 순간 이동이 자연스럽게 끝나버리면 move_rel 이 예외 없이 돌아올 수 있다
        #    (motion.py 의 폴링과 우리 감시 스레드 사이의 경합) — 그래도 우리가 halt 를 걸었던 거면 놓침이다.
        if lost['via_halt']:
            raise _lost_error() from None
    finally:
        stop_watch.set()
        t.join(timeout=0.5)


def soap(count: int, kind: str = None) -> Result:
    """세제 담금. kind 는 안 쓴다(쥔 위치로 스스로 판정)."""
    _set_baseline()
    return _soap_twist_updown()


def _soap_is_cup():
    """지금 잡은 위치(BASE X)로 컵솔인지 판정한다."""
    split = float(cc.cfg()['f3']['soap']['tool_split_x_mm'])
    return cc.where()[0] > split


def _soap_target(is_cup):
    """작업 위치 (x, y, z) — 수세미는 HOME, 컵솔은 HOME + z(over_cup_up_mm) + y(over_cup_dy_mm)."""
    home = cc.cfg()['cell']['stations'][START]
    x, y, z = float(home['posx_x_mm']), float(home['posx_y_mm']), float(home['posx_z_mm'])
    if is_cup:
        wc = cc.cfg()['f3']['wipe_cup']
        z += float(wc['over_cup_up_mm'])
        y += float(wc['over_cup_dy_mm'])
    return x, y, z


def _soap_move_to(target_xyz):
    """지금 자리에서 목표로 — z 먼저(제자리 상승) → x·y(수평 이동)."""
    wb = cc.cfg()['f3']['wipe_bowl']
    vel, acc = float(wb['fast_vel_mm_s']) * _scale(), float(wb['fast_acc_mm_s2']) * _scale()
    tx, ty, tz = target_xyz
    dz = tz - cc.where()[2]
    if dz > 0:
        _guarded_move_rel(0.0, 0.0, dz, 'BASE', vel, acc)
    now = cc.where()
    dx, dy = tx - now[0], ty - now[1]
    if abs(dx) > 1e-6 or abs(dy) > 1e-6:
        _guarded_move_rel(dx, dy, 0.0, 'BASE', vel, acc)


def _soap_twist_updown() -> Result:
    """비틀기 → Z 왕복 → 작업 위치 이동. soap() 의 실제 구현."""
    p = cc.cfg()['f3']['soap']
    duration = float(p['duration_s'])
    ramp = float(p['ramp_s'])
    t0 = time.monotonic()
    code, moved = ROBOT_ERROR, True
    is_cup = _soap_is_cup()
    target = _soap_target(is_cup)
    try:
        _halt_check('세제 동작 시작')
        twist = float(p['twist_deg'])
        twist_period = float(p['twist_period_s'])
        peak = 2.0 * math.pi * twist / twist_period          # 로봇 한계 넘으면 거절 — 미리 본다
        limit = float(p['rot_vel_limit_deg_s'])
        if peak > limit:
            raise ValueError(f'soap: 비틀기 최고 {peak:.0f}°/s > 로봇 한계 {limit:g}°/s — twist_period_s 를 '
                             f'{2 * math.pi * twist / limit:.2f} s 이상으로')
        if time.monotonic() - t0 > duration:
            raise cc.MotionTimeout(f'soap: {duration:g} s 안에 비틀기를 시작 못 했다')
        cc.move_periodic([0.0, 0.0, 0.0, 0.0, 0.0, twist], [0.0, 0.0, 0.0, 0.0, 0.0, twist_period],
                          repeat=int(p['twist_cycles']), ref='TOOL', atime=ramp, scale=False)
        while not cc.motion_done():
            _halt_check('비틀기 도는 중')
            if time.monotonic() - t0 > duration:
                cc.stop_now()
                raise cc.MotionTimeout(f'soap: {duration:g} s 안에 비틀기를 못 끝냈다')
            time.sleep(0.05)                                      # 50 ms 마다 진행 확인

        updown = float(p['updown_mm'])
        up_period = float(p['updown_period_s'])
        if time.monotonic() - t0 > duration:
            raise cc.MotionTimeout(f'soap: {duration:g} s 안에 왕복을 시작 못 했다')
        cc.move_periodic([0.0, 0.0, updown, 0.0, 0.0, 0.0], [0.0, 0.0, up_period, 0.0, 0.0, 0.0],
                          repeat=int(p['updown_cycles']), ref='TOOL', atime=ramp, scale=False)
        while not cc.motion_done():
            _halt_check('왕복 도는 중')
            if time.monotonic() - t0 > duration:
                cc.stop_now()
                raise cc.MotionTimeout(f'soap: {duration:g} s 안에 왕복을 못 끝냈다')
            time.sleep(0.05)                                      # 50 ms 마다 진행 확인
        _halt_check('작업 위치로 이동')
        if time.monotonic() - t0 > duration:
            raise cc.MotionTimeout(f'soap: {duration:g} s 안에 작업 위치로 이동을 못 끝냈다')
        _soap_move_to(target)
        code = OK
    except (cc.MotionHalted, cc.MoveIncomplete):          # 위치를 모른다 → 올리지 않는다
        moved = False
        raise
    except ToolLostError as e:
        code = _on_tool_lost(e, 'soap')
    except (cc.MotionTimeout, cc.MoveTimeout):
        code = TIMEOUT
    except (RuntimeError, ValueError, KeyError):
        code = ROBOT_ERROR
    finally:
        try:
            cc.force_off()
        except Exception:                                  # noqa: BLE001 — 복구는 끝까지
            _warn('정리 실패: force_off — 눈으로 확인')
        if not _finish_guard(moved, code) and code != OK:   # 성공했으면 이미 목표 위치 — 실패했을 때만 후퇴
            try:
                _soap_move_to(target)
            except Exception as e:                          # noqa: BLE001
                _warn(f'정리 실패: 목표 위치로 후퇴 — {e!r} · 눈으로 확인')
    return Result(ok=(code == OK), code=code)


def wipe_bowl() -> WipeBowlResult:
    """그릇 안쪽을 수세미로 닦는다 — 고정 좌표 방식. 호출된 자리에서 바로 하강한다."""
    p = cc.cfg()['f3']['wipe_bowl']
    t0 = time.monotonic()
    log = _Log(p, t0)
    code, started, moved, bowl_check_z = ROBOT_ERROR, False, True, None
    try:
        _set_baseline()
        _halt_check('그릇 닦기 시작')
        bowl_check_z = cc.where()[2]                        # 호출된 높이 기록 — 안 움직임
        started = True
        _bowl_move_z(-float(p['fast_down_mm']), p['fast_vel_mm_s'], p['fast_acc_mm_s2'])
        _bowl_zero(log)
        if abs(log.base[2]) > float(p['air_force_max_n']):
            raise RuntimeError(f'빠른 하강 뒤 공중 |Fz| {abs(log.base[2]):.1f} N > {p["air_force_max_n"]:g} N — 툴 무게·접촉 확인')
        depth, f = cc.contact_down(float(p['find_max_mm']), float(p['find_limit_n']),
                                   timeout_s=float(p['contact_timeout_s']), keep_compliance=True)
        z_contact = cc.where()[2]
        _info(f'wipe_bowl 바닥: 빠르게 {p["fast_down_mm"]:g} mm + 찾기 {depth:.1f} mm · 접촉 힘 {f:.1f} N '
              f'· 바닥 Z {z_contact:.1f} · 공중 기준 Fz {log.base[2]:.2f} N')
        if depth >= float(p['find_max_mm']) - 0.5:       # 0.5 mm 여유: 최대 깊이까지 다 내려갔다 = 바닥이 없었다
            raise RuntimeError(f'{p["find_max_mm"]:g} mm 를 내려가도 바닥을 못 찾았다 — 그릇·좌표 확인')
        _bowl_settle_at_contact(p, z_contact)                # 순응은 contact_down 이 켜 둔 채로 넘어온다
        _halt_check('바닥 나선')
        r_wall = _bowl_spiral(p, log)                        # 바닥 나선
        _bowl_force_on(p, log, float(p['target_force_n']))   # 힘제어 → 벽면
        _halt_check('벽면 회전')
        _bowl_wall(p, log, r_wall)
        _check_tool('벽면 끝')
        cc.force_release()
        log.target = 0.0
        _bowl_to_center(p, log)
        cc.force_off()
        code = OK
    except (cc.MotionHalted, cc.MoveIncomplete) as e:        # 위치를 모른다 → 힘만 끄고 움직이지 않는다
        _warn(f'wipe_bowl 중단: {type(e).__name__}: {e}')
        moved = False
        raise
    except ToolLostError as e:
        code = _on_tool_lost(e, 'wipe_bowl')
    except cc.ForceLimitError as e:
        _warn(f'wipe_bowl 중단: {e}')
        code = FORCE_LIMIT
    except (cc.MotionTimeout, cc.MoveTimeout) as e:
        _warn(f'wipe_bowl 중단: {e}')
        code = TIMEOUT
    except (RuntimeError, ValueError, KeyError) as e:
        _warn(f'wipe_bowl 중단: {type(e).__name__}: {e}')
        code = ROBOT_ERROR
    finally:
        _bowl_finish(p, started, moved, bowl_check_z, code)
    return WipeBowlResult(ok=(code == OK), code=code, force_log_path=log.save(),
                          duration_s=time.monotonic() - t0, force_mean_n=log.mean())


def _bowl_move_z(dz, vel, acc):
    """빠른 하강·상승 (BASE z 상대 이동)."""
    _guarded_move_rel(0.0, 0.0, float(dz), 'BASE', float(vel) * _scale(), float(acc) * _scale())


def _bowl_zero(log):
    """공중 힘 기준값 — 5회 평균."""
    fs = [cc.read_force() for _ in range(5)]
    log.start([sum(v) / len(fs) for v in zip(*fs)])


def _bowl_settle_at_contact(p, z_contact):
    """밀렸으면(0.05mm 넘게) 찾은 높이로만 되돌린다. 순응은 끄지 않는다."""
    dz = z_contact - cc.where()[2]
    if abs(dz) > 0.05:                                  # 0.05 mm 아래는 밀린 게 아니라 측정 잡음으로 본다
        _bowl_move_z(dz, p['press_vel_mm_s'], p['press_acc_mm_s2'])
    _info(f'wipe_bowl 순응 유지 · Z {z_contact:.1f} → {cc.where()[2]:.1f} mm')


def _bowl_spiral(p, log):
    """바닥 닦기 — move_spiral 한 번(최대 3회 재시도는 force.py 안에서)."""
    p0 = cc.where()
    log.center = list(p0)
    r_wall = log.wall_r()
    rev = max(1.0, round(r_wall / p['spiral_pitch_mm'], 1))
    cc.move_spiral(rev, r_wall, float(p['spiral_time_s']))
    rmax_seen = _bowl_sample_spiral(p, log, p0)
    _info(f'wipe_bowl 나선: 최대 반지름 {rmax_seen:.1f} mm (목표 {r_wall:.1f})')
    if rmax_seen < r_wall * 0.5:                        # 목표 반지름의 절반도 못 나갔으면 나선이 돌지 않은 것
        raise RuntimeError(f'나선이 돌지 않았다(최대 {rmax_seen:.1f} mm)')
    return r_wall


def _bowl_sample_spiral(p, log, p0):
    """나선 도는 동안 힘·반지름 샘플링, 끝나면 최대 반지름을 돌려준다."""
    rmax = 0.0
    t0 = time.monotonic()
    while True:
        log.watch('spiral')
        now = cc.where()
        rmax = max(rmax, math.hypot(now[0] - p0[0], now[1] - p0[1]))
        if cc.motion_done():
            return rmax
        if time.monotonic() - t0 > float(p['spiral_time_s']) + 5.0:   # 나선 명령 시간 + 5 s 여유
            raise cc.MotionTimeout('나선이 끝나지 않는다')
        if log.over_time():
            raise cc.MotionTimeout(f'wipe_bowl: 전체 {p["duration_s"]} s 초과(나선)')
        _check_tool('나선 도는 중')
        time.sleep(p['sample_s'])


def _bowl_force_on(p, log, target):
    """힘제어 ON — 공중 기준값을 더한 목표로."""
    cc.wait_done()
    cc.force_on('z', target + abs(log.base[2]), p['limit_n'])
    log.target = target


def _bowl_wall(p, log, r_wall):
    """벽면 원호 — turns 바퀴, 매번 ±twist_deg 비틀며 시계 방향."""
    x0, y0, z_now, a, b, c = log.center
    lin_v, rot_v = float(p['lin_vel_mm_s']), float(p['rot_vel_deg_s'])
    lin_a, rot_a = float(p['lin_acc_mm_s2']), float(p['rot_acc_deg_s2'])
    now = cc.where()
    dx, dy = now[0] - x0, now[1] - y0
    th0 = math.atan2(dy, dx) if math.hypot(dx, dy) > 1e-6 else 0.0
    per = max(2, int(round(360.0 / p['wall_arc_deg'])))
    n = int(p['turns'] * per)
    dth = -2 * math.pi / per
    chord = 2 * r_wall * abs(math.sin(dth / 2))
    radius = min(float(p['blend_radius_mm']), chord * 0.45)   # 블렌딩 반지름은 현(chord)의 절반 미만이어야 원호가 겹치지 않는다
    tw = float(p['twist_deg'])

    def pose(th, rz):
        return [x0 + r_wall * math.cos(th), y0 + r_wall * math.sin(th), z_now,
                a, b, (c + rz + 180.0) % 360.0 - 180.0]

    twist = 1
    cc.wait_done()
    cc.move_pose(pose(th0, tw), float(p['wall_approach_vel_mm_s']), rot_v, lin_a, rot_a)
    log.watch('wall')
    for k in range(n):
        if log.over_time():
            raise cc.MotionTimeout(f'wipe_bowl: 전체 {p["duration_s"]} s 초과(벽면)')
        th_mid, th_end = th0 + dth * (k + 0.5), th0 + dth * (k + 1)
        rz_mid = tw * twist
        twist = -twist
        cc.move_arc(pose(th_mid, rz_mid), pose(th_end, tw * twist), lin_v, rot_v,
                    0.0 if k == n - 1 else radius, lin_a, rot_a)
        if k % max(1, int(p['force_every'])) == 0:
            log.watch('wall')
            _check_tool('벽면 도는 중')
    cc.wait_done()


def _bowl_to_center(p, log):
    """벽면 끝나면 중심 자리로 복귀."""
    x0, y0, z_now, a, b, c = log.center
    cc.wait_done()
    cc.move_pose([x0, y0, z_now, a, b, c], float(p['lin_vel_mm_s']), float(p['rot_vel_deg_s']),
                 float(p['lin_acc_mm_s2']), float(p['rot_acc_deg_s2']))


def _bowl_finish(p, started, moved, bowl_check_z, code=None):
    """(힘 상한·시간 초과면 먼저 즉시 정지) → 힘 끄기는 언제나 → moved 면 동작 끝 대기 → 곧게 호출 시점 높이로 상승.
    움직여서 자리를 다시 찾지 않는다."""
    if not started:
        try:
            cc.force_off()
        except Exception:                                    # noqa: BLE001
            _warn('정리 실패: force_off — 눈으로 확인')
        return
    _stop_if_aborted(moved, code)
    try:
        cc.force_off()
    except Exception as e:                                    # noqa: BLE001
        _warn(f'정리 실패: 힘·순응 끄기 — {e!r} · 눈으로 확인')
    if _finish_guard(moved, code):
        return

    def rise():
        dz = bowl_check_z - cc.where()[2]
        if dz > 0:
            _bowl_move_z(dz, p['fast_vel_mm_s'], p['fast_acc_mm_s2'])

    _finish_rise(rise)


# ── 아래 cup_hops · _Trip 은 치구(rig_v10 · sim_f3_seq) 전용 — 제품 흐름(wipe_bowl · wipe_cup)은 쓰지 않는다. 사이의 _fast_z 는 wipe_cup 도 쓴다 ──
def cup_hops(p):
    """HOME → 컵 위 상대 이동 [(dx, dy, dz), ...] — rig_v10 전용 도구, 제품 코드는 안 쓴다."""
    up, dy = float(p['over_cup_up_mm']), float(p['over_cup_dy_mm'])
    return [(0.0, 0.0, up), (0.0, dy, 0.0)]


def _fast_z(p, dz):
    """빠른 하강·상승 (BASE z 상대 이동, 컵 전용 속도) — wipe_cup 과 _Trip 이 같이 쓴다."""
    _guarded_move_rel(0.0, 0.0, float(dz), 'BASE',
                      float(p['fast_vel_mm_s']) * _scale(), float(p['fast_acc_mm_s2']) * _scale())


class _Trip:
    """HOME ↔ 닦는 자리 오가기 — rig_v10 전용 도구, 제품 코드(wipe_cup)는 안 쓴다."""

    def __init__(self, hops, p):
        self.hops, self.done, self.spot_z, self.started = list(hops), [], None, False
        self.p = p

    def go(self):
        self.started = True
        cc.move_to(START, carrying=True)
        for hop in self.hops:
            cc.move_rel(*hop, 'BASE')
            self.done.append(hop)
        self.spot_z = cc.where()[2]

    def back(self, move=True):
        try:
            cc.force_off()
        except Exception:                                     # noqa: BLE001
            _warn('정리 실패: force_off — 눈으로 확인')
        if not move:
            _warn('🚨 로봇이 어디 있는지 모른다 → 힘만 끄고 **움직이지 않았다**. '
                  '티치펜던트로 상태를 확인하고 사람이 복구한다')
            return
        if not self.started:
            return
        try:
            if self.spot_z is not None:
                rise = self.spot_z - cc.where()[2]
                if rise > 0:
                    _fast_z(self.p, rise)
            for dx, dy, dz in reversed(self.done):
                cc.move_rel(-dx, -dy, -dz, 'BASE')
            cc.move_to(START, carrying=True)
        except Exception:                                     # noqa: BLE001
            _warn('정리 실패: HOME 복귀 — 눈으로 확인')


def _info(msg):
    cc.io_node().get_logger().info(msg)


def _warn(msg):
    cc.io_node().get_logger().error(msg)


def _halt_check(where):
    """구간 사이에서 강제정지·놓침을 본다 — 나선·원호는 도는 중에 끊을 수 없다."""
    if cc.is_halted():
        cc.stop_now()
        raise cc.MotionHalted(f'{where} 앞에서 강제정지')
    _check_tool(where)


class _Log:
    """닦는 동안의 공중 기준값·중심 자세·힘 로그."""

    def __init__(self, p, t0):
        self.p, self.t0 = p, t0
        self.samples, self.presses = [], []
        self.base = [0.0] * 6
        self.center = None
        self.sweep = 0.0
        self.target = 0.0

    def start(self, force):
        self.base = list(force)

    def wall_r(self):
        """벽에 닿는 반지름 = (그릇 안지름 − 툴 지름)/2 + 벽 누름. 힘으로 찾지 않는다(고정 좌표 방식)."""
        p = self.p
        return max(0.0, (p['bowl_inner_d_mm'] - p['tool']['d_mm']) / 2 + p['wall_press_mm'])

    def watch(self, phase):
        """힘만 읽어 기록·상한 확인."""
        p = self.p
        f = cc.read_force()
        press = abs(f[2] - self.base[2])
        lateral = math.hypot(f[0] - self.base[0], f[1] - self.base[1])
        self.samples.append((round(time.monotonic() - self.t0, 3), f[0], f[1], f[2], self.target))
        self.presses.append(press)
        if press > p['limit_n']:
            raise cc.ForceLimitError(f'{phase}: 누르는 힘 {press:.1f} N > {p["limit_n"]} N')
        if lateral > p['lateral_max_n']:
            raise cc.ForceLimitError(f'{phase}: 옆 힘 {lateral:.1f} N > {p["lateral_max_n"]} N')

    def over_time(self):
        return time.monotonic() - self.t0 > self.p['duration_s']

    def mean(self):
        return sum(self.presses) / len(self.presses) if self.presses else 0.0

    def save(self):
        return _save_force_log(self.samples, self.p['log_dir']) if self.samples else ''


def _scale():
    """실행 인자 vel_scale."""
    return float(cc.cfg().get('run', {}).get('vel_scale', 1.0))


def wipe_cup() -> WipeCupResult:
    """컵 안을 솔로 닦는다. 호출된 자리에서 바로 하강해 삽입만 힘으로 찾는다."""
    p = cc.cfg()['f3']['wipe_cup']
    t0 = time.monotonic()
    log = _Log(p, t0)
    code, depth, moved, cup_check_z = ROBOT_ERROR, 0.0, True, None
    try:
        _set_baseline()
        _halt_check('컵 닦기 시작')
        cup_check_z = cc.where()[2]                           # 호출된 높이 기록 — 안 움직임
        log.start(cc.read_force())
        fast = float(p['fast_down_mm'])
        _fast_z(p, -fast)
        found, _f = cc.contact_down(float(p['find_max_mm']), float(p['find_limit_n']))
        log.center = cc.where()
        depth = fast + found
        _info(f'wipe_cup 바닥: 빠르게 {fast:.0f} mm + 찾기 {found:.1f} mm (최대 {p["find_max_mm"]:g}) '
              f'= {depth:.1f} mm · 실제 Z {log.center[2]:.1f} mm')
        if found >= float(p['find_max_mm']) - 0.5:
            raise RuntimeError(f'wipe_cup: {p["find_max_mm"]:g} mm 를 내려가도 바닥을 못 찾았다 — 컵·좌표 확인')
        _scrub_cup(p, log)
        _check_tool('세척 끝')
        code = OK
    except (cc.MotionHalted, cc.MoveIncomplete):               # 위치를 모른다 → 올리지 않는다
        moved = False
        raise
    except JointGuardStop as e:                                # 1·4번 조인트가 움직였다 — 곧게 뽑아 호출된 높이로
        code = ROBOT_ERROR
        _warn(f'{e} → 호출된 높이로 복귀했다. 티치펜던트로 자세 확인')
    except ToolLostError as e:
        code = _on_tool_lost(e, 'wipe_cup')
    except cc.ForceLimitError as e:
        _warn(f'wipe_cup 중단: {e}')
        code = FORCE_LIMIT
    except (cc.MotionTimeout, cc.MoveTimeout) as e:
        _warn(f'wipe_cup 중단: {e}')
        code = TIMEOUT
    except (RuntimeError, ValueError, KeyError):
        code = ROBOT_ERROR
    finally:
        _cup_finish(p, moved, cup_check_z, code)
    return WipeCupResult(ok=(code == OK), code=code, force_log_path=log.save(),
                         duration_s=time.monotonic() - t0, insert_depth_mm=depth)


def _cup_finish(p, moved, cup_check_z, code=None):
    """(힘 상한·시간 초과면 먼저 즉시 정지) → 힘 끄기는 언제나 → moved 면 동작 끝 대기 → 곧게 호출 시점 높이로 상승."""
    _stop_if_aborted(moved, code)
    try:
        cc.force_off()
    except Exception as e:                                     # noqa: BLE001
        _warn(f'정리 실패: 힘 끄기 — {e!r} · 눈으로 확인')
    if _finish_guard(moved, code):
        return

    def rise():
        if cup_check_z is None:
            return
        dz = cup_check_z - cc.where()[2]
        if dz > 0:
            _fast_z(p, dz)

    _finish_rise(rise)


def cup_stroke(p):
    """위아래 편진폭(mm) — 솔 길이 기준으로 꼭대기에서도 keep_in_mm 은 컵 안에 남게 줄인다."""
    room = max(0.0, float(p['tool']['clean_h_mm']) - float(p['lift_mm']) - float(p['keep_in_mm']))
    return min(float(p['stroke_mm']), room / 2.0)


def spin_room(j6, p):
    """6번 조인트가 시작 각 ± spin_deg/2 를 돌아도 한계 안인가 — 아니면 ValueError(돌지 않는다)."""
    half, lim = float(p['spin_deg']) / 2.0, float(p['j6_limit_deg']) - float(p['j6_margin_deg'])
    if abs(j6) + half > lim:
        raise ValueError(f'wipe_cup: 6번 조인트 {j6:.1f}° 에서 ±{half:g}° 를 돌면 한계(±{lim:g}°)를 넘는다 — 돌지 않는다')


def cup_periodic(p, stroke):
    """세척 한 명령의 (진폭, 주기) — TOOL 기준 z(위아래) + rz(6번 조인트 회전)."""
    t = float(p['period_s'])
    return ([0.0, 0.0, float(stroke), 0.0, 0.0, float(p['spin_deg']) / 2.0],
            [0.0, 0.0, t, 0.0, 0.0, t])


def _scrub_cup(p, log):
    """가장 낮은 곳(바닥 + lift_mm)에서 Move Periodic 한 번(위아래 + 6번 조인트 회전) × cycles."""
    stroke = cup_stroke(p)
    if stroke <= 0:
        raise RuntimeError('wipe_cup: 솔 길이로는 왕복할 자리가 없다 — f3.wipe_cup 설정 확인')
    _halt_check('세척')
    cc.move_rel(0.0, 0.0, float(p['lift_mm']) + stroke, 'BASE',
                vel_mm_s=float(p['lift_vel_mm_s']) * _scale())
    log.watch('cup-lift')
    q0 = cc.joints()
    spin_room(q0[5], p)
    amp, period = cup_periodic(p, stroke)
    # soap() 처럼 회전 속도를 미리 계산해 로봇 한계(rot_vel_limit_deg_s)를 넘으면 움직이기 전에 멈춘다
    #    (spin_room 은 조인트 각도만 본다) — period_s 를 잘못 줄이면 컨트롤러 한계를 조용히 넘길 수 있다.
    if period[5]:
        peak = 2.0 * math.pi * amp[5] / period[5]
        limit = float(p['rot_vel_limit_deg_s'])
        if peak > limit:
            raise ValueError(f'wipe_cup: 회전 최고 {peak:.0f}°/s > 로봇 한계 {limit:g}°/s — period_s 를 '
                             f'{2 * math.pi * amp[5] / limit:.2f} s 이상으로')
    guard = float(p['joint_guard_deg'])
    cc.move_periodic(amp, period, repeat=int(p['cycles']), ref='TOOL', atime=float(p['ramp_s']), scale=False)
    _info(f'wipe_cup 세척: 위아래 {2 * stroke:.0f} mm · 6번 조인트 {p["spin_deg"]:g}° 폭 · 주기 {p["period_s"]:g} s '
          f'· {p["cycles"]} 회 (Move Periodic · TOOL rz · 6번 조인트 {q0[5]:.1f}° 에서 시작)')
    while not cc.motion_done():                                # 도는 동안 1·4번 조인트·힘 감시
        q = cc.joints()
        bad = [(k + 1, q[k] - q0[k]) for k in (0, 3) if abs(q[k] - q0[k]) > guard]
        if bad:
            cc.stop_now()
            raise JointGuardStop('wipe_cup: ' + ' · '.join(f'{k}번 조인트 {d:+.1f}°' for k, d in bad)
                                 + ' 가 움직였다 — 6번 조인트만 돌아야 한다. 즉시 정지 · 자동으로 움직이지 않는다')
        if log.over_time():
            cc.stop_now()
            raise cc.MotionTimeout('wipe_cup: 세척 시간 초과')
        log.watch('cup-scrub')
        _check_tool('세척 도는 중')
        time.sleep(float(p['sample_s']))
    end = cc.joints()[5]
    if abs(end - q0[5]) > 5.0:                                 # 5° 넘게 어긋나면 주기 운동이 시작 각으로 안 돌아온 것
        _warn(f'wipe_cup: 끝난 뒤 6번 조인트 {end:.1f}° — 시작 {q0[5]:.1f}° 로 돌아오지 않았다')
    cc.move_rel(0.0, 0.0, -stroke, 'BASE',
                vel_mm_s=float(p['lift_vel_mm_s']) * _scale())
    log.watch('cup-end')


def _save_force_log(samples, log_dir):
    """힘 로그를 CSV로 저장하고 경로를 돌려준다."""
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, time.strftime('force_%Y%m%d_%H%M%S.csv'))
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(FORCE_LOG_HEADER)
        w.writerows(samples)
    return path
