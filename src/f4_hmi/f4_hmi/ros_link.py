# -*- coding: utf-8 -*-
"""hmi_bridge 의 ROS 쪽 귀 — 토픽 4개를 듣고 StateStore 에 넣는다. 별도 스레드에서 spin 한다(웹 서버와 섞지 않는다).

콜백은 값 저장만 한다(SDD §3.2 규칙 ③과 같은 원칙). 두산 API 를 쓰지 않으므로 cobot_common.init() 을 부르지 않는다.
버튼: call('start'|'stop'|'resume'|'abort') → flow 의 /flow/<이름>(std_srvs/Trigger)을 부르고 {ok, message, latency_ms} 를 돌려준다.
    웹 서버의 작업 스레드에서 불린다. 요청은 call_async 로 보내고 응답은 이 파일의 ROS 스레드가 받는다 → 상한 시간만큼만 기다린다.
"""
import threading
import time

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.signals import SignalHandlerOptions
from std_msgs.msg import Bool, Float32
from std_srvs.srv import Trigger

from cobot_msgs.msg import FlowEvent, FlowState


def to_dict(msg) -> dict:
    """메시지 → dict. stamp 는 초(float)로 바꾼다 — 나머지 필드는 이름·값 그대로(IRD §7)."""
    out = {}
    for name in msg.get_fields_and_field_types():
        value = getattr(msg, name)
        out[name] = round(value.sec + value.nanosec / 1e9, 3) if name == 'stamp' else value
    return out


COMMANDS = ('start', 'stop', 'resume', 'abort')         # /flow/<이름> — IRD §6


class RosLink:
    """ROS 노드 'hmi_bridge' — 구독 4개(/flow/state · /flow/event · /cell/force · /cell/gripping)와
    서비스 클라이언트 4개(/flow/start·stop·resume·abort)를 들고 별도 스레드에서 spin 한다."""

    def __init__(self, store, service_timeout_s=1.0):
        """store: StateStore(콜백이 값을 넣는 곳) · service_timeout_s: 버튼(서비스) 응답을 기다리는 상한(s)."""
        self.store = store
        self._timeout = float(service_timeout_s)
        self._clients = {}
        self.node = None
        self._executor = None
        self._thread = None
        self._stopping = False

    def start(self):
        """rclpy 초기화 → 노드·구독·클라이언트 생성 → spin 스레드(hmi_ros · daemon) 시작. Ctrl+C 처리는 uvicorn 에 맡긴다."""
        rclpy.init(signal_handler_options=SignalHandlerOptions.NO)      # Ctrl+C 는 웹 서버(uvicorn)가 받는다
        self.node = rclpy.create_node('hmi_bridge')
        n, s = self.node, self.store
        n.create_subscription(FlowState, '/flow/state', lambda m: s.put_state(to_dict(m)), 10)
        n.create_subscription(FlowEvent, '/flow/event', lambda m: s.put_event(to_dict(m)), 50)
        n.create_subscription(Float32, '/cell/force', lambda m: s.put_force(m.data), 10)
        n.create_subscription(Bool, '/cell/gripping', lambda m: s.put_gripping(m.data), 10)
        for name in COMMANDS:
            self._clients[name] = n.create_client(Trigger, f'/flow/{name}')
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(n)
        self._thread = threading.Thread(target=self._spin, name='hmi_ros', daemon=True)
        self._thread.start()

    def _spin(self):
        """스레드 본체 — 콜백 하나가 예외를 내도 로그만 남기고 다시 spin 한다."""
        while rclpy.ok() and not self._stopping:
            try:
                self._executor.spin()
                return
            except Exception:                                # noqa: BLE001 — 콜백 하나가 터져도 듣기를 멈추지 않는다
                import traceback
                self.node.get_logger().error('ROS 콜백 예외 — 계속 듣는다\n' + traceback.format_exc())

    def call(self, name) -> dict:
        """버튼 1번 = 서비스 호출 1번. flow 의 대답을 그대로 돌려준다. 안 보이거나 늦으면 ok=False (요청 스레드를 오래 막지 않는다)."""
        client = self._clients[name]
        t0 = time.monotonic()

        def answer(ok, message):
            return {'ok': bool(ok), 'message': message, 'latency_ms': round((time.monotonic() - t0) * 1000)}
        if not client.service_is_ready():
            return answer(False, f'flow 가 보이지 않는다 (/flow/{name} 서비스 없음)')
        done, box = threading.Event(), {}

        def on_done(future):
            box['res'] = future.result()
            done.set()
        future = client.call_async(Trigger.Request())
        future.add_done_callback(on_done)
        if not done.wait(self._timeout):
            future.cancel()
            return answer(False, f'flow 응답 없음 ({self._timeout:g} s)')
        res = box.get('res')
        return answer(res.success, res.message) if res is not None else answer(False, 'flow 응답을 읽지 못했다')

    def stop(self):
        """순서가 중요하다: 듣기를 멈추고 → 스레드가 끝나기를 기다린 뒤 → 노드·rclpy 를 닫는다.
        스레드가 spin 중인 채로 닫으면 프로그램이 끝날 때 'terminate called' 로 비정상 종료한다."""
        self._stopping = True
        if self._executor is not None:
            self._executor.shutdown(timeout_sec=1.0)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self.node is not None:
            self.node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
