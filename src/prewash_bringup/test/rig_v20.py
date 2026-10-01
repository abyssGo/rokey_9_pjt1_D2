#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V-20 실행 뼈대 확인 — 팀 코드(cobot_common + flow_node + f1·f2·f3 모듈)를 Virtual 에서 한 번에 돌린다. 주의: Virtual 전용.

기능 모듈이 아직 골격(로봇을 안 움직임)이라, 각 기능 함수 앞에 작은 관절 왕복 1회를 끼워 넣고
flow_node.main() 을 그대로 실행한다(모듈 파일은 고치지 않는다 — 이 프로세스 안에서만 감싼다).

실행 (저장소 루트, 터미널 3개 · rosinfo 로 RANGE=LOCALHOST 확인)
    1) sod && sodvir                                              (이미 떠 있으면 그대로 쓴다)
    2) soc && python3 src/prewash_bringup/test/rig_v20.py flow    ← flow_node (robot=True · use_mock 없음)
    3) soc && python3 src/prewash_bringup/test/rig_v20.py probe   ← start → 2 Hz 측정 → stop → PAUSED → resume → DONE
    4) 2) 의 터미널에서 (멈춰 있을 때) Ctrl+C → 다시 2)·3) → 통과하면 "Ctrl+C 뒤 재실행 정상"

완료 기준(SDD §9.2 V-20): 함수 번갈아 2바퀴 · 모션 중 /flow/state 2 Hz · stop 수락(함수 사이) · 멈춰 있을 때 Ctrl+C 뒤 재실행 정상.
시험 값은 같은 폴더의 rig_v20.yaml. probe 종료 코드 0(통과) / 1(실패).

표기 — E-nn: 팀 결정 번호(docs/decisions/20260919_결정기록_DSN-03.md) · V-nn/INT-nn: 검증 항목(docs/test-reports/) · TS-nn: 트러블슈팅(docs/troubleshooting/)
"""
import functools
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SRC = HERE.parent.parent                                    # src/


def _params():
    with open(HERE / 'rig_v20.yaml', encoding='utf-8') as f:
        return yaml.safe_load(f)


# ------------------------------------------------------------------ flow: 팀의 flow_node 를 Virtual 에서
def run_flow() -> int:
    p = _params()
    # 시험용 설정 묶음: Virtual 좌표(cell) + 저장소의 params.yaml 그대로
    cfg_dir = Path(tempfile.mkdtemp(prefix='v20_cfg_'))
    shutil.copy(SRC / 'cobot_common' / 'test' / 'config_virtual' / 'cell.yaml', cfg_dir / 'cell.yaml')
    shutil.copy(SRC / 'cobot_common' / 'config' / 'params.yaml', cfg_dir / 'params.yaml')
    os.environ['PREWASH_CONFIG_DIR'] = str(cfg_dir)
    os.environ['PREWASH_USE_MOCK'] = ''                     # 전부 실제 모듈 → robot=True

    import cobot_common as cc
    from cobot_api import F1Api, F2Api, F3Api
    from cobot_common.bootstrap import dsr
    from f1_handling import handling
    from f2_sense_flow import flow_node, sense
    from f3_wipe import wipe

    orig_init = cc.init

    def init_virtual_only(name, robot=True):
        orig_init(name, robot=robot)
        if not robot or dsr().get_robot_system() != dsr().ROBOT_SYSTEM_VIRTUAL:
            cc.shutdown()
            sys.exit('V-20 rig 는 Virtual + robot=True 에서만 돈다 (실기·mock 에서는 실행하지 않는다)')
    cc.init = init_virtual_only

    m = p['motion']

    def with_motion(fn):
        @functools.wraps(fn)
        def wrapped(*a, **kw):
            cc.move_joint_rel(m['joint'], +m['delta_deg'], time_s=m['time_s'])     # 메인 스레드에서 — flow 가 부르는 자리
            cc.move_joint_rel(m['joint'], -m['delta_deg'], time_s=m['time_s'])
            return fn(*a, **kw)
        return wrapped

    for module, api in ((handling, F1Api), (sense, F2Api), (wipe, F3Api)):
        for name in (n for n in vars(api) if not n.startswith('_') and callable(getattr(api, n))):
            setattr(module, name, with_motion(getattr(module, name)))
    try:
        flow_node.main()                                    # flow_node 의 메인 프로그램 그대로
        return 0
    finally:
        shutil.rmtree(cfg_dir, ignore_errors=True)


# ------------------------------------------------------------------ probe: HMI 자리에서 누르고 재 본다
def run_probe() -> int:
    import rclpy
    from cobot_msgs.msg import FlowEvent, FlowState
    from rclpy.node import Node
    from std_srvs.srv import Trigger

    p = _params()['probe']
    rclpy.init()
    node = Node('v20_probe')
    log = node.get_logger()
    states, events = [], []
    node.create_subscription(FlowState, '/flow/state', lambda msg: states.append((time.monotonic(), msg)), 10)
    node.create_subscription(FlowEvent, '/flow/event', lambda msg: events.append(msg), 10)
    clients = {n: node.create_client(Trigger, f'/flow/{n}') for n in ('start', 'stop', 'resume')}
    fails = []

    def check(what, ok, detail=''):
        log.info(f"{'OK  ' if ok else 'FAIL'} {what} {detail}")
        if not ok:
            fails.append(what)

    def spin(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.05)

    def call(name):
        t0 = time.monotonic()
        fut = clients[name].call_async(Trigger.Request())
        rclpy.spin_until_future_complete(node, fut, timeout_sec=p['service_timeout_s'])
        ms = (time.monotonic() - t0) * 1000
        res = fut.result()
        check(f'/flow/{name} 응답', res is not None and res.success, f'{ms:.0f} ms · {res.message if res else "응답 없음"!r}')

    def step():
        return states[-1][1].step if states else None

    def wait_step(wanted, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end and step() not in wanted:
            rclpy.spin_once(node, timeout_sec=0.05)
        return step() in wanted

    try:
        if not clients['start'].wait_for_service(timeout_sec=p['wait_flow_s']):
            log.error('flow_node 가 안 보인다 — 터미널 2 에서 rig_v20.py flow 를 먼저 띄운다')
            return 1
        spin(1.5)
        check('시작 전 IDLE', step() == 'IDLE', f'step={step()}')

        call('start')
        t_run = time.monotonic()
        spin(p['run_before_stop_s'])                        # 로봇이 움직이는 동안
        moving = [t for t, s in states if t >= t_run and s.step not in ('IDLE', 'DONE', 'PAUSED')]
        gaps = [b - a for a, b in zip(moving, moving[1:])]
        hz = len(gaps) / sum(gaps) if gaps else 0.0
        check('모션 중 /flow/state 주기', bool(gaps) and abs(hz - p['rate_hz']) <= p['rate_tol_hz'] and max(gaps) < 2.0 / p['rate_hz'],
              f'{hz:.3f} Hz · 최대 간격 {max(gaps) if gaps else 0:.2f} s · {len(moving)}건')
        seen = sorted({s.step for _, s in states})
        check('단계가 바뀌는 것이 보인다', len(seen) >= 3, f'{seen}')

        call('stop')                                        # 움직이는 중에 누른다 → 지금 함수가 끝난 뒤 멈춰야 한다 (SDD §5.1 · IRD §6)
        t_stop, n_at_stop = time.monotonic(), len(states)
        paused = wait_step(('PAUSED',), p['pause_within_s'])
        after = [s.step for _, s in states[n_at_stop - 1:]]
        extra = [b for a, b in zip(after, after[1:]) if b != a and b != 'PAUSED']      # stop 뒤에 새로 들어간 단계
        check('stop → PAUSED', paused, f'{time.monotonic() - t_stop:.1f} s 뒤 · step={step()}')
        check('stop 은 함수 사이에서 먹는다(stop 뒤 새 단계 ≤ 1)', paused and len(extra) <= 1, f'stop 뒤에 더 간 단계 {extra}')
        n_ev = len(events)
        frozen = step()
        spin(p['hold_paused_s'])
        check('PAUSED 동안 진행 없음', step() == frozen and len(events) == n_ev)

        call('resume')
        check('resume → 끝까지(DONE)', wait_step(('DONE',), p['finish_within_s']), f'step={step()}')
        last = states[-1][1]
        check('용기 수 · 이벤트 수', (last.done_bowl, last.done_cup) == (last.target_bowl, last.target_cup)
              and len(events) == last.target_bowl + last.target_cup,
              f'그릇 {last.done_bowl}/{last.target_bowl} · 컵 {last.done_cup}/{last.target_cup} · 이벤트 {len(events)}건')
        check('다시 IDLE', wait_step(('IDLE',), p['idle_within_s']), f'step={step()}')
        log.info(f"결과: {'통과' if not fails else '실패 ' + str(fails)}")
        return 0 if not fails else 1
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('flow', 'probe'):
        sys.exit(__doc__)
    sys.exit(run_flow() if sys.argv[1] == 'flow' else run_probe())
