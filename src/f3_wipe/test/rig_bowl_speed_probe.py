#!/usr/bin/env python3
"""그릇 세척 속도 튜닝 probe — 그릇은 사람이 미리 스펀지틀(SPONGE_BED_B)에 놓아 둔다.

wipe.py·params.yaml 은 손대지 않는다. 툴 픽업(SPONGE, PICK) → soap → wipe_bowl → 툴 반납(SPONGE, RETURN)
만 돌리는 최소 왕복 — 반납 구역 pick·rack_place 등 나머지 시나리오는 뺐다(속도 값 확인이 목적).

cc.cfg() 를 이 스크립트 안에서만 monkeypatch(런타임 교체)해서 f3.wipe_bowl.rot_vel_deg_s(벽면 회전 —
   좌우 비틀기도 같은 값) · spiral_time_s(나선 시간)를 아래 상수로 덮어쓴다. wipe.py·cell.yaml/params.yaml
   원본은 그대로. 되는 값 찾으면 그때 params.yaml 에 반영한다.

    # 저장소 루트에서
    soc && PREWASH_VEL_SCALE=0.3 python3 src/f3_wipe/test/rig_bowl_speed_probe.py

준비(손으로): 그릇을 SPONGE_BED_B 자리에 놓고, 그리퍼는 빈손으로 시작.
"""
import sys

import cobot_common as cc
from cobot_api import PICK, RETURN, SPONGE
from f1_handling import handling as f1
from f3_wipe import wipe

ROT_VEL_DEG_S = 2000.0                  # arc 90 · turns 3 조합에서 1600 확인됨(17.7s) → 순수 속도만 더 올려본다
SPIRAL_TIME_S = 2.0                     # 1.7 은 알람 1209(원호 가속도 초과)로 실패 — 2.0 확정, 더 안 건드림
TWIST_DEG = 10.0                        # 18 → 10(확인됨) 그대로 유지
WALL_ARC_DEG = 90.0                     # 45 는 세그먼트가 늘어 더 느려짐 — 원래 값(90)으로 되돌려 순수 속도만 본다
TURNS = 3                               # 그대로
LIN_VEL_MM_S = 1000.0                   # 600 → 1000 (회전속도는 2000에서 정체 · 이제 직선속도가 병목으로 보임)

_orig_cfg = cc.cfg


def _cfg_with_override():
    c = _orig_cfg()
    wb = c['f3']['wipe_bowl']
    wb['rot_vel_deg_s'] = ROT_VEL_DEG_S
    wb['spiral_time_s'] = SPIRAL_TIME_S
    wb['twist_deg'] = TWIST_DEG
    wb['wall_arc_deg'] = WALL_ARC_DEG
    wb['turns'] = TURNS
    wb['lin_vel_mm_s'] = LIN_VEL_MM_S
    return c


cc.cfg = _cfg_with_override


def _fast_return(tool, log):
    """f1.tool(RETURN) 의 careful contact_down 대신 — 처음 PICK 때 기록된 _LAST_PICK 자리 위로 빠르게 가서
    그 자리로 곧장 내려가 그리퍼만 편다. 테스트 반복 속도용(이 probe 전용, 공용 파일 아님)."""
    pick = f1._LAST_PICK.get(tool)
    if not pick:
        log.error(f'_fast_return: _LAST_PICK[{tool}] 이 없다 — PICK 을 먼저 해야 한다')
        raise RuntimeError('_LAST_PICK 없음')
    clear = float(cc.cfg()['f1']['tool_clear_mm'])
    motion, limits = cc.cfg()['cell']['motion'], cc.cfg()['cell']['limits']
    vel = float(motion['vel_tcp_max_mm_s']) * float(limits['vel_free_pct']) / 100.0
    acc = float(motion['acc_tcp_max_mm_s2']) * float(limits['vel_free_pct']) / 100.0
    above = list(pick)
    above[2] = pick[2] + clear
    cc.move_pose(above, vel, 60.0, acc, 60.0)
    cc.move_pose(pick, vel, 60.0, acc, 60.0)
    cc.release()
    log.info(f'[빠른 반납] {tool} — 처음 집었던 자리로 곧장 가서 폈다')


def main():
    cc.init('rig_bowl_speed_probe')
    log = cc.io_node().get_logger()
    try:
        vel_scale = float(cc.cfg().get('run', {}).get('vel_scale', 1.0))
        log.info(f'그릇 세척 속도 probe · vel_scale {vel_scale:g} · rot_vel_deg_s {ROT_VEL_DEG_S:g} · '
                 f'lin_vel_mm_s {LIN_VEL_MM_S:g} · twist_deg {TWIST_DEG:g} · wall_arc_deg {WALL_ARC_DEG:g} · '
                 f'turns {TURNS} · spiral_time_s {SPIRAL_TIME_S:g} · 🚨 실기면 E-Stop 에 손을 두고 본다 '
                 '— 경고음·떨림·나선이 도는지 직접 본다')

        cc.release()                                           # 그리퍼 힘을 한 번 읽으려면 먼저 움직여야 한다(빈손 시작)

        rt = f1.tool(SPONGE, PICK)
        log.info(f'[F1] tool PICK: {rt.code} · 폭={rt.width_mm:.2f}mm')
        if not rt.ok:
            log.error(f'tool PICK {rt.code} — 여기서 멈춘다')
            return 1

        r_soap = wipe.soap(3, 'BOWL')
        log.info(f'[F3] soap: {r_soap.code}')
        if not r_soap.ok:
            log.error(f'soap {r_soap.code} — 여기서 멈춘다(툴은 손에 쥔 채)')
            return 1

        r_wipe = wipe.wipe_bowl()
        log.info(f'[F3] wipe_bowl: {r_wipe.code} · {r_wipe.duration_s:.1f} s · 평균 힘 {r_wipe.force_mean_n:.1f} N')
        if not r_wipe.ok:
            log.error(f'wipe_bowl {r_wipe.code} — 여기서 멈춘다(툴은 손에 쥔 채)')
            return 1

        _fast_return(SPONGE, log)

        log.info('그릇 세척 속도 probe 완료 — 경고음·떨림 있었는지, 나선이 끝까지 돌았는지 로그의 '
                  '"wipe_bowl 나선: 최대 반지름" 줄로 확인')
        return 0
    finally:
        cc.shutdown()


if __name__ == '__main__':
    sys.exit(main())
