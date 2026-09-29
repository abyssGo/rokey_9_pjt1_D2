#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V-24 단독 시험 — cc.pause()·cc.resume()·cc.halt() 가 **이동 도중에** 먹는가. 🚨 Virtual 전용.

HMI 의 "일시정지 ↔ 재개"(결정 E5: 즉시 멈추고, 재개하면 하던 동작을 이어서)를 로봇 쪽에서 확인한다.
    메인 스레드      : cc.move_joint_rel · cc.move_rel 로 긴 이동을 한다 — flow_node 가 기능 함수를 도는 자리
    통신 노드 스레드 : 타이머 콜백에서 cc.pause()·cc.resume()·cc.halt() 를 부른다 — /flow/stop·resume 콜백이 도는 자리

실행 — 세 가지 모드 (rosinfo 로 RANGE=LOCALHOST 확인)
  ① Virtual 시험 (기본, 지금까지 쓰던 것)   sod && sodvir  →  soc && python3 src/cobot_common/test/rig_pause.py
       시험용 좌표(config_virtual)로 크게 움직인다. 🚨 Virtual 이 아니면 거부한다.
  ② 실기 예행연습 (로봇 없이 절차만)        soc && python3 src/cobot_common/test/rig_pause.py --real --rehearse
       ③ 과 **같은 절차**를 Virtual 에서 돈다 — 진짜 cell.yaml 좌표 + 비어 있는 limits·motion 만 시험 값으로 채움.
       🚨 실기면 거부한다(시험 값으로 실기를 움직이지 않는다).
  ③ 실기 확인 (V-24)                        sod && sodreal →  PREWASH_VEL_SCALE=0.3 python3 src/cobot_common/test/rig_pause.py --real
       진짜 cell.yaml 그대로 · rig_pause.yaml 의 `real:` 절(작은 이동) · **단계마다 Enter** 로 사람이 확인하고 넘어간다.
       용기를 든 이동까지 보려면 그리퍼에 그릇을 쥐여 주고 --carrying 을 붙여 한 번 더 돈다(완료 기준 "관절·직선·용기를 든 이동 3회").
       🚨 E-Stop 을 손에 잡고, 로봇 반경 안에 사람이 없는지 확인한 뒤에 시작한다.

RViz·로봇에서 볼 것: ① J1 이 돌다가 **잠깐 멈췄다가 이어서** 끝까지 ② 옆으로 곧게 가다가 멈췄다 이어서 ③ 돌다가 **멈추고 끝**(강제정지)
               ④ 일시정지를 먼저 눌러 두면 **출발하지 않다가** 재개 뒤에 출발.
시험 값은 rig_pause.yaml. 종료 코드 0(통과) / 1(실패) / 2(실행 거부).
"""
import argparse
import math
import os
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
# 🚨 설정 폴더는 cobot_common 을 import 하기 **전에** 정해야 한다 → 여기서 인자를 먼저 본다.
#    --real 이면 진짜 cell.yaml 을 그대로 쓴다(시험용 좌표로 실기를 움직이지 않는다).
#    --rehearse 는 그 위에 **비어 있는** limits·motion 만 Virtual 시험 값으로 채운다(rig_coords 와 같은 방식).
REAL = '--real' in sys.argv
REHEARSE = '--rehearse' in sys.argv
if not REAL:
    os.environ.setdefault('PREWASH_CONFIG_DIR', str(HERE / 'config_virtual'))
elif REHEARSE:
    sys.path.insert(0, str(HERE))
    import rig_coords                                    # noqa: E402  같은 폴더의 시험 도구
    with open(HERE / 'rig_coords.yaml', encoding='utf-8') as _f:
        os.environ['PREWASH_CONFIG_DIR'] = str(rig_coords._filled_copy(yaml.safe_load(_f)['fill']))

import cobot_common as cc                   # noqa: E402
from cobot_common.bootstrap import dsr      # noqa: E402  cobot_common 자체 시험이라 내부 함수를 쓴다


def main() -> int:
    from sensor_msgs.msg import JointState

    ap = argparse.ArgumentParser(description='V-24 일시정지·재개 시험 (기본 Virtual · --real 로 실기 절차)')
    ap.add_argument('--real', action='store_true', help='실기 절차로 돈다 — 진짜 cell.yaml · 작은 이동 · 단계마다 Enter')
    ap.add_argument('--rehearse', action='store_true', help='--real 절차를 Virtual 에서 예행연습(비어 있는 값만 시험 값으로) · 실기면 거부')
    ap.add_argument('--carrying', action='store_true', help='그리퍼에 용기를 쥔 채로 돈다 (라벨·안내만 바뀐다 — V-24 완료 기준의 "용기를 든 이동")')
    opt = ap.parse_args([v for v in sys.argv[1:] if not v.startswith('--ros-args')])

    with open(HERE / 'rig_pause.yaml', encoding='utf-8') as f:
        p = yaml.safe_load(f)
    if opt.real:
        p = {**p, **p['real']}                              # 실기용 작은 값으로 덮어쓴다
    cc.init('rig_pause')
    io = cc.io_node()
    log = io.get_logger()
    track = []                                              # (t, J1 deg) — 통신 노드 스레드가 채운다
    fails = []

    def on_joint(msg):
        i = msg.name.index('joint_1') if 'joint_1' in msg.name else 0
        track.append((time.monotonic(), math.degrees(msg.position[i])))
    io.create_subscription(JointState, '/dsr01/joint_states', on_joint, 50)

    def later(after_s, fn):
        """after_s 뒤에 통신 노드 스레드에서 fn() 을 한 번 부른다(HMI 버튼 흉내). fn 은 깃발만 세운다."""
        holder = {}

        def fire():
            holder['t'].cancel()
            holder['at'] = time.monotonic()
            fn()
        holder['t'] = io.create_timer(after_s, fire)
        return holder

    def j1(t):
        past = [d for s, d in track if s <= t]
        return past[-1] if past else float('nan')

    def moved(t_from, t_to):
        pts = [d for s, d in track if t_from <= s <= t_to]
        return max(pts) - min(pts) if pts else float('nan')

    def check(what, ok, detail=''):
        log.info(f"{'OK  ' if ok else 'FAIL'} {what} {detail}")
        if not ok:
            fails.append(what)

    def home():
        cc.move_to('HOME', False)                           # 시험 사이 복귀(시험 대상 아님) — vel_scale·limits 를 지킨다
        time.sleep(0.5)

    def step(title):
        """실기에서는 단계마다 사람이 확인하고 넘어간다. Enter = 진행 / q = 그만."""
        log.info(f'──── {title} ────')
        if opt.real and input('    Enter = 실행 / q = 그만 > ').strip().lower() == 'q':
            raise KeyboardInterrupt

    d = dsr()
    try:
        virtual = d.get_robot_system() == d.ROBOT_SYSTEM_VIRTUAL
        if not opt.real and not virtual:
            log.error('Virtual 이 아니다 → 실행하지 않는다 (실기는 --real, 값이 채워진 cell.yaml 로)')
            return 2
        if opt.rehearse and not virtual:
            log.error('--rehearse 는 예행연습이다(시험 값으로 실기를 움직이지 않는다) → 실행하지 않는다')
            return 2
        if opt.real:
            scale = cc.cfg()['run']['vel_scale']
            log.info(f"실기 절차{' (Virtual 예행연습)' if virtual else ''} · vel_scale {scale:g}"
                     f"{' · 그리퍼에 용기를 쥔 상태' if opt.carrying else ' · 빈손'}")
            if not virtual and scale > 0.3:
                log.error(f'첫 실기는 vel_scale ≤ 0.3 이다 (지금 {scale:g}) → PREWASH_VEL_SCALE=0.3 으로 다시')
                return 2
            if not virtual and input('    🚨 E-Stop 을 손에 · 로봇 반경 안에 사람 없음 · 격리(rosinfo) 확인했으면 Enter > ').strip().lower() == 'q':
                return 2
        k, line = p['long_joint'], p['long_line']
        t_press, t_gap, within = p['press_at_s'], p['resume_after_s'], p['stop_within_s']
        hand = ' (용기를 든 채)' if opt.carrying else ''

        # ① 관절 이동 도중 일시정지 → 재개
        home()
        step(f'① 관절 이동 도중 일시정지 → 재개{hand}')
        a, b = later(t_press, cc.pause), later(t_press + t_gap, cc.resume)
        t0, j0 = time.monotonic(), j1(time.monotonic())
        cc.move_joint_rel(k['joint'], k['delta_deg'], time_s=k['time_s'])
        took = time.monotonic() - t0
        still = moved(a['at'] + within, b['at'])
        check('일시정지: 누른 뒤 서 있다', still < p['still_deg'], f"누른 뒤 {within} s~재개 사이 움직인 각도 {still:.3f}° · 멈춘 곳 J1 {j1(b['at']):.1f}°")
        check('재개: 같은 이동이 이어져 목표 도달', abs(j1(time.monotonic()) - (j0 + k['delta_deg'])) <= p['reach_tol_deg'],
              f"J1 {j1(time.monotonic()):.1f}° (목표 {j0 + k['delta_deg']:.0f}°)")
        check('함수는 재개 뒤에야 돌아온다', took >= k['time_s'] + t_gap - 0.5, f"{took:.1f} s (이동 {k['time_s']} s + 멈춘 {t_gap} s)")

        # ② 직선 이동 도중 일시정지 → 재개
        home()
        step(f'② 직선 이동 도중 일시정지 → 재개{hand}')
        y0 = float(d.get_current_posx(ref=d.DR_BASE)[0][1])
        a, b = later(t_press, cc.pause), later(t_press + t_gap, cc.resume)
        cc.move_rel(0, line['dy_mm'], 0, 'BASE', vel_mm_s=line['vel_mm_s'], acc_mm_s2=line['acc_mm_s2'])
        y1 = float(d.get_current_posx(ref=d.DR_BASE)[0][1])
        still = moved(a['at'] + within, b['at'])
        check('일시정지: 직선 이동도 선다', still < p['still_deg'], f'서 있는 동안 J1 변화 {still:.3f}°')
        check('재개: 직선 이동이 이어져 목표 도달', abs((y1 - y0) - line['dy_mm']) <= p['reach_tol_mm'], f"Δy {y1 - y0:.1f} mm (목표 {line['dy_mm']})")

        # ③ 강제정지: 끊기고, 풀기 전에는 새 이동이 나가지 않는다
        home()
        step(f'③ 강제정지(halt){hand}')
        a = later(t_press, cc.halt)
        halted = False
        try:
            cc.move_joint_rel(k['joint'], k['delta_deg'], time_s=k['time_s'])
        except cc.MotionHalted:
            halted = True
        time.sleep(0.6)
        t_now = time.monotonic()
        check('강제정지: 이동이 MotionHalted 로 끝나고 도중에 선다', halted and moved(t_now - 0.5, t_now) < p['still_deg'] and j1(t_now) < k['delta_deg'] - 10,
              f'선 곳 J1 {j1(t_now):.1f}° (목표 {k["delta_deg"]}°)')
        blocked = False
        try:
            cc.move_joint_rel(k['joint'], 5)
        except cc.MotionHalted:
            blocked = True
        time.sleep(0.4)
        check('강제정지 중에는 새 이동이 나가지 않는다', blocked and moved(t_now, time.monotonic()) < p['still_deg'])
        cc.clear_halt()
        before = j1(time.monotonic())
        cc.move_joint_rel(k['joint'], 5)
        time.sleep(0.3)
        check('clear_halt 뒤에는 다시 움직인다', abs(j1(time.monotonic()) - (before + 5)) <= p['reach_tol_deg'])

        # ④ 이동이 없을 때 누른 일시정지 → 다음 이동이 출발하지 않는다
        home()
        step(f'④ 멈춰 있을 때 누른 일시정지{hand}')
        cc.pause()
        b = later(t_gap, cc.resume)
        t0 = time.monotonic()
        cc.move_joint_rel(k['joint'], 20)
        check('재개 전에는 출발하지 않는다', moved(t0, b['at']) < p['still_deg'], f"재개까지 {b['at'] - t0:.1f} s 동안 J1 변화 {moved(t0, b['at']):.3f}°")
        time.sleep(0.3)
        check('재개 뒤에 출발해 도달', abs(j1(time.monotonic()) - 20) <= p['reach_tol_deg'], f'J1 {j1(time.monotonic()):.1f}°')

        home()
        log.info(f"결과: {'통과' if not fails else '실패 ' + str(fails)}")
        return 0 if not fails else 1
    except KeyboardInterrupt:
        return 130
    finally:
        cc.clear_halt()
        cc.shutdown()


if __name__ == '__main__':
    sys.exit(main())
