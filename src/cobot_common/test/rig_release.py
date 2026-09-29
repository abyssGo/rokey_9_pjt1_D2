#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🛟 복구 전용(시험 아님) — **그리퍼만 연다**. 로봇 팔은 움직이지 않는다.

언제: 프로그램이 오류로 죽어 툴·용기를 **쥔 채** 멈췄을 때(예: flow_node 가 수세미를 쥔 채 ROBOT_ERROR 로 끝남).
  놓은 뒤 팔을 치우는 것은 release_force.py --home --up-mm 150 (곧게 올린 뒤 HOME · 0.3배).

    soc && python3 src/cobot_common/test/rig_release.py

🚨 손을 넣지 않는다 — 새 프로세스는 그리퍼 힘 값을 아직 못 읽어서 release() 가 **열고 → 한 번 닫고 → 다시 연다**
   (cobot_common.gripper.release 의 약속). 툴이 홀더 안이면 손잡이를 한 번 다시 쥐고 놓는 것뿐이라 괜찮다.
   용기·툴이 공중이면 **떨어진다** — 아래에 받을 것이 있는지 먼저 본다(그릇 위라면 그릇 안으로 떨어진다).
"""
import sys

import cobot_common as cc


def main() -> int:
    cc.init('rig_release')
    log = cc.io_node().get_logger()
    try:
        w0 = float(cc.grip_width())
        log.info(f'지금 그리퍼 폭 {w0:.1f} mm → 연다(로봇 팔은 안 움직임)')
        cc.release()
        w1 = float(cc.grip_width())
        log.info(f'그리퍼 열림 — 폭 {w0:.1f} → {w1:.1f} mm' + (' ✅' if w1 > w0 + 5.0 else ' ⚠ 폭이 거의 안 변했다 — 안전 스위치·드라이버 확인'))
        return 0
    finally:
        cc.shutdown()


if __name__ == '__main__':
    sys.exit(main())
