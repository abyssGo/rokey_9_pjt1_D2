# -*- coding: utf-8 -*-
"""실행 뼈대 — SDD §3.2 · TS-01. 바탕: docs/troubleshooting/ts01_repro/virtual/s4_script.py (Virtual 에서 확인)

    import cobot_common as cc

    def main():
        cc.init('rig_f3')              # ① 프로그램 맨 앞에서 한 번 (메인 스레드)
        try:
            ...                        # ② 로봇 함수는 여기(메인 스레드)에서만 차례로
        finally:
            cc.shutdown()              # ③ 끝낼 때 — Ctrl+C 로 끝나도 여기를 지난다

프로세스 안 구조
    메인 스레드       : 기능 함수를 차례로 실행. 두산 함수는 여기서만 (dsr() 가 검사한다)
    통신 노드 스레드  : io_node() — /flow/* 서비스·상태 타이머·구독. 콜백은 값 저장·깃발만
    DSR 전용 노드     : <name>_dsr (ns dsr01). 두산 API 가 명령마다 잠깐 실행기에 넣었다 뺀다. 우리는 건드리지 않는다

Ctrl+C 처리 (flow_node·rig 는 signal.signal 을 따로 걸지 않는다 — try/finally 만 쓴다)
    rclpy 기본 처리기는 Ctrl+C 때 컨텍스트를 먼저 닫아 버려 정지 명령을 보낼 수 없다. 그래서 init 이
    rclpy 처리기를 끄고, 신호가 오면 ⓐ 두산 API 가 돌리는 실행기를 깨워 ⓑ 메인 스레드에 KeyboardInterrupt 를
    일으킨다. finally 의 shutdown() 이 move_stop(정지) → 실행기 종료 → rclpy.shutdown() 순으로 끝낸다.

표기 — E-nn: 팀 결정 번호(docs/meetings/20260919_결정기록_DSN-03.md) · V-nn/INT-nn: 검증 항목(docs/test_logs/) · TS-nn: 트러블슈팅(docs/troubleshooting/)
"""
import atexit
import signal
import socket
import threading

from . import config as _config

ROBOT_ID = 'dsr01'                  # 두산 드라이버 네임스페이스
ROBOT_MODEL = 'm0609'
_SRV_PROBE = 'dsr_controller2/system/get_robot_mode'    # 브링업이 떠 있는지 보는 서비스
_SRV_STOP = 'dsr_controller2/motion/move_stop'          # 설치된 DSR_ROBOT2 에는 stop() 이 없어 직접 부른다
_STOP_MODE = 1                      # DR_QSTOP(Stop Category 2). 제한: motion.py 와 같은 값(두 파일) · 값 확인은 실기 기록 참조
_DRIVER_WAIT_S = 10.0               # 브링업 대기 상한
_STOP_WAIT_S = 2.0                  # 정지 명령 응답 상한
_JOIN_WAIT_S = 2.0                  # 통신 노드 스레드 종료 대기 상한
_IO_MODULES = ('motion', 'gripper', 'force', 'weigh')   # setup_io(node) 가 있으면 init 이 불러 준다

_lock = threading.Lock()
_started = False
_robot = False
_cfg = None
_io = None              # 통신 노드
_dsr_node = None        # DSR 전용 노드
_dsr_mod = None         # import 된 DSR_ROBOT2 모듈
_stop_client = None
_executor = None
_thread = None
_wake_socks = None


def _log():
    from rclpy.logging import get_logger
    return get_logger('cobot_common')


# ------------------------------------------------------------------ 공개 함수
def init(name: str, robot: bool = True):
    """프로그램 맨 앞에서 한 번. robot=False 면 두산 드라이버 없이 통신 노드·설정만 만든다(전부 mock 일 때)."""
    global _started, _robot, _cfg, _io, _dsr_node, _dsr_mod, _stop_client, _executor, _thread
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError('cobot_common.init() 은 메인 스레드에서 부른다 (SDD §3.2)')
    with _lock:
        if _started:
            raise RuntimeError('cobot_common.init() 은 프로그램에서 한 번만 부른다 (SDD §3.2)')
        _started = True
    _cfg = _config.load()           # 설정 오류는 ROS 를 띄우기 전에 드러낸다

    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.signals import SignalHandlerOptions
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    atexit.register(shutdown)       # finally 를 빠뜨린 프로그램의 안전망
    _install_signal_handling()
    try:
        if robot:
            _init_dsr(name)
        _robot = robot
        _io = rclpy.create_node(name)
        _call_setup_io(_io, robot)
        _executor = SingleThreadedExecutor()
        _executor.add_node(_io)
        _thread = threading.Thread(target=_spin_io, name='cc_io', daemon=True)
        _thread.start()
        if robot:
            _dsr_mod.set_robot_mode(_dsr_mod.ROBOT_MODE_AUTONOMOUS)
    except BaseException:
        shutdown()
        raise
    _log().info(f'init 완료: 통신 노드 {name}' + (f' · DSR 전용 노드 {name}_dsr' if robot else ' · robot=False(드라이버 없음)')
                + f" · vel_scale {_cfg['run']['vel_scale']:g} · use_mock {_cfg['flow'].get('use_mock', [])}")
    if robot:
        empty = _config.unfilled(_cfg)
        if empty:
            _log().warn(f'설정에 비어 있는 값 {len(empty)}개 (예: {", ".join(empty[:3])} …) — 쓰는 함수에서 None 이 나온다. '
                        'cell.yaml · params.yaml 에 값을 채운다')


def io_node():
    """통신 노드. 여기에 서비스·발행기·타이머·구독을 단다. 콜백은 값 저장·깃발 세우기만 (로봇 함수 호출 금지)."""
    if _io is None:
        raise RuntimeError('cobot_common.init() 을 먼저 부른다')
    return _io


def cfg() -> dict:
    """설정(cell.yaml + params.yaml). cfg()['cell'] · cfg()['f3'] … init 전이면 그 자리에서 읽는다."""
    global _cfg
    if _cfg is None:
        _cfg = _config.load()
    return _cfg


def shutdown():
    """동작 정지 명령 → 통신 노드 실행기 종료 → rclpy.shutdown(). 여러 번 불러도 된다."""
    global _started, _robot, _io, _dsr_node, _dsr_mod, _stop_client, _executor, _thread
    if not _started:
        return
    try:
        import rclpy
    except ImportError:
        return
    main = threading.current_thread() is threading.main_thread()
    if main:
        signal.signal(signal.SIGINT, signal.SIG_IGN)    # 정리하는 동안의 Ctrl+C 연타는 무시
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    if _robot and _stop_client is not None and rclpy.ok():
        if main:
            _send_stop()
        else:
            _log().warn('shutdown() 이 메인 스레드 밖에서 불려 정지 명령을 보내지 않았다')
    if _executor is not None:
        _executor.shutdown(timeout_sec=_JOIN_WAIT_S)
    if _thread is not None and _thread is not threading.current_thread():
        _thread.join(timeout=_JOIN_WAIT_S)
    for node in (_io, _dsr_node):
        if node is not None:
            try:
                node.destroy_node()
            except Exception:
                pass
    if rclpy.ok():
        rclpy.shutdown()
    _remove_signal_handling(main)
    _io = _dsr_node = _dsr_mod = _stop_client = _executor = _thread = None
    _robot = False
    _started = False


# ------------------------------------------------------------------ cobot_common 내부용 (motion·force·weigh)
def dsr():
    """import 된 DSR_ROBOT2 모듈. cobot_common 안에서만 쓴다: dsr().movej(...)

    기능 패키지(f1·f2·f3)는 이 함수도 DSR_ROBOT2 도 직접 쓰지 않는다 — cc.move_to() 같은 공용 함수만.
    """
    if _dsr_mod is None:
        raise RuntimeError('두산 API 가 없다: cobot_common.init(name) 을 먼저 부르거나, robot=False(mock) 로 시작했다')
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError('로봇 함수는 메인 스레드에서만 부른다 — 콜백·타이머·다른 스레드 금지 (SDD §3.2, TS-01)')
    return _dsr_mod


# ------------------------------------------------------------------ 내부
def _init_dsr(name):
    """DSR 전용 노드를 DR_init 에 넣은 뒤에 DSR_ROBOT2 를 import 한다 (TS-01 증상 A)."""
    global _dsr_node, _dsr_mod, _stop_client
    import rclpy
    try:
        import DR_init
    except ImportError as e:
        raise RuntimeError('DR_init 을 못 찾는다: .bashrc 의 PYTHONPATH 에 ws_dsr/install/dsr_common2/lib/dsr_common2/imp '
                           '를 넣는다 (docs/setup/M0609_환경설정.md 8-7)') from e
    DR_init.__dsr__id = ROBOT_ID
    DR_init.__dsr__model = ROBOT_MODEL
    _dsr_node = rclpy.create_node(f'{name}_dsr', namespace=ROBOT_ID)
    DR_init.__dsr__node = _dsr_node

    from dsr_msgs2.srv import GetRobotMode, MoveStop
    probe = _dsr_node.create_client(GetRobotMode, _SRV_PROBE)
    if not probe.wait_for_service(timeout_sec=_DRIVER_WAIT_S):
        raise RuntimeError(f'두산 드라이버가 안 보인다(/{ROBOT_ID}/{_SRV_PROBE}, {_DRIVER_WAIT_S:.0f} s). '
                           '브링업(sod && sodvir)과 ROS_DOMAIN_ID 를 확인한다')
    _dsr_node.destroy_client(probe)
    _stop_client = _dsr_node.create_client(MoveStop, _SRV_STOP)

    import DSR_ROBOT2               # 주의: 반드시 노드를 넣은 뒤. 모듈 맨 위로 올리지 않는다
    _dsr_mod = DSR_ROBOT2


def _call_setup_io(node, robot):
    """기능 모듈이 통신 노드에 구독·클라이언트를 다는 자리. 예: gripper.py 의 setup_io(node) 가 그리퍼 폭을 구독한다.

    robot=True  : 훅이 실패하면 init 도 실패한다 — 실기·Virtual 에서는 빠진 것을 바로 드러내는 편이 안전하다.
    robot=False : 훅 실패는 경고만 남기고 건너뛴다 — "전부 mock 이면 드라이버 없이 돈다"(SDD §5.1)를 지킨다.
                  예: 드라이버 워크스페이스(ws_dsr)가 없는 PC 에서는 gripper 훅이 onrobot_rg_msgs 를 못 찾는다.
    """
    import importlib
    for mod_name in _IO_MODULES:
        mod = importlib.import_module(f'{__package__}.{mod_name}')
        hook = getattr(mod, 'setup_io', None)
        if not callable(hook):
            continue
        try:
            hook(node)
        except Exception as e:
            if robot:
                raise
            _log().warn(f'{mod_name}.setup_io 를 건너뛴다(robot=False 라 계속 진행): {e!r}')


def _spin_io():
    """통신 노드 실행기를 돌린다. 콜백 하나가 예외를 내도 스레드는 죽지 않는다 — 로그를 남기고 계속 돈다.

    rclpy 실행기는 콜백 예외를 spin() 밖으로 다시 던진다. 여기서 끝내 버리면 프로세스는 살아 있는데
    /flow/state 가 멈추고 start·stop·resume 이 응답하지 않는다(메인 스레드는 로봇을 계속 움직이는데 정지 버튼이 안 먹는다).
    """
    import traceback
    from rclpy.executors import ExternalShutdownException
    executor = _executor                    # shutdown() 이 전역을 None 으로 바꿔도 이 스레드는 자기 것을 본다
    while True:
        try:
            executor.spin()                 # 정상 반환 = executor.shutdown() 또는 컨텍스트 종료
            return
        except ExternalShutdownException:
            return
        except Exception:                   # 콜백 안에서 난 예외 — 그 콜백 1회만 버리고 나머지는 계속 돈다
            _log().error('통신 노드 콜백에서 예외가 났다(통신 노드는 계속 돈다). 콜백은 값 저장·깃발만 하게 고친다:\n'
                         + traceback.format_exc(limit=6))


def _send_stop():
    """동작 정지. 두산 API 의 전역 실행기는 Ctrl+C 로 끊긴 상태일 수 있어 새 실행기로 기다린다."""
    from rclpy.executors import SingleThreadedExecutor
    from dsr_msgs2.srv import MoveStop
    if not _stop_client.service_is_ready():
        _log().warn('move_stop 서비스가 안 보여 정지 명령을 보내지 못했다')
        return
    req = MoveStop.Request()
    req.stop_mode = _STOP_MODE
    ex = SingleThreadedExecutor()
    try:
        ex.add_node(_dsr_node)
        future = _stop_client.call_async(req)
        ex.spin_until_future_complete(future, timeout_sec=_STOP_WAIT_S)
        if future.done() and future.result() is not None and future.result().success:
            _log().info('정지 명령(move_stop) 완료')
        else:
            _log().warn(f'정지 명령 응답이 없다({_STOP_WAIT_S:.0f} s). 로봇이 움직이는 중이었다면 브링업부터 다시 띄운다')
    except Exception as e:
        _log().warn(f'정지 명령 실패: {e!r}')
    finally:
        ex.remove_node(_dsr_node)
        ex.shutdown(timeout_sec=0)


def _install_signal_handling():
    """SIGINT·SIGTERM → 메인 스레드에 KeyboardInterrupt.

    두산 API 는 응답을 기다리며 rcl wait(C 코드) 안에 머문다. 파이썬 신호 처리기는 C 코드가 돌아와야 실행되므로,
    신호가 오면 감시 스레드가 전역 실행기를 깨워 wait 를 끝낸다.
    """
    global _wake_socks
    import rclpy
    r, w = socket.socketpair()
    w.setblocking(False)
    _wake_socks = (r, w)
    signal.set_wakeup_fd(w.fileno(), warn_on_full_buffer=False)
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, _raise_interrupt)

    def watch():
        while True:
            try:
                if not r.recv(16):
                    return
            except OSError:
                return
            try:
                rclpy.get_global_executor().wake()
            except Exception:
                pass
    threading.Thread(target=watch, name='cc_signal', daemon=True).start()


def _raise_interrupt(signum, frame):
    raise KeyboardInterrupt


def _remove_signal_handling(main):
    global _wake_socks
    if not main:                    # 신호 설정은 메인 스레드에서만 바꿀 수 있다 → 그대로 둔다
        return
    signal.set_wakeup_fd(-1)
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    if _wake_socks is not None:
        for s in _wake_socks:
            try:
                s.close()
            except OSError:
                pass
        _wake_socks = None
