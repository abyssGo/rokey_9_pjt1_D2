"""F2 기능 함수(weigh·leftover_loop·shake·dip) 시험 — 🚨 로봇·브링업·ROS 없이 돈다.

sense.py 는 cobot_common 을 통해서만 로봇을 부르므로, 그 모듈을 가짜로 바꿔 끼우면
호출 **순서와 인자**를 그대로 검사할 수 있다. 값은 params.yaml 이 아니라 아래 CFG 를 쓴다.

이 시험이 지키려는 것
  · 티칭 자세까지 내려가는가 (move_to 가 돌려준 남은 높이만큼)
  · 한 주기 시간을 구간별로 나눠 쓰는가 (period/4 · period/2)
  · HOLD 를 **반드시** NORMAL 로 되돌리는가 (실패해도)
  · 미끄러짐을 폭으로 잡는가
  · 예외가 밖으로 새지 않고 Result.fail(ROBOT_ERROR) 가 되는가
"""
import sys
import types

import pytest

from cobot_api import GRIP_FAIL, LEFTOVER_REMAIN, OK, ROBOT_ERROR

CFG = {'f2': {
    'empty_weight_g': {'BOWL': 180.0, 'CUP': 120.0},
    'leftover_threshold_g': 50.0,
    'weigh_samples': 5,
    'weigh_settle_s': 0.5,                     # 🚨 0 으로 두면 sleep 을 지워도 시험이 통과한다
    'slip_tol_mm': 1.0,
    'limits': {'max_amp_deg': 45.0, 'max_depth_mm': 150.0, 'max_hold_s': 5.0,
               'max_settle_s': 5.0, 'min_net_g': -30.0},
    'shake': {'WASTE': {'joint': 5, 'amp_deg': 15.0, 'cycles': 4, 'period_s': 0.6},
              'RINSE': {'joint': 4, 'amp_deg': 30.0, 'period_s': 0.7, 'acc_deg_s2': 600.0, 'at': 'RINSE_SHAKE', 'fast': True, 'smooth': True}},   # E36
    'dip': {'RINSE': {'depth_mm': 60.0, 'hold_s': 0.2}},
}, 'cell': {'stations': {'RINSE': {}, 'RINSE_SHAKE': {}, 'WASTE': {}, 'WEIGH': {}, 'HOME': {}},
            'motion': {'vel_joint_max_deg_s': 100.0, 'acc_joint_max_deg_s2': 200.0}, 'limits': {'vel_carry_pct': 30}}}   # shake at=<스테이션> · smooth 복구 검사용


class Rec:
    """가짜 cobot_common — 부른 것을 순서대로 적어 둔다."""

    def __init__(self, weights=(), widths=(), up=0.0, raise_on=None):
        self.calls = []
        self._weights = list(weights)
        self._widths = list(widths)
        self._up = up
        self._raise_on = raise_on

    # ── 기록용 도우미 ──
    def _note(self, name, *args, **kw):
        self.calls.append((name, args, kw))
        if self._raise_on == name:
            raise RuntimeError(f'{name} 일부러 실패')

    def names(self):
        return [c[0] for c in self.calls]

    def of(self, name):
        return [c for c in self.calls if c[0] == name]

    # ── cobot_common 이 내주는 함수들 ──
    def cfg(self):
        return CFG

    def io_node(self):
        log = types.SimpleNamespace(info=lambda m: None, warn=lambda m: None, error=lambda m: None)
        return types.SimpleNamespace(get_logger=lambda: log)

    def move_to(self, station, carrying, kind=None):
        # 🚨 kind 까지 적어 둔다 — 안 넘기면 실기에서 ValueError 가 난다(E8)
        self._note('move_to', station, carrying, kind)
        return self._up

    def move_rel(self, dx, dy, dz, frame, **kw):
        self._note('move_rel', dx, dy, dz, frame, **kw)      # vel_mm_s 등 키워드도 기록(직선 왕복 시험)

    def move_joint_rel(self, joint, delta_deg, *, time_s=None, carrying=True, **kw):
        self._note('move_joint_rel', joint, delta_deg, time_s, **kw)          # scale=False(E36 fast) 도 기록

    def joints(self):
        self._note('joints')
        return [0.0, 0.0, 90.0, 0.0, 90.0, 0.0]

    def move_joints_via(self, q_list, **kw):
        self._note('move_joints_via', [list(q) for q in q_list], **kw)

    def move_joints(self, q, vel, acc):
        self._note('move_joints', list(q), vel, acc)

    def force_off(self):
        self._note('force_off')

    def safe_retreat(self):
        self._note('safe_retreat')

    def grip_level(self, kind, level):
        # 🚨 진짜 grip_level 도 폭을 돌려주지만 sense 는 그 값을 쓰지 않는다
        #    (폭은 NORMAL 상태에서만 재야 비교가 되므로 grip_width 로 따로 잰다).
        #    그래서 여기서도 widths 를 소비하지 않는다 — widths 는 grip_width 순서 그대로다.
        self._note('grip_level', kind, level)
        return 2.0

    def grip_width(self):
        self._note('grip_width')
        return self._widths.pop(0) if self._widths else 2.0

    def weigh(self, n):
        self._note('weigh', n)
        return self._weights.pop(0) if self._weights else 180.0


@pytest.fixture
def rec(monkeypatch):
    r = Rec()
    _install(monkeypatch, r)
    return r


def _install(monkeypatch, r):
    """가짜 cobot_common 을 끼우고 sense 를 다시 읽어 들인다."""
    fake = types.ModuleType('cobot_common')
    for name in ('cfg', 'io_node', 'move_to', 'move_rel', 'move_joint_rel', 'joints', 'move_joints_via', 'move_joints',
                 'force_off', 'safe_retreat', 'grip_level', 'grip_width', 'weigh'):
        setattr(fake, name, getattr(r, name))
    # 🚨 sense 가 "삼키지 않고 위로 올릴" 예외 클래스 — **진짜 클래스**를 그대로 넣는다.
    #    가짜로 만들면 sense 가 잡는 클래스와 시험이 던지는 클래스가 달라져 시험이 거짓으로 통과한다.
    from cobot_common.motion import MotionHalted, MoveIncomplete
    fake.MoveIncomplete, fake.MotionHalted = MoveIncomplete, MotionHalted
    monkeypatch.setitem(sys.modules, 'cobot_common', fake)
    # 🚨 시험 사이에 가짜에 묶인 모듈이 남지 않게 되돌린다(L6)
    monkeypatch.delitem(sys.modules, 'f2_sense_flow.sense', raising=False)
    import importlib
    mod = importlib.import_module('f2_sense_flow.sense')
    monkeypatch.setattr(mod.time, 'sleep', lambda s: r._note('sleep', s))
    return mod


def _sense(monkeypatch, r):
    return _install(monkeypatch, r)


# ────────────────────────────────── weigh
def test_weigh_subtracts_empty_container(monkeypatch):
    """🔑 weigh 는 '측정값' 이 아니라 **잔반 무게**(측정값 − 빈 용기)를 돌려준다.

    이 함수가 kind 를 받는 이유가 빈 용기 기준값을 고르기 위해서다(SDD §5.3).
    로봇 하중 옵셋(V-02 의 +42~45 g)은 두 값을 같은 경로로 재면 상쇄된다.
    """
    r = Rec(weights=[223.0])                   # 그릇 180 + 잔반 43
    s = _sense(monkeypatch, r)
    out = s.weigh('BOWL')
    assert out.ok and out.code == OK
    assert out.weight_g == pytest.approx(43.0)


def test_weigh_goes_down_remaining_height(monkeypatch):
    """🚨 move_to 는 상공까지만 간다 — 남은 높이만큼 더 내려가야 티칭 자세다(SDD §5.3)."""
    r = Rec(weights=[180.0], up=35.0)
    s = _sense(monkeypatch, r)
    s.weigh('BOWL')
    assert ('move_to', ('WEIGH', True, 'BOWL'), {}) in r.calls
    assert ('move_rel', (0.0, 0.0, -35.0, 'BASE'), {}) in r.calls


def test_weigh_does_not_move_when_already_there(monkeypatch):
    """남은 높이가 0 이면 쓸데없이 움직이지 않는다."""
    r = Rec(weights=[180.0], up=0.0)
    s = _sense(monkeypatch, r)
    s.weigh('BOWL')
    assert not r.of('move_rel')


def test_weigh_uses_configured_sample_count(monkeypatch):
    r = Rec(weights=[180.0])
    s = _sense(monkeypatch, r)
    s.weigh('BOWL')
    assert r.of('weigh')[0][1] == (5,)         # params.yaml 의 weigh_samples


def test_weigh_exception_becomes_robot_error(monkeypatch):
    """🚨 기능 함수는 예외를 밖으로 내보내지 않는다."""
    r = Rec(weights=[180.0], raise_on='move_to')
    s = _sense(monkeypatch, r)
    out = s.weigh('BOWL')
    assert not out.ok and out.code == ROBOT_ERROR


def test_weigh_missing_config_is_robot_error_not_crash(monkeypatch):
    """설정이 비어 있으면 **조용히 기본값으로 돌지 않고** 실패로 알린다."""
    r = Rec(weights=[180.0])
    s = _sense(monkeypatch, r)
    monkeypatch.setitem(CFG['f2'], 'empty_weight_g', None)
    try:
        out = s.weigh('BOWL')
        assert not out.ok and out.code == ROBOT_ERROR
    finally:
        CFG['f2']['empty_weight_g'] = {'BOWL': 180.0, 'CUP': 120.0}


# ────────────────────────────────── leftover_loop
def test_leftover_passes_when_under_threshold(monkeypatch):
    """임계 미만이면 털지 않고 통과한다(본세척은 식기세척기 담당)."""
    r = Rec(weights=[210.0])                   # 잔반 30 g < 50
    s = _sense(monkeypatch, r)
    out = s.leftover_loop('BOWL', 2)
    assert out.ok and out.rounds == 0
    assert out.weight_before_g == pytest.approx(30.0)
    assert not r.of('move_joint_rel'), '털지 않아야 한다'


def test_leftover_shakes_until_clean(monkeypatch):
    """넘으면 털고 다시 잰다 — 깨끗해지면 거기서 멈춘다."""
    r = Rec(weights=[280.0, 190.0])            # 100 g → (털기) → 10 g
    s = _sense(monkeypatch, r)
    out = s.leftover_loop('BOWL', 2)
    assert out.ok and out.rounds == 1
    assert out.weight_before_g == pytest.approx(100.0)
    assert out.weight_after_g == pytest.approx(10.0)


def test_leftover_gives_up_after_max_rounds(monkeypatch):
    """계속 넘으면 LEFTOVER_REMAIN — flow 의 정책이 격리로 보낸다."""
    r = Rec(weights=[280.0, 280.0, 280.0])
    s = _sense(monkeypatch, r)
    out = s.leftover_loop('BOWL', 2)
    assert not out.ok and out.code == LEFTOVER_REMAIN
    assert out.rounds == 2
    assert len(r.of('weigh')) == 3, '처음 1회 + 털고 2회'


def test_leftover_stops_when_shake_fails(monkeypatch):
    """털기가 실패하면 더 돌지 않고 그 코드를 그대로 올린다."""
    r = Rec(weights=[280.0], widths=[2.0, 9.0], raise_on=None)
    s = _sense(monkeypatch, r)
    out = s.leftover_loop('BOWL', 2)
    assert not out.ok and out.code == GRIP_FAIL      # 폭이 7 mm 변함 → 미끄러짐
    assert len(r.of('weigh')) == 1, '실패한 뒤 다시 재지 않는다'


# ────────────────────────────────── shake
def test_shake_splits_period_into_segments(monkeypatch):
    """🚨 period_s 는 **한 주기** 다. time_s 는 **한 구간** 이라 나눠 써야 한다.

    가운데 → 끝 = period/4 · 끝 → 반대쪽 끝 = period/2 · 끝 → 가운데 = period/4
    그대로 넘기면 4배 느려진다.
    """
    r = Rec()
    s = _sense(monkeypatch, r)
    s.shake('WASTE', 1, 'BOWL')
    moves = [(c[1][0], c[1][1], c[1][2]) for c in r.of('move_joint_rel')]
    assert moves == [(5, +15.0, 0.15), (5, -30.0, 0.30), (5, +15.0, 0.15)]


def test_shake_tilts_first_then_returns(monkeypatch):
    """tilt_deg — 기울이기(+tilt) → 왕복 → 되돌리기(−tilt). 합은 0, 흔들기는 기울인 자세를 가운데로."""
    import copy
    cfg = copy.deepcopy(CFG)
    cfg['f2']['shake']['WASTE']['tilt_deg'] = 60.0
    cfg['f2']['limits']['max_tilt_deg'] = 100.0

    class R2(Rec):
        def cfg(self):
            return cfg
    r = R2()
    s = _sense(monkeypatch, r)
    assert s.shake('WASTE', 1, 'BOWL').ok
    moves = [(c[1][1], c[1][2]) for c in r.of('move_joint_rel')]
    assert moves == [(60.0, None), (15.0, 0.15), (-30.0, 0.30), (15.0, 0.15), (-60.0, None)]
    names = r.names()
    assert names.index('grip_level') < names.index('move_joint_rel'), '기울이기 전에 꽉 쥔다'
    assert [c for c in r.calls if c[0] == 'grip_level'][-1][1][1] == 'NORMAL'
    assert names.index('move_joint_rel') < len(names) - 1 - names[::-1].index('grip_level'), '되돌린 뒤에 힘을 푼다'


def test_shake_linear_axis_moves_with_move_rel(monkeypatch):
    """axis·amp_mm — BASE X 로 +amp → −2amp → +amp (mm) · 속도 = amp ÷ (period/4) · 관절은 안 돈다."""
    import copy
    cfg = copy.deepcopy(CFG)
    cfg['f2']['shake']['RINSE'] = {'axis': 'x', 'amp_mm': 20.0, 'period_s': 0.5}
    cfg['f2']['limits']['max_amp_mm'] = 60.0

    class R2(Rec):
        def cfg(self):
            return cfg
    r = R2()
    s = _sense(monkeypatch, r)
    assert s.shake('RINSE', 2, 'BOWL').ok
    assert not r.of('move_joint_rel')
    moves = [(c[1][0], c[1][1], c[1][2], c[1][3], c[2].get('vel_mm_s')) for c in r.of('move_rel')]
    # _goto 의 하강(up=0 이라 없음) 뒤 왕복만 — 2 주기 × 3 구간
    assert moves == [(20.0, 0.0, 0.0, 'BASE', 160.0), (-40.0, 0.0, 0.0, 'BASE', 160.0), (20.0, 0.0, 0.0, 'BASE', 160.0)] * 2
    assert sum(m[0] for m in moves) == pytest.approx(0.0)


def test_shake_params_per_kind(monkeypatch):
    """f2.shake.<mode> 에 BOWL/CUP 묶음이 있으면 kind 것을 쓴다 · 없으면 공용 · 한쪽만 있으면 KeyError(조용히 안 돈다)."""
    import copy
    cfg = copy.deepcopy(CFG)
    cfg['f2']['shake']['RINSE'] = {'BOWL': {'joint': 5, 'amp_deg': 10.0, 'period_s': 0.5},
                                   'CUP': {'joint': 5, 'amp_deg': 6.0, 'period_s': 0.6}}

    class R2(Rec):
        def cfg(self):
            return cfg
    r = R2()
    s = _sense(monkeypatch, r)
    assert s.shake('RINSE', 1, 'CUP').ok
    assert [c[1][1] for c in r.of('move_joint_rel')] == [6.0, -12.0, 6.0]        # 컵 값
    r2 = R2(); s = _sense(monkeypatch, r2)
    assert s.shake('RINSE', 1, 'BOWL').ok
    assert [c[1][1] for c in r2.of('move_joint_rel')] == [10.0, -20.0, 10.0]     # 그릇 값
    assert s.shake_params(cfg['f2'], 'WASTE', 'CUP') is cfg['f2']['shake']['WASTE']   # 공용 묶음은 그대로
    del cfg['f2']['shake']['RINSE']['CUP']
    r3 = R2(); s = _sense(monkeypatch, r3)
    out = s.shake('RINSE', 1, 'CUP')
    assert not out.ok and not r3.of('move_joint_rel'), '한쪽만 있으면 움직이기 전에 거절'


def test_shake_linear_passes_acc(monkeypatch):
    """acc_mm_s2 — 있으면 move_rel 에 그대로, 없으면 None(기본)."""
    import copy
    cfg = copy.deepcopy(CFG)
    cfg['f2']['shake']['RINSE'] = {'axis': 'x', 'amp_mm': 20.0, 'period_s': 0.5, 'acc_mm_s2': 800.0}
    cfg['f2']['limits']['max_amp_mm'] = 60.0

    class R2(Rec):
        def cfg(self):
            return cfg
    r = R2()
    s = _sense(monkeypatch, r)
    assert s.shake('RINSE', 1, 'BOWL').ok
    assert {c[2].get('acc_mm_s2') for c in r.of('move_rel')} == {800.0}


def test_shake_linear_returns_to_center_when_motion_fails(monkeypatch):
    import copy
    cfg = copy.deepcopy(CFG)
    cfg['f2']['shake']['RINSE'] = {'axis': 'y', 'amp_mm': 15.0, 'period_s': 0.5}
    cfg['f2']['limits']['max_amp_mm'] = 60.0
    calls = {'n': 0}

    class R2(Rec):
        def cfg(self):
            return cfg

        def move_rel(self, dx, dy, dz, frame, **kw):
            calls['n'] += 1
            if calls['n'] == 2:
                raise RuntimeError('두 번째 구간 일부러 실패')
            self._note('move_rel', dx, dy, dz, frame, **kw)
    r = R2()
    s = _sense(monkeypatch, r)
    assert not s.shake('RINSE', 1, 'BOWL').ok
    assert sum(c[1][1] for c in r.of('move_rel')) == pytest.approx(0.0), 'Y 가 밀린 채 끝났다'


def test_shake_linear_amp_over_limit_is_refused(monkeypatch):
    import copy
    cfg = copy.deepcopy(CFG)
    cfg['f2']['shake']['RINSE'] = {'axis': 'x', 'amp_mm': 80.0, 'period_s': 0.5}
    cfg['f2']['limits']['max_amp_mm'] = 60.0

    class R2(Rec):
        def cfg(self):
            return cfg
    r = R2()
    s = _sense(monkeypatch, r)
    out = s.shake('RINSE', 1, 'BOWL')
    assert not out.ok and not r.of('move_rel') and not r.of('move_joint_rel')


def test_shake_tilt_over_limit_is_refused(monkeypatch):
    import copy
    cfg = copy.deepcopy(CFG)
    cfg['f2']['shake']['WASTE']['tilt_deg'] = 120.0
    cfg['f2']['limits']['max_tilt_deg'] = 100.0

    class R2(Rec):
        def cfg(self):
            return cfg
    r = R2()
    s = _sense(monkeypatch, r)
    out = s.shake('WASTE', 1, 'BOWL')
    assert not out.ok and out.code == 'ROBOT_ERROR'
    assert not r.of('move_joint_rel'), '상한을 넘는 값이면 움직이기 전에 거절'


def test_shake_returns_to_center(monkeypatch):
    """🚨 한 주기가 끝나면 **가운데로 돌아온다** — 반복해도 자세가 밀리지 않는다."""
    r = Rec()
    s = _sense(monkeypatch, r)
    s.shake('WASTE', 4, 'BOWL')
    total = sum(c[1][1] for c in r.of('move_joint_rel'))
    assert total == pytest.approx(0.0)
    assert len(r.of('move_joint_rel')) == 12, '4 주기 × 3 구간'


def test_shake_turns_force_off_first(monkeypatch):
    """🚨 순응·힘제어가 켜져 있으면 관절 이동이 안 된다(2.1903) → 먼저 끈다."""
    r = Rec()
    s = _sense(monkeypatch, r)
    s.shake('WASTE', 1, 'BOWL')
    names = r.names()
    assert names.index('force_off') < names.index('move_joint_rel')


def test_shake_holds_then_restores(monkeypatch):
    """시작할 때 HOLD, 끝날 때 NORMAL (IRD §4)."""
    r = Rec()
    s = _sense(monkeypatch, r)
    s.shake('WASTE', 1, 'BOWL')
    levels = [c[1][1] for c in r.of('grip_level')]
    assert levels == ['HOLD', 'NORMAL']


def test_shake_restores_normal_even_when_motion_fails(monkeypatch):
    """🚨 **실패해도** NORMAL 로 되돌린다 — flow 는 '단계 사이는 NORMAL' 을 전제로 멈춘다(SDD §5.1)."""
    r = Rec(raise_on='move_joint_rel')
    s = _sense(monkeypatch, r)
    out = s.shake('WASTE', 1, 'BOWL')
    assert not out.ok and out.code == ROBOT_ERROR
    levels = [c[1][1] for c in r.of('grip_level')]
    assert levels == ['HOLD', 'NORMAL'], 'finally 가 되돌려야 한다'


def test_shake_detects_slip_by_width(monkeypatch):
    """전후 폭이 허용치보다 변하면 미끄러진 것으로 본다."""
    r = Rec(widths=[2.0, 5.0])                 # HOLD 뒤 2.0 → 흔든 뒤 5.0
    s = _sense(monkeypatch, r)
    out = s.shake('WASTE', 1, 'BOWL')
    assert not out.ok and out.code == GRIP_FAIL


def test_slip_tol_per_kind(monkeypatch):
    """실기: 컵 테두리는 HOLD 로 쥐면 1.0 mm 눌린다 → f2.slip_tol_mm 를 {BOWL: 1.0, CUP: 1.5} 처럼 종류별로 둘 수 있다.
    같은 1.0 mm 변화가 그릇에서는 GRIP_FAIL, 컵에서는 통과(놓친 컵은 다음 weigh 가 잡는다)."""
    r = Rec(widths=[12.2, 12.2, 11.2])             # 컵 98 g 3회차 실기 값 (첫 읽기는 사전 확인 · 그다음 HOLD 전 · NORMAL 뒤)
    s = _sense(monkeypatch, r)
    s.cc.cfg()['f2']['slip_tol_mm'] = {'BOWL': 1.0, 'CUP': 1.5}
    try:
        assert s.shake('WASTE', 1, 'CUP').ok
        assert s._slip_tol(s.cc.cfg()['f2'], 'BOWL') == pytest.approx(1.0)   # 그릇은 그대로 1.0
        assert s._slip_tol(s.cc.cfg()['f2'], 'CUP') == pytest.approx(1.5)
        assert s._slipped('x', 12.25, 11.2, 1.0) is True                       # 1.05 mm 변화 — 그릇 허용(1.0)에서는 미끄러짐(실기 1.00 은 부동소수점으로 살짝 넘어 걸렸다)
        assert s._slipped('x', 12.25, 11.2, 1.5) is False
        s.cc.cfg()['f2']['slip_tol_mm'] = 1.0                                   # 숫자도 그대로 받는다
        assert s._slip_tol(s.cc.cfg()['f2'], 'CUP') == pytest.approx(1.0)
    finally:
        s.cc.cfg()['f2']['slip_tol_mm'] = 1.0          # CFG 는 모듈 공용 — 되돌린다


def test_shake_small_width_change_is_ok(monkeypatch):
    """허용치 안이면 통과한다 — 폭 읽기는 원래 조금 흔들린다."""
    r = Rec(widths=[2.0, 2.4])
    s = _sense(monkeypatch, r)
    assert s.shake('WASTE', 1, 'BOWL').ok


def test_shake_zero_count_does_nothing(monkeypatch):
    r = Rec()
    s = _sense(monkeypatch, r)
    assert s.shake('WASTE', 0, 'BOWL').ok
    assert not r.of('move_joint_rel')


def test_shake_rinse_uses_its_own_preset(monkeypatch):
    """모드마다 다른 값을 쓴다 — 코드가 아니라 YAML 이 정한다."""
    r = Rec()
    s = _sense(monkeypatch, r)
    s.shake('RINSE', 1, 'CUP')
    spl = r.of('move_joints_via')[0]           # E36 RINSE: 스플라인 한 번 · J4 ±30 · 100 deg/s(4·30/1.2) · vel_scale 예외
    assert [q[3] for q in spl[1][0]] == [30.0, -30.0, 0.0] and spl[2] == {'vel_deg_s': pytest.approx(4 * 30 / 0.7), 'acc_deg_s2': 600.0, 'scale': False}
    assert not r.of('move_joint_rel')


# ────────────────────────────────── E36 물 털기 재설계 — 접근 높이에서 J4 좌우 · 빠르게
def test_shake_rinse_rises_then_goes_to_shake_station(monkeypatch):
    """E36: 담금 뒤 수조 안에서 부르면 ① move_to(RINSE) = 접근점(같은 x·y)까지 곧게 위로 ② move_to(RINSE_SHAKE) 관절 이동으로 털기 자세.
    **내려가지 않는다**(move_rel 없음) · 끝나도 거기 · HOLD → 흔들기 → NORMAL."""
    r = Rec(up=248.6)
    s = _sense(monkeypatch, r)
    assert s.shake('RINSE', 3, 'BOWL').ok
    names = r.names()
    tos = [c[1] for c in r.of('move_to')]
    assert tos == [('RINSE', True, 'BOWL'), ('RINSE_SHAKE', True, 'BOWL')], '접근점 먼저 · 그다음 털기 자세'
    assert not r.of('move_rel'), '티칭 자세로 내려가지 않는다'
    assert names.index('force_off') < names.index('move_to') < names.index('move_joints_via')
    levels = [c[1][1] for c in r.of('grip_level')]
    assert levels[0] == 'HOLD' and levels[-1] == 'NORMAL'


def test_shake_rinse_at_approach_variant(monkeypatch):
    """at: approach 도 남아 있다 — 접근점까지만 가고(move_to 1번) 내려가지 않는다."""
    import copy
    cfg = copy.deepcopy(CFG)
    cfg['f2']['shake']['RINSE'] = {'joint': 4, 'amp_deg': 20.0, 'period_s': 0.8, 'at': 'approach', 'fast': True}

    class R2(Rec):
        def cfg(self):
            return cfg
    r = R2(up=248.6)
    s = _sense(monkeypatch, r)
    assert s.shake('RINSE', 1, 'BOWL').ok
    assert [c[1] for c in r.of('move_to')] == [('RINSE', True, 'BOWL')] and not r.of('move_rel')


def test_shake_rinse_joint4_fast_three_cycles(monkeypatch):
    """E36(smooth): 4번 관절 ±30° 3회를 **스플라인 한 번**으로 — 점 7개(+30 −30 +30 −30 +30 −30 → 가운데 0) · 다른 관절 그대로 · vel_scale 예외 · 정지 없음."""
    r = Rec()
    s = _sense(monkeypatch, r)
    assert s.shake('RINSE', 3, 'BOWL').ok
    spl = r.of('move_joints_via')
    assert len(spl) == 1 and not r.of('move_joint_rel')
    pts = spl[0][1][0]
    assert [q[3] for q in pts] == [30.0, -30.0, 30.0, -30.0, 30.0, -30.0, 0.0]
    assert all(q[:3] == [0.0, 0.0, 90.0] and q[4:] == [90.0, 0.0] for q in pts), '다른 관절은 시작 자세 그대로'
    assert spl[0][2]['scale'] is False and spl[0][2]['vel_deg_s'] == pytest.approx(4 * 30 / 0.7) and spl[0][2]['acc_deg_s2'] == 600.0
    assert not r.of('move_joints'), '성공했으면 되돌리기 없음'


def test_shake_smooth_failure_returns_to_start_pose(monkeypatch):
    """스플라인 도중 실패 → 시작 관절 자세(q0)로 되돌린다(들고 가는 속도 30 % · vel_scale 은 move_joints 가 곱함) · NORMAL 복구 · ROBOT_ERROR."""
    r = Rec(raise_on='move_joints_via')
    s = _sense(monkeypatch, r)
    out = s.shake('RINSE', 3, 'BOWL')
    assert not out.ok and out.code == ROBOT_ERROR
    back = r.of('move_joints')
    assert len(back) == 1 and back[0][1] == ([0.0, 0.0, 90.0, 0.0, 90.0, 0.0], 30.0, 60.0)
    assert [c[1][1] for c in r.of('grip_level')][-1] == 'NORMAL'


def test_shake_fast_is_joint_only_and_at_is_validated(monkeypatch):
    """직선 왕복에 fast 를 주거나 at 이 이상하면 **움직이기 전에** 거절(ROBOT_ERROR)."""
    import copy
    for bad in ({'axis': 'x', 'amp_mm': 20.0, 'period_s': 0.5, 'fast': True},
                {'joint': 4, 'amp_deg': 20.0, 'period_s': 0.8, 'at': 'NOWHERE_STATION'}):
        cfg = copy.deepcopy(CFG)
        cfg['f2']['shake']['RINSE'] = bad
        cfg['f2']['limits']['max_amp_mm'] = 60.0

        class R2(Rec):
            def cfg(self):
                return cfg
        r = R2()
        s = _sense(monkeypatch, r)
        out = s.shake('RINSE', 1, 'BOWL')
        assert not out.ok and out.code == ROBOT_ERROR
        assert not r.of('move_to') and not r.of('move_joint_rel') and not r.of('move_rel')


def test_shake_and_dip_refuse_to_move_when_gripper_is_open(monkeypatch):
    """첫 폭이 100 mm 넘게 열려 있으면(빈손) shake·dip 은 **움직이기 전에** GRIP_FAIL — 실기(열린 채 담금 시작)."""
    for call in (lambda s: s.shake('RINSE', 3, 'CUP'), lambda s: s.dip('RINSE', 2, 'CUP')):
        r = Rec(widths=[110.6])
        s = _sense(monkeypatch, r)
        out = call(s)
        assert not out.ok and out.code == GRIP_FAIL
        assert not r.of('move_to') and not r.of('move_rel') and not r.of('move_joints_via') and not r.of('grip_level')


def test_shake_and_dip_refuse_to_move_when_gripper_is_closed_empty(monkeypatch):
    """폭 판정 프리셋(벽 집기)에서 폭 ≤ 영점 + 허용오차 = **꽉 닫힌 빈손** → 움직이기 전에 GRIP_FAIL(실기 10.5 mm).
    고정 폭 프리셋(grip_target_mm · 옆면 컵)은 이 판정을 하지 않는다."""
    for call in (lambda s: s.shake('RINSE', 3, 'BOWL'), lambda s: s.dip('RINSE', 2, 'BOWL')):
        r = RecCell(widths=[10.5])                          # BOWL: 영점 10.58 · tol 0.6 → 11.18 이하 = 빈손
        s = _sense(monkeypatch, r)
        out = call(s)
        assert not out.ok and out.code == GRIP_FAIL
        assert not r.of('move_to') and not r.of('move_rel') and not r.of('move_joints_via') and not r.of('grip_level')
    r = RecCell(widths=[76.0, 76.0, 76.0])                  # CUP(고정 폭 76 · E19): 판정 안 함 → 움직인다
    s = _sense(monkeypatch, r)
    assert s.dip('RINSE', 1, 'CUP').ok and r.of('move_to')


def test_shake_waste_unchanged_by_e36(monkeypatch):
    """잔반 털기(WASTE)는 그대로 — 티칭 자세까지 가고(_goto) J5 · vel_scale 적용(scale 키워드 없음)."""
    r = Rec(up=30.0)
    s = _sense(monkeypatch, r)
    assert s.shake('WASTE', 1, 'BOWL').ok
    assert r.of('move_rel')[0][1][2] == pytest.approx(-30.0), '접근점이 있으면 티칭 자세까지 내려간다'
    assert all(c[1][0] == 5 and c[2] == {} for c in r.of('move_joint_rel'))


def test_shake_unknown_mode_is_robot_error(monkeypatch):
    r = Rec()
    s = _sense(monkeypatch, r)
    out = s.shake('없는모드', 1, 'BOWL')
    assert not out.ok and out.code == ROBOT_ERROR


# ────────────────────────────────── dip
def test_dip_goes_down_and_comes_back_up(monkeypatch):
    """🚨 매번 **올라와서** 끝난다 — 용기가 수조에 걸린 채 다음 이동으로 가면 안 된다."""
    r = Rec()
    s = _sense(monkeypatch, r)
    s.dip('RINSE', 2, 'BOWL')
    rel = [(c[1][2]) for c in r.of('move_rel')]
    assert rel == [-60.0, +60.0, -60.0, +60.0]
    assert sum(rel) == pytest.approx(0.0)


def test_dip_holds_then_restores(monkeypatch):
    r = Rec()
    s = _sense(monkeypatch, r)
    s.dip('RINSE', 1, 'BOWL')
    assert [c[1][1] for c in r.of('grip_level')] == ['HOLD', 'NORMAL']


def test_dip_restores_normal_even_when_motion_fails(monkeypatch):
    r = Rec(raise_on='move_rel')
    s = _sense(monkeypatch, r)
    out = s.dip('RINSE', 1, 'BOWL')
    assert not out.ok and out.code == ROBOT_ERROR
    assert [c[1][1] for c in r.of('grip_level')] == ['HOLD', 'NORMAL']


def test_dip_detects_slip(monkeypatch):
    r = Rec(widths=[2.0, 6.0])
    s = _sense(monkeypatch, r)
    out = s.dip('RINSE', 1, 'BOWL')
    assert not out.ok and out.code == GRIP_FAIL


def test_dip_zero_count_does_nothing(monkeypatch):
    r = Rec()
    s = _sense(monkeypatch, r)
    assert s.dip('RINSE', 0, 'BOWL').ok
    assert not r.of('move_rel')


# ══════════════════════════════════════════════════════════════════
# 코드를 일부러 망가뜨려도 통과하던 구멍(변형 시험으로 찾음).
# 아래 시험들은 그 변형을 각각 잡는다 — 무엇을 잡는지 주석에 적어 둔다.
# ══════════════════════════════════════════════════════════════════

# ── 🚨 실패하면 안전 높이로 물러나는가
#    flow.call() 은 **예외가 올라올 때만** 후퇴한다. sense 는 예외를 Result 로 바꾸므로
#    여기서 직접 후퇴해야 한다 — 안 하면 용기를 수조 안에 담근 채 멈춘다.
def test_exception_retreats_to_safe_height(monkeypatch):
    r = Rec(raise_on='move_joint_rel')
    s = _sense(monkeypatch, r)
    out = s.shake('WASTE', 1, 'BOWL')
    assert not out.ok and out.code == ROBOT_ERROR
    assert r.of('safe_retreat'), '실패했는데 후퇴하지 않았다'


def test_slip_failure_also_retreats(monkeypatch):
    """미끄러짐은 예외가 아니라 정상 반환이다 — 이쪽도 후퇴해야 한다."""
    r = Rec(widths=[2.0, 8.0])
    s = _sense(monkeypatch, r)
    assert s.shake('WASTE', 1, 'BOWL').code == GRIP_FAIL
    assert r.of('safe_retreat')


def test_leftover_remain_retreats(monkeypatch):
    r = Rec(weights=[280.0, 280.0, 280.0])
    s = _sense(monkeypatch, r)
    assert s.leftover_loop('BOWL', 2).code == LEFTOVER_REMAIN
    assert r.of('safe_retreat')


# ── 🚨 실패해도 원래 자리로 되돌아오는가
def test_dip_comes_back_up_even_when_rise_fails(monkeypatch):
    """하강은 됐는데 상승이 실패하면 — finally 가 되올려야 한다.

    안 그러면 용기를 **수조 안 60 mm 아래**에 담근 채 멈추고, resume 하면
    그 자세에서 다음 용기를 집으러 간다.
    """
    calls = {'n': 0}

    class R2(Rec):
        def move_rel(self, dx, dy, dz, frame, **kw):
            calls['n'] += 1
            if calls['n'] == 2:                 # 올라오는 이동만 실패시킨다
                raise RuntimeError('상승 일부러 실패')   # 🚨 기록 전에 — 실제로 안 움직였다
            self._note('move_rel', dx, dy, dz, frame)

    r = R2()
    s = _sense(monkeypatch, r)
    out = s.dip('RINSE', 1, 'BOWL')
    assert not out.ok
    net = sum(c[1][2] for c in r.of('move_rel'))
    assert net == pytest.approx(0.0), f'수조 안에 {-net:.0f} mm 내려간 채 끝났다'


def test_shake_returns_to_center_even_when_motion_fails(monkeypatch):
    """도중에 실패해도 관절이 가운데로 돌아와야 한다 — 기울어진 채 다음 용기로 가면 안 된다."""
    calls = {'n': 0}

    class R2(Rec):
        def move_joint_rel(self, joint, delta_deg, *, time_s=None, carrying=True):
            calls['n'] += 1
            if calls['n'] == 2:
                raise RuntimeError('두 번째 구간 일부러 실패')   # 🚨 기록 전에
            self._note('move_joint_rel', joint, delta_deg, time_s)

    r = R2()
    s = _sense(monkeypatch, r)
    out = s.shake('WASTE', 1, 'BOWL')
    assert not out.ok
    net = sum(c[1][1] for c in r.of('move_joint_rel'))
    assert net == pytest.approx(0.0), f'J5 가 {net:+.0f}° 기울어진 채 끝났다'


# ── 🚨 어느 스테이션으로 가는가 (전에는 목적지를 바꿔도 통과했다)
def test_leftover_shakes_over_the_waste_bin(monkeypatch):
    """잔반은 **잔반통 위에서** 턴다 — 헹굼 수조 위에서 털면 잔반이 헹굼물에 떨어진다."""
    r = Rec(weights=[280.0, 190.0])
    s = _sense(monkeypatch, r)
    s.leftover_loop('BOWL', 2)
    assert ('move_to', ('WASTE', True, 'BOWL'), {}) in r.calls
    assert ('move_to', ('RINSE', True, 'BOWL'), {}) not in r.calls
    n_cycles = CFG['f2']['shake']['WASTE']['cycles']
    assert len(r.of('move_joint_rel')) == 3 * n_cycles, 'YAML 의 cycles 만큼 털어야 한다'


def test_shake_and_dip_go_to_their_station(monkeypatch):
    """전에는 _goto 를 지워도 25개가 통과했다 — 제자리에서 담그면 수조 밖에서 헛돈다."""
    r = Rec(up=25.0)
    s = _sense(monkeypatch, r)
    s.dip('RINSE', 1, 'BOWL')
    assert ('move_to', ('RINSE', True, 'BOWL'), {}) in r.calls
    assert r.of('move_rel')[0][1][2] == pytest.approx(-25.0), '남은 높이만큼 먼저 내려가야 한다'

    r2 = Rec()
    s2 = _sense(monkeypatch, r2)
    s2.shake('RINSE', 1, 'CUP')
    assert ('move_to', ('RINSE', True, 'CUP'), {}) in r2.calls


def test_every_move_passes_kind(monkeypatch):
    """🚨 세 함수 모두 move_to 에 kind 를 넘겨야 한다 (결정 E8).

    WEIGH·WASTE·RINSE 자세가 cell.yaml 에서 BOWL/CUP 으로 갈렸다. 안 넘기면 cc.move_to 가
    "골라야 하는데 안 줬다"로 ValueError 를 내고 **기능 셋이 통째로 멈춘다**.
    빠뜨리기 쉬운 자리라(인자가 선택형이다) 함수별로 못 박는다.
    """
    for call, kind in (
        (lambda s: s.weigh('BOWL'), 'BOWL'),
        (lambda s: s.shake('WASTE', 1, 'CUP'), 'CUP'),
        (lambda s: s.dip('RINSE', 1, 'BOWL'), 'BOWL'),
    ):
        r = Rec(weights=[180.0])
        call(_sense(monkeypatch, r))
        # weigh 가 먼저 HOME 을 거친다 — HOME 은 종류로 갈리지 않는 자리라 kind 가 없어도 된다
        moves = [c for c in r.of('move_to') if c[1][0] != 'HOME']
        assert moves, 'move_to 를 한 번은 불러야 한다'
        for c in moves:
            assert c[1][2] == kind, f'move_to 에 kind 가 빠졌다 — {c[1]}'


def test_moves_are_carrying(monkeypatch):
    """🚨 용기를 든 채 움직이므로 carrying=True — False 면 빈손 속도로 빨리 움직인다."""
    r = Rec(weights=[180.0])
    s = _sense(monkeypatch, r)
    s.weigh('BOWL')
    assert all(c[1][1] is True for c in r.of('move_to'))


# ── 🚨 미끄러짐 — 폭이 **줄어드는** 쪽 (실제 낙하 방향)
def test_slip_detected_when_width_shrinks(monkeypatch):
    """실제 낙하는 그리퍼가 닫히며 폭이 **줄어든다**(2 mm → 0). 늘어나는 쪽만 보면 못 잡는다."""
    r = Rec(widths=[2.0, 0.2])
    s = _sense(monkeypatch, r)
    assert s.shake('WASTE', 1, 'BOWL').code == GRIP_FAIL

    r2 = Rec(widths=[2.0, 0.1])
    s2 = _sense(monkeypatch, r2)
    assert s2.dip('RINSE', 1, 'BOWL').code == GRIP_FAIL


def test_slip_check_covers_both_force_changes(monkeypatch):
    """🚨 폭을 **HOLD 로 바꾸기 전**과 **NORMAL 로 되돌린 뒤**에 잰다.

    힘 전환은 드라이버상 '다시 잡기' 라서 그 순간에도 미끄러진다. 전환 사이에서만 재면
    두 번의 전환이 검사 밖에 남는다.
    """
    r = Rec(widths=[2.0, 2.0])
    s = _sense(monkeypatch, r)
    s.shake('WASTE', 1, 'BOWL')
    names = r.names()
    first_w = names.index('grip_width')
    first_level = names.index('grip_level')
    last_w = len(names) - 1 - names[::-1].index('grip_width')
    last_level = len(names) - 1 - names[::-1].index('grip_level')
    assert first_w < first_level, 'HOLD 로 바꾸기 전에 재야 한다'
    assert last_w > last_level, 'NORMAL 로 되돌린 뒤에 재야 한다'


# ── 🚨 순응 끄기 · 대기
def test_all_three_turn_force_off_before_moving(monkeypatch):
    """순응이 켜진 채면 관절 이동이 거부되고(2.1903), 직교 이동도 힘제어가 눌러 안 간다."""
    for fn, args in (('weigh', ('BOWL',)), ('shake', ('WASTE', 1, 'BOWL')),
                     ('dip', ('RINSE', 1, 'BOWL'))):
        r = Rec(weights=[180.0])
        s = _sense(monkeypatch, r)
        getattr(s, fn)(*args)
        names = r.names()
        assert 'force_off' in names, f'{fn} 이 force_off 를 안 부른다'
        assert names.index('force_off') < names.index('move_to'), f'{fn}: 이동보다 먼저여야 한다'


def test_weigh_waits_before_measuring(monkeypatch):
    """🚨 움직이는 중에 재면 가속도가 섞인다(SDD §5.3) — 설정한 시간만큼 기다려야 한다."""
    r = Rec(weights=[180.0])
    s = _sense(monkeypatch, r)
    s.weigh('BOWL')
    slept = [c[1][0] for c in r.of('sleep')]
    assert CFG['f2']['weigh_settle_s'] in slept
    names = r.names()
    assert names.index('sleep') < names.index('weigh'), '재기 전에 기다려야 한다'


def test_dip_holds_at_the_bottom(monkeypatch):
    r = Rec()
    s = _sense(monkeypatch, r)
    s.dip('RINSE', 1, 'BOWL')
    assert CFG['f2']['dip']['RINSE']['hold_s'] in [c[1][0] for c in r.of('sleep')]


# ── 🚨 빈손 감지
def test_weigh_detects_lost_container(monkeypatch):
    """용기를 놓치면 하중이 옵셋만 남아 잔반이 크게 음수가 된다 — 그냥 통과시키면
    빈 그리퍼로 세제·닦기까지 전 공정을 돈다. F2 가 이걸 잡을 수 있는 유일한 자리다."""
    r = Rec(weights=[43.0])                     # 빈 용기 180 없이 옵셋만 → net = -137
    s = _sense(monkeypatch, r)
    out = s.weigh('BOWL')
    assert not out.ok and out.code == GRIP_FAIL
    assert r.of('safe_retreat')


def test_weigh_small_negative_is_still_ok(monkeypatch):
    """조금 음수인 것은 측정 흔들림이다 — 하한 안이면 통과."""
    r = Rec(weights=[170.0])                    # net = -10, 하한 -30 안
    s = _sense(monkeypatch, r)
    assert s.weigh('BOWL').ok


# ── 🚨 오타 방어 (자릿수 실수가 그대로 로봇 명령이 되면 안 된다)
def test_absurd_amplitude_is_refused_before_moving(monkeypatch):
    """amp_deg 를 15 대신 150 으로 적으면 용기를 쥔 채 300° 를 왕복한다."""
    r = Rec()
    s = _sense(monkeypatch, r)
    monkeypatch.setitem(CFG['f2']['shake']['WASTE'], 'amp_deg', 150.0)
    out = s.shake('WASTE', 1, 'BOWL')
    assert not out.ok and out.code == ROBOT_ERROR
    assert not r.of('move_joint_rel'), '움직이기 전에 거절해야 한다'


def test_absurd_depth_is_refused_before_moving(monkeypatch):
    r = Rec()
    s = _sense(monkeypatch, r)
    monkeypatch.setitem(CFG['f2']['dip']['RINSE'], 'depth_mm', 600.0)
    out = s.dip('RINSE', 1, 'BOWL')
    assert not out.ok and out.code == ROBOT_ERROR
    assert not r.of('move_rel')


def test_negative_depth_is_refused(monkeypatch):
    """음수 깊이는 위로 갔다 내려온다 — 순서가 뒤집힌다."""
    r = Rec()
    s = _sense(monkeypatch, r)
    monkeypatch.setitem(CFG['f2']['dip']['RINSE'], 'depth_mm', -60.0)
    assert s.dip('RINSE', 1, 'BOWL').code == ROBOT_ERROR
    assert not r.of('move_rel')


# ── 🚨 진단이 거짓말하지 않는가
def test_rounds_counts_only_finished_rounds(monkeypatch):
    """털기가 실패한 회차는 세지 않는다 — 'N회 털었는데 그대로' 는 거짓 보고다.

    rounds 는 FlowEvent 로 HMI·기록에 나가는 값이라 시연에서 그대로 보인다.
    """
    r = Rec(weights=[280.0], widths=[2.0, 9.0])      # 1회차 털기에서 미끄러짐
    s = _sense(monkeypatch, r)
    out = s.leftover_loop('BOWL', 2)
    assert out.code == GRIP_FAIL
    assert out.rounds == 0, '한 번도 못 털었으면 0 이어야 한다'


# ── 🚨 이동이 도중에 선 예외는 삼키지 않는다 (SDD §7)
def test_move_incomplete_is_not_swallowed(monkeypatch):
    """MoveIncomplete = 이동이 도중에 섰다 → **로봇이 어디 있는지 모른다.**

    여기서 Result 로 바꾸면 flow 가 평범한 실패로 보고 **재시도하거나 이어서 내려간다.**
    그러면 안 되므로 위로 그대로 올린다 — flow.call() 이 받아 ROBOT_ERROR(그 자리 정지)로 맺는다.
    """
    from cobot_common.motion import MoveIncomplete

    class Boom(Rec):
        def move_to(self, station, carrying, kind=None):
            self._note('move_to', station, carrying, kind)
            raise MoveIncomplete('목표 6 mm 앞에서 섰다')

    for call in (lambda s: s.weigh('BOWL'),
                 lambda s: s.shake('WASTE', 1, 'BOWL'),
                 lambda s: s.dip('RINSE', 1, 'BOWL')):
        r = Boom(weights=[180.0])
        s = _sense(monkeypatch, r)
        with pytest.raises(MoveIncomplete):
            call(s)
        assert not r.of('safe_retreat'), '위치를 모르는데 후퇴하면 안 된다'


# ── 🚨 잔반통(뒤) ↔ 앞쪽 사이는 HOME 을 거친다 (결정 E15)
def test_leftover_goes_via_home_between_scale_and_waste_bin(monkeypatch):
    """잔반통 그릇 자세가 로봇 **뒤쪽**으로 옮겨졌다(앞쪽은 팔이 펴진 특이점이라 실기에서 케이블이 꼬였다).

    저울·스펀지 홈·반납 구역은 **앞**이라, 앞뒤를 곧장 오가면 로봇 몸통을 가로지른다.
    E7 로 안전 높이 경유까지 없어져 더 그렇다 → 사이마다 HOME 을 거친다.
    """
    r = Rec(weights=[280.0, 190.0])            # 잔반 100 g → 털고 → 10 g
    s = _sense(monkeypatch, r)
    s.leftover_loop('BOWL', 2)
    stations = [c[1][0] for c in r.of('move_to')]
    assert stations == ['HOME', 'WEIGH', 'HOME', 'WASTE', 'HOME', 'WEIGH'], stations


def test_weigh_goes_via_home_first(monkeypatch):
    """실기: 무게는 **항상 HOME 을 거쳐** WEIGH 로 내려와 잰다.

    같은 그릇을 같은 WEIGH 자세에서 재도, 집어 올린 자리에서 바로 재면 −113 g · HOME 을 거쳐 재면 −23 g
    (1분 간격 · 90 g 차). 관절 토크로 힘을 추정하는 로봇이라 마지막 이동 이력이 값에 남는다.
    기준값 도구(rig_f2 empty)·털기 뒤 재측정은 원래 HOME 을 거쳤으므로 첫 측정만 이 길을 안 타고 있었다.
    """
    r = Rec(weights=[180.0])
    s = _sense(monkeypatch, r)
    s.weigh('BOWL')
    stations = [c[1][0] for c in r.of('move_to')]
    assert stations == ['HOME', 'WEIGH'], stations


# ────────────────────────────────── 🔑 놓쳤는지는 **폭**이 답한다 (영점 이동)
_CELL_PRESETS = {'cell': {'presets': {
    'BOWL': {'grip_zero_mm': 10.58, 'grip_width_mm': 2.15, 'width_tol_mm': 0.6},
    'CUP': {'grip_zero_mm': 10.58, 'grip_target_mm': 76.0, 'grip_width_mm': 65.42, 'width_tol_mm': 10.0},
}}}


class RecCell(Rec):
    """cell.presets 까지 들고 있는 가짜 — 폭 판정을 켠다."""

    def cfg(self):
        c = dict(CFG)
        c['cell'] = {**CFG.get('cell', {}), **_CELL_PRESETS['cell']}   # stations·motion 은 CFG 것 + presets 덧붙임(깊은 합치기)
        return c


def test_weigh_low_but_width_says_held_is_not_a_drop(monkeypatch):
    """🚨 무게만 이상하고 **폭으로는 쥐고 있으면** 놓친 게 아니다 — 빈 용기 기준값이 낡은 것이다.

    실기: 빈 그릇 기준값 −12 g 를 잰 그 자세에서 −117.5 g 이 읽혔다(그릇 자체는 47 g).
    영점이 통째로 밀린 것인데 옛 코드는 GRIP_FAIL 로 막아 통합이 멈췄다.
    """
    r = RecCell(weights=[-100.0], widths=[12.90])        # 12.90 − 10.58 = 2.32 ≈ 2.15 ± 0.6 → 쥐고 있다
    s = _sense(monkeypatch, r)
    out = s.weigh('BOWL')
    assert out.ok and out.code == OK, '쥐고 있으면 막지 않는다'
    assert out.weight_g == pytest.approx(-280.0)         # −100 − 180(기준값) — 값은 그대로 돌려준다


def test_weigh_low_and_width_says_empty_is_a_drop(monkeypatch):
    """폭이 빈손이면 진짜로 놓친 것 — GRIP_FAIL 로 막는다."""
    r = RecCell(weights=[-100.0], widths=[10.58])        # 영점까지 닫혔다 → 빈손
    s = _sense(monkeypatch, r)
    out = s.weigh('BOWL')
    assert not out.ok and out.code == GRIP_FAIL


def test_weigh_low_falls_back_to_weight_when_width_cannot_judge(monkeypatch):
    """컵은 고정 폭(E19)이라 빈손과 구분이 안 된다 → 예전대로 무게만 보고 막는다."""
    r = RecCell(weights=[-100.0], widths=[76.0])
    s = _sense(monkeypatch, r)
    out = s.weigh('CUP')
    assert not out.ok and out.code == GRIP_FAIL

