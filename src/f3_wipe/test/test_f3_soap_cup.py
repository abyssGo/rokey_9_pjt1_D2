# -*- coding: utf-8 -*-
"""soap · wipe_cup(F3-03) 시험 — 로봇 없이 가짜 공용 함수로 순서·판정·실패 처리를 본다.

    python3 -m pytest -q src/f3_wipe/test/test_f3_soap_cup.py

soap 은 접촉 동작이 아니다(수조가 비어 있다) → 순응·힘제어·힘 감시가 없어야 한다.
wipe_cup 은 **삽입만** 힘으로 찾고(contact_down), 문지르기는 순응을 끈 위치 제어다(관절 이동, 2.1903).
🔧 9/22 3차(박진용): soap이 쥔 폭으로 수세미/컵솔을 스스로 가려 movej 없이 좌표로 작업 위치까지 데려간다.
   wipe_bowl·wipe_cup 은 더 이상 스스로 위치를 찾지 않는다 — 호출되자마자 바로 하강하고, 끝나면 호출 시점
   높이로만 상승한다.
실제 깊이·회전각은 V-10(실기)에서 확정한다 — 여기서는 순서·상한 처리만 본다.
"""
import math

import pytest

from cobot_api import FORCE_LIMIT, OK, ROBOT_ERROR, TIMEOUT, TOOL_LOST
from f3_wipe import wipe

HOME_X, HOME_Y, HOME_Z = 367.48, 8.09, 215.11

CFG = {
    'run': {'vel_scale': 0.3},
    'f2': {'slip_tol_mm': 1.0},                                          # TOOL_LOST 판정 허용오차(재사용)
    'cell': {'limits': {'insert_limit_n': 15.0, 'timeout_s': 30.0},      # main 값 — 컵은 이것을 쓰지 않는다
             'stations': {'HOME': {'posj': [0.0, 0.0, 90.0, 0.0, 90.0, 0.0],
                                    'posx_x_mm': HOME_X, 'posx_y_mm': HOME_Y, 'posx_z_mm': HOME_Z}},
             'motion': {'vel_joint_max_deg_s': 100.0, 'acc_joint_max_deg_s2': 200.0}},
    'f3': {
        'soap': {'depth_mm': 40.0, 'hold_s': 0.0, 'vel_mm_s': 80.0, 'log_dir': 'logs/f3',
                 'twist_deg': 20.0, 'twist_cycles': 3, 'twist_period_s': 1.0,
                 'updown_mm': 5.0, 'updown_cycles': 2, 'updown_period_s': 0.3,
                 'ramp_s': 0.2, 'rot_vel_limit_deg_s': 225.0,
                 'duration_s': 60, 'tool_split_x_mm': 349.0},
        'wipe_bowl': {'fast_vel_mm_s': 220.0, 'fast_acc_mm_s2': 440.0,    # soap 의 상승·이동 속도가 이 값을 그대로 읽는다
                      'home_vel_deg_s': 40.0, 'home_acc_deg_s2': 40.0},
        'wipe_cup': {
            'tool': {'clean_h_mm': 95, 'd_mm': 55},
            'over_cup_up_mm': 40.0, 'over_cup_dy_mm': 140.0, 'find_limit_n': 5.0,
            'fast_down_mm': 80.0, 'fast_vel_mm_s': 180.0, 'fast_acc_mm_s2': 360.0, 'find_max_mm': 40.0,
            'lift_mm': 3.0, 'lift_vel_mm_s': 40.0,
            'stroke_mm': 20.0,
            'spin_deg': 360.0, 'period_s': 6.3, 'rot_vel_limit_deg_s': 225.0, 'ramp_s': 1.5, 'joint_guard_deg': 1.0, 'j6_limit_deg': 360.0, 'j6_margin_deg': 10.0,
            'cycles': 3, 'keep_in_mm': 10.0,
            'limit_n': 10.0, 'lateral_max_n': 25.0, 'sample_s': 0.0,
            'duration_s': 120, 'log_dir': 'logs/f3',
        },
    },
}
SPONGE_X, BRUSH_X = 273.0, 425.0                                          # 문턱값(349.0) 위/아래 — 수세미/컵솔 홀더 실측 X
POSE0 = [SPONGE_X, 100.0, 200.0, 45.0, 180.0, 45.0]                       # 픽업 위치(soap) / 임의 현재 위치(wipe_cup 단독 시험)


class _Logger:
    def __init__(self):
        self.lines = []

    def info(self, m):
        self.lines.append(('info', m))

    def error(self, m):
        self.lines.append(('error', m))


class FakeCell:
    """가짜 셀 — 공용 함수 호출을 순서대로 적어 둔다."""

    def __init__(self, up=80.0, depth=8.0, press=2.0, lateral=1.0):
        self.calls = []
        self.up, self.depth = up, depth          # up = 접근점 → 닦는 높이 · depth = 거기서 바닥까지(찾기 구간)
        self.press, self.lateral = press, lateral
        self.pose = list(POSE0)
        self.inserted = False
        self.halted = False
        self.j6 = self.j6_min = self.j6_max = 21.0      # 컵 위 자세의 6번 축 (9/21 Virtual 기록)
        self.j4 = 0.0                                    # 4번 조인트 — 움직이면 안 된다
        self.j4_during = 0.0                             # 세척 도는 동안 4번 조인트 (시험에서 바꾼다)
        self.periodic = 0
        self.j6_sign = 1                                 # 자세 c + → 6번 축 + (Virtual 기록). −1 이면 반대로 도는 로봇
        self.logger = _Logger()
        self.width = 20.0                                # TOOL_LOST 시험용 — 기본은 안 변한다(안 놓침)

    def cfg(self):
        return CFG

    def grip_width(self):
        return self.width

    def move_to(self, station, carrying, kind=None, point=None):
        self.calls.append(('move_to', station, kind, point))
        self.pose = list(POSE0)
        return self.up

    def move_rel(self, dx, dy, dz, frame, **kw):
        self.calls.append(('move_rel', round(dx, 2), round(dy, 2), round(dz, 2),
                           round(kw.get('vel_mm_s') or 0.0, 1)))
        self.pose = [self.pose[0] + dx, self.pose[1] + dy, self.pose[2] + dz] + self.pose[3:]

    def move_joint_rel(self, joint, delta_deg, *, time_s=None, carrying=True):
        self.calls.append(('move_joint_rel', joint, round(delta_deg, 1), time_s))
        if joint == 6:
            self.j6 += delta_deg

    def move_joints(self, q, vel_deg_s, acc_deg_s2):
        self.calls.append(('move_joints', list(q), vel_deg_s, acc_deg_s2))
        self.j6 = q[5]

    def move_periodic(self, amp, period, repeat, ref='TOOL', atime=None, scale=True):
        self.calls.append(('periodic', list(amp), list(period), repeat, ref, scale))
        self.periodic = 3
        self.j6_min, self.j6_max = min(self.j6_min, self.j6 - amp[5]), max(self.j6_max, self.j6 + amp[5])
        self.j4 = self.j4_during

    def motion_done(self):
        if self.periodic > 0:
            self.periodic -= 1
            return False
        return True

    def stop_now(self):
        self.calls.append(('stop_now',))
        self.periodic = 0

    def joints(self):
        return [0.0, 0.0, 90.0, self.j4, 90.0, self.j6]

    def contact_down(self, max_depth, limit):
        self.calls.append(('contact_down', max_depth, limit))
        self.inserted = True
        self.pose[2] -= self.depth
        return self.depth, limit                 # 바닥을 찾은 깊이(찾기 구간 안에서)

    def read_force(self):
        if not self.inserted:
            return [0.0, 0.0, 2.0, 0.0, 0.0, 0.0]
        return [self.lateral, 0.0, 2.0 + self.press, 0.0, 0.0, 0.0]

    def force_off(self):
        self.calls.append(('force_off',))

    def safe_retreat(self):
        self.calls.append(('safe_retreat',))

    def is_halted(self):
        return self.halted

    def io_node(self):
        return self

    def get_logger(self):
        return self.logger

    def where(self):
        return list(self.pose)


@pytest.fixture
def cell(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    c = FakeCell()
    for name in ('cfg', 'move_to', 'move_rel', 'move_joint_rel', 'move_joints', 'move_periodic', 'motion_done',
                 'stop_now', 'contact_down', 'read_force', 'force_off', 'safe_retreat', 'io_node', 'is_halted',
                 'where', 'joints', 'grip_width'):
        monkeypatch.setattr(wipe.cc, name, getattr(c, name), raising=False)
    monkeypatch.setattr(wipe, '_tool_baseline_mm', None, raising=False)   # 다른 시험의 soap() 기준이 새지 않게
    return c


def _rels(calls):
    return [(c[1], c[2], c[3]) for c in calls if c[0] == 'move_rel']       # (dx, dy, dz)


# ------------------------------------------------------------------ soap
def test_soap_sponge_twists_then_updowns_then_goes_to_home(cell):
    """수세미(잡은 위치 X=273 < 문턱값 349) — 비틀기 3회 → 왕복 2회(둘 다 move_periodic·scale=False) → HOME 좌표로 직접."""
    assert cell.pose[0] == pytest.approx(SPONGE_X)                        # POSE0 기본값이 수세미 홀더 위치
    r = wipe.soap(3, 'BOWL')
    assert r.ok and r.code == OK
    assert ('move_to', 'SOAP', 'BOWL', None) not in cell.calls             # SOAP 자리로 안 간다

    periodics = [c for c in cell.calls if c[0] == 'periodic']
    assert len(periodics) == 2                                            # 비틀기 1번 + 왕복 1번(각각 move_periodic 한 번)

    twist = periodics[0]
    assert twist[1] == [0.0, 0.0, 0.0, 0.0, 0.0, 20.0]                    # amp — 6번 관절(rz)만
    assert twist[2] == [0.0, 0.0, 0.0, 0.0, 0.0, 1.0]                     # period
    assert twist[3] == 3 and twist[4] == 'TOOL' and twist[5] is False      # repeat · ref · scale=False

    updown = periodics[1]
    assert updown[1] == [0.0, 0.0, 5.0, 0.0, 0.0, 0.0]                    # amp — Z만
    assert updown[2] == [0.0, 0.0, 0.3, 0.0, 0.0, 0.0]                    # period
    assert updown[3] == 2 and updown[4] == 'TOOL' and updown[5] is False   # repeat · ref · scale=False

    rels = _rels(cell.calls)
    rise = [c for c in rels if c[2] == pytest.approx(HOME_Z - POSE0[2])]   # z 먼저(제자리 상승)
    assert len(rise) == 1 and rise[0][0] == 0.0 and rise[0][1] == 0.0
    move_xy = [c for c in rels if c[0] == pytest.approx(HOME_X - POSE0[0]) and c[1] == pytest.approx(HOME_Y - POSE0[1])]
    assert len(move_xy) == 1 and move_xy[0][2] == 0.0                      # 그다음 x·y만(수평)
    assert 'move_joints' not in [c[0] for c in cell.calls]                 # movej 없음(박진용 9/22 3차)
    assert cell.pose[0] == pytest.approx(HOME_X) and cell.pose[1] == pytest.approx(HOME_Y) and cell.pose[2] == pytest.approx(HOME_Z)


def test_soap_cup_position_goes_to_cup_top_instead_of_home(cell):
    """컵솔(잡은 위치 X=425 > 문턱값 349) — 같은 비틀기·왕복, 끝은 HOME이 아니라 z+40·y+140(컵 위)."""
    cell.pose[0] = BRUSH_X
    r = wipe.soap(3, 'CUP')
    assert r.ok and r.code == OK
    periodics = [c for c in cell.calls if c[0] == 'periodic']
    assert len(periodics) == 2                                             # 비틀기 + 왕복 — 그릇과 동일
    target_z = HOME_Z + CFG['f3']['wipe_cup']['over_cup_up_mm']
    target_y = HOME_Y + CFG['f3']['wipe_cup']['over_cup_dy_mm']
    assert cell.pose[0] == pytest.approx(HOME_X)
    assert cell.pose[1] == pytest.approx(target_y)
    assert cell.pose[2] == pytest.approx(target_z)


def test_soap_is_not_a_contact_motion(cell):
    """수조가 비어 있다 → 순응·힘제어·힘 감시가 없어야 한다(AGENTS 규칙 3)."""
    wipe.soap(2)
    names = [c[0] for c in cell.calls]
    assert 'contact_down' not in names and 'force_on' not in names and 'compliance_on' not in names
    assert names[-1] == 'force_off' and 'safe_retreat' not in names        # 성공했으면 이미 목표 위치 — 더 안 움직인다


def test_soap_count_is_ignored(cell):
    """9/22: count 는 이제 안 쓴다(횟수는 config 의 twist_cycles·updown_cycles) — 0 이어도 그대로 돈다."""
    r = wipe.soap(0)
    assert r.ok and len([c for c in cell.calls if c[0] == 'periodic']) == 2


def test_soap_timeout(cell):
    CFG['f3']['soap']['duration_s'] = -1
    try:
        r = wipe.soap(3)
    finally:
        CFG['f3']['soap']['duration_s'] = 60
    assert not r.ok and r.code == TIMEOUT
    names = [c[0] for c in cell.calls]
    assert 'safe_retreat' not in names                                    # 9/22 2차: safe_z_mm 대신 목표 위치로 후퇴
    rels = _rels(cell.calls)
    rise = [c for c in rels if c[2] == pytest.approx(HOME_Z - POSE0[2])]
    assert rise                                                           # 실패해도 목표 z 까지는 후퇴 시도


def test_soap_halt_does_not_auto_move(cell):
    cell.halted = True
    with pytest.raises(wipe.cc.MotionHalted):
        wipe.soap(3)
    assert 'safe_retreat' not in [c[0] for c in cell.calls]


def test_soap_detects_tool_lost_during_twist(cell, monkeypatch):
    """9/23: 비틀기 도는 중 폭이 기준(soap 시작 때 잰 값)보다 크게 벗어나면 TOOL_LOST."""
    def dropped():
        cell.width = 20.0 + 5.0                      # slip_tol_mm(1.0)보다 훨씬 크게 벗어남 — 실기 재현 값 참고
        if cell.periodic > 0:
            cell.periodic -= 1
            return False
        return True
    monkeypatch.setattr(wipe.cc, 'motion_done', dropped, raising=False)
    r = wipe.soap(3)
    assert not r.ok and r.code == TOOL_LOST


# ------------------------------------------------------------------ wipe_cup
# 돌려주는 insert_depth_mm = 컵 위에서 바닥까지 내려간 거리 = 빠른 하강 80 + 찾기 8 (가짜는 8 mm 에서 바닥).
DEPTH = 80.0 + 8.0


def _split(cell):
    """(닦기까지의 호출, 마지막 force_off 부터의 정리 호출)."""
    i = max(k for k, c in enumerate(cell.calls) if c[0] == 'force_off')
    return cell.calls[:i], cell.calls[i:]


def test_cup_does_not_seek_its_own_position(cell):
    """🔧 9/22 3차: wipe_cup 은 더 이상 스스로 위치를 찾지 않는다 — 호출되자마자 바로 하강한다(soap이 이미 데려다 놨다는 전제)."""
    wipe.wipe_cup()
    assert 'move_to' not in [c[0] for c in cell.calls]                     # HOME 등 어디로도 스스로 이동 안 함
    rels = _rels(cell.calls)
    assert rels[0] == (0.0, 0.0, -80.0)                                    # 첫 이동이 바로 빠른 하강(fast_down_mm)


def test_cup_returns_to_call_height_only(cell):
    """⑦ 솔을 곧게 뽑아 **호출된 자리 높이로만** — 수평 복귀·HOME 이동 없음(박진용 9/22 3차)."""
    wipe.wipe_cup()
    _work, back = _split(cell)
    assert 'move_to' not in [c[0] for c in back]                           # HOME으로 안 감
    rels = _rels(back)
    assert len(rels) == 1 and rels[0][0] == 0.0 and rels[0][1] == 0.0 and rels[0][2] > 0   # 곧게 뽑기 1번뿐
    assert cell.pose[2] == pytest.approx(POSE0[2])                         # 호출된 높이로 돌아왔다
    assert cell.pose[0] == pytest.approx(POSE0[0]) and cell.pose[1] == pytest.approx(POSE0[1])  # x·y는 안 움직였다


def test_cup_fast_then_finds_bottom_by_force(cell):
    """① 호출된 자리에서 fast_down_mm 만큼 빠르게 → ② 나머지는 힘으로 찾는다(시나리오 1·2)."""
    r = wipe.wipe_cup()
    assert r.ok and r.code == OK
    names = [c[0] for c in cell.calls]
    fast = _rels(cell.calls)[0]
    assert fast == (0.0, 0.0, -80.0)                                       # fast_down_mm
    assert ('contact_down', 40.0, 5.0) in cell.calls                       # find_max_mm · find_limit_n (insert_limit_n 15 아님)
    assert names.index('contact_down') < names.index('periodic')
    assert r.insert_depth_mm == pytest.approx(DEPTH)                       # 잰 값 — 바닥 위치를 미리 정하지 않는다


def _periodic(cell):
    return [c for c in cell.calls if c[0] == 'periodic']


def _work_rels(cell):
    i = max(k for k, c in enumerate(cell.calls) if c[0] == 'force_off')
    return [c[3] for c in cell.calls[:i] if c[0] == 'move_rel']            # dz 만


def test_cup_scrub_is_one_periodic_on_tool_z_and_rz(cell):
    """④⑤ Move Periodic 한 명령 · **TOOL** 기준 · z ±20 mm + rz(그리퍼 축 = 6번 조인트) ±180° · 같은 주기 6.3 s · 3 회.
    🚨 rx 칸은 실기에서 4번 조인트를 돌렸다(9/21) — rx·ry 칸은 0 이어야 한다."""
    wipe.wipe_cup()
    per = _periodic(cell)
    assert len(per) == 1
    _n, amp, period, repeat, ref, scale = per[0]
    assert amp == [0.0, 0.0, 20.0, 0.0, 0.0, 180.0] and period == [0.0, 0.0, 6.3, 0.0, 0.0, 6.3]
    assert repeat == 3 and ref == 'TOOL' and scale is False
    assert all((a != 0) == (t != 0) for a, t in zip(amp, period))          # 진폭 준 축은 주기도(오류 2.1218)


def test_cup_lowest_point_is_bottom_plus_lift(cell):
    """③ 가장 낮은 곳 = 바닥 + lift_mm(3). Periodic 은 가운데 기준 ±stroke 라 바닥 + 3 + stroke 에서 시작하고
    ⑥ 끝나면 stroke 만큼 내려서 가장 낮은 곳(바닥 + 3)에서 끝낸다."""
    wipe.wipe_cup()
    lift, stroke = CFG['f3']['wipe_cup']['lift_mm'], 20.0
    rels = _work_rels(cell)
    assert rels[-2] == pytest.approx(lift + stroke) and rels[-1] == pytest.approx(-stroke)
    assert rels[-2] + rels[-1] == pytest.approx(lift)                     # 끝 = 바닥 + 3


def test_cup_j6_stays_inside_limit(cell):
    wipe.wipe_cup()
    assert cell.j6_min == pytest.approx(21.0 - 180.0) and cell.j6_max == pytest.approx(21.0 + 180.0)


def test_cup_fast_moves_use_fast_speed(cell):
    """빠른 하강(−80)과 곧게 뽑기가 fast_vel_mm_s × vel_scale(0.3) = 54 mm/s 로 간다."""
    wipe.wipe_cup()
    calls = [c for c in cell.calls if c[0] == 'move_rel']
    fast = [c for c in calls if c[3] == pytest.approx(-80.0)]
    assert fast and fast[0][4] == pytest.approx(180.0 * 0.3)
    _work, back = _split(cell)
    rise = [c for c in back if c[0] == 'move_rel'][0]
    assert rise[3] > 0 and rise[4] == pytest.approx(180.0 * 0.3)


def test_spin_room():
    p = CFG['f3']['wipe_cup']
    wipe.spin_room(21.0, p)
    with pytest.raises(ValueError):
        wipe.spin_room(171.0, p)                                           # 171 + 180 = 351 > 350


def test_cup_no_room_to_spin_is_error_and_retreats(cell):
    cell.j6 = cell.j6_min = cell.j6_max = 200.0
    r = wipe.wipe_cup()
    assert not r.ok and r.code == ROBOT_ERROR
    assert _periodic(cell) == []
    _work, back = _split(cell)
    rels = _rels(back)
    assert rels and rels[-1][2] > 0                                        # 곧게 뽑아 호출된 높이로


def test_cup_stops_now_then_goes_home_if_j4_moves(cell):
    """🚨 세척 도는 중 4번 조인트가 1° 넘게 움직이면 **즉시 정지** → ROBOT_ERROR → 곧게 뽑아 호출된 높이로 복귀
    (수세미·솔 둘 다 물러서 그릇처럼 자동 복귀해도 된다 — 박진용 9/22, PR #56 리뷰 대체)."""
    cell.j4_during = 5.0
    r = wipe.wipe_cup()
    assert not r.ok and r.code == ROBOT_ERROR
    names = [c[0] for c in cell.calls]
    i = names.index('stop_now')
    assert names.index('periodic') < i
    assert names[i + 1] == 'force_off' and 'move_rel' in names[i + 1:]     # 정지 뒤에도 힘 끄고 곧게 복귀


def test_cup_stroke_shrinks_so_brush_stays_in(cell):
    CFG['f3']['wipe_cup']['tool']['clean_h_mm'] = 40.0
    try:
        wipe.wipe_cup()
    finally:
        CFG['f3']['wipe_cup']['tool']['clean_h_mm'] = 95
    lift = CFG['f3']['wipe_cup']['lift_mm']
    assert _periodic(cell)[0][1][2] == pytest.approx((40.0 - lift - 10.0) / 2)


def test_cup_no_bottom_found_is_error(cell):
    cell.depth = 40.0                                                      # find_max_mm 까지 내려가도 못 찾음
    r = wipe.wipe_cup()
    assert not r.ok and r.code == ROBOT_ERROR
    assert 'periodic' not in [c[0] for c in cell.calls]


def test_cup_press_over_limit_is_force_limit(cell):
    cell.press = 99.0
    r = wipe.wipe_cup()
    assert not r.ok and r.code == FORCE_LIMIT


def test_cup_lateral_over_limit_is_force_limit(cell):
    cell.lateral = 99.0
    r = wipe.wipe_cup()
    assert not r.ok and r.code == FORCE_LIMIT


def test_cup_over_time_is_timeout(cell):
    CFG['f3']['wipe_cup']['duration_s'] = -1
    try:
        r = wipe.wipe_cup()
    finally:
        CFG['f3']['wipe_cup']['duration_s'] = 120
    assert not r.ok and r.code == TIMEOUT


def test_cup_halt_does_not_auto_move(cell):
    """강제정지 뒤에는 로봇 위치를 모른다 → 힘만 끄고 움직이지 않는다(9/21 케이블 꼬임 사고)."""
    cell.halted = True
    with pytest.raises(wipe.cc.MotionHalted):
        wipe.wipe_cup()
    assert [c[0] for c in cell.calls] == ['stop_now', 'force_off']         # 즉시 정지 → 끄기만, 움직이지 않는다


def test_cup_logs_depth_and_saves_force_log(cell):
    r = wipe.wipe_cup()
    assert any('바닥' in m for lvl, m in cell.logger.lines if lvl == 'info')
    assert r.force_log_path.endswith('.csv')


# ── 힘 상한·시간 초과면 남은 주기 운동을 먼저 즉시 정지(E60) — 정리의 동작 끝 대기(mwait)가 주기 운동을 끝까지 기다리지 않게
def _with_wait(cell, monkeypatch):
    """가짜 wait_done — 주기 운동이 아직 도는데 부르면(=끝까지 기다림) 표시해 둔다."""
    cell.waited_while_moving = False

    def wait_done():
        cell.calls.append(('mwait',))
        if cell.periodic > 0:
            cell.waited_while_moving = True
            cell.periodic = 0
    monkeypatch.setattr(wipe.cc, 'wait_done', wait_done, raising=False)
    return cell


def _press_up_after_periodic(cell, monkeypatch, attr='press'):
    real = cell.move_periodic

    def periodic(*a, **kw):
        real(*a, **kw)
        setattr(cell, attr, 99.0)                            # 주기 운동이 시작된 뒤에 힘이 튄다
    monkeypatch.setattr(wipe.cc, 'move_periodic', periodic, raising=False)


def test_cup_force_limit_in_periodic_stops_now_before_wait_and_force_off(cell, monkeypatch):
    _with_wait(cell, monkeypatch)
    _press_up_after_periodic(cell, monkeypatch)
    seen = {}
    real_stop = cell.stop_now

    def stop_now():
        seen['periodic_running'] = cell.periodic > 0
        real_stop()
    monkeypatch.setattr(wipe.cc, 'stop_now', stop_now, raising=False)
    r = wipe.wipe_cup()
    n = [c[0] for c in cell.calls]
    assert r.code == FORCE_LIMIT and n.count('stop_now') == 1 and seen['periodic_running']
    i = n.index('stop_now')
    assert n.index('periodic') < i and n[i + 1] == 'force_off' and 'mwait' in n[i + 1:]
    assert 'mwait' not in n[n.index('periodic'):i] and not cell.waited_while_moving
    assert _rels(cell.calls)[-1][2] > 0                      # 곧게 호출된 높이로


def test_cup_lateral_limit_in_periodic_stops_now_first(cell, monkeypatch):
    _with_wait(cell, monkeypatch)
    _press_up_after_periodic(cell, monkeypatch, attr='lateral')
    r = wipe.wipe_cup()
    n = [c[0] for c in cell.calls]
    i = n.index('stop_now')
    assert r.code == FORCE_LIMIT and n.count('stop_now') == 1 and n[i + 1] == 'force_off'
    assert 'mwait' not in n[n.index('periodic'):i] and not cell.waited_while_moving


def test_cup_timeout_stops_before_wait_and_force_off(cell, monkeypatch):
    """주기 운동 중 시간 초과는 세척 루프가 이미 한 번 멈춘다 — 정리에서 한 번 더(이미 멈춘 로봇에 정지는 무해) → 힘 끄기."""
    _with_wait(cell, monkeypatch)
    CFG['f3']['wipe_cup']['duration_s'] = -1
    try:
        r = wipe.wipe_cup()
    finally:
        CFG['f3']['wipe_cup']['duration_s'] = 120
    n = [c[0] for c in cell.calls]
    assert r.code == TIMEOUT and n.count('stop_now') == 2 and n[n.index('force_off') - 1] == 'stop_now'
    assert 'mwait' not in n[n.index('periodic'):n.index('stop_now')] and not cell.waited_while_moving


def test_cup_normal_end_has_no_stop_now(cell, monkeypatch):
    _with_wait(cell, monkeypatch)
    r = wipe.wipe_cup()
    assert r.ok and 'stop_now' not in [c[0] for c in cell.calls]


def test_cup_joint_guard_keeps_single_stop(cell, monkeypatch):
    _with_wait(cell, monkeypatch)
    cell.j4_during = 5.0
    r = wipe.wipe_cup()
    assert r.code == ROBOT_ERROR and [c[0] for c in cell.calls].count('stop_now') == 1


def test_cup_tool_lost_in_periodic_keeps_single_stop_and_does_not_rise(cell, monkeypatch):
    _with_wait(cell, monkeypatch)
    _press_up_after_periodic(cell, monkeypatch, attr='width')    # 주기 운동 시작 뒤 폭이 99 mm = 놓침
    r = wipe.wipe_cup()
    n = [c[0] for c in cell.calls]
    assert r.code == TOOL_LOST and n.count('stop_now') == 1 and 'mwait' not in n[n.index('stop_now'):]

