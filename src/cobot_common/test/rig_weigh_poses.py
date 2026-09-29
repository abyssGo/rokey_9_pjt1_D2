#!/usr/bin/env python3
"""V-02 전 R2 — 무게 자세 두 높이에서 하중 원값을 비교한다 (ENV-05 툴 무게 재등록 뒤).

    rosinfo                                                     # 🚨 RANGE=LOCALHOST 확인
    터미널 1:  sod && sodreal                                   (이미 떠 있으면 그대로 쓴다)
    터미널 2:  PREWASH_VEL_SCALE=0.3 python3 src/cobot_common/test/rig_weigh_poses.py --kind BOWL -n 10
               PREWASH_VEL_SCALE=0.3 python3 src/cobot_common/test/rig_weigh_poses.py --kind CUP  -n 10

무엇을 하나 — 단계마다 Enter (q = 그만)
    ① HOME → ② WEIGH.<kind> 티칭 자세(그릇 z 158 · 컵 z 147) → 멈추고 n 회 읽기
    ③ 같은 x·y 로 곧게 올라가 z --up-to(기본 235 = safe_z) → n 회 읽기 → ④ HOME
    빈손으로 한 번, 용기를 쥐여 주고 한 번(`rig_f2.py release` → 손으로 대 주기 → `rig_f2.py grip --kind BOWL`).
왜: 앞선 실기에서 같은 그릇이 z 158 에서 9 g(0 에 잘림), z 235 에서 68 g 으로 읽혔다(자세 고정 오차).
    툴 무게를 다시 등록한 뒤 **두 높이의 차이가 줄었는지**가 R2 의 핵심이다. z 158 빈손이 0 근처로 잘리면
    WEIGH 자세를 z 235 로 옮긴다(E14 — 고친 뒤 보고).
두 값을 나란히 찍는다 — 판정하지 않는다(판정은 기록 문서에서).
    · 하중 API get_workpiece_weight() — kg · 🚨 Fz 의 **절댓값**이라 0 을 지나며 되튄다 = 앞선 "0 에 잘림"의 정체
    · 툴 힘 Fz(BASE) 부호 그대로 → 무게 g = −Fz × 101.97 (빈손이 음수여도 기준값 빼기로 상쇄)
파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다. 종료 코드 0 / 2(실행 거부) / 130(q·Ctrl+C).
"""
import argparse
import statistics
import time

import cobot_common as cc
from cobot_common.bootstrap import dsr      # 시험 도구라 내부 함수를 쓴다(기능 코드에서는 쓰지 않는다)

_STATE = {0: 'INITIALIZING', 1: 'STANDBY', 2: 'MOVING', 3: 'SAFE_OFF', 4: 'TEACHING', 5: 'SAFE_STOP',
          6: 'EMERGENCY_STOP', 7: 'HOMMING', 8: 'RECOVERY', 9: 'SAFE_STOP2', 10: 'SAFE_OFF2'}


N_TO_G = 101.97        # 1 N = 101.97 g (중력)


def summary(label, grams, signed=False):
    """[(g)...] → 한 줄 요약. 하중 API 는 0 근처 값을 따로 센다(절댓값이라 되튄 값일 수 있다)."""
    if not grams:
        return f'{label}: 읽은 값 없음'
    med = statistics.median(grams)
    zeros = 0 if signed else sum(1 for g in grams if g <= 0.5)
    return (f'{label}: 중앙값 {med:.1f} g · 최소 {min(grams):.1f} · 최대 {max(grams):.1f} · 폭 {max(grams) - min(grams):.1f} g'
            + (f' · 🚨 0 근처 {zeros}회(잘림 의심)' if zeros else ''))


def main():
    ap = argparse.ArgumentParser(description='R2 — 무게 자세 두 높이 하중 원값 비교')
    ap.add_argument('--kind', default='BOWL', choices=['BOWL', 'CUP'])
    ap.add_argument('-n', type=int, default=10, help='높이마다 읽는 횟수')
    ap.add_argument('--up-to', type=float, default=235.0, help='둘째 높이 z (mm) — 기본 safe_z 235')
    ap.add_argument('--gap', type=float, default=0.5, help='읽기 사이 대기 (s)')
    ap.add_argument('--settle', type=float, default=5.0, help='도착 뒤 기다릴 시간 (s) — 실기: 5 s 전에는 +30 g')
    ap.add_argument('--home-read', action='store_true',
                    help='HOME 에서도 읽는다(처음·끝) — 팔을 접은 자세(HOME)와 편 자세(WEIGH)의 오르내림을 비교 ('
                         '"아래에서 재면 관절 때문에 값이 계속 변한다" 가설). -n 45 --gap 0.7 이면 자세마다 약 63 s 창')
    ap.add_argument('--revisit', action='store_true',
                    help='용기를 쥔 채 결정 시험 — WEIGH 1회차 → HOME → WEIGH 2회차(다시 방문 · 방문 사이 차이) → 물건 넣고 3회차 → HOME. '
                         'z --up-to 는 가지 않는다. 빈손 비교에서 어느 자세도 ±10 g 가 안 돼 "기준값 빼기"가 몇 분 뒤에도 서는지 본다')
    ap.add_argument('--object-g', type=float, default=None, help='--revisit 3회차에 넣는 물건의 저울 무게(g) — 판정 참고용')
    ap.add_argument('--at-z', type=float, default=None,
                    help='--revisit 를 WEIGH 티칭 자세가 아니라 같은 x·y 의 이 높이(z mm)에서 한다 — 실기 z158 에서 100 g 물건이 +8 g 로만 '
                         '보여 "쥔 그릇이 아래(공급 구조·뒤 용기)에 닿는다" 의심 → 높은 곳에서 다시 본다. 지금 z 보다 높고 150 mm 이내만')
    a = ap.parse_args()

    cc.init('rig_weigh_poses')
    log = cc.io_node().get_logger()
    d = dsr()

    def ask(msg):
        if input(f'    {msg} — Enter = 진행 / q = 그만 > ').strip().lower() == 'q':
            raise KeyboardInterrupt

    def standby(why):
        s = int(d.get_robot_state())
        if s == 1:
            return True
        log.error(f'🚨 로봇 상태 {s}({_STATE.get(s, "?")}) — STANDBY(1)가 아니라 {why} 전에 멈춘다. 숫자·자세를 믿을 수 없다')
        return False

    def z_now():
        return float(d.get_current_posx(ref=d.DR_BASE)[0][2])

    def read(tag):
        time.sleep(a.settle)                                 # 도착 뒤 약 5 s 는 +30 g 높게 읽힌다(실기)
        z = z_now()
        api, fz_g = [], []
        log.info(f'── {tag} · z {z:.1f} mm · {a.n}회 (도착 뒤 {a.settle:g} s 기다린 뒤)')
        for i in range(a.n):
            v = d.get_workpiece_weight()
            fz = float(cc.read_force()[2])                   # BASE 기준 Fz (N)
            g_fz = -fz * N_TO_G
            fz_g.append(g_fz)
            if isinstance(v, (int, float)) and v >= 0:
                api.append(float(v) * 1000.0)                # kg → g (실기: 단위 kg)
                log.info(f'  {i + 1:2d}  하중 API {float(v):.4f} kg = {float(v) * 1000.0:7.1f} g   ·   Fz {fz:+.3f} N → {g_fz:+7.1f} g')
            else:
                log.warn(f'  {i + 1:2d}  하중 API {v!r} — 읽기 실패   ·   Fz {fz:+.3f} N → {g_fz:+7.1f} g')
            time.sleep(a.gap)
        log.info('   ' + summary(f'{tag} · 하중 API', api))
        log.info('   ' + summary(f'{tag} · −Fz', fz_g, signed=True))
        if len(fz_g) >= 20:                                  # 긴 창이면 10회 묶음 중앙값 — 10~20 s 주기 오르내림이 보이게(실기 그릇 폭 45 g)
            blocks = [statistics.median(fz_g[i:i + 10]) for i in range(0, len(fz_g) - len(fz_g) % 10, 10)]
            log.info(f'   {tag} · −Fz 10회 묶음 중앙값: ' + ' · '.join(f'{b:+.1f}' for b in blocks)
                     + f'   (묶음 사이 폭 {max(blocks) - min(blocks):.1f} g)')
        return z, api, fz_g

    try:
        scale = float(cc.cfg()['run']['vel_scale'])
        if scale > 0.3:
            log.error(f'실기 첫 실행은 vel_scale ≤ 0.3 (지금 {scale:g}) → PREWASH_VEL_SCALE=0.3 으로 다시')
            return 2
        if not standby('시작'):
            return 2
        log.info(f'R2 · {a.kind} · vel_scale {scale:g} · 단계마다 Enter')
        ask('🚨 E-Stop 을 손에 · 반경 안에 사람 없음 · 격리(rosinfo) · 그리퍼 상태(빈손 / 용기 쥠) 확인')
        ask('① HOME 으로 (관절 이동)')
        cc.move_to('HOME', True, a.kind)
        home1_fz = home2_fz = []
        if a.home_read:
            if not standby('HOME 읽기'):
                return 2
            _, _, home1_fz = read('HOME (처음)')
        ask(f'② WEIGH.{a.kind} 티칭 자세로 (HOME → 저울 · 실기 5.5 s 경로)')
        up = float(cc.move_to('WEIGH', True, a.kind) or 0.0)
        if up > 0.0:
            cc.move_rel(0.0, 0.0, -up, 'BASE')
        if not standby('읽기'):
            return 2
        if a.revisit:
            def lift():                                      # --at-z: 티칭 자세에서 같은 x·y 로 곧게 올라간다
                if a.at_z is None:
                    return
                dz = a.at_z - z_now()
                if dz <= 0 or dz > 150:
                    raise RuntimeError(f'--at-z {a.at_z:g} 가 지금 z {z_now():.1f} 보다 낮거나 150 mm 넘게 높다')
                cc.move_rel(0.0, 0.0, dz, 'BASE')
            lift()
            z1, _, v1 = read(f'WEIGH.{a.kind} 1회차')
            ask('HOME 에 갔다가 같은 자세로 다시 온다 (방문 사이 차이)')
            cc.move_to('HOME', True, a.kind)
            up = float(cc.move_to('WEIGH', True, a.kind) or 0.0)
            if up > 0.0:
                cc.move_rel(0.0, 0.0, -up, 'BASE')
            lift()
            if not standby('2회차 읽기'):
                return 2
            _, _, v2 = read(f'WEIGH.{a.kind} 2회차 (다시 방문)')
            ask('🚨 로봇은 서 있다 — 물건을 용기에 넣고 손을 뺀 뒤 Enter')
            _, _, v3 = read(f'WEIGH.{a.kind} + 물건')
            ask('HOME 으로')
            cc.move_to('HOME', True, a.kind)
            m1, m2, m3 = (statistics.median(v) for v in (v1, v2, v3))
            log.info('──── 결과 (판정은 기록 문서에서) ────')
            log.info('  ' + summary('1회차 · −Fz', v1, signed=True))
            log.info('  ' + summary('2회차 · −Fz', v2, signed=True))
            log.info('  ' + summary('물건 · −Fz', v3, signed=True))
            log.info(f'  방문 사이 차이(2회차 − 1회차): {m2 - m1:+.1f} g   ← 기준값을 한 번 재 두고 빼는 방식이 서려면 작아야 한다')
            log.info(f'  물건 무게(물건 − 2회차): {m3 - m2:+.1f} g'
                     + (f'   (저울 {a.object_g:g} g → 오차 {m3 - m2 - a.object_g:+.1f} g)' if a.object_g is not None else ''))
            return 0
        z1, low, low_fz = read(f'WEIGH.{a.kind} 티칭 자세')
        dz = a.up_to - z1
        if dz <= 0 or dz > 150:
            log.error(f'둘째 높이 z {a.up_to:g} 가 지금 z {z1:.1f} 보다 낮거나 150 mm 넘게 높다 — 올라가지 않는다')
            return 2
        ask(f'③ 같은 x·y 로 곧게 {dz:.1f} mm 올라가 z {a.up_to:g} 로')
        cc.move_rel(0.0, 0.0, dz, 'BASE')
        z2, high, high_fz = read(f'z {a.up_to:g} (같은 x·y)')
        ask('④ HOME 으로')
        cc.move_to('HOME', True, a.kind)
        if a.home_read:
            _, _, home2_fz = read('HOME (끝)')
        log.info('──── 결과 (판정은 기록 문서에서) ────')
        if home1_fz:
            log.info('  ' + summary('HOME 처음 · −Fz', home1_fz, signed=True))
        if home2_fz:
            log.info('  ' + summary('HOME 끝 · −Fz', home2_fz, signed=True))
        if home1_fz and home2_fz:
            log.info(f'  HOME 처음 → 끝 · −Fz 중앙값 변화: {statistics.median(home2_fz) - statistics.median(home1_fz):+.1f} g'
                     '   (같은 자세로 돌아왔는데 다르면 시간에 따른 흐름)')
        log.info('  ' + summary(f'z {z1:.1f} · 하중 API', low))
        log.info('  ' + summary(f'z {z2:.1f} · 하중 API', high))
        log.info('  ' + summary(f'z {z1:.1f} · −Fz', low_fz, signed=True))
        log.info('  ' + summary(f'z {z2:.1f} · −Fz', high_fz, signed=True))
        if low and high:
            log.info(f'  두 높이 차이 · 하중 API: {statistics.median(high) - statistics.median(low):+.1f} g'
                     '  ← 툴 무게 등록 전: 그릇 약 +56 g (12.9 → 68.4)')
        if low_fz and high_fz:
            log.info(f'  두 높이 차이 · −Fz: {statistics.median(high_fz) - statistics.median(low_fz):+.1f} g   (0 에 가까울수록 자세와 무관)')
        return 0
    except KeyboardInterrupt:
        log.warn('q 또는 Ctrl+C — 정지 명령을 보내고 끝낸다')
        return 130
    finally:
        cc.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
