"""cobot_common.weigh 시험 (INF-02c) — 🚨 로봇 없이 돈다.

두산 API(dsr())와 로거를 가짜로 바꿔 넣고 계산·거르기만 확인한다.
실기 확인(100/200 g 추, 연속 3회)은 V-02 와 한 세션에서 한다.
"""
import importlib
import sys
import types

import pytest

# 🚨 `from cobot_common import weigh` 는 **함수**를 준다 — __init__.py 의 `from .weigh import *`
#    가 함수 이름을 패키지에 올려 모듈 이름을 가린다(모듈과 함수 이름이 같아서).
#    모듈을 얻으려면 importlib 를 쓴다.
W = importlib.import_module('cobot_common.weigh')


class FakeLog:
    def __init__(self):
        self.lines = []

    def info(self, m):
        self.lines.append(('info', m))

    def warn(self, m):
        self.lines.append(('warn', m))

    def error(self, m):
        self.lines.append(('error', m))


class FakeDsr:
    """get_tool_force 가 미리 정한 값을 차례로 돌려준다.

    🚨 값은 **g 로 적고** API 처럼 [fx, fy, fz, mx, my, mz] 로 돌려준다 — fz = −g / 101.97 (중력은 −Z, ⑥).
       실패 신호는 API 그대로 -1 (리스트가 아님). 예외는 그대로 던진다.
    """
    DR_BASE = 0

    def __init__(self, values, reset_raises=False, reset_delay=0.0):
        self.values = list(values)
        self.reset_calls = 0
        self._reset_raises = reset_raises
        self._reset_delay = reset_delay

    def get_tool_force(self, ref=None):
        if not self.values:
            raise RuntimeError('값이 더 없다')
        v = self.values.pop(0)
        if isinstance(v, Exception):
            raise v
        if v == -1:                                   # 실패 신호 — API 는 리스트 대신 -1
            return -1
        return [0.0, 0.0, -float(v) / 101.97, 0.0, 0.0, 0.0]

    def reset_workpiece_weight(self):
        self.reset_calls += 1
        if self._reset_raises:
            raise RuntimeError('컨트롤러가 응답하지 않는다')
        if self._reset_delay:
            import time
            time.sleep(self._reset_delay)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """읽기 간격(weigh_sample_gap_s)의 sleep 을 없앤다 — 시험은 시간을 기다리지 않는다. 간격 자체는 아래 시험이 따로 본다."""
    monkeypatch.setattr(W.time, 'sleep', lambda s: None)


@pytest.fixture
def fake(monkeypatch):
    """bootstrap 의 dsr·cfg·io_node 를 가짜로 바꾼다."""
    log = FakeLog()
    state = {}

    def install(dsr_obj, conf=None):
        state['dsr'] = dsr_obj
        boot = types.ModuleType('cobot_common.bootstrap')
        boot.dsr = lambda: dsr_obj
        boot.cfg = lambda: conf or {}
        boot.io_node = lambda: types.SimpleNamespace(get_logger=lambda: log)
        monkeypatch.setitem(sys.modules, 'cobot_common.bootstrap', boot)
        return log

    return install


# ────────────────────────────────── 🚨 부호 있는 Fz — 무게 = −Fz × 101.97 (실기 · ⑥)
def test_fz_sign_and_unit(fake):
    """실기: 그릇+107 g 이 Fz −0.79 N → +80.6 g. 빈손 +0.87 N(편향) → −88.7 g. 부호를 버리면(|Fz|) 둘을 구분 못 한다."""
    class Raw(FakeDsr):
        def get_tool_force(self, ref=None):
            return [0.1, -0.2, self.values.pop(0), 0.0, 0.0, 0.0]
    fake(Raw([-0.79]))
    assert W.weigh(1) == pytest.approx(80.6, abs=0.1)
    fake(Raw([+0.87]))
    assert W.weigh(1) == pytest.approx(-88.7, abs=0.1)      # 음수가 그대로 나온다 — 기준값 빼기가 상쇄한다


def test_negative_weight_is_kept(fake):
    """⑥ 편향이 음수면 무게도 음수다 — 이건 실패가 아니다(실패 신호는 -1 **리스트가 아닌 것**)."""
    fake(FakeDsr([-40.0, -42.0, -41.0]))
    assert W.weigh(3) == pytest.approx(-41.0)


# ────────────────────────────────── 🚨 읽기 간격 — 갱신 전에 다시 읽으면 같은 값 (실기)
def test_sleeps_between_samples_not_before_first(fake, monkeypatch):
    slept = []
    monkeypatch.setattr(W.time, 'sleep', lambda s: slept.append(s))
    fake(FakeDsr([10.0, 11.0, 12.0]), {'f2': {'weigh_sample_gap_s': 0.7}})
    W.weigh(3)
    assert slept == [0.7, 0.7]                      # n−1 번, 첫 읽기 앞에는 안 기다린다


def test_no_gap_when_unset(fake, monkeypatch):
    slept = []
    monkeypatch.setattr(W.time, 'sleep', lambda s: slept.append(s))
    fake(FakeDsr([10.0, 11.0]))
    W.weigh(2)
    assert slept == []


# ────────────────────────────────── 중앙값
def test_median_ignores_one_wild_value(fake):
    """🚨 핵심 — 한 번 크게 튀어도 끌려가지 않는다.

    V-02 에서 200 g 추가 40.8 g 폭으로 흔들렸다. 평균이면 튄 값에 끌려간다.
    """
    log = fake(FakeDsr([220.0, 221.0, 500.0, 222.0, 223.0]))   # 500 이 튄 값
    g = W.weigh(5)
    assert g == 222.0                       # 평균이면 277.2 가 된다
    assert 220.0 < g < 224.0


def test_median_even_count(fake):
    fake(FakeDsr([100.0, 200.0]))
    assert W.weigh(2) == 150.0


def test_single_sample(fake):
    fake(FakeDsr([181.5]))
    assert W.weigh(1) == 181.5


# ────────────────────────────────── 🚨 음수 = 실패 신호
def test_failure_value_is_dropped(fake):
    """API 는 실패를 -1(리스트가 아님)로 알려 준다 — 계산에 섞이면 안 된다."""
    log = fake(FakeDsr([220.0, -1, 222.0, -1, 224.0]))
    g = W.weigh(5)
    assert g == pytest.approx(222.0)
    assert sum(1 for lv, _ in log.lines if lv == 'warn') >= 2


def test_all_failed_raises(fake):
    """하나도 못 읽으면 숫자를 지어내지 않고 예외를 던진다.

    숫자 하나로는 '0 g' 과 '실패' 를 구분할 수 없다.
    """
    fake(FakeDsr([-1, -1, -1]))
    with pytest.raises(RuntimeError, match='읽지 못했다'):
        W.weigh(3)


def test_exception_in_one_call_continues(fake):
    """한 번 예외가 나도 나머지로 이어 간다."""
    fake(FakeDsr([220.0, RuntimeError('일시 실패'), 222.0]))
    assert W.weigh(3) == 221.0


# ────────────────────────────────── 🚨 reset 은 위험하다 (TS-03)
def test_reset_not_called_unless_asked(fake):
    """🚨 기본은 0점 재설정을 하지 않는다 — TS-03 에서 컨트롤러가 전부 멈췄다."""
    d = FakeDsr([200.0])
    fake(d)
    W.weigh(1)
    assert d.reset_calls == 0


def test_reset_called_once_when_asked(fake):
    d = FakeDsr([200.0])
    fake(d)
    W.weigh(1, reset=True)
    assert d.reset_calls == 1


def test_reset_failure_does_not_stop_measurement(fake):
    """🚨 reset 이 터져도 측정은 계속한다. 그리고 다시 부르지 않는다."""
    d = FakeDsr([200.0, 201.0, 202.0], reset_raises=True)
    log = fake(d)
    g = W.weigh(3, reset=True)
    assert g == 201.0                       # 측정은 됐다
    assert d.reset_calls == 1               # 한 번만 불렀다
    assert any('0점 재설정 실패' in m for _, m in log.lines)


# ────────────────────────────────── 기록
def test_individual_values_are_logged(fake):
    """V-02 에서 회차 값을 안 남겨 평균·표준편차를 못 냈다 — 개별 값을 남긴다."""
    log = fake(FakeDsr([220.0, 221.0, 222.0]))
    W.weigh(3)
    info = [m for lv, m in log.lines if lv == 'info']
    assert any('220.0' in m and '221.0' in m and '222.0' in m for m in info)


# ────────────────────────────────── 🔗 케이블 장력 경고 — 표본 퍼짐
def test_jitter_warns_about_cable(fake):
    """**떨림**(추세를 뺀 폭)이 크면 케이블 장력 경고 — 값은 그대로 중앙값."""
    jumpy = [0, 70, 5, 75, 10, 65, 0, 70, 5, 75]                  # 위아래로 튄다 · 흐름은 거의 0
    log = fake(FakeDsr(jumpy), {'f2': {'limits': {'max_weigh_spread_g': 50}}})
    W.weigh(10)
    assert any('케이블' in m for lv, m in log.lines if lv == 'warn')
    assert W.weigh_last()['jitter_g'] > 50 and W.weigh_last()['n'] == 10


def test_steady_slide_is_drift_not_cable(fake):
    """🚨 한 방향으로 미끄러지는 것은 **영점 흐름**이지 케이블이 아니다 (실기 거짓 경보).

    옛 코드는 퍼짐 하나만 봐서 이 경우에도 '케이블 장력' 이라고 했다.
    """
    slide = [0, 5, 10, 15, 20, 60, 65, 70, 75, 80]                # 계속 커진다 · 추세를 빼면 떨림은 작다
    log = fake(FakeDsr(slide), {'f2': {'limits': {'max_weigh_spread_g': 50, 'max_weigh_drift_g': 20}}})
    g = W.weigh(10)
    assert g == pytest.approx(40.0)
    assert not any('케이블' in m for lv, m in log.lines if lv == 'warn'), '케이블 경고는 뜨면 안 된다'
    assert any('영점이 움직이고' in m for lv, m in log.lines if lv == 'warn'), '영점 흐름 경고가 떠야 한다'
    assert W.weigh_last()['drift_g'] > 20


def test_spread_quiet_when_within_limit(fake):
    log = fake(FakeDsr([40, 42, 44, 41, 43, 45, 42, 44, 43, 42]),
               {'f2': {'limits': {'max_weigh_spread_g': 50, 'max_weigh_drift_g': 20}}})
    W.weigh(10)
    assert not any('케이블' in m or '영점' in m for lv, m in log.lines if lv == 'warn')
    assert W.weigh_last()['spread_g'] < 10 and abs(W.weigh_last()['drift_g']) < 5


def test_spread_no_limit_no_warning(fake):
    log = fake(FakeDsr([0, 100, 0, 100, 0, 100]))
    W.weigh(6)
    assert not any('케이블' in m for lv, m in log.lines if lv == 'warn')


# ────────────────────────────────── 재는 값을 화면으로 — 표본마다 듣는 함수를 부른다
def test_listener_gets_every_sample_then_the_median(fake):
    """표본을 하나 읽을 때마다 지금까지 읽은 값 전부를, 다 재면 done=True 와 중앙값을 넘긴다(화면의 무게 측정 칸)."""
    fake(FakeDsr([10.0, 30.0, 20.0]))
    heard = []
    W.set_weigh_listener(lambda samples, n, done, median_g: heard.append((samples, n, done, median_g)))
    try:
        g = W.weigh(3)
    finally:
        W.set_weigh_listener(None)
    assert [len(h[0]) for h in heard] == [1, 2, 3, 3]
    assert [h[2] for h in heard] == [False, False, False, True]
    assert all(h[1] == 3 for h in heard) and heard[0][3] is None
    assert heard[-1][3] == pytest.approx(g) and heard[-1][0] == pytest.approx(heard[2][0])
    heard[0][0].append(999.0)                                 # 넘겨받은 목록을 고쳐도 다음 값에 섞이지 않는다(사본)
    assert 999.0 not in heard[1][0]


def test_listener_failure_does_not_stop_weighing(fake):
    """듣는 함수가 터져도(화면 쪽 문제) 무게는 끝까지 잰다 — 경고만 남긴다."""
    log = fake(FakeDsr([10.0, 30.0, 20.0]))

    def boom(*a):
        raise RuntimeError('화면이 없다')
    W.set_weigh_listener(boom)
    try:
        assert W.weigh(3) == pytest.approx(W.weigh_last()['median_g'])
    finally:
        W.set_weigh_listener(None)
    assert any('표본 알림 실패' in m for lv, m in log.lines if lv == 'warn')


def test_no_listener_by_default(fake):
    """듣는 함수를 걸지 않으면 예전과 같다."""
    fake(FakeDsr([10.0, 11.0, 12.0]))
    assert W._listener is None
    assert W.weigh(3) == pytest.approx(W.weigh_last()['median_g'])
