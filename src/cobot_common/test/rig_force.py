#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INF-02b 단독 시험 — 힘 함수(force.py)의 호출 순서 확인. 🚨 Virtual 전용 (실기 값은 V-03).

실행 (저장소 루트에서, 격리 상태 solo — docs/env/M0609_환경설정.md)
    터미널 1:  sod && sodvir
    터미널 2:  soc && python3 src/cobot_common/test/rig_force.py

흐름: 시작 자세 → 작업 높이로 approach_down_mm 하강 → [바퀴 × rounds] → 시작 자세로 복귀
한 바퀴: read_force → force_reached → contact_down → force_on·유지·force_off → periodic_search → safe_retreat
확인하는 것 (완료 기준 "Virtual 에서 호출 순서 오류 0")
    ① 모든 함수가 두산 오류 없이 끝난다 — 연속 3바퀴 이상 (TS-01 B′)
    ② Virtual 은 힘이 없으므로 contact_down 은 최대 깊이까지 내려간다
    ③ safe_retreat 뒤 Z 가 안전 높이(= 작업 높이)로 돌아온다 · 끝나면 시작 자세로 복귀

설정은 같은 폴더의 rig_force_config/(시험 전용 cell.yaml) 과 rig_force.yaml. 팀 cell.yaml 은 읽지 않는다.
종료 코드 0(통과) / 1(실패) / 2(실행 거부) / 130(Ctrl+C).
"""
import argparse
import os
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
os.environ['PREWASH_CONFIG_DIR'] = str(HERE / 'rig_force_config')     # cc.init 이 설정을 읽기 전에

import cobot_common as cc                                               # noqa: E402
from cobot_common.bootstrap import dsr                                  # noqa: E402  cobot_common 자체 시험이라 내부 함수를 쓴다


def main() -> int:
    ap = argparse.ArgumentParser(description='cobot_common 힘 함수 시험 (Virtual 전용)')
    ap.add_argument('--real', action='store_true', help='Virtual 이 아니어도 실행한다 (🚨 팀 확인 뒤, V-03 은 따로)')
    args = ap.parse_args()
    with open(HERE / 'rig_force.yaml', encoding='utf-8') as f:
        p = yaml.safe_load(f)

    cc.init('rig_force')                                                # ① 맨 앞에서 한 번
    log = cc.io_node().get_logger()
    code = 1
    try:
        d = dsr()
        if d.get_robot_system() != d.ROBOT_SYSTEM_VIRTUAL and not args.real:
            log.error('Virtual 이 아니다 → 실행하지 않는다. 실기 힘 시험은 V-03 절차로')
            return 2
        d.movej(p['start_posj'], vel=p['start_vel_deg_s'], acc=p['start_acc_deg_s2'])
        z_home = d.get_current_posx(ref=d.DR_BASE)[0][2]
        d.movel([0.0, 0.0, -p['approach_down_mm'], 0.0, 0.0, 0.0], vel=p['approach_vel_mm_s'],
                acc=p['approach_acc_mm_s2'], ref=d.DR_BASE, mod=d.DR_MV_MOD_REL)
        z_start = d.get_current_posx(ref=d.DR_BASE)[0][2]
        cc.cfg()['cell']['limits']['safe_z_mm'] = z_start               # 시험 전용: 안전 높이 = 작업 높이
        log.info(f'시작 자세 Z {z_home:.1f} → 작업 높이 Z {z_start:.1f} mm (= 이 시험의 safe_z)')

        bad = 0
        for rnd in range(1, p['rounds'] + 1):                           # ② 같은 순서를 연속으로
            t0 = time.monotonic()
            try:
                f = cc.read_force()
                reached = cc.force_reached('z', min=p['contact_limit_n'])
                depth, fz = cc.contact_down(p['contact_max_depth_mm'], p['contact_limit_n'])
                cc.force_on('z', p['force_target_n'], p['force_limit_n'])
                time.sleep(p['force_hold_s'])
                cc.force_off()
                cc.periodic_search(p['search_amp_mm'], p['search_period_s'], p['search_duration_s'])
                cc.safe_retreat()
                z_end = d.get_current_posx(ref=d.DR_BASE)[0][2]
                depth_ok = abs(depth - p['contact_max_depth_mm']) <= p['depth_tol_mm']
                ok = depth_ok and abs(z_end - z_start) <= p['depth_tol_mm']
                log.info(f'바퀴 {rnd}: Fz {f[2]:.1f} N · force_reached={reached} · contact_down 깊이 {depth:.1f} mm '
                         f'(|Fz| {fz:.1f} N) · 복귀 Z {z_end:.1f} · {time.monotonic() - t0:.1f} s · '
                         f'{"OK" if ok else "FAIL"}')
            except (cc.ForceLimitError, cc.MotionTimeout, RuntimeError, ValueError, KeyError) as e:
                ok = False
                log.error(f'바퀴 {rnd}: {type(e).__name__}: {e}')
                cc.safe_retreat()
            bad += 0 if ok else 1
        code = 0 if bad == 0 else 1
        log.info(f"결과: {p['rounds'] - bad}/{p['rounds']} 바퀴 OK → {'통과' if code == 0 else '실패'}")
        cc.safe_retreat()
        d.movej(p['start_posj'], vel=p['start_vel_deg_s'], acc=p['start_acc_deg_s2'])
        log.info(f"시작 자세로 복귀 · Z {d.get_current_posx(ref=d.DR_BASE)[0][2]:.1f} mm")
        return code
    except KeyboardInterrupt:
        log.warning('Ctrl+C — 정지 명령을 보내고 끝낸다')
        return 130
    finally:
        cc.shutdown()                                                   # ③ 끝낼 때 (Ctrl+C 포함)


if __name__ == '__main__':
    sys.exit(main())
