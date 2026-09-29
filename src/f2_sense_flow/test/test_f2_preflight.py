# -*- coding: utf-8 -*-
"""preflight — 툴·TCP 이름 문지기 (TS-07). 로봇·ROS 없이 가짜 노드로."""
import sys
import types

import pytest

from f2_sense_flow import preflight as P


class _Res:
    def __init__(self, info, success=True):
        self.info, self.success = info, success


class _Client:
    def __init__(self, res, available=True):
        self._res, self._available = res, available

    def wait_for_service(self, timeout_sec=0):
        return self._available

    def call(self, req):
        return self._res


class _Node:
    """create_client 가 서비스 이름별로 미리 정한 응답을 준다."""
    def __init__(self, answers):
        self.answers = answers            # {'tool/get_current_tool': _Client, ...}
        self.destroyed = 0

    def create_client(self, srv, name):
        return self.answers[name.replace(P._SRV_PREFIX, '')]

    def destroy_client(self, c):
        self.destroyed += 1


@pytest.fixture(autouse=True)
def fake_srv(monkeypatch):
    """dsr_msgs2 없이 돌게 — Request() 만 있으면 된다."""
    m = types.ModuleType('dsr_msgs2.srv')
    for n in ('GetCurrentTool', 'GetCurrentTcp'):
        setattr(m, n, type(n, (), {'Request': staticmethod(lambda: object())}))
    monkeypatch.setitem(sys.modules, 'dsr_msgs2', types.ModuleType('dsr_msgs2'))
    monkeypatch.setitem(sys.modules, 'dsr_msgs2.srv', m)


CFG = {'flow': {'preflight': {'tool_name': 'Tool Weight', 'tcp_name': 'GripperDA_v1', 'timeout_s': 0.1}}}


def _node(tool='Tool Weight', tcp='GripperDA_v1', tool_ok=True, tcp_avail=True):
    return _Node({'tool/get_current_tool': _Client(_Res(tool, tool_ok)),
                  'tcp/get_current_tcp': _Client(_Res(tcp), available=tcp_avail)})


def test_pass_when_names_match():
    n = _node()
    got = P.require_controller(n, CFG)
    assert got == {'tool': 'Tool Weight', 'tcp': 'GripperDA_v1'}
    assert n.destroyed == 2                                   # 클라이언트를 남기지 않는다


def test_refuse_when_tcp_unset():
    """실기 사고 — TCP 가 풀려 있으면 같은 좌표가 208 mm 아래로 간다. 시작을 거부한다."""
    with pytest.raises(P.PreflightError, match="tcp: 기대 'GripperDA_v1' · 지금 ''"):
        P.require_controller(_node(tcp=''), CFG)


def test_refuse_when_tool_differs():
    with pytest.raises(P.PreflightError, match='tool'):
        P.require_controller(_node(tool='NoTool'), CFG)


def test_refuse_when_service_missing():
    with pytest.raises(P.PreflightError, match='서비스'):
        P.require_controller(_node(tcp_avail=False), CFG)


def test_refuse_when_success_false():
    with pytest.raises(P.PreflightError, match='응답 없음'):
        P.require_controller(_node(tool_ok=False), CFG)


def test_skip_item_when_name_empty():
    """비워 둔 항목은 검사하지 않는다 — TCP 만 확인하고 싶을 때."""
    cfg = {'flow': {'preflight': {'tool_name': '', 'tcp_name': 'GripperDA_v1'}}}
    assert P.require_controller(_node(tool='아무거나'), cfg) == {'tcp': 'GripperDA_v1'}


def test_no_config_warns_and_passes():
    class Log:
        def __init__(self): self.w = []
        def warn(self, m): self.w.append(m)
        def info(self, m): pass
    log = Log()
    assert P.require_controller(_node(), {'flow': {}}, log) == {}
    assert any('preflight' in m for m in log.w)


def test_virtual_controller_skips_check(monkeypatch):
    """에뮬레이터면 이름이 달라도 통과(경고만) — 실기(또는 모름)면 그대로 검사한다."""
    monkeypatch.setattr(P, '_is_virtual', lambda: True)

    class Log:
        def __init__(self): self.w = []
        def warn(self, m): self.w.append(m)
        def info(self, m): pass
    log = Log()
    assert P.require_controller(_node(tcp=''), CFG, log) == {}
    assert any('Virtual' in m for m in log.w)
    monkeypatch.setattr(P, '_is_virtual', lambda: False)
    with pytest.raises(P.PreflightError):
        P.require_controller(_node(tcp=''), CFG)


# ────────────────────────────────── 🔗 시작 전 케이블 확인
class _Log2:
    def __init__(self): self.w, self.i = [], []
    def warn(self, m): self.w.append(m)
    def info(self, m): self.i.append(m)


def _cable_cfg(**kw):
    return {'flow': {'preflight': {'cable': dict({'samples': 6, 'gap_s': 0.0, 'max_spread_g': 60}, **kw)}}}


def test_cable_warns_when_fz_wanders(monkeypatch):
    vals = iter([-0.5, -0.9, -0.3, -1.2, -0.4, -1.1])               # N — g 로 ±40 넘게 널뜀
    monkeypatch.setattr(P, '_read_fz', lambda: next(vals))
    monkeypatch.setattr(P, '_is_virtual', lambda: False)
    log = _Log2()
    spread, samples = P.warn_if_cable_tight(_cable_cfg(), log)
    assert len(samples) == 6 and spread > 60 and any('케이블' in m for m in log.w)


def test_cable_quiet_when_steady(monkeypatch):
    vals = iter([-0.50, -0.52, -0.49, -0.51, -0.50, -0.53])
    monkeypatch.setattr(P, '_read_fz', lambda: next(vals))
    monkeypatch.setattr(P, '_is_virtual', lambda: False)
    log = _Log2()
    spread, _ = P.warn_if_cable_tight(_cable_cfg(), log)
    assert spread < 10 and not log.w and any('✅' in m for m in log.i)


def test_cable_skips_without_config_or_on_virtual(monkeypatch):
    monkeypatch.setattr(P, '_read_fz', lambda: (_ for _ in ()).throw(AssertionError('읽으면 안 된다')))
    monkeypatch.setattr(P, '_is_virtual', lambda: False)
    assert P.warn_if_cable_tight({'flow': {'preflight': {}}}, _Log2()) == (None, [])
    assert P.warn_if_cable_tight(_cable_cfg(samples=0), _Log2()) == (None, [])
    monkeypatch.setattr(P, '_is_virtual', lambda: True)
    assert P.warn_if_cable_tight(_cable_cfg(), _Log2()) == (None, [])


# ────────────────────────────────── 🚨 낮은 자세에서 HOME (테이블 충돌)
class _FakeCC:
    """cobot_common 흉내 — 부른 순서를 적는다."""

    def __init__(self, z=-13.6, where_raises=False):
        self.calls, self._z, self._raises = [], z, where_raises

    def where(self):
        if self._raises:
            raise RuntimeError('못 읽는다')
        self.calls.append(('where',))
        return [0.0, 0.0, self._z, 0.0, 0.0, 0.0]

    def safe_retreat(self):
        self.calls.append(('safe_retreat',))

    def move_to(self, station, carrying, kind=None):
        self.calls.append(('move_to', station, carrying, kind))


def test_go_home_safely_rises_before_moving_home(monkeypatch):
    """🚨 수조 안(z −13.6)에서 곧장 HOME 으로 가면 테이블을 쓴다 → **safe_retreat 이 먼저**여야 한다."""
    fake = _FakeCC(z=-13.6)
    monkeypatch.setattr(P, '_cc', lambda: fake)
    log = _Log2()
    P.go_home_safely('BOWL', log)
    order = [c[0] for c in fake.calls]
    assert order.index('safe_retreat') < order.index('move_to'), f'순서가 틀렸다: {order}'
    assert fake.calls[-1] == ('move_to', 'HOME', True, 'BOWL')
    assert any('안전 높이' in m for m in log.i)


def test_go_home_safely_still_retreats_when_height_unreadable(monkeypatch):
    """높이를 못 읽어도 후퇴는 한다 — 읽기 실패로 충돌 방지를 포기하지 않는다."""
    fake = _FakeCC(where_raises=True)
    monkeypatch.setattr(P, '_cc', lambda: fake)
    P.go_home_safely(None, _Log2(), carrying=False)
    assert [c[0] for c in fake.calls] == ['safe_retreat', 'move_to']
    assert fake.calls[-1] == ('move_to', 'HOME', False, None)

