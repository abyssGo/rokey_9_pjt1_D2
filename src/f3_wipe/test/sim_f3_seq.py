# -*- coding: utf-8 -*-
"""F3 가상 연속 시험 — HOME → 그릇 닦기 → HOME → 컵 세척 → HOME (Virtual 전용).

    sod && sodvir                                         # 터미널 1: Virtual 브링업 (이미 떠 있으면 그대로)
    soc && python3 src/f3_wipe/test/sim_f3_seq.py         # 터미널 2: 그릇 → 컵 한 번
    soc && python3 src/f3_wipe/test/sim_f3_seq.py --runs 3   # 연속 3 회

🔸 속도를 바꾸려면 **아래 SPEED 칸만** 고친다. None = params.yaml · cell.yaml 값 그대로(실기 확정값).
   이 파일 안에서만 덮어쓴다 — params.yaml 은 안 바뀐다. 마음에 들면 그 값을 params.yaml 에 옮긴다.
🔸 제품 코드(wipe.wipe_bowl · wipe.wipe_cup)를 **그대로** 부른다 — 바닥 찾기·감시·복귀 전부 같다.
🔸 Virtual 에는 힘이 없다 → 실기 로그를 흉내 낸 **가짜 힘**을 넣는다(아래 SIM_* 값).
🚨 실기에서는 실행을 거부한다. 가짜 힘 · 나선/세척 그리기(아래)는 Virtual 에서만 쓰는 것이다.
   Virtual 은 나선(amove_spiral)에 대답을 안 하고 Periodic 회전을 실기와 다르게 움직여서, 그 두 동작만 실기와 같은 길로 직접 그린다.
파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
"""
import argparse
import faulthandler
import os
import sys
import time

# ════════════════════════════════════════════════════════════════════════════════
#  ⚙️ 속도 조절 칸 — 여기만 고친다.  None = 지금 값 그대로 (괄호 안이 지금 값)
# ════════════════════════════════════════════════════════════════════════════════
VEL_SCALE = 0.3                 # 전체 속도 배수 (실기와 같게 0.3). 아래에서 "× vel" 표시된 값에 곱해진다. 0 초과 1 이하

SPEED = {
    # ── ① HOME 이동 · 컵으로 옆 이동 (HOME 관절 이동, 컵 z+40 → y+140 → z−40 과 그 반대) ──
    #    cell.yaml limits.vel_carry_pct (지금 30 %) × vel → HOME 관절 30 °/s × 0.3, 옆 이동 120 mm/s × 0.3 = 36 mm/s
    #    🟡 공용값(cell.yaml)이라 여기서는 시험만 — 실제로 바꾸려면 cell.yaml 을 고친다
    'move_pct': None,

    # ── ② 빠른 하강 · 곧게 올라오기 (그릇 135 mm · 컵 80 mm) — 그릇·컵 **같은 값**으로 들어간다 ──
    'fast_vel_mm_s': None,       # (180) × vel → 54 mm/s
    'fast_acc_mm_s2': None,      # (360) × vel → 108 mm/s²
    #    🚨 직선 이동은 cell.motion.vel_tcp_max_mm_s(400) × vel = 120 mm/s 를 넘지 못한다(넘게 줘도 잘린다)

    # ── ③ 바닥 찾기 — 3 mm 씩 내려가는 걸음 속도 (그릇·컵 공용, cell.yaml force 절 = 내 값) ──
    'contact_vel_mm_s': None,    # (20) × vel → 6 mm/s
    'contact_acc_mm_s2': None,   # (30) — vel 안 곱함

    # ── ④ 그릇 바닥 나선 — **시간**으로 준다(짧을수록 빠름) ──
    'spiral_time_s': None,       # (3.0) 실제 값 그대로 — vel 안 곱함(실기에서 돈 방식).  🚨 너무 짧으면 나선이 시작조차 안 한다(1.5 s 는 안 돌았다)

    # ── ⑤ 그릇 벽으로 붙기 (나선이 벽까지 못 갔을 때 남은 만큼) ──
    'wall_approach_vel_mm_s': None,   # (60) × vel → 18 mm/s

    # ── ⑥ 그릇 벽면 3 바퀴 + 손목 ±18° 비틀기 · 끝나고 중심 복귀 ──
    'lin_vel_mm_s': None,        # (180) × vel → 54 mm/s  (벽면 원호 · 중심 복귀)
    'rot_vel_deg_s': None,       # (400) × vel → 120 °/s  (손목 비틀기)

    # ── ⑦ 컵 — 바닥 찾은 뒤 세척 시작 자리로 띄우기 · 세척 끝나고 가장 낮은 곳으로 ──
    'lift_vel_mm_s': None,       # (40) × vel → 12 mm/s

    # ── ⑧ 컵 세척 (Periodic 위아래 3 cm + 6번 조인트 ±90°) — **vel 안 곱함, 실제 값**(결정 E17) ──
    'period_s': None,            # (3.0) 한 번 오르내리는 시간 s. 🚨 ±90° 면 2.1 s 보다 짧으면 로봇 한계 225 °/s 초과
                                 #        → 코드가 움직이기 전에 멈춘다(2.6 s = 217 °/s 까지 권장)
    'cycles': None,              # (5) 오르내리는 횟수
}

# ════════════════════════════════════════════════════════════════════════════════
#  가짜 힘 (실기 기준) — 속도 시험에는 안 고쳐도 된다
# ════════════════════════════════════════════════════════════════════════════════
SIM_AIR_FZ = 1.8                # 공중에서도 읽히는 Fz (실기 1.4 ~ 2.4 N)
SIM_BOWL_DEPTH = 145.0          # HOME 에서 수세미 ~ 그릇 바닥 (실측 145 mm)
SIM_BOWL_K = 0.7                # 수세미가 눌리는 만큼 오르는 힘 N/mm — 물러서 늦게 오른다 → 약 150 mm 에서 3.5 N 으로 찾음
SIM_CUP_DEPTH = 91.5            # 컵 위(HOME 높이)에서 솔 ~ 컵 바닥 (실측 90, 실기 5 N 에서 92.8 ~ 93.1 mm 에서 멈춤)
SIM_CUP_K = 1.7                 # 솔 N/mm → 95 mm 에서 약 6 N 으로 찾음
                                #   (Virtual 은 순응으로 처지지 않아 걸음 끝까지 가므로 실기보다 2 mm 쯤 깊게 찾는다)
SIM_CUP_Y = 70.0                # HOME 보다 y 가 이만큼 크면 컵 자리로 본다 (컵은 HOME y +140)

import cobot_common as cc                                                   # noqa: E402
from cobot_common import force as _force                                   # noqa: E402
from cobot_common.bootstrap import dsr                                     # noqa: E402
from f3_wipe import wipe                                                   # noqa: E402

_times = []                     # (구간, 초, 덧붙임)
_home = {}


def _apply_speed(log):
    c = cc.cfg()
    changed = []

    def put(sect, key, val):
        if val is not None:
            changed.append(f'{key} {sect.get(key)} → {val}')
            sect[key] = val

    put(c['cell']['limits'], 'vel_carry_pct', SPEED['move_pct'])
    for k in ('fast_vel_mm_s', 'fast_acc_mm_s2'):                          # 그릇·컵 같은 값
        put(c['f3']['wipe_bowl'], k, SPEED[k])
        put(c['f3']['wipe_cup'], k, SPEED[k])
    for k in ('contact_vel_mm_s', 'contact_acc_mm_s2'):
        put(c['cell']['force'], k, SPEED[k])
    for k in ('spiral_time_s', 'wall_approach_vel_mm_s', 'lin_vel_mm_s', 'rot_vel_deg_s'):
        put(c['f3']['wipe_bowl'], k, SPEED[k])
    for k in ('lift_vel_mm_s', 'period_s', 'cycles'):
        put(c['f3']['wipe_cup'], k, SPEED[k])
    log.info('속도 덮어씀: ' + (' · '.join(changed) if changed else '없음 (지금 값 그대로)'))
    b, u = c['f3']['wipe_bowl'], c['f3']['wipe_cup']
    s = c['run']['vel_scale']
    log.info(f'실제 속도 (vel_scale {s:g}): 옆 이동 {c["cell"]["motion"]["vel_tcp_max_mm_s"] * c["cell"]["limits"]["vel_carry_pct"] / 100 * s:.0f} mm/s'
             f' · 빠른 하강·올라오기 {b["fast_vel_mm_s"] * s:.0f} mm/s · 바닥 찾기 {c["cell"]["force"]["contact_vel_mm_s"] * s:.0f} mm/s'
             f' · 나선 {b["spiral_time_s"]:g} s · 벽면 {b["lin_vel_mm_s"] * s:.0f} mm/s · 비틀기 {b["rot_vel_deg_s"] * s:.0f} °/s'
             f' · 컵 띄우기 {u["lift_vel_mm_s"] * s:.0f} mm/s · 컵 세척 주기 {u["period_s"]:g} s × {u["cycles"]}')


_sim = {'mode': None, 'z': None}   # 지금 닦는 것('bowl'·'cup') · 마지막으로 읽힌 TCP z


def _fake_force():
    """가짜 힘 [fx, fy, fz, mx, my, mz] — 바닥 아래로 들어간 만큼 k 배.

    🚨 여기서 로봇 위치를 **새로 읽지 않는다** — 도는 중에 위치를 계속 읽으면 드라이버가 멈춘다(이 시험 1차에서 나선 시작 뒤 멈춤).
       제품 코드가 어차피 읽는 z(바닥 찾기 걸음마다 · cc.where)를 받아 둔 값만 쓴다."""
    z, mode = _sim['z'], _sim['mode']
    if not _home or z is None or mode is None:
        return [0.0, 0.0, SIM_AIR_FZ, 0.0, 0.0, 0.0]
    depth, k = (SIM_CUP_DEPTH, SIM_CUP_K) if mode == 'cup' else (SIM_BOWL_DEPTH, SIM_BOWL_K)
    press = k * max(0.0, (_home['z'] - depth) - z)
    return [0.0, 0.0, SIM_AIR_FZ + press, 0.0, 0.0, 0.0]


def _keep_z(fn, pick):
    def run(*a, **kw):
        out = fn(*a, **kw)
        _sim['z'] = float(pick(out))
        return out
    return run


_orig = {}


def _virtual_periodic(amp, period, repeat, ref='TOOL', atime=None, scale=True):
    """🚨 Virtual 전용 — 컵 세척 Move Periodic 을 **실기에서 로봇이 하는 움직임 그대로** 관절 경로로 그린다.

    왜: Virtual 은 Periodic 회전 칸을 실기와 다르게 움직인다(rz 는 4번, rx 도 4번이 1° 움직여 감시에 걸림).
        실기에서 TOOL rz 는 **6번 조인트만** 돈다(실기 확정). 그래서 Virtual 에서는 Periodic 대신 같은 움직임을 직접 만든다:
        · 위아래 z ±amp[2] mm → 2·3·5번 조인트 (역기구학 ikin 으로 위·아래 끝 관절값을 구해 사이를 사인으로)
        · 6번 조인트 ±amp[5]° → 같은 주기 사인
        · 1·4번 조인트는 **그대로** · 시작·끝 atime 동안 진폭을 천천히 키우고 줄인다(Periodic 의 atime 과 같은 뜻)
        → amovesj(관절 스플라인) 한 명령, 총 시간 = repeat × 주기. 제품 코드의 감시(1·4번 조인트) 루프는 그대로 돈다."""
    import math
    d = dsr()
    s = float(cc.cfg()['run']['vel_scale'])
    T = float(period[2] or period[5]) / (s if scale else 1.0)
    A, spin = float(amp[2]), float(amp[5])
    ramp = float(atime or 0.0)
    q0 = cc.joints()
    p0 = cc.where()
    sol = int(d.get_current_solution_space())

    def ik(dz):
        pose = list(p0)
        pose[2] -= dz                                                      # 툴 z 가 아래를 보므로 툴 +z = 베이스 −z
        q = [float(v) for v in d.ikin(pose, sol, d.DR_BASE)]
        return q
    qc, qa, qb = ik(0.0), ik(+A), ik(-A)
    da = [qa[i] - qc[i] for i in range(5)]
    db = [qb[i] - qc[i] for i in range(5)]
    total = repeat * T
    n = 12 * repeat                                                        # 한 주기에 12 점
    pts = []
    for k in range(1, n + 1):
        t = total * k / n
        r = 1.0 if ramp <= 0 else min(1.0, t / ramp, (total - t) / ramp)
        w = math.sin(2 * math.pi * t / T) * max(0.0, r)
        dq = da if w >= 0 else db
        q = [q0[i] + dq[i] * abs(w) for i in range(5)] + [q0[5] + spin * w]
        pts.append(q)
    pts[-1] = list(q0)
    wipe._info(f'(Virtual) 세척을 관절 경로로 그린다 — 위아래 ±{A:g} mm(2·3·5번 {max(abs(v) for v in da):.1f}°) · '
               f'6번 ±{spin:g}° · 1·4번 고정(계산 {abs(da[0]):.2f}° · {abs(da[3]):.2f}°) · {repeat} × {T:g} s')
    if d.amovesj([d.posj(*q) for q in pts], time=total) != 0:
        raise RuntimeError('(Virtual) amovesj 실패')


def _virtual_spiral(p, log):
    """🚨 Virtual 전용 — Virtual 드라이버는 amove_spiral 에 **대답을 안 해서** 멈춘다(이 시험에서 두 번 확인 · 순응 끄고도 같음).
    그래서 **실기의 나선과 같은 길**을 직접 그린다: 바닥 중심에서 벽 반지름(14 mm)까지 rev 바퀴, 시간 spiral_time_s ÷ vel_scale.
    길 = 베이스에서 시계 방향(실기: 툴에서 반시계 = 베이스에서 시계, wipe._spiral 주석) → amovesx(직선 스플라인) 한 명령.
    도는 동안은 제품 코드처럼 힘만 보고, 끝나면 반지름을 재서 제품과 같은 로그를 남긴다."""
    import math
    wipe._halt_check('바닥 나선')
    d = dsr()
    s = float(cc.cfg()['run']['vel_scale'])
    r_wall = log.wall_r()
    rev = max(1.0, round(r_wall / p['spiral_pitch_mm'], 1))
    x0, y0, z0, a, b, c = log.center
    n = int(math.ceil(rev * 16))
    pts = []
    for k in range(1, n + 1):
        f = k / n
        th = -2 * math.pi * rev * f                                        # 시계 방향
        pts.append(d.posx(x0 + r_wall * f * math.cos(th), y0 + r_wall * f * math.sin(th), z0, a, b, c))
    t = float(p['spiral_time_s'])                                        # 실기와 같게 vel_scale 무관
    if d.amovesx(pts, time=t, ref=d.DR_BASE) != 0:
        raise RuntimeError('(Virtual) 나선 amovesx 실패')
    while not cc.motion_done():
        if log.over_time():
            raise cc.MotionTimeout('wipe_bowl: 나선 시간 초과')
        log.watch('spiral')
        time.sleep(float(p['sample_s']))
    now = cc.where()
    r_seen = math.hypot(now[0] - x0, now[1] - y0)
    log.sweep = -2 * math.pi * rev
    wipe._info(f'wipe_bowl 나선 끝 (Virtual 그림): 반지름 {r_seen:.1f} mm (목표 {r_wall:.1f}) · '
               f'돈 각도 {math.degrees(log.sweep):+.0f}° · {t:.1f} s → 벽면은 반대로 돈다')
    if r_seen < r_wall * 0.5:
        raise RuntimeError(f'(Virtual) 나선이 벽까지 안 갔다 {r_seen:.1f} mm')


def _timed(label, fn, note=None):
    def run(*a, **kw):
        t0 = time.monotonic()
        try:
            return fn(*a, **kw)
        finally:
            _times.append((label, time.monotonic() - t0, note(*a) if note else ''))
    return run


def _patch():
    _force.read_force = _fake_force                                        # contact_down 안에서 부르는 것
    cc.read_force = _fake_force                                            # wipe.py 가 부르는 것
    _force._current_z = _keep_z(_force._current_z, lambda z: z)            # 바닥 찾기 걸음마다 읽는 z 를 받아 둔다
    cc.where = _keep_z(cc.where, lambda p: p[2])                           # 제품 코드가 읽는 위치도 받아 둔다
    cc.move_periodic = _virtual_periodic                                   # 컵 세척 — 실기 움직임(z + 6번 조인트)을 관절 경로로
    wipe._fast_z = _timed('빠른 하강·올라오기', wipe._fast_z,
                          lambda p, dz: f'{float(dz):+.0f} mm · {float(p["fast_vel_mm_s"]) * cc.cfg()["run"]["vel_scale"]:.0f} mm/s')
    cc.contact_down = _timed('바닥 찾기', cc.contact_down, lambda mx, lim: f'한계 {lim:g} N')
    wipe._spiral = _timed('그릇 나선', _virtual_spiral)
    wipe._wall_laps = _timed('그릇 벽면', wipe._wall_laps)
    wipe._to_center = _timed('그릇 중심 복귀', wipe._to_center)
    wipe._scrub_cup = _timed('컵 띄우기+세척', wipe._scrub_cup)
    wipe._Trip.go = _timed('HOME → 닦는 자리', wipe._Trip.go)
    wipe._Trip.back = _timed('닦는 자리 → HOME (올라오기 포함)', wipe._Trip.back)


def main() -> int:
    ap = argparse.ArgumentParser(description='F3 Virtual 연속 시험 — HOME → 그릇 → HOME → 컵 → HOME')
    ap.add_argument('--runs', type=int, default=1, help='몇 번 연속 (기본 1)')
    a = ap.parse_args()

    faulthandler.dump_traceback_later(60, repeat=True)                     # 60 s 동안 아무 로그 없이 멈추면 어디서 멈췄는지 찍는다
    os.environ['PREWASH_VEL_SCALE'] = str(VEL_SCALE)                       # cc.init 이 읽기 전에
    cc.init('sim_f3_seq')
    log = cc.io_node().get_logger()
    code = 1
    try:
        d = dsr()
        if d.get_robot_system() != d.ROBOT_SYSTEM_VIRTUAL:
            log.error('🚨 실기다 — 이 시험은 가짜 힘을 쓰므로 Virtual(sodvir)에서만 돈다. 실기는 rig_f3.py · rig_v10.py')
            return 2
        _apply_speed(log)
        _patch()
        log.info('HOME 으로 (Virtual 은 0 자세에서 시작한다)')
        cc.move_to('HOME', True)
        x, y, z = cc.where()[:3]
        _home.update(x=x, y=y, z=z)
        log.info(f'HOME TCP ({x:.1f}, {y:.1f}, {z:.1f}) · 가짜 바닥: 그릇 z {z - SIM_BOWL_DEPTH:.1f} · 컵 z {z - SIM_CUP_DEPTH:.1f}')

        results = []
        for n in range(1, a.runs + 1):
            _times.clear()
            t0 = time.monotonic()
            _sim.update(mode='bowl', z=None)
            rb = wipe.wipe_bowl()
            log.info(f'[{n}] 그릇: {rb.code} · {rb.duration_s:.1f} s · 평균 힘 {rb.force_mean_n:.1f} N')
            if not rb.ok:
                log.error(f'[{n}] 그릇이 {rb.code} — 컵은 하지 않는다')
                _report(log, n)
                return 1
            _sim.update(mode='cup', z=None)
            rc = wipe.wipe_cup()
            log.info(f'[{n}] 컵: {rc.code} · {rc.duration_s:.1f} s · 컵 위 → 바닥 {rc.insert_depth_mm:.1f} mm')
            _report(log, n)
            total = time.monotonic() - t0
            results.append((rb.duration_s, rc.duration_s, total))
            log.info(f'[{n}] 합계 {total:.1f} s  (그릇 {rb.duration_s:.1f} + 컵 {rc.duration_s:.1f})')
            if not rc.ok:
                log.error(f'[{n}] 컵이 {rc.code} — 멈춘다')
                return 1
        if a.runs > 1:
            log.info('회차 | 그릇 s | 컵 s | 합계 s')
            for i, (b, c, t) in enumerate(results, 1):
                log.info(f'{i} | {b:.1f} | {c:.1f} | {t:.1f}')
        code = 0
    except KeyboardInterrupt:
        log.warning('Ctrl+C — 힘 끄고 끝낸다 (Virtual 이라 자동 복귀하지 않는다 · 다시 돌리면 HOME 부터 간다)')
        code = 130
    except Exception as e:                                                 # noqa: BLE001
        log.error(f'중단: {type(e).__name__}: {e}')
    finally:
        try:
            cc.force_off()
        except Exception:                                                  # noqa: BLE001
            pass
        cc.shutdown()
    return code


def _report(log, n):
    log.info(f'[{n}] 구간별 시간 ─────────────')
    for label, sec, note in _times:
        log.info(f'   {label:<24} {sec:6.1f} s   {note}')


if __name__ == '__main__':
    sys.exit(main())
