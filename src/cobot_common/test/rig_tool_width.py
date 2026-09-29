#!/usr/bin/env python3
"""V-08 앞 — 툴(수세미·솔)을 **손으로 대 주고** 그리퍼가 읽는 폭을 n 회 잰다 (F1-03 프리셋 채우기).

    soc && python3 src/cobot_common/test/rig_tool_width.py --tool SPONGE -n 5                # 손으로 대 주기(팔 안 움직임)
    soc && PREWASH_VEL_SCALE=0.3 python3 src/cobot_common/test/rig_tool_width.py --tool SPONGE -n 5 --at-holder   # 🚨 홀더로 가서

손 모드: 그리퍼만(init(robot=False)). 회차마다: 연다 → 사람이 툴을 **홀더에 꽂힌 방향 그대로** 손가락 사이에 댄다 → Enter →
영점까지 닫는다(툴에 걸려 멈춘 폭이 읽는 값) → 폭 출력.
--at-holder: HOME → cell.stations.TOOL_*.pick(관절) → 홀더에 꽂힌 툴을 n 회 쥐었다 놓으며 잰다 → 놓고 올라와 HOME. 단계마다 Enter.
  실제 tool(PICK)(F1-03)이 쥐는 자리·힘과 같은 조건이라 이 값이 프리셋이 된다.
끝에 cell.presets.<툴> 에 넣을 줄을 두 가지로 보여 준다:
    · 무른 툴(수세미): grip_target_mm 고정 폭(E19 방식 · 폭 판정 안 함)
    · 단단한 툴(솔 손잡이): grip_width_mm(영점 뺀 값) + width_tol_mm → tool() 이 E16 방식으로 판정
참고값: 티칭 스크립트 수세미 30 mm·40 N / 솔 22 mm·30 N(SDD 초안) · F3 실기 수세미 목표 22 mm.
파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
"""
import argparse
import statistics

import cobot_common as cc

DEFAULT_FORCE = {'SPONGE': 40.0, 'BRUSH': 30.0}


def main():
    ap = argparse.ArgumentParser(description='툴 폭 손 측정 (V-08 앞)')
    ap.add_argument('--tool', default='SPONGE', choices=['SPONGE', 'BRUSH'])
    ap.add_argument('-n', type=int, default=5)
    ap.add_argument('--force-n', type=float, default=None, help='닫는 힘(N) — 기본 수세미 40 · 솔 30')
    ap.add_argument('--at-holder', action='store_true',
                    help='🚨 팔이 움직인다 — HOME → 홀더 pick 자세(cell.stations.TOOL_*.pick)로 가서 홀더에 꽂힌 툴을 n 회 쥐었다 놓으며 잰다 → '
                         '놓고 tool_clear_mm 만큼 올라와 HOME. 첫 실행은 PREWASH_VEL_SCALE=0.3')
    a = ap.parse_args()
    force = a.force_n if a.force_n is not None else DEFAULT_FORCE[a.tool]

    cc.init('rig_tool_width', robot=a.at_holder)
    log = cc.io_node().get_logger()
    conf = cc.cfg()
    zero = float(conf['cell']['presets']['BOWL']['grip_zero_mm'])          # 빈손 영점은 그리퍼 것이라 툴과 무관(V-01 10.58)
    got = []

    def ask(msg):
        if input(f'    {msg} — Enter = 진행 / q = 그만 > ').strip().lower() == 'q':
            raise KeyboardInterrupt

    try:
        if a.at_holder:
            station = {'SPONGE': 'TOOL_SPONGE', 'BRUSH': 'TOOL_BRUSH'}[a.tool]
            clear = float(conf['f1']['tool_clear_mm'])
            scale = float(conf['run']['vel_scale'])
            if scale > 0.3:
                log.error(f'홀더로 가는 첫 실행은 vel_scale ≤ 0.3 (지금 {scale:g}) → PREWASH_VEL_SCALE=0.3 으로 다시')
                return 2
            log.info(f'{a.tool} · {force:g} N · 영점 {zero:.2f} mm · {a.n}회 · {station}.pick 에서 잰다 · vel_scale {scale:g}')
            ask(f'🚨 E-Stop 을 손에 · {a.tool} 이 홀더에 꽂혀 있음 · 그리퍼 빈손 · 반경 안에 사람 없음')
            ask('① HOME 으로 (관절 이동)')
            cc.move_to('HOME', False)
            ask(f'② {station}.pick 으로 (관절 이동 — 홀더 위에서 툴을 물 자리)')
            up = float(cc.move_to(station, False, point='pick') or 0.0)
            if up > 0.0:
                cc.move_rel(0.0, 0.0, -up, 'BASE')
            ask(f'③ 여기서 {a.n}회 쥐었다 놓는다 (팔은 그대로)')
            for i in range(a.n):
                cc.release()
                w = float(cc.grip(zero, force))                           # 영점까지 닫는다 → 툴에 걸려 멈춘 폭
                got.append(w)
                log.info(f'      {i + 1}/{a.n}  읽은 폭 {w:.2f} mm · 영점 뺀 {w - zero:.2f} mm')
            cc.release()                                                  # 툴은 홀더에 두고 간다
            ask(f'④ 놓은 채 {up if up > 0.0 else clear:g} mm 올라와 HOME 으로')
            cc.move_rel(0.0, 0.0, up if up > 0.0 else clear, 'BASE')
            cc.move_to('HOME', False)
        else:
            log.info(f'{a.tool} · {force:g} N · 영점 {zero:.2f} mm · {a.n}회 — 팔은 움직이지 않는다')
            for i in range(a.n):
                cc.release()
                try:
                    input(f'    {i + 1}/{a.n}  손가락이 다 열리면 {a.tool} 을 홀더에 꽂힌 방향 그대로 대고 잡은 채 Enter (q = 그만) > ')
                except EOFError:
                    break
                w = float(cc.grip(zero, force))                           # 영점까지 닫는다 → 툴에 걸려 멈춘 폭
                got.append(w)
                log.info(f'      읽은 폭 {w:.2f} mm · 영점 뺀 {w - zero:.2f} mm')
        if not got:
            return 2
        med = statistics.median(got)
        spread = max(got) - min(got)
        log.info(f'── {a.tool} 결과: 중앙값 {med:.2f} mm · 최소 {min(got):.2f} · 최대 {max(got):.2f} · 폭 {spread:.2f} mm'
                 f' · 영점 뺀 중앙값 {med - zero:.2f} mm')
        tol = max(0.6, round(spread * 2.0, 1))
        log.info('   cell.presets 후보 ① 고정 폭(무른 툴 · 폭 판정 안 함):')
        log.info(f'     {a.tool}: {{grip_target_mm: {med:.1f}, grip_force_n: {force:g}, grip_zero_mm: {zero:.2f}, width_tol_mm: {tol:.1f}}}')
        log.info('   cell.presets 후보 ② 폭 판정(단단한 툴 · E16):')
        log.info(f'     {a.tool}: {{grip_width_mm: {med - zero:.2f}, grip_zero_mm: {zero:.2f}, grip_force_n: {force:g}, width_tol_mm: {tol:.1f}}}')
        if spread > 1.0:
            log.warn(f'폭이 {spread:.2f} mm 흔들린다 — 대는 자리·깊이가 회차마다 달랐거나 툴이 무르다 → ① 고정 폭 쪽이 안전')
        return 0
    except KeyboardInterrupt:
        log.warn('q 또는 Ctrl+C — 끝낸다 (그리퍼는 지금 상태 그대로)')
        return 130
    finally:
        cc.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
