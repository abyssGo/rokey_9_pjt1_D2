#!/usr/bin/env python3
"""rig_goto — cell.yaml 의 자리(스테이션) 한 곳으로 **가서 멈춘다**(놓지 않음 · 되돌아오지 않음). 펜던트 티칭·자세 확인용.

  soc && PREWASH_VEL_SCALE=0.3 python3 src/cobot_common/test/rig_goto.py RINSE_SHAKE --kind CUP --carrying --via RINSE
      → 수조 위 접근점(RINSE · z 235)까지 곧게 간 뒤 관절 이동으로 털기 자세(RINSE_SHAKE.CUP)로 — 물 털기(f2.shake · at: RINSE_SHAKE)와 같은 길
  soc && PREWASH_VEL_SCALE=0.3 python3 src/cobot_common/test/rig_goto.py WEIGH --kind BOWL --carrying

왜: rig_f1 move_to 는 cobot_api.STATIONS 에 있는 이름만 받아 RINSE_SHAKE 같은 새 자리로는 못 간다.
🚨 실기는 vel_scale ≤ 0.3 · E26 문지기(툴·TCP 이름) 통과해야 움직인다 · 용기를 들고 있으면 --carrying(저속).
"""
import argparse
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('station', help='cell.yaml 의 자리 이름 (stations · beds · zones · rack.slots)')
    ap.add_argument('--kind', choices=['BOWL', 'CUP'], help='종류별 자리(WEIGH·WASTE·RINSE·RINSE_SHAKE·ISOLATE …)')
    ap.add_argument('--point', help='자리 안의 자세 이름 (툴 홀더 pick/return · 홈 place/regrip · 반납 구역 슬롯 번호)')
    ap.add_argument('--carrying', action='store_true', help='용기·툴을 들고 이동(저속 · cell.limits.vel_carry_pct)')
    ap.add_argument('--via', help='먼저 이 자리의 접근점(없으면 끝점)으로 곧게 간 뒤 station 으로 (예: RINSE → 수조 위 235)')
    a = ap.parse_args()

    import cobot_common as cc
    from cobot_common.bootstrap import dsr
    cc.init('rig_goto')
    log = cc.io_node().get_logger()
    try:
        scale = float((cc.cfg().get('run') or {}).get('vel_scale') or 1.0)
        if scale > 0.3:
            log.error(f'실기 이동은 vel_scale ≤ 0.3 (지금 {scale:g}) → PREWASH_VEL_SCALE=0.3 으로 다시')
            return 2
        want = ((cc.cfg().get('flow') or {}).get('preflight') or {})
        got_tool, got_tcp = str(dsr().get_tool()), str(dsr().get_tcp())
        bad = [f'{k} {g!r} ≠ {w!r}' for k, g, w in (('tool', got_tool, want.get('tool_name')), ('tcp', got_tcp, want.get('tcp_name'))) if w and g != w]
        if bad:
            log.error('🚨 컨트롤러 툴·TCP 이름이 다르다 — ' + ' · '.join(bad) + ' → 움직이지 않는다(E26 · 펜던트에서 재선택)')
            return 3
        log.info(f'문지기 통과 — tool {got_tool!r} · tcp {got_tcp!r}')
        point = int(a.point) if (a.point or '').isdigit() else a.point
        cc.force_off()
        if a.via:
            up = cc.move_to(a.via, a.carrying, a.kind)
            log.info(f'{a.via} 접근점 도착 (끝점까지 남은 높이 {float(up or 0.0):.1f} mm · 내려가지 않는다)')
        up = cc.move_to(a.station, a.carrying, a.kind, point)
        j = [round(float(v), 2) for v in dsr().get_current_posj()]
        x = [round(float(v), 2) for v in dsr().get_current_posx(ref=dsr().DR_BASE)[0]]
        log.info(f'{a.station}' + (f'.{a.kind}' if a.kind else '') + (f' {point}' if point is not None else '')
                 + f' 도착 · 멈춤 (끝점까지 남은 높이 {float(up or 0.0):.1f} mm)')
        log.info('  관절 posj: [' + ', '.join(f'{v:.2f}' for v in j) + ']')
        log.info('  좌표 posx: [' + ', '.join(f'{v:.2f}' for v in x) + ']')
        log.info('→ 펜던트 수동으로 전환해 자세를 고치고 J1~J6 를 읽는다. 끝나면 자동으로 되돌리고 다음 명령의 문지기가 이름을 확인한다')
        return 0
    finally:
        cc.shutdown()


if __name__ == '__main__':
    sys.exit(main())
