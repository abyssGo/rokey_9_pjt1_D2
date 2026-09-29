"""F1-01 move_to · 일반 place · F1-03 tool — 가짜 cobot_common 으로 로봇 없이 돈다.  실행: python3 -m pytest -q src/f1_handling

보는 것: 공용 함수를 **어떤 순서·인자로** 부르는가 · 실패하면 **놓지 않는가**(공중에서 떨어뜨리지 않는다) · 예외를 삼키지 않는가.
"""
import pytest

from cobot_api import PlaceResult, Result, ToolResult
from f1_handling import handling


class MoveIncomplete(RuntimeError):
    pass


class ForceLimitError(RuntimeError):
    pass


class MotionTimeout(RuntimeError):
    pass


class FakeCC:
    """cobot_common 흉내 — 부른 것을 순서대로 적어 둔다."""
    MoveIncomplete = MoveIncomplete
    ForceLimitError = ForceLimitError
    MotionTimeout = MotionTimeout

    def __init__(self):
        self.calls = []
        self.up = {('SPONGE_BED_B', 'place'): 147.7, ('SPONGE_BED_C', 'place'): 188.2}      # 접근점 → 끝점 높이(cell.yaml 값)
        self.fail_on = None                                                                 # 이 이름의 호출에서 예외
        self.grip_result = 40.5                                                             # grip() 이 돌려줄 실제 폭(드라이버 값 — 영점 10.5 + 툴 30)
        self.contact = (3.0, 8.0)                                                           # contact_down 이 돌려줄 (깊이, 힘)
        self.contact_raises = None
        self.retreat_raises = None
        self.conf = {'f1': {'place_clear_mm': 100, 'tool_clear_mm': 100,
                            'tool_return_depth_mm': 20, 'tool_return_contact_n': 8, 'contact_timeout_ref_mm': 20},
                     'cell': {'beds': {'SPONGE_BED_B': {}, 'SPONGE_BED_C': {}},
                              'motion': {'vel_tcp_max_mm_s': 400, 'acc_tcp_max_mm_s2': 800}, 'limits': {'vel_carry_pct': 30, 'vel_free_pct': 60, 'timeout_s': 10},
                              'presets': {'SPONGE': {'grip_width_mm': 30, 'grip_zero_mm': 10.5, 'grip_force_n': 30, 'width_tol_mm': 3},
                                          'BRUSH': {'grip_width_mm': 30, 'grip_zero_mm': 10.5, 'grip_force_n': 30, 'width_tol_mm': 3}}}}

    def cfg(self):
        return self.conf

    def _note(self, name, *args):
        self.calls.append((name, *args))
        if self.fail_on == name or self.fail_on == (name, len([c for c in self.calls if c[0] == name])):
            raise MoveIncomplete(f'{name} 이 도중에 멈췄다')

    def move_to(self, station, carrying, kind=None, point=None, **kw):     # kw = j6_period(툴 홀더 J6 동치각)
        self._note('move_to', station, carrying, kind, point, *([kw] if kw else []))
        return self.up.get((station, point), 0.0)

    def move_rel(self, dx, dy, dz, frame, **kw):                 # kw = vel_mm_s(마지막 완충 구간)
        self._note('move_rel', dx, dy, dz, frame, *([kw] if kw else []))

    def where(self):                                                 # 집은 자리(RETURN 역순용)
        self._note('where')
        return [273.6, -222.9, 65.2, 128.2, 180.0, -52.0]

    def move_pose(self, pose, vel_mm_s, vel_deg_s, acc_mm_s2, acc_deg_s2):
        self._note('move_pose', [round(v, 1) for v in pose])

    def release(self):
        self._note('release')

    def safe_retreat(self):
        self._note('safe_retreat')
        if self.retreat_raises is not None:
            raise self.retreat_raises('후퇴 실패')

    def io_node(self):
        return self

    def grip(self, width, force):
        self._note('grip', width, force)
        return self.grip_result

    def force_off(self):
        self._note('force_off')

    def contact_down(self, max_depth, limit, timeout_s=None, step_mm=None):   # step_mm = 마지막 감시 구간 걸음
        self._note('contact_down', max_depth, limit, *([step_mm] if step_mm is not None else []))
        if self.contact_raises is not None:
            raise self.contact_raises('시험')
        return self.contact


@pytest.fixture
def cc(monkeypatch):
    fake = FakeCC()
    monkeypatch.setattr(handling, 'cc', fake)
    handling._LAST_PICK.clear()                        # 다른 테스트의 PICK 이 남긴 자리가 새지 않게
    yield fake
    handling._LAST_PICK.clear()


# ------------------------------------------------------------------ move_to
def test_move_to_wraps_cc_move_to(cc):
    r = handling.move_to('WEIGH', True, 'CUP')
    assert type(r) is Result and r.ok and r.code == 'OK'
    assert cc.calls == [('move_to', 'WEIGH', True, 'CUP', None)]
    handling.move_to('HOME', False)                                         # kind 는 생략할 수 있다
    assert cc.calls[-1] == ('move_to', 'HOME', False, None, None)


def test_move_to_lets_motion_errors_through(cc):
    """도착하지 못했으면(cc.MoveIncomplete) 삼키지 않는다 — flow.call() 이 ROBOT_ERROR 로 바꾸고 문구를 HMI 에 싣는다."""
    cc.fail_on = 'move_to'
    with pytest.raises(MoveIncomplete):
        handling.move_to('WASTE', True, 'BOWL')


# ------------------------------------------------------------------ place
def test_place_on_sponge_bed_descends_releases_and_comes_back_up(cc):
    r = handling.place('SPONGE_BED_B')
    assert isinstance(r, PlaceResult) and r.ok and r.offset_mm == 0.0
    assert cc.calls == [('move_to', 'SPONGE_BED_B', True, None, 'place'),   # ① 접근점 — 스펀지 홈은 point='place', 들고 있으니 저속
                        ('move_rel', 0.0, 0.0, -147.7, 'BASE'),             # ② 끝점까지 곧게
                        ('release',),                                       # ③
                        ('move_rel', 0.0, 0.0, 147.7, 'BASE')]              # ④ 내려간 만큼 되올라온다


def test_place_without_approach_point_lifts_by_clear_height(cc):
    r = handling.place('ISOLATE', 'CUP')                                    # 종류별 자리 · 접근점 없음 → 끝점까지 곧장
    assert r.ok
    assert cc.calls == [('move_to', 'ISOLATE', True, 'CUP', None), ('release',), ('move_rel', 0.0, 0.0, 100.0, 'BASE')]


@pytest.mark.parametrize('fail_on', ['move_to', ('move_rel', 1)])
def test_place_never_releases_after_a_failed_move(cc, fail_on):
    """접근이나 하강이 도중에 멈추면 **쥔 채로** 예외를 올린다 — 공중에서 놓지 않는다."""
    cc.fail_on = fail_on
    with pytest.raises(MoveIncomplete):
        handling.place('SPONGE_BED_C')
    assert ('release',) not in cc.calls


def test_place_checks_its_setting_before_moving(cc):
    del cc.conf['f1']['place_clear_mm']
    with pytest.raises(KeyError):
        handling.place('ISOLATE', 'BOWL')
    assert cc.calls == []                                                   # 값이 없으면 로봇에 손대지 않는다


def test_place_works_three_times_in_a_row(cc):
    for _ in range(3):                                                      # SDD §3.2 ⑧ — "첫 번째만 되는" 결함 방지
        assert handling.place('SPONGE_BED_B').ok
    assert [c[0] for c in cc.calls] == ['move_to', 'move_rel', 'release', 'move_rel'] * 3


# ------------------------------------------------------------------ F1-03 tool
def test_tool_pick_grips_at_the_holder_and_stays_there(cc):
    """E35: 잡은 자리에서 끝난다 — 빼내지 않는다(F3 soap 이 그 자리에서 비틀고 올라간다)."""
    r = handling.tool('SPONGE', 'PICK')
    assert isinstance(r, ToolResult) and r.ok and r.width_mm == 40.5      # 돌려주는 폭은 드라이버 값 그대로(E16 — 판정만 영점을 뺀다)
    assert cc.calls == [('move_to', 'TOOL_SPONGE', False, None, 'pick'),   # 빈손으로 집는 자세까지 (관절 자세 → 남은 높이 0)
                        ('grip', 34.5, 30.0),                              # 영점 10.5 + (기대 30 − 2 × 허용오차 3) · 프리셋 힘 (E16)
                        ('where',)]                                        # 집은 자리를 기억(RETURN 역순용) · 빼내지 않는다


def test_tool_pick_reverses_to_the_last_pick_spot_when_repicked(cc):
    """E37 — 이미 한 번 집은 적 있으면(TOOL_LOST 뒤 재PICK) 홀더 자세로 곧장 가지 않고
    처음 집었던 **정확한 자리**로 곧장 내려가 다시 잡는다(힘 감시 없이 — 실기: contact_down 은
    상대할 저항이 없어 TIMEOUT). _tool_return 과 같은 역순 패턴이지만 마지막은 더듬지 않는다."""
    assert handling.tool('SPONGE', 'PICK').ok            # 첫 PICK — _LAST_PICK 을 남긴다
    cc.calls.clear()
    r = handling.tool('SPONGE', 'PICK')                   # 재PICK — 역순 패턴을 타야 한다
    assert r.ok
    assert cc.calls == [('release',),                                              # 놓친 폭에서 바로 grip 하면 헛잡음(실기)
                        ('move_pose', [273.6, -222.9, 165.2, 128.2, 180.0, -52.0]),  # 집은 자리 + clear(100) 위로
                        ('move_pose', [273.6, -222.9, 65.2, 128.2, 180.0, -52.0]),   # 그 정확한 자리로 곧장 하강
                        ('grip', 34.5, 30.0),
                        ('where',)]
    assert 'move_to' not in [c[0] for c in cc.calls]      # 홀더 자세로 곧장 가지 않는다


def test_tool_pick_descends_and_returns_when_the_holder_has_an_approach_point(cc):
    cc.up[('TOOL_BRUSH', 'pick')] = 40.0                                   # 홀더 재티칭(CELL-04b)으로 접근점이 생기면
    assert handling.tool('BRUSH', 'PICK').ok
    assert [c[0] for c in cc.calls] == ['move_to', 'move_rel', 'grip', 'where']   # 접근점 → 하강 → 쥠 · 올라오지 않는다
    assert cc.calls[1] == ('move_rel', 0.0, 0.0, -40.0, 'BASE')


def test_tool_pick_that_missed_leaves_the_tool_in_the_holder(cc):
    cc.grip_result = 34.5                                                  # 빈손 — 명령한 폭에서 그대로 멈췄다(영점 뺀 24 ≠ 30 ± 3)
    r = handling.tool('SPONGE', 'PICK')
    assert not r.ok and r.code == 'TOOL_FAIL' and r.width_mm == 34.5
    assert [c[0] for c in cc.calls] == ['move_to', 'grip', 'release', 'safe_retreat']   # 놓고 물러난다 — 빼내지 않는다


def test_tool_return_reverses_the_pick_when_this_program_picked(cc):
    """E35: 같은 프로그램이 집었으면 집은 자리 위(clear) → 곧게 내려 놓음 → 올라옴. 바닥 찾기 없음."""
    assert handling.tool('BRUSH', 'PICK').ok
    cc.calls.clear()
    r = handling.tool('BRUSH', 'RETURN')
    assert r.ok
    assert cc.calls == [('move_pose', [273.6, -222.9, 165.2, 128.2, 180.0, -52.0]),   # 집은 자리 + clear 100
                        ('move_rel', 0.0, 0.0, -80.0, 'BASE'),                        # 자유 하강 (clear − tool_return_depth_mm 20)
                        ('contact_down', 20.0, 8.0),                                  # 마지막 20 mm 는 힘 감시
                        ('release',),
                        ('move_rel', 0.0, 0.0, 83.0, 'BASE')]                         # 80 + 닿은 깊이 3
    assert 'BRUSH' not in handling._LAST_PICK                               # 한 번 쓰면 잊는다


def test_tool_return_depth_zero_goes_straight_to_pick_pose_and_releases(cc):
    """E44: tool_return_depth_mm 0 이면 힘 감시 없이 집은 자리로 곧게 내려가 놓고 올라온다(contact_down 없음)."""
    cc.conf['f1']['tool_return_depth_mm'] = 0
    handling.tool('SPONGE', 'PICK')
    cc.calls.clear()
    r = handling.tool('SPONGE', 'RETURN')
    assert r.ok
    names = [c[0] for c in cc.calls]
    assert 'contact_down' not in names
    assert names[names.index('release') - 1] == 'move_rel'                  # 내려간 뒤 놓는다
    rel = [c for c in cc.calls if c[0] == 'move_rel']
    assert rel[0][3] == pytest.approx(-100.0) and rel[-1][3] == pytest.approx(100.0)   # clear 만큼 내려가고 다시 올라옴


def test_tool_return_finds_the_bottom_then_releases(cc):
    """이 프로그램이 집지 않은 툴(집은 자리를 모름) → 옛 방식: 티칭한 return 자세 + 바닥 찾기."""
    handling._LAST_PICK.clear()
    r = handling.tool('BRUSH', 'RETURN')
    assert r.ok
    assert cc.calls == [('move_to', 'TOOL_BRUSH', True, None, 'return'),   # 툴을 들고 간다
                        ('contact_down', 20.0, 8.0),                       # 최대 깊이 tool_return_depth_mm · 힘 tool_return_contact_n
                        ('release',),
                        ('move_rel', 0.0, 0.0, 103.0, 'BASE')]             # 내려간 3 + tool_clear_mm 100


def test_tool_return_uses_the_approach_height_as_the_search_depth(cc):
    cc.up[('TOOL_SPONGE', 'return')] = 12.0
    cc.contact = (5.0, 8.0)
    assert handling.tool('SPONGE', 'RETURN').ok
    assert cc.calls[1] == ('contact_down', 12.0, 8.0)                      # 접근점까지의 높이만큼만 찾는다
    assert cc.calls[-1] == ('move_rel', 0.0, 0.0, 5.0, 'BASE')             # 접근점으로 되올라온다(이미 충분히 높다)


def test_tool_return_never_releases_when_the_bottom_was_not_found(cc):
    """🚨 최대 깊이까지 내려가도 안 닿았다 = 홀더가 거기 없다 → 공중에서 툴을 놓지 않는다."""
    cc.contact = (20.0, 1.0)                                               # depth >= budget(20)
    r = handling.tool('SPONGE', 'RETURN')
    assert not r.ok and r.code == 'TOOL_FAIL'
    assert ('release',) not in cc.calls and cc.calls[-1] == ('safe_retreat',)


@pytest.mark.parametrize('exc,code', [(ForceLimitError, 'FORCE_LIMIT'), (MotionTimeout, 'TIMEOUT')])
def test_tool_return_maps_contact_failures_to_codes_and_retreats(cc, exc, code):
    cc.contact_raises = exc
    r = handling.tool('SPONGE', 'RETURN')
    assert not r.ok and r.code == code
    assert ('release',) not in cc.calls and cc.calls[-1] == ('safe_retreat',)


@pytest.mark.parametrize('args', [('SPONGE', 'PICK'), ('BRUSH', 'RETURN')])
def test_tool_lets_motion_errors_through(cc, args):
    cc.fail_on = 'move_to'
    with pytest.raises(MoveIncomplete):
        handling.tool(*args)
    assert ('release',) not in cc.calls                                    # 쥔 채로 올린다


@pytest.mark.parametrize('args', [('MOP', 'PICK'), ('SPONGE', 'WAVE')])
def test_tool_rejects_unknown_names_without_moving(cc, args):
    with pytest.raises(ValueError):
        handling.tool(*args)
    assert cc.calls == []


@pytest.mark.parametrize('drop', ['tool_clear_mm', 'tool_return_depth_mm'])
def test_tool_checks_its_settings_before_moving(cc, drop):
    del cc.conf['f1'][drop]
    with pytest.raises(KeyError):
        handling.tool('SPONGE', 'RETURN')
    assert cc.calls == []                                                  # 값이 없으면 로봇에 손대지 않는다


def test_tool_without_preset_does_not_move(cc):
    del cc.conf['cell']['presets']['SPONGE']
    with pytest.raises(KeyError):
        handling.tool('SPONGE', 'PICK')
    assert cc.calls == []


def test_tool_pick_and_return_three_times_in_a_row(cc):
    for _ in range(3):                                                     # SDD §3.2 ⑧
        assert handling.tool('SPONGE', 'PICK').ok and handling.tool('SPONGE', 'RETURN').ok
    assert [c[0] for c in cc.calls] == ['move_to', 'grip', 'where', 'move_pose', 'move_rel', 'contact_down', 'release', 'move_rel'] * 3


def test_tool_keeps_its_failure_code_even_if_the_retreat_fails(cc):
    """후퇴가 실패해도 TOOL_FAIL 을 잃지 않는다 — 로그만 남기고 코드를 돌려준다(f2 sense.py 와 같은 방식)."""
    cc.grip_result = 34.5
    cc.retreat_raises = KeyError
    r = handling.tool('SPONGE', 'PICK')
    assert not r.ok and r.code == 'TOOL_FAIL' and r.width_mm == 34.5


@pytest.mark.parametrize('key', ['grip_width_mm', 'grip_zero_mm', 'grip_force_n', 'width_tol_mm'])
def test_tool_pick_with_an_unfilled_preset_does_not_move(cc, key):
    """골격 cell.yaml 은 값이 None 이다 — TypeError 가 아니라 어느 키인지 알려 주는 KeyError 여야 한다."""
    cc.conf['cell']['presets']['SPONGE'][key] = None
    with pytest.raises(KeyError, match=key):
        handling.tool('SPONGE', 'PICK')
    assert cc.calls == []


def test_tool_pick_reads_the_width_without_the_zero_offset(cc):
    """결정 E16 D-A — 드라이버는 빈손으로 꽉 닫아도 10.5 를 읽는다. 영점을 빼고 판정한다."""
    cc.grip_result = 10.5 + 31.0                                           # 영점 뺀 31 — 30 ± 3 안
    assert handling.tool('SPONGE', 'PICK').ok
    cc.calls.clear()
    cc.grip_result = 31.0                                                  # 영점을 안 뺐다면 통과했을 값 — 영점 뺀 20.5 는 밖
    assert handling.tool('SPONGE', 'PICK').code == 'TOOL_FAIL'


def test_tool_pick_with_a_fixed_width_closes_only_that_far_and_skips_the_check(cc):
    """툴이 물러서 고정 폭(E19 방식)으로 정하면 그 폭까지만 닫고 폭 판정을 하지 않는다 — V-08 에서 정한다."""
    cc.conf['cell']['presets']['SPONGE'] = {'grip_target_mm': 36.0, 'grip_force_n': 5}
    cc.grip_result = 36.0                                                  # 빈손과 구분이 안 되는 값이어도
    r = handling.tool('SPONGE', 'PICK')
    assert r.ok and r.width_mm == 36.0
    assert cc.calls[1] == ('grip', 36.0, 5.0)


# ------------------------------------------------------------------ 툴 홀더 J6 동치각 · 반납 마지막 구간 한 걸음
def test_tool_pick_uses_the_nearest_j6_for_a_symmetric_tool(cc):
    cc.conf['cell']['presets']['SPONGE']['j6_symmetric'] = True
    handling.tool('SPONGE', 'PICK')
    assert ('move_to', 'TOOL_SPONGE', False, None, 'pick', {'j6_period': 180.0}) in cc.calls


def test_tool_pick_goes_to_the_taught_j6_when_the_tool_is_not_marked_symmetric(cc):
    handling.tool('BRUSH', 'PICK')
    assert ('move_to', 'TOOL_BRUSH', False, None, 'pick') in cc.calls


def test_tool_return_watches_the_last_millimetres_in_one_step(cc):
    cc.conf['f1']['tool_return_depth_mm'] = 5
    cc.conf['f1']['watch_step_mm'] = 5
    cc.contact = (5.0, 2.0)
    handling.tool('SPONGE', 'PICK')
    handling.tool('SPONGE', 'RETURN')
    assert ('contact_down', 5.0, 8.0, 5.0) in cc.calls                           # (감시 깊이, 접촉 힘, 걸음)


def test_tool_return_step_never_exceeds_the_watch_depth(cc):
    cc.conf['f1']['tool_return_depth_mm'] = 3
    cc.conf['f1']['watch_step_mm'] = 5
    cc.contact = (3.0, 2.0)
    handling.tool('SPONGE', 'PICK')
    handling.tool('SPONGE', 'RETURN')
    assert ('contact_down', 3.0, 8.0, 3.0) in cc.calls


def test_tool_return_without_watch_step_setting_uses_the_default_step(cc):
    cc.conf['f1']['tool_return_depth_mm'] = 5
    cc.contact = (5.0, 2.0)
    handling.tool('SPONGE', 'PICK')
    handling.tool('SPONGE', 'RETURN')
    assert ('contact_down', 5.0, 8.0) in cc.calls                                # step_mm 없이 → force 기본 걸음


# ------------------------------------------------------------------ E44 — 곧게 내려 놓기 · 마지막 land_slow_mm 완충
def test_place_descends_in_one_go_when_no_soft_landing_is_set(cc):
    handling.place('SPONGE_BED_B')
    assert ('move_rel', 0.0, 0.0, -147.7, 'BASE') in cc.calls                    # 한 구간


def test_place_slows_only_the_last_millimetres_when_soft_landing_is_set(cc):
    cc.conf['f1']['land_slow_mm'] = 15
    cc.conf['f1']['land_vel_mm_s'] = 30
    handling.place('SPONGE_BED_B')
    rel = [c for c in cc.calls if c[0] == 'move_rel']
    assert rel[0][1:4] == (0.0, 0.0, pytest.approx(-132.7)) and len(rel[0]) == 5      # 빠르게 147.7 − 15
    assert rel[1][1:4] == (0.0, 0.0, -15.0) and rel[1][5] == {'vel_mm_s': 30.0}       # 마지막 15 mm 는 30 mm/s
    assert cc.calls.index(rel[1]) < cc.calls.index(('release',))                      # 그 뒤 놓는다


def test_tool_return_depth_zero_uses_the_soft_landing_and_releases_at_the_spot(cc):
    cc.conf['f1']['tool_return_depth_mm'] = 0
    cc.conf['f1']['land_slow_mm'] = 15
    handling.tool('SPONGE', 'PICK')
    cc.calls.clear()
    handling.tool('SPONGE', 'RETURN')
    names = [c[0] for c in cc.calls]
    assert 'contact_down' not in names and 'force_off' not in names               # 힘 감시·순응 없음
    rel = [c for c in cc.calls if c[0] == 'move_rel']
    assert rel[0][3] == pytest.approx(-85.0) and rel[1][3] == -15.0 and rel[1][5] == {'vel_mm_s': 30.0}
    assert names.index('release') > cc.calls.index(rel[1]) and rel[2][3] == 100.0   # 놓고 → 곧게 올라온다
