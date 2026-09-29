#!/usr/bin/env python3
"""컵 세척 속도 튜닝 probe — 컵은 사람이 미리 스펀지틀(SPONGE_BED_C)에 놓아 둔다.

wipe.py·params.yaml 은 손대지 않는다. 툴 픽업(BRUSH, PICK) → soap → wipe_cup → 툴 반납(BRUSH, RETURN)
만 돌리는 최소 왕복 — 반납 구역 pick·rack_place 등 나머지 시나리오는 뺐다(속도 값 확인이 목적).

TOOL x축에 SIDE_AMP_MM(1.0mm) 진폭을 얹어서 위아래+6번 조인트 회전과 동시에 살짝 옆으로도 움직인다 —
   wipe.cup_periodic() 을 이 스크립트 안에서만 monkeypatch(런타임 교체)한다. wipe.py 원본은 그대로.
   되는 게 확인되면 그때 wipe.py/params.yaml 에 반영한다.

    # 저장소 루트에서
    soc && PREWASH_VEL_SCALE=0.3 python3 src/f3_wipe/test/rig_cup_speed_probe.py

준비(손으로): 컵을 SPONGE_BED_C 자리에 놓고, 그리퍼는 빈손으로 시작.
"""
import math
import sys
import time

import cobot_common as cc
from cobot_api import BRUSH, PICK, RETURN
from f1_handling import handling as f1
from f3_wipe import wipe

SIDE_AMP_MM = 5.0                       # 8 → 5(실기: 8mm·정상속도에서 6번 조인트 실측 326.5°/s로 한계 225 초과 확인됨 — 그 결과 확인용)
PERIOD_SCALE = 1.0                      # 정상 속도로 되돌림(실기: ×0.5 는 컨트롤러가 조용히 무시 — 알람도 없이 세척 자체가 빠짐)

_orig_cup_periodic = wipe.cup_periodic
_actual_period_s = [None]               # 실제로 보낸 주기 — 리포트에서 예측치 계산에 쓴다


def _cup_periodic_with_side(p, stroke):
    """원래 위아래(z)+회전(rz) 왕복에 TOOL x 를 얹고, 주기를 PERIOD_SCALE 배로 줄인다."""
    amp, period = _orig_cup_periodic(p, stroke)
    amp[0] = SIDE_AMP_MM
    half_t = period[2] * PERIOD_SCALE
    period[2] = half_t                  # z
    period[5] = half_t                  # rz
    period[0] = half_t                  # x
    _actual_period_s[0] = half_t
    return amp, period


wipe.cup_periodic = _cup_periodic_with_side


_j6_samples = []                        # (시각, 6번 조인트 각도) — cc.joints() 를 가로채 기록
_orig_joints = cc.joints


def _joints_logging():
    """cc.joints() 를 감싸서 부를 때마다 기록한다 — 새 스레드를 안 만든다(로봇 함수는 메인 스레드에서만).
    wipe.py 의 세척 루프가 이미 메인 스레드에서 매 걸음 cc.joints() 를 부르므로
    거기 얹혀서 공짜로 표본을 얻는다."""
    v = _orig_joints()
    _j6_samples.append((time.monotonic(), v[5]))
    return v


cc.joints = _joints_logging


def _report_j6_speed(samples, p):
    log = cc.io_node().get_logger()
    if len(samples) < 2:
        log.warn('[속도 측정] 표본이 너무 적어 계산 못 함')
        return
    sample_s = float(p['sample_s'])
    dts = [samples[i + 1][0] - samples[i][0] for i in range(len(samples) - 1)]
    # 🚨 세척 루프는 매번 cc.joints() 호출 뒤 sleep(sample_s) — dt 가 sample_s 의 절반보다 짧으면
    #    파이썬 스레드/스케줄링 잡음으로 찍힌 이상치다(진짜로 그렇게 빨리 두 번 읽지 않는다).
    rates = [(abs(samples[i + 1][1] - samples[i][1]) / dts[i], dts[i])
             for i in range(len(dts)) if dts[i] > 0]
    clean = [(r, dt) for r, dt in rates if dt >= sample_s * 0.5]
    dropped = len(rates) - len(clean)
    peak_raw, dt_raw = max(rates, key=lambda x: x[0])
    if clean:
        peak, dt_at_peak = max(clean, key=lambda x: x[0])
    else:
        peak, dt_at_peak = peak_raw, dt_raw
    spin_deg = float(p['spin_deg'])
    period_s = _actual_period_s[0] if _actual_period_s[0] is not None else float(p['period_s'])
    predicted = 2.0 * math.pi * (spin_deg / 2.0) / period_s
    limit = float(p['rot_vel_limit_deg_s'])
    log.info(f'[속도 측정] 6번 조인트 실측 최고 {peak:.1f}°/s (dt={dt_at_peak * 1000:.0f}ms · 표본 {len(samples)}개 · '
             f'이상치(dt < {sample_s * 0.5 * 1000:.0f}ms) {dropped}개 걸러냄 · 거른 것 포함 최고는 {peak_raw:.1f}°/s) · '
             f'공식 예측 {predicted:.1f}°/s · 로봇 한계 {limit:.1f}°/s · '
             f'여유(한계 − 실측) {limit - peak:.1f}°/s')


def main():
    cc.init('rig_cup_speed_probe')
    log = cc.io_node().get_logger()
    try:
        vel_scale = float(cc.cfg().get('run', {}).get('vel_scale', 1.0))
        log.info(f'컵 세척 속도 probe · vel_scale {vel_scale:g} · TOOL x 진폭 {SIDE_AMP_MM:g} mm · '
                 f'주기 ×{PERIOD_SCALE:g} · 🚨 실기면 E-Stop 에 손을 두고 본다')

        cc.release()                                           # 그리퍼 힘을 한 번 읽으려면 먼저 움직여야 한다(빈손 시작)

        rt = f1.tool(BRUSH, PICK)
        log.info(f'[F1] tool PICK: {rt.code} · 폭={rt.width_mm:.2f}mm')
        if not rt.ok:
            log.error(f'tool PICK {rt.code} — 여기서 멈춘다')
            return 1

        r_soap = wipe.soap(3, 'CUP')
        log.info(f'[F3] soap: {r_soap.code}')
        if not r_soap.ok:
            log.error(f'soap {r_soap.code} — 여기서 멈춘다(툴은 손에 쥔 채)')
            return 1

        r_wipe = wipe.wipe_cup()
        _report_j6_speed(_j6_samples, cc.cfg()['f3']['wipe_cup'])
        log.info(f'[F3] wipe_cup: {r_wipe.code} · {r_wipe.duration_s:.1f} s · 삽입 깊이 {r_wipe.insert_depth_mm:.1f} mm')
        if not r_wipe.ok:
            log.error(f'wipe_cup {r_wipe.code} — 여기서 멈춘다(툴은 손에 쥔 채)')
            return 1

        rr = f1.tool(BRUSH, RETURN)
        log.info(f'[F1] tool RETURN: {rr.code}')
        if not rr.ok:
            log.error(f'tool RETURN {rr.code} — 여기서 멈춘다')
            return 1

        log.info('컵 세척 속도 probe 완료')
        return 0
    finally:
        cc.shutdown()


if __name__ == '__main__':
    sys.exit(main())
