#!/usr/bin/env python3
"""rig_fkin — 관절 자세(posj) 6개를 **로봇을 움직이지 않고** BASE 좌표(posx)로 바꿔 찍는다 (두산 fkin 서비스).

  soc && python3 src/cobot_common/test/rig_fkin.py -29.24 19.3 132.86 68.2 71.8 -63.8
  soc && python3 src/cobot_common/test/rig_fkin.py --bed SPONGE_BED_C          # cell.beds.<bed>.regrip.posj 를 읽어서

왜: 컵 옆면 재파지 자세는 관절값(posj)으로만 있어 접근점을 못 둔다(motion.py — posj 의 접근점은 아직 없다).
  HOME 에서 관절 이동으로 곧장 가니 열린 그리퍼가 홈 C 의 컵에 걸려 SAFE_STOP. → posx 로 바꿔 **위에서 자세를 맞추고 Z 만 내리는**
  접근점(approach_posx = posx + Z)을 만든다. 실기 브링업이 떠 있어야 하고(가상도 됨), 로봇은 안 움직인다.
"""
import argparse
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('posj', nargs='*', type=float, help='J1 J2 J3 J4 J5 J6 (도)')
    ap.add_argument('--bed', help='cell.beds.<bed>.regrip.posj 를 읽는다 (예 SPONGE_BED_C)')
    ap.add_argument('--up', type=float, default=100.0, help='접근점 높이(Z +mm · 기본 100)')
    a = ap.parse_args()

    import cobot_common as cc
    from cobot_common.bootstrap import dsr
    cc.init('rig_fkin')
    log = cc.io_node().get_logger()
    try:
        posj = list(a.posj)
        if a.bed:
            spec = ((cc.cfg().get('cell') or {}).get('beds') or {}).get(a.bed) or {}
            posj = list((spec.get('regrip') or {}).get('posj') or [])
            if len(posj) != 6:
                sys.exit(f'cell.beds.{a.bed}.regrip.posj 가 없다(주석이면 살린다)')
        if len(posj) != 6:
            sys.exit('관절값 6개를 주거나 --bed 를 쓴다')
        d = dsr()
        posx = [round(float(v), 2) for v in d.fkin(posj, d.DR_BASE)]
        log.info('관절 posj: [' + ', '.join(f'{v:.2f}' for v in posj) + ']  (로봇은 움직이지 않았다)')
        log.info('좌표 posx: [' + ', '.join(f'{v:.2f}' for v in posx) + ']')
        above = list(posx); above[2] = round(posx[2] + a.up, 2)
        log.info(f'접근점(+{a.up:g} mm): [' + ', '.join(f'{v:.2f}' for v in above) + ']')
        log.info(f'→ cell.yaml 에:  regrip: {{approach_posx: {above}, posx: {posx}}}')
    finally:
        cc.shutdown()


if __name__ == '__main__':
    main()
