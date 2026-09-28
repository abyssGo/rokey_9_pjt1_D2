# -*- coding: utf-8 -*-
"""flow_node — PreWash-Cell 의 메인 프로그램 (민범진). 통신 배선만 맡는다.

이 셀에서 노드는 둘뿐이다: flow_node(여기)와 hmi_bridge(F4 · HMI 브리지).
f1·f2·f3 는 노드가 아니라 그냥 함수이고, 이 파일의 메인 스레드가 차례로 부른다.

왜 이렇게 하나 (TS-01 · SDD §3.2):
    두산 API 는 "혼자 위에서 아래로 도는 스크립트"를 전제로 만들어졌다. 로봇 명령마다 자기가
    실행기를 돌려 응답을 기다리므로, 서비스 콜백 안에서 부르면 교착한다.
    그래서 로봇을 움직이는 코드는 전부 메인 스레드에서 차례로 실행한다.

     ┌ 메인 스레드      : flow.run() → 기능 함수 호출        ← 로봇은 여기서만
     ├ 통신 노드 스레드 : Io — 서비스·타이머·발행기
     │                    주의: 콜백은 깃발만 세운다 (규칙 ③)
     └ DSR 전용 노드    : cobot_common 이 관리 (우리는 안 건드린다)

Ctrl+C 는 cobot_common.init() 이 단독으로 맡는다 (SDD §3.1).
  → 여기서는 signal.signal 을 걸지 않고 try/finally 로 cc.shutdown() 만 부른다.

실행 (SDD §10):
    ros2 launch prewash_bringup prewash.launch.py vel_scale:=0.3      # 실기
    ros2 launch prewash_bringup prewash_mock.launch.py                # 전부 가짜, 드라이버 없이
    PREWASH_USE_MOCK=f1,f3 ros2 run f2_sense_flow flow_node           # 손으로 돌릴 때

주의: flow_node 에는 name=·namespace=·--ros-args -r __node:= 를 주지 않는다 (SDD §10).
   프로세스 안의 두 노드(flow_node · flow_node_dsr)에 모두 걸려 이름이 같아진다.

표기 — E-nn: 팀 결정 번호(docs/meetings/20260919_결정기록_DSN-03.md) · V-nn/INT-nn: 검증 항목(docs/test_logs/) · TS-nn: 트러블슈팅(docs/troubleshooting/)
"""
import functools
import traceback

import rclpy.logging

from cobot_api import ROBOT_ERROR

import cobot_common as cc
from cobot_common import config as cc_config
from cobot_msgs.msg import FlowEvent, FlowState
from std_srvs.srv import Trigger

from f2_sense_flow.flow import Flow, Signals, load_features
from f2_sense_flow.preflight import PreflightError, require_controller, warn_if_cable_tight

FEATURES = ('f1', 'f2', 'f3')


def safe_cb(what):
    """ROS 콜백을 감싼다 — 주의: 콜백에서 예외가 나가면 통신이 영구히 죽는다.

    rclpy 의 SingleThreadedExecutor 는 콜백 예외를 spin() 밖으로 다시 던지고,
    cobot_common 의 spin 스레드는 그것을 잡아 로그만 남기고 스레드를 끝낸다.
    그러면 프로세스는 살아 있는데 /flow/state 가 멈추고 start·stop·resume 이
    영원히 응답하지 않는다 — 메인 스레드는 로봇을 계속 움직이는데 정지 버튼이 안 먹는다.
    """
    def deco(fn):
        @functools.wraps(fn)
        def wrapped(self, *a, **kw):
            try:
                return fn(self, *a, **kw)
            except Exception as e:                # noqa: BLE001 — 통신 스레드를 죽이면 안 된다
                try:
                    self.log.error(f'{what} 콜백에서 예외 — {e!r} (통신은 계속한다)')
                except Exception:                 # noqa: BLE001
                    pass
                return a[1] if len(a) > 1 else None   # 서비스면 응답 객체를 그대로 돌려준다
        return wrapped
    return deco


class Io:
    """통신 배선 — /flow/* 서비스 4개, /flow/state 타이머, /flow/event 발행기.

    주의: 콜백에서 하는 일은 깃발 세우기와 값 읽기뿐이다. 로봇 함수를 부르지 않는다.
       콜백에서 로봇을 움직이면 TS-01 의 교착이 그대로 되살아난다.
    """

    def __init__(self, node, flow, sig):
        self.node, self.flow, self.sig = node, flow, sig
        self.log = node.get_logger()

        node.create_service(Trigger, '/flow/start', self._on_start)
        node.create_service(Trigger, '/flow/stop', self._on_stop)
        node.create_service(Trigger, '/flow/resume', self._on_resume)
        node.create_service(Trigger, '/flow/abort', self._on_abort)      # FLOW-03 (IRD §6)
        self.state_pub = node.create_publisher(FlowState, '/flow/state', 10)
        self.event_pub = node.create_publisher(FlowEvent, '/flow/event', 10)

        self.rate_hz = flow.state_pub_hz          # Flow 가 이미 검증했다(0·음수·문자열 → 2.0)
        node.create_timer(1.0 / self.rate_hz, self._on_state_timer)

    # ────────────────────────────────── 서비스 콜백 (깃발만!)
    @safe_cb('/flow/start')
    def _on_start(self, req, res):
        if self.flow.step == 'IDLE':
            self.sig.raise_('start')
            res.success, res.message = True, '시작합니다'
        else:
            res.success, res.message = False, f'IDLE 이 아닙니다 (현재 {self.flow.step})'
        return res                                   # 즉시 응답. 실행은 메인 스레드가 한다

    @safe_cb('/flow/stop')
    def _on_stop(self, req, res):
        """일시 정지 — 즉시 멈춘다 (IRD §6 · V-24).

        주의: cc.pause() 는 깃발만 세운다(motion.py 머리말) — 콜백에서 불러도 된다.
           이동 중이면 폴링 루프가 그 자리에서 세우고, 이동이 없으면 다음 이동이 출발하지 않는다.
           깃발(stop)도 같이 세운다 — 단계 사이에서 멈추는 길이 따로 있다(SDD §5.1).
        """
        self.sig.raise_('stop')
        cc.pause()
        res.success, res.message = True, '즉시 멈춥니다 (재개하면 하던 동작을 이어서)'
        return res

    @safe_cb('/flow/resume')
    def _on_resume(self, req, res):
        # 주의: PAUSED 일 때만 받는다 (_on_start 와 같은 방식).
        #    운전 중에 들어온 resume 을 그냥 세워 두면 깃발이 남아 있다가, 나중에
        #    사람이 확인해야 하는 정지(ROBOT_ERROR·RACK_FULL — SDD §7)에서 그것을
        #    바로 소비해 0 초 만에 재개해 버린다. HMI 가 버튼을 잠가도 REST /api/resume
        #    이나 ros2 service call 로 직접 들어올 수 있으므로 서버에서도 막는다.
        #    주의: 이동 도중 멈추면 메인 스레드가 기능 함수 안에 갇혀 있어 step 이 아직
        #       'PAUSED' 가 아니다 → cc.is_paused() 도 같이 본다. 이게 없으면
        #       "멈췄는데 재개가 거부되는" 막다른 길이 된다.
        if self.flow.step == 'PAUSED' or cc.is_paused():
            cc.resume()                              # 멈춰 있던 이동을 이어서 끝낸다
            self.sig.raise_('resume')
            res.success, res.message = True, '재개합니다'
        else:
            res.success, res.message = False, f'PAUSED 가 아닙니다 (현재 {self.flow.step})'
        return res                                   # 거절 이유는 HMI 가 그대로 보여 준다

    @safe_cb('/flow/abort')
    def _on_abort(self, req, res):
        """중단 — 지금 용기를 접고 다음 용기로 간다 (IRD §6 · 결정 E11).

        주의: PAUSED 일 때만 받는다. 운전 중에 받으면 사람이 상태를 보지 않은 채 용기를 버린다.
        주의: ROBOT_ERROR 로 멈춘 것은 거부한다 — 로봇이 어디 있는지 모르는데 격리함까지
           이송하면 더 위험하다. 사람이 복구한 뒤 재개한다(SDD §7).
        cc.halt() 로 하던 이동을 끊는다(깃발만 세운다 — 콜백에서 불러도 된다).
        정리 순서는 메인 스레드의 flow.abort_container 가 한다.
        """
        if not (self.flow.step == 'PAUSED' or cc.is_paused()):
            res.success, res.message = False, f'PAUSED 가 아닙니다 (현재 {self.flow.step})'
            return res
        if self.flow.last_code == ROBOT_ERROR:
            res.success, res.message = False, (
                '로봇 위치를 알 수 없어 중단할 수 없습니다 — 복구한 뒤 재개를 눌러 주세요')
            return res
        cc.halt()                                    # 하던 이동을 그 자세로 끊는다
        self.sig.raise_('abort')
        res.success, res.message = True, '이 용기를 접고 다음 용기로 갑니다'
        return res

    # ────────────────────────────────── 상태 발행 (메시지만 만든다)
    @safe_cb('/flow/state 타이머')
    def _on_state_timer(self):
        s = self.flow.snapshot()
        m = FlowState()
        for k, v in s.items():
            setattr(m, k, v)
        m.stamp = self.node.get_clock().now().to_msg()
        self.state_pub.publish(m)

    @safe_cb('/flow/event')
    def publish_event(self, ev):
        """flow(두뇌)가 용기 1개를 끝낼 때마다 부른다. dict → 메시지로 옮긴다."""
        m = FlowEvent()
        m.stamp = self.node.get_clock().now().to_msg()
        for k, v in ev.items():
            setattr(m, k, v)
        self.event_pub.publish(m)


def main():
    """flow_node 의 진입점 — 설정을 읽어 로봇 유무를 정하고, cc.init → 문지기 → Flow·Io 를 만들어 메인 스레드에서 flow.run.

    기능이 전부 가짜(use_mock 에 f1·f2·f3 모두)면 두산 드라이버 없이 돈다. 어떤 경우에도 finally 의 cc.shutdown() 이 정리한다.
    """
    # ── init 전에 설정을 읽어 robot 여부를 정한다 (SDD §4.3·§5.1) ──
    #    런치 인자 use_mock 은 환경변수 PREWASH_USE_MOCK 으로 와서 로더가 이미 얹어 준다.
    #    cc.cfg() 는 init() 뒤에만 되므로 여기서는 config.load() 를 직접 부른다.
    #    기능이 전부 가짜면 두산 드라이버 없이 돈다 → 브링업 없이 flow·HMI 개발 가능
    cfg = cc_config.load()
    use_mock = cfg.get('flow', {}).get('use_mock') or []
    if isinstance(use_mock, str):
        # 주의: YAML 에 use_mock: "f1,f3" 처럼 문자열로 적으면 set() 이 글자 단위가 되어
        #    'f1' in use_mock 이 부분문자열 매칭으로 조용히 틀린 선택을 한다
        use_mock = cc_config.parse_use_mock(use_mock)
    use_mock = [m for m in use_mock if m in FEATURES]
    robot = not set(FEATURES) <= set(use_mock)

    cc.init('flow_node', robot=robot)                # ① 맨 앞에서 한 번 (SDD §3.2)
    try:
        node = cc.io_node()
        log = node.get_logger()
        if robot:
            # 주의: 첫 이동 전 문지기(TS-07) — 남이 펜던트에서 툴·TCP 를 바꿔 뒀으면 좌표 전체가 틀어진다.
            #    다르면 여기서 끝낸다(PreflightError → 아래 except 가 traceback 없이 종료 코드 2).
            require_controller(node, cc.cfg(), log)
            warn_if_cable_tight(cc.cfg(), log)          # 시작 전 케이블 장력(경고만 · 약 5 s)
        sig = Signals()
        log.info('기능 모듈:')
        features = load_features(use_mock, log)      # 진짜/가짜 선택 (IRD §10)
        # 전부 가짜면 물러날 로봇이 없다 → 후퇴를 부르지 않는다(cc.safe_retreat 는 뼈대라 예외를 낸다)
        flow = Flow(cc.cfg(), log, features=features,
                    safe_retreat=cc.safe_retreat if robot else None,
                    # 주의: 이동이 도중에 서면(MoveIncomplete) 로봇 위치를 모른다 → 후퇴 금지,
                    #    힘·순응만 끄고 사람이 확인한다 (SDD §7)
                    force_off=cc.force_off if robot else None,
                    no_retreat_errors=(cc.MoveIncomplete,) if robot else (),
                    # FLOW-03 — 정지·재개·중단 (IRD §6). flow 는 로봇을 모른다.
                    is_paused=cc.is_paused if robot else None,
                    halt=cc.halt if robot else None,
                    clear_halt=cc.clear_halt if robot else None,
                    halt_errors=(cc.MotionHalted,) if robot else (),
                    pause=cc.pause if robot else None,
                    resume=cc.resume if robot else None)
        io = Io(node, flow, sig)
        flow._publish_event = io.publish_event       # 두뇌 → 배선 (두뇌는 ROS 를 모른다)

        log.info(f'flow 준비됨 — plan 그릇 {flow.target_bowl} · 컵 {flow.target_cup} · '
                 f'state {io.rate_hz} Hz · use_mock={use_mock or "없음"} · robot={robot}')
        unfilled = cc_config.unfilled(cc.cfg())      # 아직 안 채운 YAML 키 (티칭 전이면 많다)
        if unfilled:
            log.warn(f'설정에 안 채워진 키 {len(unfilled)}개 — 좌표가 필요한 동작은 아직 못 한다')
        flow.run(sig)                                # ② 메인 스레드에서 실행
    except KeyboardInterrupt:                        # Ctrl+C — 처리기는 cobot_common 이 건다
        pass
    except PreflightError as e:                      # 컨트롤러 설정이 다르다 — 움직이지 않고 끝낸다 (TS-07)
        rclpy.logging.get_logger('flow_node').error(str(e))
        raise SystemExit(2)
    except Exception:                                # noqa: BLE001
        # 여기까지 온 예외는 flow 의 보호를 모두 지나온 것이다(설정·초기화·구조 문제).
        # 트레이스백을 그대로 남겨 원인을 알 수 있게 하고, 정리는 finally 가 한다.
        # 노드를 못 쓸 수도 있는 자리라 rclpy 의 이름 있는 로거를 쓴다(AGENTS §4: print 금지).
        rclpy.logging.get_logger('flow_node').error(
            'flow_node 를 계속할 수 없다\n' + traceback.format_exc())
        raise
    finally:
        cc.shutdown()                                # ⑦ 어떤 경우에도 정리


if __name__ == '__main__':
    main()
