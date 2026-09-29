#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""넛지 감지 사전 확인 — start_nudge_watch()/check_nudge() 가 실기에서 맞는지만 본다 (박진용 9/23).

로봇 팔은 움직이지 않는다(`init(robot=False)`) — 힘 센서만 본다. 확인 없이 바로 돈다.

실행 (저장소 루트에서, 격리 상태 solo)
    sod && sodreal   (이미 떠 있으면 그대로)
    soc && python3 src/f3_wipe/test/rig_nudge_probe.py
"""
import sys
import time

import cobot_common as cc


def main():
    cc.init("rig_nudge_probe", robot=False)
    try:
        force_n = float(cc.cfg()["cell"]["limits"]["nudge_force_n"])
        hold_s = float(cc.cfg()["cell"]["limits"]["nudge_hold_s"])
        print("=" * 74)
        print(f"넛지 감지 — 임계 {force_n:.1f} N · 유지 {hold_s:.2f} s")
        print("로봇팔을 가볍게 밀면 된다. Ctrl+C 로 종료.")
        print("=" * 74)

        cc.start_nudge_watch()
        t0 = time.monotonic()
        while True:
            if cc.check_nudge(force_n, hold_s):
                print(f"\n→ 넛지 감지! {time.monotonic() - t0:.2f}초 만에")
                return 0
            time.sleep(0.02)

    except KeyboardInterrupt:
        print("\n사용자 중단")
        return 130
    finally:
        cc.shutdown()


if __name__ == "__main__":
    sys.exit(main())
