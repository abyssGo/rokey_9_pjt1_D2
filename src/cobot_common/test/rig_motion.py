#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INF-02 단독 시험 — 이동 함수(move_to · move_rel · move_joint_rel)를 Virtual 에서 연속으로 돌린다. 🚨 Virtual 전용.

실행 (저장소 루트에서)
    rosinfo                                                  # 🚨 RANGE=LOCALHOST(격리) 확인
    터미널 1:  sod && sodvir                                  (이미 떠 있으면 그대로 쓴다 — 두 개를 띄우지 않는다)
    터미널 2:  soc && python3 src/cobot_common/test/rig_motion.py

좌표는 우리 셀의 cell.yaml 이 아니라 **test/config_virtual/**(가상 로봇이 닿는 아무 점)를 쓴다 → 실기면 실행하지 않는다.
시험 값은 같은 폴더의 rig_motion.yaml. 종료 코드 0(통과) / 1(실패) / 2(실행 거부) / 130(Ctrl+C).
"""
import os
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
os.environ.setdefault('PREWASH_CONFIG_DIR', str(HERE / 'config_virtual'))   # 설정을 읽기 전에 (init 보다 먼저)

import cobot_common as cc                   # noqa: E402
from cobot_common.bootstrap import dsr      # noqa: E402  cobot_common 자체 시험이라 내부 함수를 쓴다


def main() -> int:
    with open(HERE / 'rig_motion.yaml', encoding='utf-8') as f:
        p = yaml.safe_load(f)
    cc.init('rig_motion')
    log = cc.io_node().get_logger()
    cell = cc.cfg()['cell']
    safe_z = cell['limits']['safe_z_mm']
    fails = []

    def posx():
        return [float(v) for v in dsr().get_current_posx(ref=dsr().DR_BASE)[0]]

    def posj():
        return [float(v) for v in dsr().get_current_posj()]

    def check(what, ok, detail=''):
        log.info(f"{'OK  ' if ok else 'FAIL'} {what} {detail}")
        if not ok:
            fails.append(what)

    def near(a, b, tol):
        return all(abs(x - y) <= tol for x, y in zip(a, b))

    try:
        if dsr().get_robot_system() != dsr().ROBOT_SYSTEM_VIRTUAL:
            log.error('Virtual 이 아니다 → 실행하지 않는다 (이 rig 의 좌표는 가상 로봇 전용이다)')
            return 2
        tol, jtol = p['pos_tol_mm'], p['joint_tol_deg']
        for rnd in range(1, p['rounds'] + 1):
            log.info(f'──── {rnd}/{p["rounds"]} 바퀴 ────')
            # move_to: 관절 자세 · 직교 자세 · 낮은 자세(E7: 위로 올리지 않고 곧장) · 낮은 곳에서 출발
            up = cc.move_to('HOME', False)
            check('move_to HOME', up == 0.0 and near(posj(), cell['stations']['HOME']['posj'], jtol))
            weigh = cell['stations']['WEIGH']['posx']
            up = cc.move_to('WEIGH', True)
            check('move_to WEIGH(들고)', up == 0.0 and near(posx()[:3], weigh[:3], tol))
            tool = cell['stations']['TOOL_SPONGE']['posx']
            up = cc.move_to('TOOL_SPONGE', False)
            now = posx()
            check('move_to TOOL_SPONGE → 낮은 자세까지 곧장', up == 0.0 and near(now[:3], tool[:3], tol) and tool[2] < safe_z,
                  f'z {now[2]:.1f} (후퇴 높이 {safe_z:g} 보다 낮다)')

            # move_rel: BASE 축 · TOOL 축 · 속도 선택 인자
            cc.move_rel(0, 0, -p['tool_step_mm'], 'BASE')
            check('move_rel BASE 하강', near(posx()[:3], [tool[0], tool[1], tool[2] - p['tool_step_mm']], tol), f'z {posx()[2]:.1f}')
            before = posx()
            cc.move_rel(0, 0, -p['tool_step_mm'], 'TOOL')             # 툴이 아래를 보므로 툴 −z = 위로
            after = posx()
            check('move_rel TOOL 축', near([after[2] - before[2]], [p['tool_step_mm']], tol), f'Δz {after[2] - before[2]:+.1f}')
            s = p['slow']
            t0 = time.monotonic()
            cc.move_rel(s['dx_mm'], 0, 0, 'BASE', vel_mm_s=s['vel_mm_s'], acc_mm_s2=s['acc_mm_s2'])
            dt = time.monotonic() - t0
            check('move_rel 속도 선택 인자(느리게)', near([posx()[0] - after[0]], [s['dx_mm']], tol) and dt >= s['min_time_s'],
                  f"{s['dx_mm']} mm 를 {dt:.1f} s")
            bed = cell['beds']['SPONGE_BED_B']['place']['posx']
            z_before = posx()[2]
            up = cc.move_to('SPONGE_BED_B', True, point='place')                     # 낮은 곳에서 출발 → 올리지 않고 곧장
            check('move_to SPONGE_BED_B(낮은 곳에서 곧장)', up == 0.0 and near(posx()[:3], bed[:3], tol) and z_before < safe_z,
                  f'출발 z {z_before:.1f} → 도착 z {posx()[2]:.1f}')

            # move_joint_rel: 시간 지정 왕복(털기) · 기본 속도
            k = p['shake']
            j0 = posj()
            times = []
            for delta in (+k['amp_deg'], -2 * k['amp_deg'], +k['amp_deg']):
                want = k['half_period_s'] * abs(delta) / k['amp_deg']
                t0 = time.monotonic()
                cc.move_joint_rel(k['joint'], delta, time_s=want)
                times.append((time.monotonic() - t0, want / cc.cfg()['run']['vel_scale']))   # vel_scale < 1 이면 그만큼 늘어난다
            check(f"move_joint_rel J{k['joint']} 왕복(시간 지정)",
                  near(posj(), j0, jtol) and all(abs(got - want) <= k['time_tol_s'] for got, want in times),
                  ' · '.join(f'{got:.2f}/{want:.2f} s' for got, want in times))
            q = p['spin']
            cc.move_joint_rel(q['joint'], q['delta_deg'])
            moved = posj()[q['joint'] - 1] - j0[q['joint'] - 1]
            cc.move_joint_rel(q['joint'], -q['delta_deg'], carrying=False)
            check(f"move_joint_rel J{q['joint']} 기본 속도", near([moved], [q['delta_deg']], jtol) and near(posj(), j0, jtol))

            # 값이 비어 있으면 움직이지 않는다
            j_before = posj()
            try:
                cc.move_to('SOAP', False)
                refused = False
            except KeyError:
                refused = True
            check('빈 좌표(SOAP) → 움직이지 않고 KeyError', refused and near(posj(), j_before, jtol))

        cc.move_to('HOME', False)
        log.info(f"결과: {'통과' if not fails else '실패 ' + str(fails)} ({p['rounds']}바퀴)")
        return 0 if not fails else 1
    except KeyboardInterrupt:
        log.warn('Ctrl+C — 정지 명령을 보내고 끝낸다')
        return 130
    finally:
        cc.shutdown()


if __name__ == '__main__':
    sys.exit(main())
