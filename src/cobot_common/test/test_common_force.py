# -*- coding: utf-8 -*-
"""힘 함수(force.py) 시험 — 로봇·ROS 없이 가짜 두산 모듈로 호출 순서와 안전 동작을 본다.

    python3 -m pytest -q src/cobot_common/test/test_common_force.py

실제 힘 값은 Virtual 에 없으므로 실기(V-03)에서 본다. 여기서는 순서·판정·예외·설정 누락만.
"""
import copy

import pytest

from cobot_common import force, motion

CFG = {'cell': {
    'limits': {'safe_z_mm': 300.0, 'timeout_s': 10.0, 'vel_carry_pct': 30},
    'motion': {'vel_tcp_max_mm_s': 400.0, 'acc_tcp_max_mm_s2': 800.0,           # move_rel 속도 상한 (motion.py)
               'vel_joint_max_deg_s': 100.0, 'acc_joint_max_deg_s2': 200.0,
               'move_timeout_s': 30.0},                                                # V-24: 이동 상한 시간 (motion.py)
    'force': {'compliance_stx': [3000, 3000, 500, 200, 200, 200], 'contact_step_mm': 2.0,
              'contact_vel_mm_s': 10.0, 'contact_acc_mm_s2': 50.0, 'retreat_vel_mm_s': 50.0,
              'retreat_acc_mm_s2': 100.0, 'force_max_n': 20.0, 'search_y_period_ratio': 2.0},
}}


class FakeDsr:
    """DSR_ROBOT2 흉내. 반환 규칙은 설치본과 같다: 성공 0 / 실패 -1, check_force_condition 은 만족 0 / 아니면 -1."""
    DR_BASE, DR_TOOL = 0, 1
    DR_AXIS_X, DR_AXIS_Y, DR_AXIS_Z = 0, 1, 2
    DR_COND_NONE = -10000
    DR_FC_MOD_ABS, DR_FC_MOD_REL = 0, 1
    DR_MV_MOD_ABS, DR_MV_MOD_REL = 0, 1

    def __init__(self, z=400.0, surface_z=None, k_n_per_mm=2.0, fail=()):
        self.calls = []
        self.pos = [100.0, 50.0, z, 0.0, 180.0, 0.0]
        self.surface_z = surface_z          # 이 높이 아래로 내려가면 힘이 생긴다 (None 이면 바닥 없음)
        self.k = k_n_per_mm
        self.fail = set(fail)

    def _r(self, name, *a, **kw):
        self.calls.append(name)
        return -1 if name in self.fail else 0

    def mwait(self, time=0):
        return self._r('mwait')

    def task_compliance_ctrl(self, stx, time=0):
        self.stx = stx
        return self._r('task_compliance_ctrl')

    def set_desired_force(self, fd, dir, time=0, mod=0):
        self.fd, self.dir, self.fmod = fd, dir, mod
        return self._r('set_desired_force')

    def release_force(self, time=0):
        return self._r('release_force')

    def release_compliance_ctrl(self):
        return self._r('release_compliance_ctrl')

    offset_fz = 0.0                     # 공중에서도 잡히는 힘 (툴 무게 설정에 없는 무게)

    def _fz(self):
        if self.surface_z is None or self.pos[2] >= self.surface_z:
            return self.offset_fz
        return self.offset_fz - (self.surface_z - self.pos[2]) * self.k

    def get_tool_force(self, ref=None):
        self.calls.append('get_tool_force')
        return -1 if 'get_tool_force' in self.fail else [0.0, 0.0, self._fz(), 0.0, 0.0, 0.0]

    def check_force_condition(self, axis, min=-10000, max=-10000, ref=None):
        self.calls.append('check_force_condition')
        f = abs(self._fz())
        ok = (min == self.DR_COND_NONE or f >= min) and (max == self.DR_COND_NONE or f <= max)
        return 0 if ok else -1

    def get_current_posx(self, ref=None):
        return list(self.pos), 2

    def movel(self, pos, vel=None, acc=None, time=None, radius=None, ref=None, mod=0):
        self.last_movel = dict(pos=list(pos), vel=vel, acc=acc, ref=ref, mod=mod)
        if mod == self.DR_MV_MOD_REL:
            self.pos = [p + dp for p, dp in zip(self.pos, pos)]
        else:
            self.pos = list(pos)
        return self._r('movel')

    def amovel(self, *a, **kw):                     # V-24: motion.py 는 비동기 이동을 보내고 check_motion 으로 끝을 기다린다
        return self.movel(*a, **kw)                 #   가짜는 보내는 즉시 도착한 것으로 친다 → 아래 check_motion 이 바로 0

    def check_motion(self):
        if self.starting:                           # 비동기 모션을 막 보낸 뒤 한 번은 '도는 중' 으로 보인다(실기처럼)
            self.starting -= 1
            return 2
        return self.motion                          # 0 = 끝남

    motion = 0
    starting = 0
    never_starts = False                            # True 면 명령을 받고도 안 움직인다 (실기 증상 재현용)

    def amove_spiral(self, rev=None, rmax=None, lmax=None, vel=None, acc=None, time=None, axis=None, ref=None):
        self.spiral = dict(rev=rev, rmax=rmax, lmax=lmax, vel=vel, acc=acc, time=time, axis=axis, ref=ref)
        self.starting = 0 if self.never_starts else 1
        return self._r('amove_spiral')

    def movec(self, mid, end, vel=None, acc=None, radius=None, ref=None, mod=0):
        self.arc = dict(mid=list(mid), end=list(end), vel=vel, acc=acc, radius=radius, ref=ref, mod=mod)
        self.pos = list(end)
        return self._r('movec')

    def move_periodic(self, amp, period, atime=None, repeat=None, ref=None):
        self.periodic = dict(amp=amp, period=period, repeat=repeat, ref=ref)
        return self._r('move_periodic')


@pytest.fixture
def robot(monkeypatch):
    """가짜 로봇 + 설정을 force·motion 모듈에 끼운다(이동은 진짜 motion.move_rel 을 거친다)."""
    state = {}

    def make(cfg=CFG, **kw):
        d = FakeDsr(**kw)
        monkeypatch.setattr(force, 'dsr', lambda: d)
        monkeypatch.setattr(force, 'cfg', lambda: cfg)
        monkeypatch.setattr(motion, 'dsr', lambda: d)
        monkeypatch.setattr(motion, 'cfg', lambda: cfg)
        state['d'] = d
        return d

    force._state.update(compliance=False, force=False, limit=None)
    yield make
    force._state.update(compliance=False, force=False, limit=None)


def test_force_on_order_and_direction(robot):
    d = robot()
    force.force_on('z', 4.0, 10.0)
    assert d.calls == ['mwait', 'task_compliance_ctrl', 'set_desired_force']     # 이동 끝 → 순응 → 힘
    assert d.fd == [0.0, 0.0, -4.0, 0.0, 0.0, 0.0] and d.dir == [0, 0, 1, 0, 0, 0]   # −Z 로 누름
    assert d.fmod == d.DR_FC_MOD_ABS and d.stx == CFG['cell']['force']['compliance_stx']   # 목표 = 실제 누르는 힘


@pytest.mark.parametrize('target,limit', [(10.0, 10.0), (12.0, 10.0), (0.0, 10.0), (4.0, 25.0), (-1.0, 10.0)])
def test_force_on_rejects_bad_values_without_moving(robot, target, limit):
    d = robot()
    with pytest.raises(ValueError):
        force.force_on('z', target, limit)
    assert d.calls == []


def test_force_on_rolls_back_when_force_fails(robot):
    d = robot(fail={'set_desired_force'})
    with pytest.raises(RuntimeError):
        force.force_on('z', 4.0, 10.0)
    assert d.calls[-1] == 'release_compliance_ctrl' and not force._state['compliance']


def test_force_off_order_and_idempotent(robot):
    d = robot()
    force.force_on('z', 4.0, 10.0)
    d.calls.clear()
    force.force_off()
    assert d.calls == ['release_force', 'release_compliance_ctrl']              # 힘 해제 → 순응 해제
    d.calls.clear()
    force.force_off()
    assert d.calls == []                                                        # 켜진 게 없으면 아무것도 안 부름


def test_force_reached_uses_zero_as_true(robot):
    d = robot(z=100.0, surface_z=110.0)                                         # 10 mm 눌림 → |Fz| 20 N
    assert force.force_reached('z', min=5.0) is True                            # 설치본 반환 0 → True (TS-01 D)
    assert force.force_reached('z', max=5.0) is False                           # 반환 -1 → False
    with pytest.raises(ValueError):
        force.force_reached('z')
    with pytest.raises(ValueError):
        force.force_reached('z', min=-1.0)
    assert d.calls.count('check_force_condition') == 2


def test_contact_down_stops_at_contact(robot):
    d = robot(z=400.0, surface_z=390.0)
    depth, f = force.contact_down(max_depth=40.0, limit=3.0)
    assert 10.0 <= depth < 40.0 and f >= 3.0                                    # 표면(10 mm) 지나 한두 단계 안에서 멈춤
    assert d.calls[:3] == ['mwait', 'get_tool_force', 'task_compliance_ctrl']    # 기준 힘을 재고 → 순응 켜고 내려간다
    assert d.calls[-1] == 'release_compliance_ctrl' and not force._state['compliance']
    assert d.last_movel['mod'] == d.DR_MV_MOD_REL and d.last_movel['ref'] == d.DR_BASE


def test_contact_down_ignores_tool_weight_offset(robot):
    """공중에서도 Fz 가 나오는 툴(솔·수세미 무게)이라도 내려가기 전에 접촉으로 보지 않는다 (실기)."""
    d = robot(z=400.0, surface_z=395.0, k_n_per_mm=1.0)
    d.offset_fz = -5.0                                                          # 공중에서도 |Fz| 5 N
    depth, f = force.contact_down(max_depth=20.0, limit=3.0)
    assert depth >= 5.0 and f == pytest.approx(3.0, abs=1.5)                    # 표면(5 mm)을 지나서야 멈춘다


def test_contact_down_stops_at_max_depth_without_surface(robot):
    d = robot(z=400.0, surface_z=None)
    depth, f = force.contact_down(max_depth=15.0, limit=3.0)
    assert depth == pytest.approx(15.0) and f == 0.0                            # 마지막 단계는 남은 깊이만큼
    assert d.pos[2] == pytest.approx(385.0)


def test_contact_down_force_over_max_raises_and_releases(robot):
    d = robot(z=400.0, surface_z=390.0, k_n_per_mm=50.0)                        # 단단한 면: 2 mm 에 100 N
    with pytest.raises(force.ForceLimitError):
        force.contact_down(max_depth=40.0, limit=15.0)
    assert d.calls[-1] == 'release_compliance_ctrl'


def test_contact_down_timeout(robot, monkeypatch):
    robot(z=400.0, surface_z=None)
    ticks = iter(range(0, 1000, 20))                                            # 한 번 볼 때마다 20 s 흐름
    monkeypatch.setattr(force.time, 'monotonic', lambda: next(ticks))
    with pytest.raises(force.MotionTimeout):
        force.contact_down(max_depth=40.0, limit=3.0)
    assert not force._state['compliance']


def test_missing_config_refuses_before_moving(robot):
    cfg = copy.deepcopy(CFG)
    del cfg['cell']['force']['contact_step_mm']
    d = robot(cfg=cfg)
    with pytest.raises(KeyError, match='contact_step_mm'):
        force.contact_down(max_depth=10.0, limit=3.0)
    assert 'movel' not in d.calls and 'task_compliance_ctrl' not in d.calls


def test_null_config_value_refuses_before_moving(robot):
    cfg = copy.deepcopy(CFG)
    cfg['cell']['limits']['safe_z_mm'] = None                                  # INF-04 골격처럼 키는 있는데 비어 있음
    d = robot(cfg=cfg, z=150.0)
    with pytest.raises(KeyError, match='safe_z_mm'):
        force.safe_retreat()
    assert 'movel' not in d.calls


def test_vel_scale_slows_contact_retreat_and_search(robot):
    cfg = copy.deepcopy(CFG)
    cfg['run'] = {'vel_scale': 0.3}                                             # 첫 실기 0.3
    d = robot(cfg=cfg, z=150.0)
    force.contact_down(max_depth=4.0, limit=3.0)
    assert d.last_movel['vel'] == pytest.approx(10.0 * 0.3)
    force.safe_retreat()
    assert d.last_movel['vel'] == pytest.approx(50.0 * 0.3)
    force.periodic_search(amp=3.0, period=0.8, duration=6.0)
    assert d.periodic['period'][:2] == [pytest.approx(0.8 / 0.3), pytest.approx(1.6 / 0.3)]
    assert d.periodic['amp'][:2] == [3.0, 3.0]                                  # 진폭은 그대로


def test_safe_retreat_goes_straight_up_to_safe_z(robot):
    d = robot(z=150.0)
    force.force_on('z', 4.0, 10.0)
    force.safe_retreat()
    assert d.calls[-3:] == ['release_force', 'release_compliance_ctrl', 'movel']  # 끄고 → 올린다
    assert d.last_movel['pos'] == [0.0, 0.0, 150.0, 0.0, 0.0, 0.0]              # move_rel: Z 만 +150 (BASE 상대)
    assert d.pos[:3] == [100.0, 50.0, 300.0]                                    # X·Y 그대로, Z 는 safe_z
    assert d.last_movel['mod'] == d.DR_MV_MOD_REL and d.last_movel['ref'] == d.DR_BASE
    assert d.last_movel['vel'] == 50.0


def test_move_speed_capped_by_motion_limit(robot):
    cfg = copy.deepcopy(CFG)
    cfg['cell']['force']['retreat_vel_mm_s'] = 1000.0                          # 설정 실수로 너무 빠르게
    d = robot(cfg=cfg, z=150.0)
    force.safe_retreat()
    assert d.last_movel['vel'] == 400.0                                         # cell.motion 100 % 기준을 넘지 못한다


def test_missing_motion_config_does_not_move(robot):
    cfg = copy.deepcopy(CFG)
    cfg['cell']['motion']['vel_tcp_max_mm_s'] = None                            # 골격처럼 비어 있음
    d = robot(cfg=cfg, z=400.0, surface_z=None)
    with pytest.raises(KeyError, match='vel_tcp_max_mm_s'):
        force.contact_down(max_depth=10.0, limit=3.0)
    assert 'movel' not in d.calls and not force._state['compliance']           # 움직이지 않고 순응도 꺼짐


def test_safe_retreat_does_nothing_above_safe_z(robot):
    d = robot(z=350.0)
    force.safe_retreat()
    assert 'movel' not in d.calls


def test_periodic_search_axes_and_repeat(robot):
    d = robot()
    force.periodic_search(amp=3.0, period=0.8, duration=6.0)
    p = d.periodic
    assert p['amp'] == [3.0, 3.0, 0.0, 0.0, 0.0, 0.0] and p['ref'] == d.DR_TOOL
    assert p['period'][:2] == [0.8, pytest.approx(1.6)] and p['repeat'] == 3   # 6 s // 1.6 s


def test_force_off_tries_both_even_if_first_fails(robot):
    """release_force 가 실패해도 순응 해제까지 시도한다 — 안 그러면 safe_retreat 의 후퇴가 막힌다."""
    d = robot(fail={'release_force'})
    force.force_on('z', 4.0, 10.0)
    d.calls.clear()
    with pytest.raises(RuntimeError):
        force.force_off()
    assert d.calls == ['release_force', 'release_compliance_ctrl']
    assert not force._state['compliance'] and not force._state['force']


def test_read_force_failure(robot):
    robot(fail={'get_tool_force'})
    with pytest.raises(RuntimeError):
        force.read_force()


# ------------------------------------------------------------------ 닦기 접촉 모션 (나선 · 원호) — F3-02 가 cc.* 로만 부른다
def test_move_spiral_uses_time_not_velocity(robot):
    """🚨 속도로 부르면 드라이버가 멈춘다 → vel·acc 는 0, 시간으로만 (중급1 p.69 · 실기)."""
    d = robot()
    force.move_spiral(2.8, 14.0, 3.0)
    assert d.spiral['vel'] == [0.0, 0.0] and d.spiral['acc'] == [0.0, 0.0]
    assert d.spiral['time'] == pytest.approx(3.0)                       # vel_scale 이 없으면 그대로
    assert d.spiral['rev'] == 2.8 and d.spiral['rmax'] == 14.0 and d.spiral['lmax'] == 0.0
    assert d.spiral['axis'] == d.DR_AXIS_Z and d.spiral['ref'] == d.DR_TOOL
    assert 'mwait' in d.calls                                           # 도는 중에 켜면 2.1903


def test_move_spiral_waits_until_it_starts(robot, monkeypatch):
    """🚨 실기: 명령 직후엔 check_motion 이 아직 0 이라 도는 동안 보는 루프가 바로 끝났다 → 시작을 기다린다."""
    monkeypatch.setattr(force, '_START_WAIT_S', 0.1)
    d = robot()
    d.never_starts = True
    with pytest.raises(RuntimeError, match='움직이지 않았다'):
        force.move_spiral(2.8, 14.0, 3.0)
    d.never_starts = False
    force.move_spiral(2.8, 14.0, 3.0)                                    # 시작하면 그대로 돌아온다


def test_move_spiral_time_ignores_vel_scale(robot):
    """실기: ÷ vel_scale(10 s)은 움직이지 않았다 · V-03 에서 돈 3 s 그대로 준다."""
    cfg = copy.deepcopy(CFG)
    cfg['run'] = {'vel_scale': 0.3}
    d = robot(cfg)
    force.move_spiral(2.8, 14.0, 3.0)
    assert d.spiral['time'] == pytest.approx(3.0)


def test_move_spiral_rejects_bad_args(robot):
    robot()
    for args in ((0, 14.0, 3.0), (2.8, 0, 3.0), (2.8, 14.0, 0)):
        with pytest.raises(ValueError):
            force.move_spiral(*args)


def test_move_spiral_failure_is_error(robot):
    robot(fail={'amove_spiral'})
    with pytest.raises(RuntimeError):
        force.move_spiral(2.8, 14.0, 3.0)


def test_move_arc_blends_and_caps_speed(robot):
    cfg = copy.deepcopy(CFG)
    cfg['run'] = {'vel_scale': 0.5}
    d = robot(cfg)
    mid = [100.0, 60.0, 50.0, 0.0, 180.0, 18.0]
    end = [110.0, 50.0, 50.0, 0.0, 180.0, -18.0]
    force.move_arc(mid, end, 180.0, 400.0, radius_mm=3.0)
    assert d.arc['mid'] == mid and d.arc['end'] == end
    assert d.arc['radius'] == 3.0 and d.arc['mod'] == d.DR_MV_MOD_ABS   # 이어 붙이기 · 절대 자세
    assert d.arc['vel'] == [pytest.approx(90.0), pytest.approx(200.0)]  # × vel_scale
    force.move_arc(mid, end, 9999.0, 400.0)                             # 100 % 기준(400) 을 넘지 못한다
    assert d.arc['vel'][0] == pytest.approx(200.0)
    assert d.arc['radius'] == 0.0


def test_where_and_motion_done(robot):
    d = robot()
    assert force.where() == d.pos
    assert force.motion_done()
    d.motion = 1
    assert not force.motion_done()


def test_safe_retreat_retreats_even_if_release_fails(robot):
    """🚨 힘 해제가 실패해도 후퇴는 한다 — 툴을 용기 안에 두고 오면 더 위험하다."""
    d = robot(fail={'release_force'}, z=100.0)
    force.force_on('z', 4.0, 10.0)
    with pytest.raises(RuntimeError):
        force.safe_retreat()
    assert d.pos[2] == pytest.approx(300.0)                             # cell.limits.safe_z_mm 까지 올라왔다


def test_contact_down_does_not_count_paused_time(robot, monkeypatch):
    """사람이 멈춰 둔 동안은 시간 상한을 세지 않는다."""
    cfg = copy.deepcopy(CFG)
    cfg['cell']['limits']['timeout_s'] = 0.0                            # 안 멈췄으면 첫 바퀴에 시간 초과
    robot(cfg, surface_z=None)                                          # 바닥이 없어 계속 내려간다
    monkeypatch.setattr(force, 'is_paused', lambda: True)
    steps = {'n': 0}
    real = force.move_rel

    def counted(*a, **kw):
        steps['n'] += 1
        if steps['n'] > 3:
            raise RuntimeError('그만')                                   # 무한 루프 방지 — 시간으로는 안 끝난다
        return real(*a, **kw)

    monkeypatch.setattr(force, 'move_rel', counted)
    with pytest.raises(RuntimeError, match='그만'):                      # MotionTimeout 이 아니다
        force.contact_down(1000.0, 5.0)
    monkeypatch.setattr(force, 'is_paused', lambda: False)              # 멈춤을 풀면 같은 설정에서 시간 초과
    with pytest.raises(force.MotionTimeout):
        force.contact_down(1000.0, 5.0)


def test_exports():
    import cobot_common as cc
    for name in ('force_on', 'force_off', 'force_reached', 'contact_down', 'periodic_search', 'safe_retreat',
                 'read_force', 'compliance_on', 'compliance_off', 'start_nudge_watch', 'check_nudge',
                 'robot_state', 'wait_robot_ready',
                 'where', 'motion_done', 'move_spiral', 'move_arc', 'move_periodic', 'joints', 'stop_now', 'ForceLimitError', 'MotionTimeout'):
        assert hasattr(cc, name), name


# ------------------------------------------------------------------ 넛지 감지 (E37 · NEW-02a/b)
@pytest.fixture
def _reset_nudge():
    force._nudge_baseline = None
    force._nudge_above_since = None
    force._nudge_counted = False
    force._nudge_taps = []
    yield
    force._nudge_baseline = None
    force._nudge_above_since = None
    force._nudge_counted = False
    force._nudge_taps = []


def test_check_nudge_requires_start_first(_reset_nudge):
    with pytest.raises(RuntimeError, match='start_nudge_watch'):
        force.check_nudge(15.0, 0.15)


def test_check_nudge_ignores_small_change(_reset_nudge, monkeypatch):
    """기준 대비 별 차이 없으면(정지 상태의 정상 흔들림) 넛지로 안 본다."""
    monkeypatch.setattr(force, 'read_force', lambda: [0.0, 0.0, 0.0, 0, 0, 0])
    force.start_nudge_watch()
    monkeypatch.setattr(force, 'read_force', lambda: [0.5, 0.0, 0.5, 0, 0, 0])
    assert force.check_nudge(15.0, 0.15) is False


def test_check_nudge_true_after_sustained_push(_reset_nudge, monkeypatch):
    """threshold_n 을 넘은 상태가 hold_s 동안 이어져야 True — 순간 노이즈 한 번으로는 안 된다."""
    monkeypatch.setattr(force, 'read_force', lambda: [0.0, 0.0, 0.0, 0, 0, 0])
    force.start_nudge_watch()
    times = iter([0.0, 0.2])
    monkeypatch.setattr(force.time, 'monotonic', lambda: next(times))
    monkeypatch.setattr(force, 'read_force', lambda: [0.0, 0.0, 20.0, 0, 0, 0])
    assert force.check_nudge(15.0, 0.15) is False    # 방금 넘었다 — 아직 hold_s 못 채움
    assert force.check_nudge(15.0, 0.15) is True     # 0.2 s 유지 → 넛지로 본다


def test_check_nudge_resets_if_it_drops_before_hold(_reset_nudge, monkeypatch):
    """hold_s 채우기 전에 힘이 가라앉으면 없던 일로 하고 처음부터 다시 센다."""
    monkeypatch.setattr(force, 'read_force', lambda: [0.0, 0.0, 0.0, 0, 0, 0])
    force.start_nudge_watch()
    times = iter([0.0, 0.05, 0.1, 0.1])
    monkeypatch.setattr(force.time, 'monotonic', lambda: next(times))
    seq = iter([[0.0, 0.0, 20.0, 0, 0, 0],    # 넘음(0.0 s) — 카운트 시작
                [0.0, 0.0, 0.0, 0, 0, 0],     # 가라앉음(0.05 s) — 리셋
                [0.0, 0.0, 20.0, 0, 0, 0],    # 다시 넘음(0.1 s) — 카운트 재시작
                [0.0, 0.0, 20.0, 0, 0, 0]])   # 아직 같은 0.1 s — hold_s(0.15) 못 채움
    monkeypatch.setattr(force, 'read_force', lambda: next(seq))
    assert force.check_nudge(15.0, 0.15) is False    # 넘음, 카운트 시작
    assert force.check_nudge(15.0, 0.15) is False    # 가라앉아 리셋
    assert force.check_nudge(15.0, 0.15) is False    # 다시 넘음, 카운트 재시작(0.1 s 기준)
    assert force.check_nudge(15.0, 0.15) is False    # 아직 0.1 s — hold_s 못 채움


def test_robot_state_reads_dsr(robot):
    """robot_state() 는 두산 API get_robot_state() 를 그대로 읽는다."""
    d = robot()
    d.get_robot_state = lambda: 1
    assert force.robot_state() == 1


def test_wait_robot_ready_true_once_standby(robot):
    """STANDBY(1) 가 될 때까지 기다리다 되면 True."""
    d = robot()
    states = iter([2, 2, 1])          # MOVING → MOVING → STANDBY
    d.get_robot_state = lambda: next(states)
    assert force.wait_robot_ready(1.0) is True


def test_wait_robot_ready_false_on_timeout(robot):
    """시간 안에 STANDBY 가 안 되면 False(예외 안 던짐 — 그래도 이어간다는 정책을 flow 가 고른다)."""
    d = robot()
    d.get_robot_state = lambda: 2      # 계속 MOVING
    assert force.wait_robot_ready(0.05) is False


# ------------------------------------------------------------------ step_mm — 마지막 감시 구간을 한 걸음에
def test_contact_down_step_mm_takes_the_watch_in_one_step(robot):
    d = robot(z=400.0, surface_z=None)
    depth, _ = force.contact_down(max_depth=5.0, limit=3.0, step_mm=5.0)
    assert depth == pytest.approx(5.0) and d.calls.count('movel') == 1          # 기본 3 mm 면 3 + 2 두 걸음


def test_contact_down_default_step_is_still_the_config_value(robot):
    import math
    d = robot(z=400.0, surface_z=None)
    force.contact_down(max_depth=5.0, limit=3.0)
    assert d.calls.count('movel') == math.ceil(5.0 / CFG['cell']['force']['contact_step_mm'])   # 설정 걸음대로 여러 걸음


def test_contact_down_rejects_a_non_positive_step_without_moving(robot):
    d = robot(z=400.0, surface_z=None)
    with pytest.raises(ValueError):
        force.contact_down(max_depth=5.0, limit=3.0, step_mm=0.0)
    assert 'movel' not in d.calls


def test_recover_robot_if_needed_already_standby(robot):
    """이미 STANDBY(1) 상태이면 서비스를 부르지 않고 바로 True."""
    d = robot()
    d.get_robot_state = lambda: 1
    assert force.recover_robot_if_needed(timeout_s=0.1) is True


def test_recover_robot_if_needed_handles_mock_gracefully(robot):
    """서비스나 ROS 노드가 없는 테스트 환경에서 상태가 5일 때도 예외 없이 False 반환."""
    d = robot()
    d.get_robot_state = lambda: 5      # SAFE_STOP
    assert force.recover_robot_if_needed(timeout_s=0.05) is False


# ------------------------------------------------------------------ E48 — 여러 번 치기(taps · window_s)
def _push_sequence(monkeypatch, samples):
    """(시각, Fz) 목록을 차례로 돌려준다 — 한 check_nudge 호출이 read_force 1번 · monotonic 1번."""
    times = iter([t for t, _ in samples]); forces = iter([f for _, f in samples])
    monkeypatch.setattr(force.time, 'monotonic', lambda: next(times))
    monkeypatch.setattr(force, 'read_force', lambda: [0.0, 0.0, next(forces), 0, 0, 0])


def test_check_nudge_two_taps_within_window(_reset_nudge, monkeypatch):
    """두 번 치기: 누름(hold 채움) → 뗌 → 다시 누름(hold 채움) = True. 첫 누름만으론 False."""
    monkeypatch.setattr(force, 'read_force', lambda: [0.0, 0.0, 0.0, 0, 0, 0])
    force.start_nudge_watch()
    _push_sequence(monkeypatch, [(0.0, 20.0), (0.2, 20.0), (0.4, 0.0), (0.6, 20.0), (0.8, 20.0)])
    r = [force.check_nudge(15.0, 0.15, 2, 2.0) for _ in range(5)]
    assert r == [False, False, False, False, True]


def test_check_nudge_one_long_push_counts_once(_reset_nudge, monkeypatch):
    """한 번 꾹 누르고 있는 것은 아무리 길어도 1번 — 손을 떼야 2번째."""
    monkeypatch.setattr(force, 'read_force', lambda: [0.0, 0.0, 0.0, 0, 0, 0])
    force.start_nudge_watch()
    _push_sequence(monkeypatch, [(0.0, 20.0), (0.2, 20.0), (0.5, 20.0), (1.0, 20.0), (1.5, 20.0)])
    assert all(force.check_nudge(15.0, 0.15, 2, 2.0) is False for _ in range(5))


def test_check_nudge_second_tap_after_window_restarts_count(_reset_nudge, monkeypatch):
    """첫 밀기 뒤 2 s 가 지나서 온 두 번째는 '첫 번째'로 다시 센다 → 아직 False."""
    monkeypatch.setattr(force, 'read_force', lambda: [0.0, 0.0, 0.0, 0, 0, 0])
    force.start_nudge_watch()
    _push_sequence(monkeypatch, [(0.0, 20.0), (0.2, 20.0), (0.4, 0.0), (3.0, 20.0), (3.2, 20.0)])
    assert [force.check_nudge(15.0, 0.15, 2, 2.0) for _ in range(5)] == [False] * 5


def test_check_nudge_default_taps_is_one_like_before(_reset_nudge, monkeypatch):
    monkeypatch.setattr(force, 'read_force', lambda: [0.0, 0.0, 0.0, 0, 0, 0])
    force.start_nudge_watch()
    _push_sequence(monkeypatch, [(0.0, 20.0), (0.2, 20.0)])
    assert force.check_nudge(15.0, 0.15) is False and force.check_nudge(15.0, 0.15) is True
