"""F2 단독 시험 스크립트 (SDD §3.2 · §10) — 내 함수만 직접 부른다.

    soc && python3 src/f2_sense_flow/test/rig_f2.py empty --kind BOWL     # 빈 용기 기준값 측정
    soc && python3 src/f2_sense_flow/test/rig_f2.py weigh                 # weigh 연속 3회
    soc && python3 src/f2_sense_flow/test/rig_f2.py loop --max-rounds 2
    soc && python3 src/f2_sense_flow/test/rig_f2.py shake --mode WASTE -n 5
    soc && python3 src/f2_sense_flow/test/rig_f2.py dip --kind CUP
    python3 src/f2_sense_flow/test/rig_f2.py weigh --no-robot             # 브링업 없이 반환만 확인

용기를 쥐는 것부터 (V-02·V-07·V-16 은 전부 '쥔 상태' 에서 시작한다):
    python3 src/f2_sense_flow/test/rig_f2.py release                      # ① 연다 (+ 힘 기준을 맞춘다)
    (손으로 용기를 그리퍼 사이에 대 준다)
    python3 src/f2_sense_flow/test/rig_f2.py grip --kind BOWL             # ② cell.yaml 프리셋으로 쥔다
    → 같은 터미널이 아니어도 된다. 그리퍼는 프로그램이 끝나도 쥔 채로 남는다

준비(손으로): 용기를 그리퍼에 쥐여 준다. weigh 시험은 100 g·200 g 추(TC-03).
같은 함수를 연속 3회 이상 부른다(SDD §3.2 ⑧ — "첫 번째만 되는" 결함은 한 번으로는 안 보인다).

🚨 로봇을 움직이기 전에 `rosinfo` 로 RANGE=LOCALHOST 인지 확인한다.
   격리가 안 되어 있으면 내 movej 가 남의 Virtual·실기에도 간다.

파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
"""
import argparse
import sys
import time

import cobot_common as cc
from cobot_api import F2Api, check_api

from f2_sense_flow import sense
from f2_sense_flow.preflight import go_home_safely, require_controller, warn_if_cable_tight   # TS-07 — 움직이기 전 툴·TCP 확인 · 🔗 케이블


def main():
    ap = argparse.ArgumentParser(description='F2 단독 시험')
    ap.add_argument('which', choices=['empty', 'weigh', 'loop', 'shake', 'dip', 'grip', 'release'],
                    help="empty = 빈 용기 기준값 측정(params.yaml f2.empty_weight_g 에 넣을 값) · "
                         "grip·release = 용기를 쥐고/놓는다(팔은 안 움직인다)")
    ap.add_argument('-n', type=int, default=3, help='연속 호출 횟수 (3 이상)')
    ap.add_argument('--kind', default='BOWL', choices=['BOWL', 'CUP'], help='용기 종류 (IRD §2)')
    ap.add_argument('--mode', default='WASTE', choices=['WASTE', 'RINSE'], help='shake 모드')
    ap.add_argument('--station', default='RINSE', choices=['RINSE'], help='dip 수조')
    ap.add_argument('--count', type=int, default=1, help='shake·dip 의 횟수 인자')
    ap.add_argument('--max-rounds', type=int, default=2, help='leftover_loop 의 최대 반복')
    ap.add_argument('--no-robot', action='store_true',
                    help='두산 드라이버 없이 (브링업 없이 함수 반환만 확인)')
    ap.add_argument('--no-home', action='store_true',
                    help='🚨 shake·dip·loop 앞의 HOME 경유를 끈다 (E15 — 이미 HOME 에 있을 때만)')
    # 값 찾기용 덮어쓰기: 설정 파일을 안 고치고 이번 실행에서만 f2.shake.<mode> 를 바꾼다(메모리에서). 찾은 값은 params.yaml 에 적는다
    ap.add_argument('--amp', type=float, help='shake 진폭 덮어쓰기 — 직선이면 mm(amp_mm) · 관절이면 °(amp_deg)')
    ap.add_argument('--period', type=float, help='shake 주기(s) 덮어쓰기')
    ap.add_argument('--acc', type=float, help='shake 직선 왕복 가속도(mm/s²) 덮어쓰기 — 상한은 cell.motion.acc_tcp_max × vel_scale')
    ap.add_argument('--tilt', type=float, help='shake 기울이기(°) 덮어쓰기 (관절 왕복만)')
    a = ap.parse_args()

    if a.which in ('grip', 'release'):
        if a.no_robot:
            sys.exit('grip·release 는 실기에서만 됩니다 — 진짜 그리퍼가 있어야 합니다.')
        return _hold_container(a)

    if a.which == 'empty':
        if a.no_robot:
            sys.exit('empty 는 실기에서만 됩니다 — 무게는 진짜 로봇의 하중 센서에서만 나옵니다.\n'
                     '  sod && sodreal   (브링업)  →  soc  →  이 명령에서 --no-robot 을 빼고 다시')
        return _measure_empty(a)

    problems = check_api(sense, F2Api)               # 약속과 어긋나면 로봇을 켜기 전에 멈춘다
    if problems:
        sys.exit(f'cobot_api.F2Api 약속과 다름: {problems}')

    fn = {
        'weigh': lambda: sense.weigh(a.kind),
        'loop': lambda: sense.leftover_loop(a.kind, a.max_rounds),
        'shake': lambda: sense.shake(a.mode, a.count, a.kind),
        'dip': lambda: sense.dip(a.station, a.count, a.kind),
    }[a.which]

    cc.init('rig_f2', robot=not a.no_robot)          # ① 맨 앞에서 한 번
    log = cc.io_node().get_logger()
    if a.no_robot:
        log.warn('--no-robot — 두산 드라이버 없이 함수 반환만 확인한다')
    else:
        require_controller(cc.io_node(), cc.cfg(), log)   # TS-07 — 다르면 PreflightError 로 여기서 끝
        warn_if_cable_tight(cc.cfg(), log)                # 🔗 케이블 장력(경고만)
    if a.which == 'shake':
        _override_shake(a, log)                          # --amp/--period/--acc/--tilt (이번 실행만)
    try:
        # 🚨 결정 E15 — 잔반통(로봇 **뒤**) ↔ 저울·수조·반납 구역(**앞**) 사이는 HOME 을 거친다.
        #    앞뒤로 곧장 가면 로봇 몸통을 가로지르고(E7 로 안전 높이 경유가 없다) 6번 관절이 163°
        #    돌아 그리퍼 케이블이 꼬인다(실기).
        #    flow 에서는 leftover_loop 이 알아서 거치지만, 여기서는 **직전에 어디 있었는지 모른다** —
        #    V-02(앞, WEIGH)를 돌린 뒤 바로 shake(뒤, WASTE)를 부르거나, 그 반대로
        #    털기 뒤에 다시 weigh 를 부르면 그 대각선 이동이 그대로 난다.
        #    → 시험대에서는 항상 HOME 에서 시작한다. `--no-home` 으로 끌 수 있다(이유가 있을 때만).
        #    --no-robot 일 때는 건너뛴다 — 여기는 _as_result 바깥이라 두산 API 가 없으면
        #    그대로 예외가 터져 나가고, 뒤의 '함수 반환만 확인' 을 못 한다.
        if a.which in ('shake', 'dip', 'loop', 'weigh') and not a.no_home and not a.no_robot:
            log.info('E15 — 먼저 HOME 으로 간다 (앞뒤를 가로지르지 않으려고 · 낮으면 곧게 올라온 뒤에)')
            go_home_safely(a.kind, log)

        for i in range(a.n):                         # ② 연속 3회 이상
            log.info(f'{i + 1}/{a.n} {a.which} → {fn()}')
    finally:
        cc.shutdown()                                # ③ 끝낼 때 (Ctrl+C 포함)


def _override_shake(a, log):
    """--amp · --period · --acc · --tilt 를 이번 실행의 설정(메모리)에 덮어쓴다. 상한 검사는 sense.shake 가 그대로 한다."""
    p = sense.shake_params(cc.cfg()['f2'], a.mode, a.kind)   # 종류별 묶음이면 그 종류 것
    changed = {}
    if a.amp is not None:
        key = 'amp_mm' if p.get('axis') is not None else 'amp_deg'
        p[key] = a.amp; changed[key] = a.amp
    if a.period is not None:
        p['period_s'] = a.period; changed['period_s'] = a.period
    if a.acc is not None:
        p['acc_mm_s2'] = a.acc; changed['acc_mm_s2'] = a.acc
    if a.tilt is not None:
        p['tilt_deg'] = a.tilt; changed['tilt_deg'] = a.tilt
    if changed:
        log.warn(f'🔧 shake.{a.mode} 덮어씀 (이번 실행만 · 파일엔 안 적힘): {changed} → 지금 값 {p}')


def _close_target(kind, preset):
    """그 종류에 맞는 **닫는 목표 폭**(드라이버 값 — 영점 포함)을 고른다.

    · CUP  : 🚨 결정 E19 — 정해진 폭(`grip_target_mm`)까지 **만** 닫고 멈춘다.
             끝까지 닫으면 RG2 최저 힘 5 N 으로도 컵이 눌린다(20 N 에서는 안전 스위치가 걸렸다).
             대가로 빈손과 구분이 안 되므로 **파지 확인을 하지 않는다**.
    · BOWL : SDD §5.2 — 기대 폭보다 `2 × 허용오차` 만큼 **작게** 준다.
             기대 폭을 그대로 주면 **빈손으로도 그 폭에서 멈춰** 쥔 것처럼 보인다.
    """
    zero = float(preset.get('grip_zero_mm') or 0.0)          # 결정 E16 D-A — 명령에는 영점을 더한다
    target = preset.get('grip_target_mm')                    # 종류가 아니라 **키**로 고른다 — 컵도 벽을 집으면(CELL-05) 폭 판정
    if target is not None:
        return float(target), '고정 폭(E19) — 파지 확인 안 함'
    expect = float(preset['grip_width_mm'])
    tol = float(preset['width_tol_mm'])
    return zero + max(0.0, expect - 2 * tol), f'영점 {zero:.2f} + 기대 {expect:.2f} − 2 × 허용오차 {tol:.2f}'


def _ask(log, msg):
    """사람이 용기를 대 줄 때까지 기다린다. 파이프로 돌리면(입력 없음) 그냥 진행한다."""
    log.info(f'▶ {msg} — 준비되면 Enter')
    try:
        input()
    except EOFError:
        log.warning('입력이 없다 — 기다리지 않고 진행한다')


def _wait_width(log, limit_s=5.0):
    """첫 폭 값을 기다린다 — /onrobot_joint_states 구독이 붙어야 읽힌다."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit_s:
        try:
            return cc.grip_width()
        except RuntimeError:
            time.sleep(0.1)
    log.error(f'{limit_s:.0f} s 안에 그리퍼 폭을 못 받았다 — 브링업과 /onrobot_joint_states 를 확인한다')
    return None


def _hold_container(a):
    """용기를 쥔다(grip) / 놓는다(release). 🚨 팔은 움직이지 않는다 — 그리퍼만.

    🚨 grip 은 **release → 사람이 용기를 댐 → grip 을 한 프로그램 안에서** 한다.
       힘은 그리퍼가 움직이거나 닫혀 있을 때만 읽히고(gripper.py 머리말),
       그 값은 **프로그램마다 새로** 잡는다. release 를 따로 돌리고 나가면
       그리퍼가 활짝 열린 채 멈춰 effort 0(= 모름)만 오므로, 다음 프로그램의
       grip 이 첫 줄에서 RuntimeError 로 죽는다(예전 절차서가 그렇게 시켰다).
       🚨 반대로 grip 앞에 release 를 넣는 것도 위험하다 — 힘을 모르면 release 가
          **빈손인 줄 알고 한 번 끝까지 닫는다**. 그래서 여는 것이 먼저, 대 주는 것이 나중이다.
    """
    cc.init('rig_f2', robot=True)
    log = cc.io_node().get_logger()
    require_controller(cc.io_node(), cc.cfg(), log)   # TS-07
    try:
        if a.which == 'release':
            cc.release()                             # 열기 + (첫 호출이면) 힘 기준 맞추기
            log.info('열었다 — 용기를 손으로 받으세요')
            return

        log.info('🚨 지금 그리퍼가 **비어 있어야** 합니다 — 먼저 열어서 힘 기준을 잡습니다')
        cc.release()                                 # ① 빈손에서 힘 기준을 잡는다
        if _wait_width(log) is None:
            return
        _ask(log, f'{a.kind} 을(를) 그리퍼 사이에 대 주세요')   # ② 사람이 댄다

        preset = cc.cfg()['cell']['presets'][a.kind]
        target, why = _close_target(a.kind, preset)
        force = float(preset['grip_force_n'])
        log.info(f'{a.kind} 쥐기 — 목표 {target:.2f} mm ({why}) · {force:.1f} N')
        got = cc.grip(target, force)
        log.info(f'  실제 폭 {got:.2f} mm')

        if preset.get('grip_target_mm') is not None:  # E19 고정 폭 — 폭으로 판정하지 않는다(지금 컵은 벽 집기라 여기 안 옴)
            log.warn('  고정 폭 파지는 확인을 하지 않는다(E19) — 눈으로 보고, 살짝 당겨 보세요')
            return
        zero = float(preset.get('grip_zero_mm') or 0.0)
        net, tol = got - zero, float(preset['width_tol_mm'])
        log.info(f'  영점 뺀 폭 {net:.2f} mm (기대 {preset["grip_width_mm"]:.2f} ± {tol:.2f})')
        if abs(got - target) < 0.3:
            log.error('  🚨 목표에 그대로 도달했다 — **빈손도 이렇게 보인다.** 용기가 안 물렸는지 보세요')
        elif abs(net - float(preset['grip_width_mm'])) > tol:
            log.warn('  🚨 기대 폭에서 벗어났다 — 대 준 자리·높이를 확인하세요')
    finally:
        cc.shutdown()                                # 🚨 그리퍼는 쥔 채로 남는다(의도한 것)


def _measure_empty(a):
    """빈 용기 기준값 측정 — params.yaml 의 f2.empty_weight_g 에 넣을 값을 구한다.

    🚨 저울로 잰 진짜 무게를 넣으면 안 된다. 로봇 하중에는 정체불명 옵셋이 있어서
       (V-02: +42~45 g), 잔반 판정 `측정값 − 기준값` 이 상쇄되려면 **같은 경로·같은 자세**로
       잰 값이어야 한다. 저울 값을 넣으면 빈 용기가 잔반 43 g 으로 보인다.

    🚨 자세가 달라지면 옵셋도 달라질 수 있다(V-02 §3 미확인 항목).
       티칭이 끝나면 WEIGH 자세에서 다시 재는 것이 정확하다.
       브링업을 다시 했으면(다른 세션) 값이 달라질 수 있으니 시연 날 아침에 다시 잰다.
    """
    cc.init('rig_f2', robot=True)
    log = cc.io_node().get_logger()
    require_controller(cc.io_node(), cc.cfg(), log)   # TS-07
    try:
        # 🚨 재기 전에 **그 종류의 WEIGH 자세로 간다.** 하중 옵셋(+42~45 g)은 자세마다 다르므로
        #    잰 자세와 실제 운전에서 재는 자세가 같아야 판정식 `측정값 − 기준값` 에서 상쇄된다.
        #    전에는 이 함수가 로봇을 **전혀 움직이지 않아서**, 직전에 서 있던 자리(다른 종류의
        #    WEIGH 나 safe_retreat 로 올라간 높이)에서 잰 값을 설정에 넣게 되어 있었다.
        #    🚨 용기가 바닥에 닿아 있으면 무게가 바닥으로 빠진다 — WEIGH 자세는 들어 올린 자세다.
        log.info('E15 — HOME 을 거쳐 WEIGH 자세로 간다 (앞뒤를 가로지르지 않으려고 · 낮으면 곧게 올라온 뒤에)')
        cc.force_off()
        go_home_safely(a.kind, log)
        up = float(cc.move_to('WEIGH', True, a.kind) or 0.0)
        if up > 0.0:
            cc.move_rel(0.0, 0.0, -up, 'BASE')
        samples = cc.cfg()['f2']['weigh_samples']
        settle = float(cc.cfg()['f2'].get('weigh_settle_s') or 0.0)
        # 전에는 여기서 cc.weigh 를 직접 불러 sense.weigh 의 정지 대기(weigh_settle_s)를 건너뛰었다
        #    → 도착 직후 5 s 동안 +30 g 높게 읽히는 구간을 그대로 기준값에 넣고 있었다. 실제 운전과 같게 기다린다
        log.info(f'도착 — {settle:.1f} s 정지 뒤 잰다 (f2.weigh_settle_s · 실제 운전과 같게)')
        time.sleep(settle)
        log.info(f'빈 {a.kind} 을(를) 그리퍼에 물린 상태에서 {a.n}회 잰다 (회당 {samples} 표본)')
        got = []
        for i in range(a.n):
            try:
                g = cc.weigh(samples)                # 내 cobot_common/weigh.py
            except Exception as e:                   # noqa: BLE001 — 무엇이 잘못됐는지 사람이 알게
                log.error(f'  {i + 1}/{a.n}  측정 실패 — {e}')
                log.error('  확인: 브링업(sodreal)이 떠 있나 · 티치펜던트 제어권을 놨나 · robotmode 가 1 인가')
                continue
            got.append(g)
            log.info(f'  {i + 1}/{a.n}  {g:.1f} g')
        if not got:
            log.error('한 번도 재지 못했습니다 — 위 확인 항목을 보세요')
            return
        got.sort()
        mid = got[len(got) // 2] if len(got) % 2 else (got[len(got) // 2 - 1] + got[len(got) // 2]) / 2
        log.info(f'중앙값 {mid:.1f} g  (폭 {max(got) - min(got):.1f} g)')
        log.info(f'→ params.yaml 의 f2.empty_weight_g.{a.kind} 에 {round(mid)} 을(를) 넣으세요')
        if max(got) - min(got) > 20:
            log.warn('회차 간 폭이 20 g 을 넘는다 — 로봇을 완전히 멈추고 다시 재는 것이 좋다')
    finally:
        cc.shutdown()


if __name__ == '__main__':
    main()
