#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TOOL_LOST 사전 확인 — 쥔 물체가 빠질 때 grip_width() 가 실시간으로 따라가는가만 본다.

배경: 놓침(TOOL_LOST) 감지를 폭 비교로 하려면, RG2 가 물체가 빠진 뒤에도 계속 목표 힘을
쫓아 손가락을 움직이는지(그래서 폭이 좁아지는지) 하드웨어 동작을 먼저 확인해야 한다.
gripper.py 코드만 봐서는 '명령 한 번 보내고 끝'이라 답을 알 수 없다 — 실기로 본다.

🚨 로봇 팔은 움직이지 않는다(`init(robot=False)`) — 그리퍼만 쓴다. 사람이 손으로
   수세미(또는 솔)를 그리퍼 앞에 대고 있다가 중간에 빼는 방식.

실행 (저장소 루트에서, 격리 상태 solo)
    sod && sodreal   (이미 떠 있으면 그대로)
    soc && python3 src/f3_wipe/test/rig_tool_lost_probe.py --tool SPONGE --trials 3
    soc && python3 src/f3_wipe/test/rig_tool_lost_probe.py --tool BRUSH --trials 3

한 번 실행에 여러 번(--trials) 반복한다 — 매번 다시 켤 필요 없이 Enter 로 다음 회차로 넘어간다.
로그는 폭이 **바뀔 때만**(+ 1초 심장박동) 찍는다 — 같은 값 반복 찍어 로그가 길어지는 걸 줄였다.
"""
import argparse
import sys
import time

import cobot_common as cc

_SAMPLE_S = 0.05      # 폭 읽는 주기
_HOLD_S = 3.0         # 처음 이만큼은 쥔 채로 유지해 달라고 안내
_TOTAL_S = 8.0         # 회차당 전체 관찰 시간
_PRINT_EPS_MM = 0.05   # 이만큼 안 바뀌면 로그를 또 안 찍는다


def _one_trial(n, tool, target, force, zero):
    print(f"\n--- {tool} 회차 {n} ---")
    cc.release()
    input(f"{tool} 손잡이를 그리퍼 손가락 사이에 넣고 Enter > ")
    cc.grip(target, force)
    w0 = cc.grip_width()
    print(f"쥔 직후 폭 = {w0:.2f} mm (영점 뺀 값 = {w0 - zero:.2f} mm)")
    print(f"{_HOLD_S:.0f}초는 그대로 쥔 채로 두세요. 그 다음 '지금 떼세요' 뜨면 손으로 완전히 떼세요.")

    samples = []   # [(t, width)]
    last_printed = None
    last_heartbeat = -1.0
    told_to_pull = False
    t0 = time.monotonic()
    while True:
        t = time.monotonic() - t0
        if t > _TOTAL_S:
            break
        if not told_to_pull and t >= _HOLD_S:
            print(f"  t={t:5.2f}s  >>> 지금 완전히 떼세요 <<<")
            told_to_pull = True
        w = cc.grip_width()
        samples.append((t, w))
        heartbeat = int(t) > last_heartbeat
        if last_printed is None or abs(w - last_printed) >= _PRINT_EPS_MM or heartbeat:
            print(f"  t={t:5.2f}s  폭={w:6.2f} mm")
            last_printed = w
            last_heartbeat = int(t)
        time.sleep(_SAMPLE_S)

    hold = [w for t, w in samples if t < _HOLD_S]
    w_last = samples[-1][1]
    moved = w_last - (sum(hold) / len(hold))
    print(f"  → 쥔 폭 평균 {sum(hold)/len(hold):.2f} mm → 뗀 뒤 {w_last:.2f} mm (변화 {moved:+.2f} mm)")
    return sum(hold) / len(hold), w_last, moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", choices=("SPONGE", "BRUSH"), default="SPONGE")
    ap.add_argument("--trials", type=int, default=3)
    args = ap.parse_args()

    cc.init("rig_tool_lost_probe", robot=False)
    try:
        preset = cc.cfg()["cell"]["presets"][args.tool]
        zero = float(preset["grip_zero_mm"])
        expect = float(preset["grip_width_mm"])
        tol = float(preset["width_tol_mm"])
        force = float(preset["grip_force_n"])
        target = zero + max(0.0, expect - 2.0 * tol)

        print("=" * 74)
        print(f"TOOL_LOST 재현성 확인 — {args.tool} · 목표폭 {target:.2f} mm · 힘 {force:.0f} N · {args.trials}회")
        print("로봇 팔은 안 움직입니다. 그리퍼만 사용합니다.")
        print("=" * 74)

        results = []
        for i in range(1, args.trials + 1):
            results.append(_one_trial(i, args.tool, target, force, zero))

        print("\n" + "=" * 74)
        print(f"{args.tool} — {args.trials}회 결과")
        print("=" * 74)
        for i, (held, after, moved) in enumerate(results, 1):
            print(f"  회차 {i}: 쥔 폭 {held:.2f} mm → 뗀 뒤 {after:.2f} mm  (변화 {moved:+.2f} mm)")
        afters = [after for _, after, _ in results]
        moves = [moved for _, _, moved in results]
        print(f"\n  뗀 뒤 폭 범위: {min(afters):.2f} ~ {max(afters):.2f} mm "
              f"(회차간 흔들림 {max(afters)-min(afters):.2f} mm)")
        print(f"  변화량 범위: {min(moves):+.2f} ~ {max(moves):+.2f} mm")
        print("=" * 74)

        cc.release()
        return 0

    except KeyboardInterrupt:
        print("\n사용자 중단 — 그리퍼는 그대로 둔다.")
        return 130
    finally:
        cc.shutdown()


if __name__ == "__main__":
    sys.exit(main())
