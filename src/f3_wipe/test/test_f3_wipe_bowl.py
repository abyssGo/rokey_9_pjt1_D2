# -*- coding: utf-8 -*-
"""wipe_bowl(F3-02) 시험 — 로봇 없이 가짜 두산 함수로 **rig_v03 과 같은 명령·순서**인지, 실패 처리가 맞는지 본다.

    python3 -m pytest -q src/f3_wipe/test/test_f3_wipe_bowl.py

9/21: wipe_bowl 은 9/20 실기 확정본 rig_v03(src/cobot_common/test/rig_v03.py)의 실행 순서·명령을 그대로 옮겼다(두산 명령은 같은 일을 하는 cc 함수로 — AGENTS 규칙 4).
바꾼 것은 박진용 지시 세 가지: 빠른 하강 140 mm · 바닥 판정 3 N · 곧게 올라오기 = 빠른 하강 속도.
"""
import copy
import math

import pytest

from cobot_api import FORCE_LIMIT, OK, ROBOT_ERROR, TIMEOUT, TOOL_LOST
from f3_wipe import wipe

WALL_R = (110.0 - 90.0) / 2 + 4.0
HOME_POSJ = [0.0, 0.0, 90.0, 0.0, 90.0, 0.0]
HOME = [367.5, 8.0, 215.0, 157.0, 180.0, 157.0]
AIR = 2.0
FIND = 11.0
CFG0 = {
    'run': {'vel_scale': 0.3},
    'f2': {'slip_tol_mm': 1.0},                                          # TOOL_LOST 판정 허용오차(재사용)
    'cell': {'force': {'compliance_stx': [1000, 1000, 200, 100, 100, 100]},
             'stations': {'HOME': {'posj': HOME_POSJ}}},
    'f3': {'wipe_bowl': {
        'tool': {'clean_h_mm': 35, 'd_mm': 90},
        'fast_down_mm': 140.0, 'home_vel_deg_s': 40.0, 'home_acc_deg_s2': 40.0,
        'fast_vel_mm_s': 220.0, 'fast_acc_mm_s2': 440.0, 'air_force_max_n': 3.0,
        'find_max_mm': 30.0, 'find_limit_n': 3.0, 'contact_timeout_s': 40.0,
        'press_vel_mm_s': 20.0, 'press_acc_mm_s2': 50.0,
        'target_force_n': 1.5, 'limit_n': 10.0, 'lateral_max_n': 25.0,
        'bowl_inner_d_mm': 110.0, 'wall_press_mm': 4.0,
        'spiral_pitch_mm': 5.0, 'spiral_time_s': 3.0,
        'turns': 3, 'wall_arc_deg': 90.0, 'wall_approach_vel_mm_s': 60.0,
        'twist_deg': 18.0, 'blend_radius_mm': 3.0, 'lin_vel_mm_s': 600.0, 'rot_vel_deg_s': 400.0,
        'lin_acc_mm_s2': 3000.0, 'rot_acc_deg_s2': 1000.0,
        'force_every': 4, 'sample_s': 0.0, 'duration_s': 120, 'log_dir': 'logs/f3',
    }},
}


class _Logger:
    def __init__(self):
        self.lines = []

    def info(self, m):
        self.lines.append(('info', m))

    def error(self, m):
        self.lines.append(('error', m))


class FakeRobot:
    """가짜 cc 함수 — rig_v03 이 부른 두산 명령과 같은 이름으로 호출을 적고, 자세·힘을 흉내 낸다."""
    REL, ABS = 'REL', 'ABS'

    def __init__(self):
        self.cfg_ = copy.deepcopy(CFG0)
        self.calls = []
        self.pose = list(HOME)
        self.find, self.contact_f = FIND, 3.4
        self.touched = False
        self.press, self.lateral, self.air = 1.5, 1.0, AIR
        self.spiral = None
        self.spiral_moves = True
        self.halted = False
        self.fail = None
        self.logger = _Logger()
        self.width = 20.0                                # TOOL_LOST 시험용 — 기본은 안 변한다(안 놓침)
        self.waited_while_moving = False                 # 나선이 도는 중에 wait_done(mwait) 으로 끝까지 기다렸는가

    def grip_width(self):
        return self.width

    def _chk(self, name):
        if self.fail == name:
            raise RuntimeError(f'{name} 실패')

    def move_joints(self, q, vel_deg_s, acc_deg_s2):
        self.calls.append(('movej', list(q), vel_deg_s * CFG0['run']['vel_scale'], acc_deg_s2))
        self._chk('movej')
        self.pose = list(HOME)

    def move_line_rel(self, dx, dy, dz, vel_mm_s, acc_mm_s2):
        self.calls.append(('movel', [dx, dy, dz, 0.0, 0.0, 0.0], vel_mm_s * CFG0['run']['vel_scale'], acc_mm_s2, self.REL))
        self._chk('movel')
        self.pose = [self.pose[0] + dx, self.pose[1] + dy, self.pose[2] + dz] + self.pose[3:]

    def move_rel(self, dx, dy, dz, frame, *, vel_mm_s=None, acc_mm_s2=None):
        """빠른 하강·올라오기 — wipe.py 가 이미 vel_scale 을 곱해서 넘긴다(컵과 같은 방식, 박진용 9/22)."""
        self.calls.append(('movel', [dx, dy, dz, 0.0, 0.0, 0.0], vel_mm_s, acc_mm_s2, self.REL))
        self._chk('movel')
        self.pose = [self.pose[0] + dx, self.pose[1] + dy, self.pose[2] + dz] + self.pose[3:]

    def move_pose(self, pose, vel_mm_s, vel_deg_s, acc_mm_s2, acc_deg_s2, radius_mm=0.0):
        s = CFG0['run']['vel_scale']
        self.calls.append(('movel', list(pose), [vel_mm_s * s, vel_deg_s * s], [acc_mm_s2, acc_deg_s2], self.ABS))
        self._chk('movel')
        self.pose = list(pose)

    def move_arc(self, mid, end, vel_mm_s, vel_deg_s, radius_mm=0.0, acc_mm_s2=None, acc_deg_s2=None):
        s = CFG0['run']['vel_scale']
        self.calls.append(('movec', list(mid), list(end), [vel_mm_s * s, vel_deg_s * s], [acc_mm_s2, acc_deg_s2], radius_mm))
        self._chk('movec')
        self.pose = list(end)

    def where(self):
        return list(self.pose)

    def wait_done(self):
        self.calls.append(('mwait',))
        if self.spiral is not None and self.spiral_moves:     # 나선이 아직 도는 중에 끝까지 기다렸다
            self.waited_while_moving = True
            self.spiral = None

    def compliance_on(self, stx=None):
        self.calls.append(('compliance',))

    def move_spiral(self, rev, rmax_mm, time_s, axis='z', ref='TOOL'):
        self.calls.append(('spiral', rev, rmax_mm, time_s, axis, ref))
        self._chk('amove_spiral')
        self.spiral = [0, 40, rmax_mm, rev, list(self.pose)]

    def motion_done(self):
        if self.spiral is None or not self.spiral_moves:
            self.spiral = None
            return True
        k, steps, rmax, rev, c = self.spiral
        if k >= steps:
            self.spiral = None
            return True
        self.spiral[0] = k + 1
        f = (k + 1) / steps
        th = rev * 2 * math.pi * f
        self.pose[0] = c[0] + rmax * f * math.cos(th)
        self.pose[1] = c[1] + rmax * f * math.sin(th)
        return False

    def force_release(self):
        self.calls.append(('release_force',))

    def stop_now(self):
        self.calls.append(('stop_now',))
        self.spiral = None                               # 즉시 정지 — 도는 나선을 끊는다

    def cfg(self):
        return self.cfg_

    def contact_down(self, max_depth, limit, timeout_s=None, keep_compliance=False):
        self.calls.append(('contact_down', max_depth, limit, timeout_s))
        found = min(self.find, max_depth)
        self.pose[2] -= found
        self.touched = found < max_depth
        return found, (self.contact_f if self.touched else 0.0)

    def read_force(self):
        if not self.touched:
            return [0.0, 0.0, self.air, 0.0, 0.0, 0.0]
        return [self.lateral, 0.0, self.air + self.press, 0.0, 0.0, 0.0]

    def force_on(self, axis, target, limit):
        self.calls.append(('force_on', axis, round(target, 2), limit))

    def force_off(self):
        self.calls.append(('force_off',))

    def is_halted(self):
        return self.halted

    def io_node(self):
        return self

    def get_logger(self):
        return self.logger


CC_NAMES = ('move_joints', 'move_line_rel', 'move_rel', 'move_pose', 'move_arc', 'where', 'wait_done', 'compliance_on',
            'move_spiral', 'motion_done', 'force_release', 'cfg', 'contact_down', 'read_force', 'force_on', 'force_off',
            'is_halted', 'io_node', 'grip_width', 'stop_now')


@pytest.fixture
def rb(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    r = FakeRobot()
    for name in CC_NAMES:
        monkeypatch.setattr(wipe.cc, name, getattr(r, name), raising=False)
    monkeypatch.setattr(wipe, '_tool_baseline_mm', None, raising=False)   # 다른 시험의 soap() 기준이 새지 않게
    return r


def _names(r):
    return [c[0] for c in r.calls]


def _ended_home(r):
    """끝: … → 곧게 호출된 높이로(movel REL +) — movej 없음(박진용 9/22 3차, soap이 이미 데려다 놨다는 전제)."""
    moves = [c for c in r.calls if c[0] in ('movel', 'movej')]
    return bool(moves) and moves[-1][0] == 'movel' and moves[-1][4] == r.REL and moves[-1][1][2] > 0


def test_order_is_rig_v03(rb):
    r = wipe.wipe_bowl()
    assert r.ok and r.code == OK
    n = _names(rb)
    assert n[0] == 'movel'                                                # movej 없음 — 호출되자마자 바로 하강(박진용 9/22 3차)
    # 🔸 순응은 contact_down(keep_compliance=True) 안에서 켜진 채로 넘어온다(박진용 9/22) — 여기서 따로 껐다 켜지 않는다
    assert (n.index('contact_down') < n.index('spiral') < n.index('force_on')
            < n.index('movec') < n.index('release_force'))
    assert 'force_off' in n and _ended_home(rb)


def test_values_same_as_rig_v03_except_four(rb):
    """하강 140 mm 66 mm/s·132(컵과 같은 방식으로 vel_scale 적용, 박진용 9/22) · 바닥 30 mm·3 N·40 s · 나선 2.8바퀴·14 mm·3 s(속도 0)."""
    wipe.wipe_bowl()
    down = [c for c in rb.calls if c[0] == 'movel'][0]
    assert down[1][2] == -140.0 and down[2] == pytest.approx(66.0) and down[3] == pytest.approx(132.0)
    assert ('contact_down', 30.0, 3.0, 40.0) in rb.calls
    sp = [c for c in rb.calls if c[0] == 'spiral'][0]
    assert sp[1] == pytest.approx(2.8) and sp[2] == pytest.approx(WALL_R) and sp[3] == 3.0
    assert sp[4] == 'z' and sp[5] == 'TOOL'


def test_rise_same_speed_as_fast_down(rb):
    wipe.wipe_bowl()
    rels = [c for c in rb.calls if c[0] == 'movel' and c[4] == rb.REL]
    assert rels[0][2] == rels[-1][2] and rels[0][3] == rels[-1][3]
    assert rels[-1][1][2] == pytest.approx(140.0 + FIND)                   # 바닥에서 HOME 높이까지


def test_wall_like_rig_v03(rb):
    """+18° 로 붙기(movel 18 mm/s) → 원호 12 개, 시계, ±18° 번갈아, 마지막만 안 이어 붙임, 180 mm/s · 가속 3000/1000."""
    wipe.wipe_bowl()
    arcs = [c for c in rb.calls if c[0] == 'movec']
    assert len(arcs) == 12
    assert arcs[-1][5] == 0.0 and all(a[5] == 3.0 for a in arcs[:-1])
    assert all(a[3] == pytest.approx([180.0, 120.0]) and a[4] == [3000.0, 1000.0] for a in arcs)
    center = [c for c in rb.calls if c[0] == 'movel' and c[4] == rb.ABS][-1][1]
    ends = [a[2] for a in arcs]
    assert all(math.hypot(e[0] - center[0], e[1] - center[1]) == pytest.approx(WALL_R) for e in ends)
    ang = [math.atan2(e[1] - center[1], e[0] - center[0]) for e in ends]
    assert all(math.sin(b - a) < 0 for a, b in zip(ang, ang[1:]))          # 시계
    tw = [round((e[5] - center[5] + 180) % 360 - 180, 1) for e in ends]
    assert set(tw) == {-18.0, 18.0}


def test_force_target_adds_air_baseline(rb):
    wipe.wipe_bowl()
    assert ('force_on', 'z', round(1.5 + AIR, 2), 10.0) in rb.calls


def test_spiral_not_started_is_error_and_goes_home(rb):
    rb.spiral_moves = False
    r = wipe.wipe_bowl()
    assert not r.ok and r.code == ROBOT_ERROR
    assert 'movec' not in _names(rb) and _ended_home(rb)
    assert any('나선이 돌지 않았다' in m for lvl, m in rb.logger.lines if lvl == 'error')


def test_bottom_not_found(rb):
    rb.find = 30.0
    r = wipe.wipe_bowl()
    assert not r.ok and 'spiral' not in _names(rb) and _ended_home(rb)


def test_tool_lost_detected_before_spiral(rb, monkeypatch):
    """9/23: soap 이 넘긴 기준 폭보다 크게 벗어나면(바닥 찾은 뒤 나선 전) TOOL_LOST — FORCE_LIMIT 과는 별개 코드."""
    monkeypatch.setattr(wipe, '_tool_baseline_mm', 20.0, raising=False)
    orig_contact_down = rb.contact_down

    def dropped(*a, **kw):
        result = orig_contact_down(*a, **kw)
        rb.width = 20.0 + 5.0                        # slip_tol_mm(1.0)보다 훨씬 크게 벗어남 — 실기 재현 값 참고
        return result

    monkeypatch.setattr(wipe.cc, 'contact_down', dropped, raising=False)
    r = wipe.wipe_bowl()
    assert not r.ok and r.code == TOOL_LOST
    # 🚨 9/23 실기 사고: 놓친 뒤 "실패했으니 원래 높이로 올라오기"까지 하면 빈 그리퍼로 더 움직인다 —
    #    TOOL_LOST 는 감지된 그 자리에 그대로 둔다(올라오지 않는다).
    assert 'spiral' not in _names(rb) and not _ended_home(rb)
    assert 'movec' not in _names(rb)                          # 나선 이후(벽면)로도 안 갔다


def test_tool_lost_during_fast_descend_halts_immediately(rb, monkeypatch):
    """9/23: 체크 지점이 없는 단일 move_rel(빠른 하강) 도중 놓쳐도 감시 스레드가 halt() 로 그 자리에서 세운다."""
    import time as _t

    monkeypatch.setattr(wipe, '_tool_baseline_mm', 20.0, raising=False)
    rb.width = 20.0
    halted = {'flag': False}
    real_move_rel = rb.move_rel

    def slow_move_rel(dx, dy, dz, frame, **kw):
        rb.width = 20.0 + 5.0                        # 이동이 시작되는 순간 놓친 걸로 바꾼다
        t0 = _t.monotonic()
        while _t.monotonic() - t0 < 0.3:
            if halted['flag']:
                raise wipe.cc.MotionHalted('시험: halt 도중')
            _t.sleep(0.01)
        return real_move_rel(dx, dy, dz, frame, **kw)

    monkeypatch.setattr(wipe.cc, 'move_rel', slow_move_rel, raising=False)
    monkeypatch.setattr(wipe.cc, 'halt', lambda: halted.update(flag=True), raising=False)
    monkeypatch.setattr(wipe.cc, 'clear_halt', lambda: halted.update(flag=False), raising=False)

    r = wipe.wipe_bowl()
    assert not r.ok and r.code == TOOL_LOST
    assert 'contact_down' not in _names(rb)          # 하강 중에 멈췄다 — 접촉까지도 못 갔다
    assert halted['flag'] is False                   # 우리가 건 halt는 우리가 풀었다(clear_halt)


def test_wipe_bowl_sets_its_own_baseline_without_soap(rb, monkeypatch):
    """9/23: TOOL_LOST 뒤 flow 는 soap() 없이 wipe_bowl() 만 재시도한다(재PICK 후) —
    이 함수 혼자서도 자기가 쥔 폭을 기준으로 놓침을 잡아야 한다(soap() 가 준 기준에 기대면 안 된다)."""
    assert wipe._tool_baseline_mm is None            # soap() 를 거치지 않았다 — fixture 가 리셋해 둔 상태
    rb.width = 30.0                                  # 이번에 실제로 쥔 폭(soap 을 안 거쳤으니 임의값)
    orig_contact_down = rb.contact_down

    def dropped(*a, **kw):
        result = orig_contact_down(*a, **kw)
        rb.width = 30.0 + 5.0                        # 기준(자기가 방금 잰 30.0)보다 크게 벗어남
        return result

    monkeypatch.setattr(wipe.cc, 'contact_down', dropped, raising=False)
    r = wipe.wipe_bowl()
    assert not r.ok and r.code == TOOL_LOST, 'soap() 없이도 wipe_bowl 스스로 기준을 잡아 놓침을 잡아야 한다'


def test_air_force_too_big(rb):
    rb.air = 3.5
    r = wipe.wipe_bowl()
    assert not r.ok and 'contact_down' not in _names(rb) and _ended_home(rb)


def test_press_over_limit(rb):
    rb.press = 99.0
    r = wipe.wipe_bowl()
    assert r.code == FORCE_LIMIT and _ended_home(rb)


def test_lateral_over_limit(rb):
    rb.lateral = 99.0
    r = wipe.wipe_bowl()
    assert r.code == FORCE_LIMIT and _ended_home(rb)


def test_doosan_failure_is_robot_error_and_goes_home(rb):
    rb.fail = 'movec'
    r = wipe.wipe_bowl()
    assert r.code == ROBOT_ERROR and _ended_home(rb)


def test_halt_before_start_does_not_move(rb):
    rb.halted = True
    with pytest.raises(wipe.cc.MotionHalted):
        wipe.wipe_bowl()
    assert _names(rb) == ['stop_now', 'force_off']


def test_spiral_timeout(rb, monkeypatch):
    rb.cfg_['f3']['wipe_bowl']['spiral_time_s'] = -10.0                     # 이미 넘은 것으로
    r = wipe.wipe_bowl()
    assert r.code == TIMEOUT and _ended_home(rb)


def test_force_log_saved(rb):
    r = wipe.wipe_bowl()
    assert r.force_log_path.endswith('.csv') and r.force_mean_n > 0


def test_over_total_time_is_timeout_and_goes_home(rb):
    """전체 duration_s(120 s) 상한은 남긴다(황인재 9/22) — 넘으면 TIMEOUT, 끄고 올라와 HOME."""
    rb.cfg_['f3']['wipe_bowl']['duration_s'] = -1
    r = wipe.wipe_bowl()
    assert r.code == TIMEOUT and _ended_home(rb)


# ------------------------------------------------------------------ 🔧 9/23 17:43 실기 — f2.slip_tol_mm 이 종류별 dict 여도 툴 놓침 감시가 살아야 한다
def test_tool_lost_tolerance_accepts_per_kind_dict(monkeypatch):
    class _CC:
        def cfg(self): return {'f2': {'slip_tol_mm': {'BOWL': 1.0, 'CUP': 1.5}}}
        def grip_width(self): return 25.7
    monkeypatch.setattr(wipe, 'cc', _CC())
    monkeypatch.setattr(wipe, '_tool_baseline_mm', 25.6)
    assert wipe._tool_tol_mm() == 1.0                                       # 가장 작은 값(툴 손잡이는 단단하다)
    assert wipe._tool_lost_now() is False                                   # 0.1 mm 차이 → 놓친 것 아님
    monkeypatch.setattr(wipe, '_tool_baseline_mm', 22.0)
    assert wipe._tool_lost_now() is True                                    # 3.7 mm → 놓침


def test_tool_lost_tolerance_accepts_a_plain_number(monkeypatch):
    class _CC:
        def cfg(self): return {'f2': {'slip_tol_mm': 2.0}}
        def grip_width(self): return 25.7
    monkeypatch.setattr(wipe, 'cc', _CC())
    assert wipe._tool_tol_mm() == 2.0


# ── 힘 상한·시간 초과면 남은 나선을 먼저 즉시 정지(E60) — 정리의 동작 끝 대기(mwait)가 나선을 끝까지 기다리지 않게
def _after(names, first, then):
    """first 가 있고, first 뒤에 then 이 한 번 이상 나온다."""
    i = names.index(first)
    return then in names[i + 1:]


def test_force_limit_in_spiral_stops_now_before_wait_and_force_off(rb, monkeypatch):
    seen = {}
    real_stop = rb.stop_now

    def stop_now():
        seen['spiral_running'] = rb.spiral is not None       # 나선이 아직 도는 중에 끊었는가
        real_stop()
    monkeypatch.setattr(wipe.cc, 'stop_now', stop_now, raising=False)
    rb.press = 99.0                                          # 나선 첫 감시에서 누름 > 10 N
    r = wipe.wipe_bowl()
    n = _names(rb)
    assert r.code == FORCE_LIMIT and n.count('stop_now') == 1 and seen['spiral_running']
    i = n.index('stop_now')
    assert 'spiral' in n[:i] and 'mwait' not in n[n.index('spiral'):i]     # 나선 뒤 정지 전에 mwait 없음
    assert n[i + 1] == 'force_off' and _after(n, 'stop_now', 'mwait') and _ended_home(rb)
    assert not rb.waited_while_moving


def test_lateral_limit_in_spiral_also_stops_now_first(rb):
    rb.lateral = 99.0
    r = wipe.wipe_bowl()
    n = _names(rb)
    i = n.index('stop_now')
    assert r.code == FORCE_LIMIT and n.count('stop_now') == 1 and n[i + 1] == 'force_off'
    assert 'mwait' not in n[n.index('spiral'):i] and not rb.waited_while_moving


def test_spiral_timeout_stops_now_before_wait_and_force_off(rb):
    rb.cfg_['f3']['wipe_bowl']['spiral_time_s'] = -10.0     # 나선 명령 시간 + 5 s 를 이미 넘은 것으로
    r = wipe.wipe_bowl()
    n = _names(rb)
    i = n.index('stop_now')
    assert r.code == TIMEOUT and n.count('stop_now') == 1 and 'mwait' not in n[n.index('spiral'):i]
    assert n[i + 1] == 'force_off' and _after(n, 'stop_now', 'mwait') and _ended_home(rb)
    assert not rb.waited_while_moving


def test_total_time_over_in_spiral_stops_now(rb):
    rb.cfg_['f3']['wipe_bowl']['duration_s'] = -1            # 전체 시간 초과(나선)
    r = wipe.wipe_bowl()
    n = _names(rb)
    i = n.index('stop_now')
    assert r.code == TIMEOUT and n.count('stop_now') == 1 and n[i + 1] == 'force_off'
    assert 'mwait' not in n[n.index('spiral'):i] and not rb.waited_while_moving


def test_normal_end_has_no_stop_now(rb):
    r = wipe.wipe_bowl()
    assert r.ok and 'stop_now' not in _names(rb)


def test_robot_error_has_no_new_stop_now(rb):
    rb.fail = 'movec'
    r = wipe.wipe_bowl()
    assert r.code == ROBOT_ERROR and 'stop_now' not in _names(rb) and _ended_home(rb)


def test_tool_lost_in_spiral_keeps_single_stop_and_does_not_rise(rb, monkeypatch):
    """TOOL_LOST 는 감시가 이미 한 번 정지한다 — 정리에서 더 부르지 않고 그 자리에 둔다."""
    real_done = rb.motion_done

    def done_and_drop():
        d = real_done()
        if rb.spiral is not None:
            rb.width = 5.0                                   # 나선 도는 중 폭이 확 줄었다 = 놓침
        return d
    monkeypatch.setattr(wipe.cc, 'motion_done', done_and_drop, raising=False)
    r = wipe.wipe_bowl()
    n = _names(rb)
    assert r.code == TOOL_LOST and n.count('stop_now') == 1 and not _ended_home(rb)


def test_halt_after_start_does_not_add_stop_or_rise(rb, monkeypatch):
    """시작한 뒤(바닥을 찾은 뒤) 강제정지 — 위치를 모른다: 기존 정지 1번 → 힘 끄기만, mwait·상승 없음."""
    real = rb.contact_down

    def contact_then_halt(*a, **kw):
        out = real(*a, **kw)
        rb.halted = True
        return out
    monkeypatch.setattr(wipe.cc, 'contact_down', contact_then_halt, raising=False)
    with pytest.raises(wipe.cc.MotionHalted):
        wipe.wipe_bowl()
    n = _names(rb)
    assert n[-3:] == ['contact_down', 'stop_now', 'force_off'] and n.count('stop_now') == 1 and 'mwait' not in n


def test_stop_now_failure_still_cleans_up_with_warning(rb, monkeypatch):
    def broken_stop():
        rb.calls.append(('stop_now',))
        raise RuntimeError('드라이버 응답 없음')
    monkeypatch.setattr(wipe.cc, 'stop_now', broken_stop, raising=False)
    rb.press = 99.0
    r = wipe.wipe_bowl()
    n = _names(rb)
    assert r.code == FORCE_LIMIT and n[n.index('stop_now') + 1] == 'force_off' and _ended_home(rb)
    assert any('즉시 정지' in m and '정리 실패' in m for lv, m in rb.logger.lines if lv == 'error')


def test_stop_now_that_does_not_stop_warns(rb, monkeypatch):
    monkeypatch.setattr(wipe.cc, 'stop_now', lambda: rb.calls.append(('stop_now',)), raising=False)   # 보냈는데 안 멈춤
    rb.press = 99.0
    r = wipe.wipe_bowl()
    assert r.code == FORCE_LIMIT and _ended_home(rb)
    assert any('3 s 안에 멈추지 않았다' in m for lv, m in rb.logger.lines if lv == 'error')

