# -*- coding: utf-8 -*-
"""fake_state_pub — **가짜 flow**. 대본대로 실제 flow_node 와 똑같은 토픽을 방송하고, 버튼(서비스)에도 반응한다. 담당 황인재 (F4-01·02)

왜: 실제 flow 는 아직 만드는 중이고, 전부 mock 으로 돌리면 단계가 0 초에 끝나 화면에 안 잡힌다(F4-00 실측)
    → HMI 화면·브리지를 혼자 개발·시험할 때 이 노드를 flow 자리에 세운다(로봇·브링업 불필요).

방송 (IRD §6 그대로)
    /flow/state     cobot_msgs/FlowState  2 Hz              /cell/force     std_msgs/Float32  닦는 동안만 10 Hz
    /flow/event     cobot_msgs/FlowEvent  용기마다 1건       /cell/gripping  std_msgs/Bool     값이 바뀔 때 1번 + 2 Hz
버튼 (std_srvs/Trigger — 대답의 뜻은 IRD §6)
    /flow/start   IDLE 에서만(--wait-start 로 기다리는 중일 때). 아니면 거절
    /flow/stop    즉시 일시정지 — 대본의 시계를 세우고 step 을 PAUSED 로 방송한다
    /flow/resume  PAUSED 에서만. 하던 단계를 **이어서**(대본이 실패로 멈춘 PAUSED 면 그 멈춤을 끝낸다)
    /flow/abort   PAUSED 에서만. 지금 용기를 접는다: ISOLATED 이벤트 + 격리 수 +1 → 다음 용기부터. ROBOT_ERROR 로 멈췄으면 **거절**

실행
    ros2 run f4_hmi fake_state_pub                          # 대본 normal 을 혼자 계속 돈다
    ros2 run f4_hmi fake_state_pub normal --wait-start      # IDLE 에서 /flow/start(화면의 시작 버튼)를 기다린다 — 버튼 시험용
    ros2 run f4_hmi fake_state_pub error --speed 2 --once   # 대본: normal · isolate · error · paused · empty_zone (scenarios/*.yaml)
🚨 실제 flow_node 와 **동시에 띄우지 않는다**(같은 토픽·서비스를 두 곳이 맡게 된다).
"""
import argparse
import sys

import rclpy
from rclpy.node import Node
from rclpy.utilities import remove_ros_args
from std_msgs.msg import Bool, Float32
from std_srvs.srv import Trigger

from cobot_msgs.msg import FlowEvent, FlowState

from . import scenario as sc

TICK_HZ = 20.0                  # 대본 시계를 돌리는 주기(장면이 바뀌는 시각의 해상도)
ROBOT_ERROR = 'ROBOT_ERROR'


class FakeFlow(Node):
    def __init__(self, scn, speed, once, wait_start):
        super().__init__('fake_state_pub')
        self.scn, self.speed, self.once, self.wait_start = scn, float(speed), once, wait_start
        self.scenes = sc.build(scn)
        self.lap_s = sc.total_s(self.scenes)
        self.t = 0.0                                        # 대본 시계(s) — 일시정지·시작 대기 중에는 멈춘다
        self.index = 0
        self.waiting = wait_start                           # /flow/start 를 기다리는 중
        self.paused = False                                 # 운영자가 /flow/stop 을 눌렀다
        self.isolated_extra = 0                             # 중단(abort)으로 늘어난 격리 수 — 한 바퀴 동안 장면 값에 더한다
        self.done_minus = {'BOWL': 0, 'CUP': 0}             # 중단으로 못 끝낸 수 — 뒤 장면의 완료 수에서 뺀다
        self.gripping = None
        self.finished = False
        rates = scn['rates']
        self.state_pub = self.create_publisher(FlowState, '/flow/state', 10)
        self.event_pub = self.create_publisher(FlowEvent, '/flow/event', 10)
        self.force_pub = self.create_publisher(Float32, '/cell/force', 10)
        self.grip_pub = self.create_publisher(Bool, '/cell/gripping', 10)
        for name in ('start', 'stop', 'resume', 'abort'):
            self.create_service(Trigger, f'/flow/{name}', getattr(self, f'_on_{name}'))
        self._last = self.get_clock().now()
        self.create_timer(1.0 / TICK_HZ, self._on_tick)
        self.create_timer(1.0 / float(rates['state_hz']), self._on_state)
        self.create_timer(1.0 / float(rates['gripping_hz']), self._on_gripping)
        self.create_timer(1.0 / float(rates['force_hz']), self._on_force)
        self.get_logger().info(f"대본 '{scn['name']}' — {scn.get('title', '')} · 한 바퀴 {self.lap_s / self.speed:.0f} s"
                               f"{' · 한 바퀴만' if once else ' · 반복'}{' · /flow/start 를 기다린다' if wait_start else ''}")
        self._announce()

    # ------------------------------------------------------------------ 지금 방송할 값
    @property
    def scene(self):
        return self.scenes[self.index]

    def state_now(self) -> dict:
        st = dict(self.scene.state)
        kind_key = {'BOWL': 'done_bowl', 'CUP': 'done_cup'}
        st['isolated'] += self.isolated_extra
        for kind, key in kind_key.items():
            st[key] = max(0, st[key] - self.done_minus[kind])
        if self.paused:
            st.update(step='PAUSED', message='일시 정지 — 운영자 요청')
        return st

    def _announce(self):
        st = self.state_now()
        self.get_logger().info(f"[{st['step']:<7}] {st['kind'] or '-':<4} {st['zone_id'] or '-':<5} 그릇 {st['done_bowl']}/{st['target_bowl']} "
                               f"컵 {st['done_cup']}/{st['target_cup']} 격리 {st['isolated']} · {self.scene.duration_s / self.speed:.1f} s"
                               + (f" · {st['message']}" if st['message'] else ''))

    # ------------------------------------------------------------------ 대본 시계
    def _on_tick(self):
        now = self.get_clock().now()
        dt, self._last = (now - self._last).nanoseconds / 1e9, now
        if self.waiting or self.paused or self.finished:
            return
        self.t += dt * self.speed
        while self.t >= sc.start_of(self.scenes, self.index) + self.scene.duration_s:
            self._emit(self.scene.event)
            if self.index == len(self.scenes) - 1:          # 한 바퀴 끝
                if self.once:
                    self.finished = True
                    return
                self._restart()
                return
            self.index += 1
            self._announce()

    def _restart(self):
        self.t, self.index, self.isolated_extra = 0.0, 0, 0
        self.done_minus = {'BOWL': 0, 'CUP': 0}
        self.waiting = self.wait_start
        self.get_logger().info('── 한 바퀴 끝 · 처음부터 다시 ──' + (' (/flow/start 를 기다린다)' if self.waiting else ''))
        self._announce()

    def _jump(self, index):
        self.index = index
        self.t = sc.start_of(self.scenes, index)
        self._announce()

    def _emit(self, event):
        if event is None:
            return
        m = FlowEvent()
        m.stamp = self.get_clock().now().to_msg()
        for k, v in event.items():
            setattr(m, k, v)
        m.duration_s = float(event['duration_s']) / self.speed
        self.event_pub.publish(m)
        self.get_logger().info(f"  ↳ 이벤트 {m.result} · {m.kind} · {m.rack_slot or '-'} · code {m.code}")

    # ------------------------------------------------------------------ 버튼(서비스) — 대답 문구는 실제 flow_node 와 같게
    def _step(self):
        return self.state_now()['step']

    def _on_start(self, req, res):
        if self.waiting:
            self.waiting = False
            self._jump(1)                                   # 기다리던 IDLE 장면을 건너뛰고 첫 용기로 (실제 flow 도 바로 PICK 으로 간다)
            res.success, res.message = True, '시작합니다'
        else:
            res.success, res.message = False, f'IDLE 이 아닙니다 (현재 {self._step()})'
        return self._answered('start', res)

    def _on_stop(self, req, res):
        if self.paused or self._step() in ('IDLE', 'DONE', 'PAUSED'):
            res.success, res.message = False, f'멈출 동작이 없습니다 (현재 {self._step()})'
        else:
            self.paused = True
            res.success, res.message = True, '일시 정지합니다'
        return self._answered('stop', res)

    def _on_resume(self, req, res):
        if self.paused:                                     # 운영자가 세운 것 → 하던 단계를 이어서
            self.paused = False
            res.success, res.message = True, '재개합니다'
        elif self.scene.state['step'] == 'PAUSED':          # 대본이 실패로 세운 것 → 그 멈춤을 끝내고 다음 장면으로
            self._jump(min(self.index + 1, len(self.scenes) - 1))
            res.success, res.message = True, '재개합니다'
        else:
            res.success, res.message = False, f'PAUSED 가 아닙니다 (현재 {self._step()})'
        return self._answered('resume', res)

    def _on_abort(self, req, res):
        st = self.state_now()
        if st['step'] != 'PAUSED':
            res.success, res.message = False, f"PAUSED 가 아닙니다 (현재 {st['step']})"
        elif st['last_code'] == ROBOT_ERROR and '케이블' not in (st.get('message') or ''):   # 케이블 이상 멈춤은 코드가 ROBOT_ERROR 라도 중단을 받는다(flow.handle_cable_tight)
            res.success, res.message = False, '로봇 오류로 멈춘 상태에서는 중단할 수 없습니다 — 사람이 복구해야 합니다'
        elif self.scene.item < 0:
            res.success, res.message = False, '접을 용기가 없습니다'
        else:
            kind = st['kind']
            self._emit(dict(kind=kind, zone_id=st['zone_id'], rack_slot='', attempts=1, weight_before_g=0.0, weight_after_g=0.0,
                            result='ISOLATED', code=st['last_code'], duration_s=0.0, force_log_path=''))
            self.isolated_extra += 1
            finished_in_script = any(s.event and s.event['result'] == 'DONE' for s in self.scenes if s.item == self.scene.item)
            if finished_in_script:
                self.done_minus[kind] += 1                  # 대본에서는 끝났을 용기다 → 뒤 장면의 완료 수에서 뺀다
            self.paused = False
            self._jump(sc.after_item(self.scenes, self.index))
            res.success, res.message = True, '이 용기를 접고 다음 용기로 넘어갑니다'
        return self._answered('abort', res)

    def _answered(self, name, res):
        self.get_logger().info(f"  ⇦ /flow/{name} → {'수락' if res.success else '거절'}: {res.message}")
        return res

    # ------------------------------------------------------------------ 타이머 (방송)
    def _on_state(self):
        st = self.state_now()
        m = FlowState()
        for k, v in st.items():
            setattr(m, k, v)
        m.stamp = self.get_clock().now().to_msg()
        self.state_pub.publish(m)
        if self.scene.gripping != self.gripping:            # 값이 바뀔 때 1번 (IRD §6)
            self.gripping = self.scene.gripping
            self.grip_pub.publish(Bool(data=self.gripping))
        if self.finished:
            self.get_logger().info('한 바퀴를 마쳤다(--once) → 끝낸다')
            raise SystemExit(0)

    def _on_gripping(self):
        if self.gripping is not None:
            self.grip_pub.publish(Bool(data=self.gripping))

    def _on_force(self):
        if self.scene.wiping and not self.paused and not self.waiting:
            self.force_pub.publish(Float32(data=sc.force_at(self.scn, self.t / self.speed)))


def main(argv=None):
    args = remove_ros_args(sys.argv if argv is None else argv)[1:]
    parser = argparse.ArgumentParser(prog='fake_state_pub', description='가짜 flow — 대본대로 /flow/state 등을 방송하고 버튼(서비스)에 반응한다')
    parser.add_argument('scenario', nargs='?', default='normal', help=f'대본 이름 또는 yaml 경로 (기본 normal) — {sc.names()}')
    parser.add_argument('--speed', type=float, default=1.0, help='빨리 감기 배수 (기본 1.0)')
    parser.add_argument('--once', action='store_true', help='한 바퀴만 돌고 끝낸다')
    parser.add_argument('--wait-start', action='store_true', help='IDLE 에서 /flow/start(시작 버튼)를 기다린다')
    opt = parser.parse_args(args)
    if not opt.speed > 0:
        parser.error('--speed 는 0 보다 커야 한다')
    scn = sc.load(opt.scenario)

    rclpy.init(args=sys.argv if argv is None else argv)
    node = FakeFlow(scn, opt.speed, once=opt.once or not scn.get('loop', True), wait_start=opt.wait_start)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
