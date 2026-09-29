"""cobot_common.gripper 시험 (INF-02d) — 🚨 로봇 없이 돈다.

드라이버 서비스·토픽을 가짜로 바꿔 넣고, 보낸 명령 문자열과 환산만 확인한다.
실기 확인은 V-05·V-23(파지 힘 전환 10회)에서.
"""
import importlib
import sys
import time
import types

import pytest

# 모듈 이름이 함수 이름과 겹치지 않지만, weigh 와 같은 방식으로 모듈을 직접 얻는다
G = importlib.import_module('cobot_common.gripper')


class FakeLog:
    def __init__(self):
        self.lines = []

    def info(self, m):
        self.lines.append(('info', m))

    def warn(self, m):
        self.lines.append(('warn', m))

    def error(self, m):
        self.lines.append(('error', m))


class FakeRes:
    def __init__(self, ok=True, message=''):
        self.success, self.message = ok, message


class FakeClient:
    """보낸 문자열을 기록한다.

    `fail_at = N` 이면 **N번째 호출만** 실패 응답을 준다(1부터 센다). 명령은 `sent` 에 남는다 —
    "보내기는 했는데 성공했는지 모른다" 가 실제 상황이고, 그리퍼가 이미 움직였을 수 있다.
    호출 번호는 `calls` 로 따로 센다(시험이 `sent.clear()` 를 해도 번호가 흐트러지지 않게).
    """

    def __init__(self, ok=True, fail_at=None):
        self.sent = []
        self.calls = 0
        self._ok = ok
        self.fail_at = fail_at

    def wait_for_service(self, timeout_sec=None):
        return True

    def call(self, req):
        self.sent.append(req.command)
        self.calls += 1
        if self.fail_at is not None and self.calls == self.fail_at:
            return FakeRes(False, f'가짜 실패({self.fail_at}번째 명령)')
        if not self._ok:
            return FakeRes(False, '가짜 실패')
        # 🚨 진짜 드라이버 흉내 — 'i'/'d' 가 목표 힘을 바꾸고 그 값이 effort 로 되돌아온다.
        #    실기에서는 콜백이 _force_n 을 갱신한다(gripper.py `_on_joint_states`).
        #    그래서 시험도 "셈" 이 아니라 "읽기" 로 굴러가야 같은 것을 본다.
        cur = G._force_n
        if cur is not None and req.command in ('i', 'd'):
            step = G._FORCE_STEP_N if req.command == 'i' else -G._FORCE_STEP_N
            G._force_n = max(0.0, min(G._MAX_FORCE_N, cur + step))
        elif cur is None and req.command == 'i':
            # 힘을 한 번도 못 읽은 채 'i' 를 보내면 — 실기 드라이버는 재파지하며 effort 를 보낸다.
            #    가짜는 "실제 힘이 20 이었다" 고 치고 한 계단 위 값을 읽힌 것으로 한다.
            G._force_n = 20.0 + G._FORCE_STEP_N
        return FakeRes(True, '')


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    """드라이버 srv 타입·bootstrap·상태를 가짜로."""
    log = FakeLog()

    srv_mod = types.ModuleType('onrobot_rg_msgs.srv')
    srv_mod.SetCommand = types.SimpleNamespace(
        Request=lambda: types.SimpleNamespace(command=''))
    monkeypatch.setitem(sys.modules, 'onrobot_rg_msgs', types.ModuleType('onrobot_rg_msgs'))
    monkeypatch.setitem(sys.modules, 'onrobot_rg_msgs.srv', srv_mod)

    boot = types.ModuleType('cobot_common.bootstrap')
    boot.cfg = lambda: FAKE_CFG
    boot.io_node = lambda: types.SimpleNamespace(get_logger=lambda: log)
    monkeypatch.setitem(sys.modules, 'cobot_common.bootstrap', boot)

    client = FakeClient()
    monkeypatch.setattr(G, '_client', client)
    monkeypatch.setattr(G, '_force_n', None)
    monkeypatch.setattr(G, '_joint_angle', None)
    monkeypatch.setattr(G, '_effort', 0.0)            # 항상 '멈춤' 으로 둬서 대기가 안 걸리게
    monkeypatch.setattr(G, '_SETTLE_HOLD_S', 0.0)     # 폭이 안 변하니 바로 '멈췄다' 로 (시험 속도)
    return types.SimpleNamespace(client=client, log=log)


FAKE_CFG = {'cell': {
    'limits': {'timeout_s': 1.0},
    'presets': {
        'BOWL': {'grip_width_mm': 2.0, 'grip_force_n': 20, 'hold_force_n': 35},
        'CUP': {'grip_width_mm': 70.0, 'grip_force_n': 15, 'hold_force_n': 30},
    },
}}


# ────────────────────────────────── 폭 환산 (드라이버 식과 같아야 한다)
@pytest.mark.parametrize('mm', [0.0, 2.0, 5.0, 20.0, 62.0, 70.0, 110.0])
def test_width_conversion_round_trip(monkeypatch, mm):
    """드라이버의 widthToJointValue 로 만든 관절각을 우리 식이 같은 폭으로 되돌려야 한다."""
    import numpy as np
    th = np.arccos(((mm / 1000 / 2) - G._DY - G._L1 * np.cos(G._THETA1)) / G._L3) - G._THETA3
    monkeypatch.setattr(G, '_joint_angle', float(th))
    assert G.grip_width() == pytest.approx(mm, abs=0.01)


def test_width_before_first_message_raises():
    """아직 한 번도 못 받았으면 지어내지 않고 알려 준다."""
    with pytest.raises(RuntimeError, match='관절각'):
        G.grip_width()


# ────────────────────────────────── 🚨 힘은 2.5 N 계단 (드라이버 제약)
def test_grip_sets_force_from_the_value_it_read(fake, monkeypatch):
    """🚨 grip 은 **읽은 힘에서 차이만큼만** 움직인다 — 0 N 까지 내려 기준을 잡지 않는다.

    실기: 드라이버가 목표 힘을 프로세스 종료 뒤에도 기억해(40 → 35 → 30 → 25 N)
    "브링업 직후 40 N" 같은 가정이 두 번째 실행부터 어긋났다. 그래서 읽은 값에서 출발한다.
    """
    monkeypatch.setattr(G, '_force_n', 30.0)           # 앞선 실행이 남긴 힘을 읽은 상태
    monkeypatch.setattr(G, '_joint_angle', 0.83)
    G.grip(2.0, 20.0)
    sent = fake.client.sent
    assert sent.count('d') == 4, '30 → 20 N 은 2.5 N × 4 계단'
    assert 'i' not in sent, '올릴 일이 없다'
    assert sent[-1] == '20', '마지막은 폭 명령 (2.0 mm → 0.1 mm 단위)'
    assert G._force_n == pytest.approx(20.0)


def test_set_force_without_any_reading_raises(fake):
    """🚨 한 번도 못 읽었으면 거부한다 — 모르는 값에서 계단을 세면 어디로 갈지 모른다."""
    with pytest.raises(RuntimeError, match='못 읽었다'):
        G._set_force(20.0)
    assert fake.client.sent == [], '거부했으면 아무 명령도 안 보낸다'


def test_second_force_moves_only_difference(fake, monkeypatch):
    """기준이 잡힌 뒤에는 차이만큼만 움직인다."""
    monkeypatch.setattr(G, '_force_n', 20.0)
    fake.client.sent.clear()
    G._set_force(35.0)
    assert fake.client.sent == ['i'] * 6, '20 → 35 N 은 2.5 N × 6 계단'
    assert G._force_n == pytest.approx(35.0)


def test_force_down(fake, monkeypatch):
    monkeypatch.setattr(G, '_force_n', 35.0)
    fake.client.sent.clear()
    G._set_force(20.0)
    assert fake.client.sent == ['d'] * 6


def test_force_not_on_step_warns(fake, monkeypatch):
    """2.5 배수가 아니면 가장 가까운 계단 + 경고."""
    monkeypatch.setattr(G, '_force_n', 0.0)
    G._set_force(21.0)
    assert any('정확히 못 맞춘' in m for _, m in fake.log.lines)


def test_force_clamped_to_max(fake, monkeypatch):
    monkeypatch.setattr(G, '_force_n', 0.0)
    G._set_force(999.0)
    assert G._force_n <= G._MAX_FORCE_N


# ────────────────────────────────── 명령 문자열
def test_grip_sends_width_in_tenths(fake, monkeypatch):
    """폭은 0.1 mm 단위 정수 문자열이다 — 62.0 mm → '620'."""
    monkeypatch.setattr(G, '_force_n', 20.0)
    monkeypatch.setattr(G, '_joint_angle', 0.26)
    fake.client.sent.clear()
    G.grip(62.0, 20.0)
    assert '620' in fake.client.sent


def test_release_sends_open(fake, monkeypatch):
    """기준이 이미 잡혀 있으면 release 는 열기만 한다."""
    monkeypatch.setattr(G, '_force_n', 20.0)
    G.release()
    assert fake.client.sent == ['o']


def test_release_makes_a_move_to_read_the_force(fake, monkeypatch):
    """🚨 힘은 **움직이거나 닫혀 있을 때만** 읽힌다 (실기).

    이미 활짝 열려 있으면 'o' 가 아무 움직임도 안 만들어 못 읽는다 → 아직 한 번도 못 읽었으면
    **빈손으로 한 번 닫았다 연다**. 여기가 손이 빈 게 확실한 유일한 자리다.
    """
    monkeypatch.setattr(G, '_joint_angle', 0.26)
    G.release()
    assert fake.client.sent == ['o', 'c', 'o'], f'읽을 기회를 안 만들었다 — {fake.client.sent}'
    assert 'd' not in fake.client.sent, '0 N 까지 내리는 옛 방식이 남아 있다'


def test_width_out_of_range_is_clamped(fake, monkeypatch):
    monkeypatch.setattr(G, '_force_n', 20.0)
    monkeypatch.setattr(G, '_joint_angle', 0.26)
    fake.client.sent.clear()
    G.grip(999.0, 20.0)
    assert '1100' in fake.client.sent                  # max_width 110.0 mm
    assert any('범위' in m for _, m in fake.log.lines)


# ────────────────────────────────── grip_level (털기·담금이 쓴다)
def test_grip_level_learns_force_by_one_step_regrip_when_unknown(fake, monkeypatch):
    """E36 실기: 쥔 용기로 새 프로세스를 시작하면 effort 가 안 와 힘을 모른다 → 놓지 않고 'i' 한 계단(+2.5 N)
    다시 잡아 읽은 뒤(20 → 22.5) 목표(HOLD 35)까지 맞춘다. 실패로 멈추지 않는다."""
    monkeypatch.setattr(G, '_force_n', None)
    monkeypatch.setattr(G, '_joint_angle', 0.83)
    G.grip_level('BOWL', 'HOLD')
    sent = G._client.sent
    assert sent[0] == 'i' and sent.count('i') == 1 + 5 and 'd' not in sent   # 탐색 1 + (35 − 22.5)/2.5 = 5
    assert G._force_n == pytest.approx(35.0)


def test_grip_level_uses_preset_force(fake, monkeypatch):
    """HOLD 는 프리셋의 hold_force_n 을 쓴다. 폭은 다시 명령하지 않는다."""
    monkeypatch.setattr(G, '_force_n', 20.0)
    monkeypatch.setattr(G, '_joint_angle', 0.83)
    fake.client.sent.clear()
    G.grip_level('BOWL', 'HOLD')                        # 20 → 35 N
    assert fake.client.sent == ['i'] * 6
    assert not any(c.isdigit() for c in fake.client.sent), '폭을 다시 명령하면 안 된다'


def test_grip_level_back_to_normal(fake, monkeypatch):
    monkeypatch.setattr(G, '_force_n', 35.0)
    monkeypatch.setattr(G, '_joint_angle', 0.83)
    fake.client.sent.clear()
    G.grip_level('CUP', 'NORMAL')                       # 35 → 15 N
    assert fake.client.sent == ['d'] * 8


def test_grip_level_without_anchor_refuses(fake, monkeypatch):
    """🚨 쥔 채 힘을 바꾸려는데 힘을 모르면 — 놓지 않고 'i' 한 계단으로 다시 잡아 읽어 본다.
    그래도 드라이버가 effort 를 안 주면 거부한다(모르는 채 계단을 보내면 놓친다).
    조용히 떨어뜨리는 대신 예외 → flow 가 ROBOT_ERROR 로 멈춘다.
    """
    monkeypatch.setattr(G, '_joint_angle', 0.83)

    class Silent(type(G._client)):
        def call(self, req):
            self.sent.append(req.command); self.calls += 1
            return FakeRes(True, '')                                     # effort 를 끝내 안 준다
    monkeypatch.setattr(G, '_client', Silent())
    with pytest.raises(RuntimeError, match='못 읽었다'):
        G.grip_level('BOWL', 'HOLD')
    assert G._client.sent == ['i'], '탐색 한 번만 · 힘 계단은 안 보냄'



def test_grip_level_refuses_when_gripper_is_open(fake, monkeypatch):
    """폭이 100 mm 넘게 열려 있으면(빈손) 힘 전환도 탐색 'i' 도 보내지 않는다(실기: 탐색이 빈손을 닫아 버림)."""
    monkeypatch.setattr(G, '_force_n', None)
    monkeypatch.setattr(G, '_joint_angle', float(G._width_to_angle(110.6)) if hasattr(G, '_width_to_angle') else G._joint_angle)
    monkeypatch.setattr(G, 'grip_width', lambda: 110.6)
    with pytest.raises(RuntimeError, match='열려 있다'):
        G.grip_level('CUP', 'HOLD')
    assert fake.client.sent == []


def test_grip_level_bad_level(fake):
    with pytest.raises(ValueError, match='NORMAL'):
        G.grip_level('BOWL', '세게')


def test_grip_level_unknown_kind(fake, monkeypatch):
    monkeypatch.setattr(G, '_joint_angle', 0.83)
    with pytest.raises(KeyError, match='SPOON'):
        G.grip_level('SPOON', 'HOLD')


# ────────────────────────────────── 실패
def test_service_failure_raises(fake, monkeypatch):
    monkeypatch.setattr(G, '_force_n', 20.0)
    fake.client._ok = False
    with pytest.raises(RuntimeError, match='그리퍼 명령'):
        G.release()


def test_no_client_raises(monkeypatch):
    monkeypatch.setattr(G, '_client', None)
    with pytest.raises(RuntimeError, match='init'):
        G.release()


# ────────────────────────────────── 🚨 기억(_force_n)과 실제 힘이 어긋나면 안 된다
def test_set_force_updates_memory_after_each_command(fake, monkeypatch):
    """명령 한 번마다 기억을 갱신한다 — 계단마다 한 칸씩 따라 올라가야 한다.

    마지막에 한꺼번에 갱신하면 중간에 끊겼을 때 실제 힘과 기억이 갈라진다.
    """
    seen = []
    real_call = fake.client.call

    def spy(req):
        seen.append(G._force_n)                        # 이 명령을 보내기 **직전** 의 기억
        return real_call(req)

    monkeypatch.setattr(fake.client, 'call', spy)
    monkeypatch.setattr(G, '_force_n', 0.0)
    G._set_force(10.0)                                 # 0 → 10 N = 'i' 4계단
    assert seen == [0.0, 2.5, 5.0, 7.5], f'계단마다 갱신하지 않았다 — {seen}'
    assert G._force_n == pytest.approx(10.0)


def test_set_force_failure_midway_does_not_keep_stale_memory(fake, monkeypatch):
    """🚨 도중에 실패하면 기억은 **실제와 맞거나 없어야(None)** 한다.

    재현(감사): 3번째 'i' 에서 실패 → 실제는 5.0~7.5 N 인데 0.0 N 으로 기억하고 있었다.
    그러면 다음부터 힘이 계속 어긋나, NORMAL 인 줄 알고 약하게 쥐어 이송 중 낙하가 된다(SDD §8).
    """
    monkeypatch.setattr(G, '_force_n', 0.0)
    fake.client.fail_at = 3
    with pytest.raises(RuntimeError, match='그리퍼 명령'):
        G._set_force(20.0)                             # 0 → 20 N = 'i' 8계단, 3번째에서 끊긴다
    done = fake.client.sent.count('i') - 1             # 앞 2계단은 확실히 들어갔다
    low = done * G._FORCE_STEP_N                       # 5.0 N
    high = (done + 1) * G._FORCE_STEP_N                # 7.5 N — 실패한 명령이 닿았을 수도 있다
    assert G._force_n is None or low - 0.01 <= G._force_n <= high + 0.01, (
        f'기억 {G._force_n} N 이 실제(≈{low}~{high} N)와 어긋난다')


def test_reading_based_memory_never_goes_stale(fake, monkeypatch):
    """🚨 읽기 기반이라 **어긋난 기억이 생기지 않는다** — 옛 방식이 풀려던 문제가 사라졌다.

    옛 코드(셈 기반)는 도중에 명령이 끊기면 '기억 10 N / 실제 17.5 N' 로 조용히 이어 갔고,
    그래서 "실패하면 기억을 버린다" 는 보호가 필요했다. 지금은 기억이 **드라이버가 돌려준 값**이라
    끊긴 자리까지만 올라가 있고 그대로 맞다 → 다음 동작도 그 값에서 이어 간다.
    """
    monkeypatch.setattr(G, '_force_n', 0.0)
    monkeypatch.setattr(G, '_joint_angle', 0.83)
    fake.client.fail_at = 3
    with pytest.raises(RuntimeError, match='그리퍼 명령'):
        G._set_force(20.0)                             # 0 → 20 N = 'i' 8계단, 3번째에서 끊긴다

    got_through = fake.client.sent.count('i') - 1      # 끊긴 명령은 안 닿았다
    assert G._force_n == pytest.approx(got_through * G._FORCE_STEP_N), (
        f'기억 {G._force_n} N 이 실제로 들어간 {got_through} 계단과 다르다')

    # 기억이 살아 있으니 쥔 채 힘 바꾸기도 그 값에서 이어 간다 (거부할 이유가 없다)
    fake.client.fail_at = None
    fake.client.sent.clear()
    G.grip_level('BOWL', 'NORMAL')                     # → 20 N
    assert G._force_n == pytest.approx(20.0)
    assert not any(c.isdigit() for c in fake.client.sent), '폭을 다시 명령하면 안 된다'


def test_force_memory_comes_only_from_reading(monkeypatch):
    """🚨 기억은 **콜백이 읽은 effort** 에서만 온다. effort 가 0(= 모름)이면 건드리지 않는다.

    활짝 열린 채 정지하면 0 이 오는데, 그걸 '힘이 0 N' 으로 적으면 다음 계산이 통째로 틀어진다.
    """
    import types as _t
    monkeypatch.setattr(G, '_force_n', 22.5)

    def msg(effort):
        return _t.SimpleNamespace(name=[G._FINGER_JOINT], position=[0.5], effort=[effort])

    G._on_joint_states(msg(0.0))
    assert G._force_n == pytest.approx(22.5), '0 이 왔다고 기억을 덮으면 안 된다'

    G._on_joint_states(msg(35.0))
    assert G._force_n == pytest.approx(35.0), '읽힌 값으로 갱신해야 한다'


# ────────────────────────────────── 안전 스위치 읽기·풀기 (상자와 직접 통신)
#   🚨 진짜 상자에 붙지 않는다 — pymodbus 를 가짜 모듈로 바꿔 끼워서 "무엇을 어디에 썼나" 만 본다.
#      실기 확인은 rig_grip_reset.py (check → watch → reset).

class FakeRegs:
    """읽기·쓰기 응답 흉내 (pymodbus 응답은 .registers 와 .isError() 를 갖는다)."""

    def __init__(self, registers=()):
        self.registers = list(registers)

    def isError(self):
        return False


class FakeErrRes:
    """상자가 오류로 답한 경우 — 툴 전원이 꺼져 있을 때 이렇게 온다."""

    registers = None

    def isError(self):
        return True

    def __repr__(self):
        return 'ExceptionResponse(가짜 오류)'


class FakeBox:
    """컴퓨트박스 흉내. 자기 자신을 클라이언트로도 돌려준다(ModbusTcpClient(...) 자리)."""

    def __init__(self):
        self.regs = [0] * 18            # 상태 18칸 — 12~16번째가 안전 스위치
        self.reads, self.writes = [], []
        self.opened = self.closed = 0
        self.connect_ok = True
        self.read_error = False
        self.on_write = None            # 쓰기가 오면 부를 함수 — 전원 재시작 효과를 흉내낸다

    def __call__(self, host=None, port=None, timeout=None):
        self.host, self.port, self.timeout = host, port, timeout
        return self

    def connect(self):
        self.opened += 1
        return self.connect_ok

    def close(self):
        self.closed += 1

    def read_holding_registers(self, address=None, count=None, slave=None):
        self.reads.append((address, count, slave))
        return FakeErrRes() if self.read_error else FakeRegs(self.regs[:count])

    def write_register(self, address=None, value=None, slave=None):
        self.writes.append((address, value, slave))
        if self.on_write:
            self.on_write(self)
        return FakeRegs()


BOX_CFG = dict(FAKE_CFG, f2={'gripper_box': {
    'ip': '192.168.1.1', 'port': 502, 'tool_unit': 65, 'box_unit': 63,
    'status_addr': 258, 'status_count': 18, 'restart_addr': 0, 'restart_value': 2,
    'connect_timeout_s': 0.1, 'restart_wait_s': 1.0, 'driver_alive_s': 0.1,
}})


@pytest.fixture
def box(fake, monkeypatch):
    """가짜 상자 + f2.gripper_box 가 채워진 설정. fake 뒤에 와야 bootstrap 이 이미 가짜다."""
    b = FakeBox()
    client_mod = types.ModuleType('pymodbus.client')
    client_mod.ModbusTcpClient = b
    monkeypatch.setitem(sys.modules, 'pymodbus', types.ModuleType('pymodbus'))
    monkeypatch.setitem(sys.modules, 'pymodbus.client', client_mod)
    monkeypatch.setattr(sys.modules['cobot_common.bootstrap'], 'cfg', lambda: BOX_CFG)
    monkeypatch.setattr(G, '_RESET_POLL_S', 0.0)      # 시험 속도 (실기는 0.5 s)
    return b


def test_safety_reads_the_right_place(box):
    """상태는 **툴 번호(65)** 로, 258번 칸부터 18칸을 읽는다 — 드라이버와 같은 자리."""
    s = G.grip_safety()
    assert box.reads == [(258, 18, 65)]
    assert s['tripped'] is False
    assert box.opened == 1 and box.closed == 1, '붙었으면 반드시 뗀다'


def test_safety_tripped_when_switch_triggered(box):
    """10번째 칸(gsta)의 Bit 3(s1_triggered, 1 << 3 = 8)이 1 이면 걸린 것이다."""
    box.regs[10] = (1 << 3)
    s = G.grip_safety()
    assert s['tripped'] is True and s['s1_triggered'] == 1
    assert s['s1_pushed'] == 0, '눌림(Bit 2)과 걸림(Bit 3)은 다른 비트다'


def test_safety_needs_config(fake):
    """🚨 주소를 모르면 아무 데도 쏘지 않는다."""
    with pytest.raises(G.GripperBoxError, match='gripper_box'):
        G.grip_safety()


def test_safety_read_error_is_reported(box):
    """상자가 오류로 답하면 '정상' 으로 읽지 않는다 — 모르는 것은 모른다고 한다."""
    box.read_error = True
    with pytest.raises(G.GripperBoxError, match='못 읽었다'):
        G.grip_safety()


def test_reset_refuses_when_hand_may_be_full(box):
    """🚨 전원을 껐다 켜면 쥔 것이 떨어진다 → 사람이 밝히기 전에는 **보내지 않는다**."""
    with pytest.raises(RuntimeError, match='떨어뜨린다'):
        G.grip_reset()
    assert box.writes == [], '거부했으면 아무것도 안 쓴다'


def test_reset_writes_restart_to_the_box(box):
    """전원 재시작은 **상자 번호(63)** 의 0번 칸에 2 — 툴 번호(65)가 아니다.

    🚨 강사 배포본의 /onrobot/restartPower 는 여기서 인자 이름이 틀려(values=) 예외가 나고
       드라이버 노드가 죽는다. 그래서 우리가 직접 보낸다(드라이버 소스 확인).
    """
    box.regs[10] = (1 << 3)                           # 걸린 상태에서 시작
    box.on_write = lambda b: b.regs.__setitem__(10, 0)   # 전원이 들어오면서 풀렸다
    s = G.grip_reset(empty_hand=True)
    assert box.writes == [(0, 2, 63)]
    assert s['tripped'] is False


def test_reset_reports_a_dead_driver(box, monkeypatch):
    """전원이 끊긴 순간 드라이버가 죽을 수 있다 → 살아남았는지 알려 준다."""
    box.regs[10] = (1 << 3)
    box.on_write = lambda b: b.regs.__setitem__(10, 0)
    monkeypatch.setattr(G, '_stamp', time.monotonic() - 5)   # 5초째 새 값이 없다
    s = G.grip_reset(empty_hand=True)
    assert s['driver_alive'] is False


def test_reset_sees_a_live_driver(box, monkeypatch):
    """전원 재시작 **뒤에** 새 상태가 오면 살아남은 것이다."""
    box.regs[10] = (1 << 3)

    def powered(b):
        b.regs[10] = 0
        G._stamp = time.monotonic()                   # 드라이버가 다시 발행하기 시작
    box.on_write = powered
    monkeypatch.setattr(G, '_stamp', time.monotonic() - 5)
    assert G.grip_reset(empty_hand=True)['driver_alive'] is True


def test_reset_still_stuck_is_not_called_success(box):
    """전원을 넣었는데도 걸려 있으면 그대로 알려 준다 — 손가락에 뭔가 걸려 있는 것이다."""
    box.regs[10] = (1 << 5)                           # s2_triggered (Bit 5)
    s = G.grip_reset(empty_hand=True)
    assert s['tripped'] is True


def test_stuck_command_now_names_the_safety_switch(box, fake, monkeypatch):
    """폭이 안 변하면 짐작하지 않고 **읽어서** 걸렸다고 말한다."""
    box.regs[10] = (1 << 3)
    monkeypatch.setattr(G, '_force_n', 20.0)
    monkeypatch.setattr(G, '_joint_angle', 0.83)      # 명령해도 폭이 그대로
    G.grip(2.0, 20.0)
    assert any(kind == 'error' and '안전 스위치가 걸렸다' in m for kind, m in fake.log.lines)


def test_stuck_without_a_box_falls_back_to_the_old_guess(fake, monkeypatch):
    """상자에 못 붙어도(Virtual) 본 동작은 막지 않는다 — 짐작 경고로 되돌아간다."""
    monkeypatch.setattr(G, '_force_n', 20.0)
    monkeypatch.setattr(G, '_joint_angle', 0.83)
    G.grip(2.0, 20.0)                                 # f2 절이 없는 FAKE_CFG → 확인 불가
    assert any(kind == 'warn' and '확인하지 못했다' in m for kind, m in fake.log.lines)

