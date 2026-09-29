# -*- coding: utf-8 -*-
"""통신 노드 스레드 시험 — 드라이버 없이(robot=False) 돈다.  실행: soc && python3 -m pytest src/cobot_common/test/test_bootstrap_io.py

검토에서 발견: 콜백 하나의 예외로 통신 스레드가 끝나면 /flow/state 가 멈추고 정지 버튼이 먹지 않는다.
"""
import time

import pytest

import cobot_common as cc

TICK_S = 0.05


def _wait_until(cond, timeout_s=3.0):
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def io():
    cc.init('test_bootstrap_io', robot=False)
    try:
        yield cc.io_node()
    finally:
        cc.shutdown()


def test_callback_exception_does_not_stop_io_thread(io):
    ticks, raised = [], []

    def bad():                                  # 한 번만 예외를 내는 콜백
        if not raised:
            raised.append(1)
            raise ValueError('콜백 안에서 난 예외(시험)')

    io.create_timer(TICK_S, bad)
    io.create_timer(TICK_S, lambda: ticks.append(1))
    assert _wait_until(lambda: raised), '예외를 내는 콜백이 불리지 않았다'
    before = len(ticks)
    assert _wait_until(lambda: len(ticks) >= before + 5), '콜백 예외 뒤에 통신 노드가 멈췄다'


def test_repeated_exceptions_keep_other_callbacks_alive(io):
    ticks, errors = [], []

    def always_bad():
        errors.append(1)
        raise RuntimeError('매번 실패(시험)')

    io.create_timer(TICK_S, always_bad)
    io.create_timer(TICK_S, lambda: ticks.append(1))
    assert _wait_until(lambda: len(errors) >= 3 and len(ticks) >= 3)


def test_shutdown_ends_io_thread_and_allows_reinit():
    cc.init('test_bootstrap_io_a', robot=False)
    cc.shutdown()
    cc.init('test_bootstrap_io_b', robot=False)     # 스레드가 남아 있으면 여기서 꼬인다
    ticks = []
    cc.io_node().create_timer(TICK_S, lambda: ticks.append(1))
    try:
        assert _wait_until(lambda: len(ticks) >= 3)
    finally:
        cc.shutdown()


# ------------------------------------------------------------------ setup_io 훅 실패
def _broken_hook(node):
    raise ModuleNotFoundError("No module named 'onrobot_rg_msgs'")     # ws_dsr 이 없는 PC 에서 gripper 훅이 내는 오류


def test_failing_hook_is_skipped_without_robot(monkeypatch):
    """robot=False(전부 mock)는 드라이버 워크스페이스 없이도 떠야 한다 — 훅 실패는 경고만."""
    from cobot_common import gripper
    monkeypatch.setattr(gripper, 'setup_io', _broken_hook, raising=False)
    cc.init('test_bootstrap_io_hook', robot=False)
    ticks = []
    cc.io_node().create_timer(TICK_S, lambda: ticks.append(1))
    try:
        assert _wait_until(lambda: len(ticks) >= 3)
    finally:
        cc.shutdown()


def test_failing_hook_stops_init_with_robot(monkeypatch):
    """robot=True 에서는 빠진 것을 바로 드러낸다(조용히 넘어가면 그리퍼 없이 로봇이 움직인다)."""
    from cobot_common import bootstrap, gripper
    monkeypatch.setattr(gripper, 'setup_io', _broken_hook, raising=False)
    class FakeNode:                                     # 다른 파일의 훅(motion.setup_io)이 클라이언트를 달 수 있게
        def create_client(self, srv_type, name):
            return object()

        def create_subscription(self, *a, **kw):
            return object()
    with pytest.raises(ModuleNotFoundError):
        bootstrap._call_setup_io(node=FakeNode(), robot=True)
