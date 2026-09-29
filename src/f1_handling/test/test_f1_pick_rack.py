"""F1-02 pick · F1-04 rack_place — 가짜 cobot_common 으로 로봇 없이.  실행: python3 -m pytest -q src/f1_handling

보는 것: 공용 함수를 **어떤 순서·인자로** 부르는가 · 빈손이면 놓고 다음 슬롯 → EMPTY_ZONE · 재파지 빈손은 GRIP_FAIL ·
삽입이 걸리면 들고 되올라와 RACK_JAM · 힘 상한/시간 초과는 코드로 · 이동 실패는 삼키지 않는다.
(9/22 민범진 이식 — PM 승인 · 경로는 한석형 rig_bowl_scenario_real.py)
"""
import pytest

from cobot_api import EMPTY_ZONE, FORCE_LIMIT, GRIP_FAIL, RACK_JAM, TIMEOUT, PickResult, Result
from cobot_common.force import ForceLimitError, MotionTimeout
from f1_handling import handling


class MoveIncomplete(RuntimeError):
    pass


class _Log:
    def info(self, m): pass
    def warn(self, m): pass
    def error(self, m): pass


class FakeCC:
    """cobot_common 흉내 — 부른 것을 순서대로 적어 둔다. 그리퍼 폭·접촉 결과는 미리 정해 준다."""
    MoveIncomplete = MoveIncomplete

    def __init__(self, grip_widths=(13.0,), contact=(30.0, 3.0), z=150.0):
        self.calls = []
        self.up = {('RET_B', 1): 112.9, ('RET_C', 1): 168.16, ('SPONGE_BED_B', 'place'): 147.7,
                   ('RACK_B1', None): 100.0, ('RACK_C1', None): 92.0}
        self.grip_widths = list(grip_widths)          # cc.grip 이 차례로 돌려줄 실제 폭(드라이버 값)
        self.contact = contact                        # cc.contact_down → (depth, force)
        self.contact_raises = None
        self.z = z
        self.fail_on = None
        self.conf = {
            'f1': {'place_clear_mm': 100, 'insert_approach_mm': 30, 'contact_timeout_ref_mm': 20},
            'cell': {
                'limits': {'insert_limit_n': 15, 'timeout_s': 10},
                'presets': {'BOWL': {'grip_width_mm': 2.15, 'grip_zero_mm': 10.58, 'grip_force_n': 20, 'width_tol_mm': 0.6},
                            'CUP': {'grip_target_mm': 76.0, 'grip_zero_mm': 10.58, 'grip_force_n': 5}},
                'zones': {'RET_B': {'slots': [{'approach_posx': [0] * 6, 'posx': [0] * 6}]},
                          'RET_C': {'slots': [{'approach_posx': [0] * 6, 'posx': [0] * 6}]},
                          'RET_X': {'slots': [{'posx': [0] * 6}, {'posx': [0] * 6}]}},        # 접근점 없는 슬롯 2개
                'beds': {'SPONGE_BED_B': {}, 'SPONGE_BED_C': {}},
                'rack': {'cup_entry_z_mm': 250.0, 'seat_tol_mm': 3.0,
                         'slots': {'RACK_B1': {'via': 'RACK_B1_VIA', 'approach_posx': [300, 600, 400, 0, 0, 0], 'exit_rel_mm': [[0, -25, 0], [0, 0, 100]]},
                                   'RACK_C1': {'via': 'RACK_C_VIA', 'approach_posx': [250, 470, 350, 0, 0, 0], 'exit_rel_mm': [[0, 0, 92], [0, -117.21, 0]]}}},
            },
        }

    def cfg(self): return self.conf
    def io_node(self): return type('N', (), {'get_logger': staticmethod(lambda: _Log())})()

    def _note(self, name, *args):
        self.calls.append((name, *args))
        if self.fail_on == name or self.fail_on == (name, len([c for c in self.calls if c[0] == name])):
            raise MoveIncomplete(f'{name} 이 도중에 멈췄다')

    def move_to(self, station, carrying, kind=None, point=None, **kw):     # 🆕 9/23 kw = j6_period(툴 홀더 J6 동치각)
        self._note('move_to', station, carrying, kind, point, *([kw] if kw else []))
        return self.up.get((station, point), 0.0)

    def move_rel(self, dx, dy, dz, frame, **kw):
        self._note('move_rel', dx, dy, dz, frame, *([kw] if kw else [])); self.z += dz   # 🆕 9/24 kw(vel_mm_s 완충 구간)도 적는다

    def release(self): self._note('release')
    def set_grip_preset(self, name): self._note('set_grip_preset', name)
    def force_off(self): self._note('force_off')
    def safe_retreat(self): self._note('safe_retreat')            # Z 만 safe_z 로 (가짜 — 높이 셈은 안 한다)
    def where(self): return [0.0, 0.0, self.z, 0.0, 0.0, 0.0]

    def grip(self, width, force):
        self._note('grip', width, force)
        return self.grip_widths.pop(0) if self.grip_widths else 13.0

    def contact_down(self, max_depth, limit, timeout_s=None, step_mm=None):   # 🆕 9/23 step_mm = 마지막 감시 구간 걸음
        self._note('contact_down', max_depth, limit, *([step_mm] if step_mm is not None else []))
        if self.contact_raises:
            raise self.contact_raises
        self.z -= float(self.contact[0])                          # 🔄 9/23 내려간 깊이만큼 z 도 내린다(재파지 접근점 시험)
        return self.contact

    def names(self): return [c[0] for c in self.calls]
    def of(self, name): return [c for c in self.calls if c[0] == name]


@pytest.fixture
def cc(monkeypatch):
    fake = FakeCC()
    monkeypatch.setattr(handling, 'cc', fake)
    return fake


# ────────────────────────────────── pick — 반납 구역
def test_pick_bowl_success_order(cc):
    """열기 → 접근점 → 곧게 하강 → 쥐기(영점+기대−2tol · 20 N) → 판정 OK → 접근 높이로 되올라와 끝. width_mm 는 영점 뺀 폭."""
    r = handling.pick('RET_B', 'BOWL')
    assert r.ok and r.attempts == 1 and r.width_mm == pytest.approx(13.0 - 10.58)
    assert cc.names() == ['release', 'move_to', 'move_rel', 'grip', 'move_rel']
    assert cc.of('move_to')[0] == ('move_to', 'RET_B', False, 'BOWL', 1)
    assert cc.of('move_rel')[0][3] == pytest.approx(-112.9) and cc.of('move_rel')[1][3] == pytest.approx(+112.9)
    assert cc.of('grip')[0] == ('grip', pytest.approx(10.58 + 2.15 - 1.2), 20.0)


def test_pick_bowl_empty_hand_goes_to_next_slot_then_empty_zone(cc):
    """빈손(폭 10.6 → 영점 뺀 0.0)이면 놓고 되올라와 다음 슬롯 · 다 돌면 EMPTY_ZONE(attempts = 슬롯 수)."""
    cc.grip_widths = [10.6, 10.7]
    r = handling.pick('RET_X', 'BOWL')
    assert not r.ok and r.code == EMPTY_ZONE and r.attempts == 2
    assert cc.names().count('grip') == 2 and cc.names().count('release') == 3     # 시작 1 + 헛잡음 2
    assert [c[4] for c in cc.of('move_to')] == [1, 2]


def test_pick_bowl_wide_grip_is_a_miss(cc):
    """폭이 기대 + 허용오차를 넘어도(잘못 잡음) 실패로 본다 — 2.15 ± 0.6."""
    cc.grip_widths = [10.58 + 3.5]
    assert handling.pick('RET_B', 'BOWL').code == EMPTY_ZONE


def test_pick_cup_no_judgement(cc):
    """컵(E19): grip_target_mm(76) · 5 N 까지만 닫고 판정 없이 성공. width_mm 는 드라이버 폭."""
    cc.grip_widths = [77.9]                                       # 빈손과 같은 값이어도
    r = handling.pick('RET_C', 'CUP')
    assert r.ok and r.width_mm == pytest.approx(77.9) and cc.of('grip')[0] == ('grip', 76.0, 5.0)


def test_pick_never_swallows_move_errors(cc):
    """이동 실패는 예외 그대로 — 쥔 뒤 되올라오다 멈춰도 release 하지 않는다."""
    cc.fail_on = ('move_rel', 2)
    with pytest.raises(MoveIncomplete):
        handling.pick('RET_B', 'BOWL')
    assert cc.names().count('release') == 1                       # 시작 때 열기만


def test_pick_missing_preset_is_keyerror_before_moving(cc):
    del cc.conf['cell']['presets']['BOWL']['width_tol_mm']
    with pytest.raises(KeyError):
        handling.pick('RET_B', 'BOWL')
    assert 'move_to' not in cc.names()


# ────────────────────────────────── pick — 재파지
def test_regrip_bowl_from_bed(cc):
    r = handling.pick('SPONGE_BED_B', 'BOWL')
    assert r.ok and r.attempts == 1
    assert cc.of('move_to')[0] == ('move_to', 'SPONGE_BED_B', False, 'BOWL', 'place')
    assert [c[3] for c in cc.of('move_rel')] == [pytest.approx(-147.7), pytest.approx(147.7)]


def test_regrip_bowl_empty_is_grip_fail_not_empty_zone(cc):
    """홈에 그릇이 없으면 GRIP_FAIL(정책 pause · 사람이 확인). EMPTY_ZONE 이면 구역을 건너뛰어 홈의 용기를 잃는다."""
    cc.grip_widths = [10.6]
    r = handling.pick('SPONGE_BED_B', 'BOWL')
    assert not r.ok and r.code == GRIP_FAIL and cc.names()[-2:] == ['release', 'move_rel']


def test_regrip_with_regrip_pose_lifts_to_entry_z(cc):
    """홈에 regrip(posj) 이 **있으면**(옆면 파지 · 한석형 9/22 컵 경로): 그 자세 → 쥐기 → rack.cup_entry_z_mm(250) 까지 올린다.
    🔄 9/22 저녁 E29: 종류가 아니라 키 유무로 고른다 — 이 시험은 키를 넣어 옛 경로를 지킨다."""
    cc.conf['cell']['beds']['SPONGE_BED_C'] = {'regrip': {'posj': [0] * 6}}
    cc.z = 120.0
    r = handling.pick('SPONGE_BED_C', 'CUP')
    assert r.ok
    assert cc.of('move_to')[0] == ('move_to', 'SPONGE_BED_C', False, 'CUP', 'regrip')
    assert cc.of('move_rel')[-1][3] == pytest.approx(130.0)


def test_regrip_uses_bed_regrip_preset(cc):
    """🔄 9/23 결정 ㉡: 홈 C 옆면 재파지는 beds.<bed>.regrip_preset(CUP_SIDE · 고정 폭 76 · 5 N)으로 잡고,
    잡은 뒤 cc.set_grip_preset 으로 알려 준다 — 그 뒤 HOLD 전환이 CUP 의 35 N 을 몸통에 걸지 않게(E19 눌림)."""
    cc.conf['cell']['beds']['SPONGE_BED_C'] = {'regrip': {'posj': [0] * 6}, 'regrip_preset': 'CUP_SIDE'}
    cc.conf['cell']['presets']['CUP_SIDE'] = {'grip_target_mm': 76.0, 'grip_zero_mm': 10.58, 'grip_force_n': 5}
    cc.grip_widths = [77.4]
    cc.z = 120.0
    r = handling.pick('SPONGE_BED_C', 'CUP')
    assert r.ok and r.width_mm == pytest.approx(77.4)           # 고정 폭은 드라이버 폭을 그대로 보고한다
    g = cc.of('grip')[-1]
    assert g[1] == pytest.approx(76.0) and g[2] == pytest.approx(5.0)
    assert cc.of('set_grip_preset') == [('set_grip_preset', 'CUP_SIDE')]


def test_regrip_with_approach_descends_then_grips_then_lifts_to_entry_z(cc):
    """🔄 9/23 08:1x: 재파지 자세에 접근점(approach_posx+posx)이 있으면 **위에서 자세를 맞추고 Z 만 내려** 잡고,
    잡은 뒤 rack.cup_entry_z_mm(250) 까지 올린다 — 07:55 실기: HOME 에서 관절 이동으로 곧장 가다 열린 그리퍼가 컵에 걸려 SAFE_STOP."""
    cc.conf['cell']['beds']['SPONGE_BED_C'] = {'regrip': {'approach_posx': [0] * 6, 'posx': [0] * 6}, 'regrip_preset': 'CUP_SIDE'}
    cc.conf['cell']['presets']['CUP_SIDE'] = {'grip_target_mm': 76.0, 'grip_zero_mm': 10.58, 'grip_force_n': 5}
    cc.up[('SPONGE_BED_C', 'regrip')] = 100.0
    cc.contact = (60.0, 2.0)                                       # 감시 60 mm 를 끝까지 내려감(닿은 것 없음)
    cc.z = 200.0
    r = handling.pick('SPONGE_BED_C', 'CUP')
    assert r.ok
    names = cc.names()
    assert names.index('move_to') < names.index('contact_down') < names.index('grip')
    assert cc.of('contact_down')[0][1:] == (60.0, 15)               # 마지막 60 mm 는 insert_limit_n 으로 감시
    rel = [c[3] for c in cc.of('move_rel')]
    assert rel == [pytest.approx(-40.0), pytest.approx(150.0)]        # 자유 40 → 감시 60(200→100) → 250 까지 올림
    assert names.index('grip') < len(names) - 1 - names[::-1].index('move_rel')


def test_regrip_contact_timeout_scales_with_watch_distance(cc):
    """🔄 9/23 10:5x 실기(PM): contact_down 은 걸음당 ≈0.8 s 라 60 mm 감시는 배속 1 에서도 16 s 가 걸리는데 10 s 로 잘렸다(36.9/60 TIMEOUT)
    → 타임아웃 = timeout_s ÷ vel_scale × (감시 거리 / 20)."""
    cc.conf['cell']['beds']['SPONGE_BED_C'] = {'regrip': {'approach_posx': [0] * 6, 'posx': [0] * 6}, 'regrip_preset': 'CUP_SIDE'}
    cc.conf['cell']['presets']['CUP_SIDE'] = {'grip_target_mm': 70.0, 'grip_zero_mm': 10.58, 'grip_force_n': 10}
    cc.up[('SPONGE_BED_C', 'regrip')] = 100.0
    cc.contact = (60.0, 2.0)
    cc.conf['run'] = {'vel_scale': 1.0}
    assert handling.pick('SPONGE_BED_C', 'CUP').ok
    assert handling._contact_timeout(60.0) == pytest.approx(30.0)          # 10 s × 3
    assert handling._contact_timeout(20.0) == pytest.approx(10.0)          # 팔레트 삽입 20 mm 은 그대로
    cc.conf['run'] = {'vel_scale': 0.3}
    assert handling._contact_timeout(60.0) == pytest.approx(100.0)


def test_contact_timeout_has_floor(cc):
    """🔄 9/23 13:52 리허설: 순응 걸음이 배속과 무관하게 ≈3 s 라 0.5 에서 20 mm 감시가 20 s 를 넘겼다 → f1.contact_timeout_min_s(30) 아래로는 안 내려간다."""
    cc.conf['run'] = {'vel_scale': 0.5}
    cc.conf['f1']['contact_timeout_min_s'] = 30.0
    assert handling._contact_timeout() == pytest.approx(30.0)               # 10 ÷ 0.5 = 20 → 바닥 30
    assert handling._contact_timeout(60.0) == pytest.approx(60.0)           # 60 mm 는 20 × 3 = 60 > 30 그대로
    cc.conf['run'] = {'vel_scale': 0.3}
    assert handling._contact_timeout() == pytest.approx(10.0 / 0.3)         # 33.3 > 30 그대로
    cc.conf['f1'].pop('contact_timeout_min_s')
    cc.conf['run'] = {'vel_scale': 0.5}
    assert handling._contact_timeout() == pytest.approx(20.0)               # 키 없으면 예전과 같다


def test_regrip_finger_on_cup_rim_backs_up_with_grip_fail(cc):
    """감시 구간에서 힘이 먼저 닿으면(손가락이 컵 테두리에 얹힘) SAFE_STOP 대신 되올라와 GRIP_FAIL — 잡기(grip)는 하지 않는다."""
    cc.conf['cell']['beds']['SPONGE_BED_C'] = {'regrip': {'approach_posx': [0] * 6, 'posx': [0] * 6}, 'regrip_preset': 'CUP_SIDE'}
    cc.conf['cell']['presets']['CUP_SIDE'] = {'grip_target_mm': 76.0, 'grip_zero_mm': 10.58, 'grip_force_n': 5}
    cc.up[('SPONGE_BED_C', 'regrip')] = 100.0
    cc.contact = (40.0, 9.0)                                       # 60 중 40 에서 9 N
    r = handling.pick('SPONGE_BED_C', 'CUP')
    assert not r.ok and r.code == GRIP_FAIL
    assert not cc.of('grip') and 'force_off' in cc.names()
    assert cc.of('move_rel')[-1][3] == pytest.approx(80.0)          # 자유 40 + 내려간 40 만큼 되올라옴


def test_regrip_with_approach_fails_back_up(cc):
    """헛잡음이면 놓고 접근점 높이로 올라간 뒤 GRIP_FAIL — 컵 옆에 손가락을 두고 멈추지 않는다."""
    cc.conf['cell']['beds']['SPONGE_BED_C'] = {'regrip': {'approach_posx': [0] * 6, 'posx': [0] * 6}}
    cc.up[('SPONGE_BED_C', 'regrip')] = 100.0
    cc.contact = (60.0, 2.0)
    cc.grip_widths = [10.6]                                        # 빈손 폭 → CUP(고정 폭 76)이 아닌 BOWL 판정으로 시험
    r = handling.pick('SPONGE_BED_C', 'BOWL')
    assert not r.ok and r.code == GRIP_FAIL
    assert cc.names()[-2:] == ['release', 'move_rel'] and cc.of('move_rel')[-1][3] == pytest.approx(100.0)


def test_regrip_without_preset_key_does_not_touch_grip_preset(cc):
    cc.conf['cell']['beds']['SPONGE_BED_C'] = {'regrip': {'posj': [0] * 6}}
    cc.z = 120.0
    assert handling.pick('SPONGE_BED_C', 'CUP').ok
    assert not cc.of('set_grip_preset')


def test_regrip_cup_without_regrip_pose_uses_place_point(cc):
    """홈에 regrip 이 **없으면**(9/22 저녁 벽 집기 · cell.yaml 기본): 컵도 그릇처럼 place 자리에서 다시 잡고 entry_z 로 올리지 않는다."""
    cc.z = 120.0
    r = handling.pick('SPONGE_BED_C', 'CUP')
    assert r.ok
    assert cc.of('move_to')[0] == ('move_to', 'SPONGE_BED_C', False, 'CUP', 'place')
    assert not cc.of('move_rel')                                    # 접근점이 없는 가짜 홈이라 오르내림 없음


# ────────────────────────────────── rack_place
def test_rack_place_bowl_route(cc):
    """수조 위로 → HOME → 경유점(via) → 칸 위 → 자유 하강(up−30) → 감시 하강 30 → 놓기 → 빠져나오기 순서."""
    cc.contact = (29.0, 4.0)                                       # 30 − 1 → seat_tol 3 안 = 들어갔다
    r = handling.rack_place('RACK_B1', 'BOWL')
    assert r.ok
    mt = [c[1] for c in cc.of('move_to')]
    assert mt == ['RINSE', 'HOME', 'RACK_B1_VIA', 'RACK_B1']
    assert cc.of('move_to')[0][3] == 'BOWL'                        # RINSE 는 종류별 자세
    assert cc.of('contact_down')[0] == ('contact_down', 30.0, 15.0)
    rels = [(c[1], c[2], c[3]) for c in cc.of('move_rel')]
    assert rels[0] == (0.0, 0.0, -70.0)                            # 100 − 30 자유 하강
    assert rels[-2:] == [(0.0, -25.0, 0.0), (0.0, 0.0, 100.0)]     # exit_rel_mm 순서 그대로
    names = cc.names()
    assert names.index('release') > names.index('contact_down')
    assert names.index('force_off') < names.index('move_to')


def test_rack_place_cup_lifts_to_entry_z_no_home(cc):
    """컵: 수조 위 → z 250 → 컵 경유점 → 칸. HOME 은 거치지 않는다(한석형 9/22 컵 경로)."""
    cc.z = 150.0; cc.contact = (30.0, 2.0)
    assert handling.rack_place('RACK_C1', 'CUP').ok
    mt = [c[1] for c in cc.of('move_to')]
    assert mt == ['RINSE', 'RACK_C_VIA', 'RACK_C1'] and 'HOME' not in mt
    assert cc.of('move_rel')[0][3] == pytest.approx(100.0)         # 150 → 250


def test_rack_place_jam_retreats_and_returns_rack_jam(cc):
    """깊이가 남았는데 힘이 먼저 닿음 = 걸림 → (자유 하강 + 내려간 깊이) 만큼 되올라와 RACK_JAM · release 안 함."""
    cc.contact = (12.0, 15.0)
    r = handling.rack_place('RACK_B1', 'BOWL')
    assert not r.ok and r.code == RACK_JAM
    assert 'release' not in cc.names()
    assert cc.of('move_rel')[-1][3] == pytest.approx(70.0 + 12.0)


@pytest.mark.parametrize('exc,code', [(ForceLimitError('힘'), FORCE_LIMIT), (MotionTimeout('시간'), TIMEOUT)])
def test_rack_place_force_limit_and_timeout_become_codes(cc, exc, code):
    cc.contact_raises = exc
    r = handling.rack_place('RACK_B1', 'BOWL')
    assert not r.ok and r.code == code and 'release' not in cc.names()
    assert cc.of('move_rel')[-1][3] == pytest.approx(70.0 + 30.0)   # 🔄 9/22 밤: 깊이를 모르니 감시 구간 전체만큼 — 접근점 위(안전) · 순응도 끈다
    assert cc.names().count('force_off') == 2                       # 시작 1 + 실패 뒤 1


def test_rack_place_missing_via_is_keyerror_before_moving(cc):
    del cc.conf['cell']['rack']['slots']['RACK_B1']['via']
    with pytest.raises(KeyError):
        handling.rack_place('RACK_B1', 'BOWL')
    assert 'move_to' not in cc.names()


def test_pick_and_rack_three_times_in_a_row(cc):
    """같은 함수 연속 3회 (SDD §3.2 ⑧)."""
    cc.grip_widths = [13.0] * 3; cc.contact = (30.0, 2.0)
    for _ in range(3):
        assert handling.pick('RET_B', 'BOWL').ok and handling.rack_place('RACK_B1', 'BOWL').ok


def test_rack_place_retry_near_the_slot_skips_rinse_and_via(cc):
    """🔄 9/22 밤(황인재): flow 의 RACK 재시도는 이미 칸 위에 있다 → 수조·HOME·경유점을 다시 거치지 않는다(22:57 실기: 헹굼 자리로 되돌아갔다)."""
    cc.contact = (29.0, 4.0)
    cc.where = lambda: [300.0, 600.0, 400.0, 0.0, 0.0, 0.0]        # 칸 접근점 바로 그 자리
    assert handling.rack_place('RACK_B1', 'BOWL').ok
    assert [c[1] for c in cc.of('move_to')] == ['RACK_B1']


def test_contact_timeout_grows_with_slow_speed(cc):
    """0.3 배속이면 접촉 타임아웃도 3.3배 — 10 s 로는 20 mm 감시 하강을 못 끝냈다(22:57 실기 19.9/20)."""
    cc.conf['run'] = {'vel_scale': 0.3}
    assert handling._contact_timeout() == pytest.approx(10.0 / 0.3)
    cc.conf['run'] = {'vel_scale': 1.0}
    assert handling._contact_timeout() == pytest.approx(10.0)


# ------------------------------------------------------------------ 🆕 9/23 튜닝 #5 — 팔레트 삽입 마지막 구간 한 걸음
def test_rack_place_watches_the_last_millimetres_in_one_step(cc):
    cc.conf['f1']['insert_approach_mm'] = 5
    cc.conf['f1']['watch_step_mm'] = 5
    cc.contact = (5.0, 3.0)
    assert handling.rack_place('RACK_B1', 'BOWL').ok
    assert ('contact_down', 5.0, 15.0, 5.0) in cc.calls


def test_rack_place_without_watch_step_setting_uses_the_default_step(cc):
    cc.conf['f1']['insert_approach_mm'] = 5
    cc.contact = (5.0, 3.0)
    assert handling.rack_place('RACK_B1', 'BOWL').ok
    assert ('contact_down', 5.0, 15.0) in cc.calls


# ------------------------------------------------------------------ 🆕 9/23 18:1x 튜닝 3차 #3 — 삽입 감시 0 = 곧게 내려 놓기
def test_rack_place_with_zero_insert_watch_descends_straight_and_releases(cc):
    cc.conf['f1']['insert_approach_mm'] = 0
    cc.conf['f1']['land_slow_mm'] = 15
    cc.conf['f1']['land_vel_mm_s'] = 30
    assert handling.rack_place('RACK_B1', 'BOWL').ok
    assert 'contact_down' not in cc.names()
    rel = [c for c in cc.calls if c[0] == 'move_rel']
    down = [c for c in rel if c[3] < 0]
    assert down[0][3] == pytest.approx(-85.0) and down[1][3] == -15.0                # 100 = 칸 위 높이 → 85 빠르게 + 15 완충
    assert cc.names().index('release') > cc.calls.index(down[1])


# ------------------------------------------------------------------ 🆕 9/24 황인재: 컵 재파지 감시 하강 0 = 곧게 내려가 바로 잡기
def _cup_bed_with_approach(cc):
    cc.conf['cell']['beds']['SPONGE_BED_C'] = {
        'regrip': {'approach_posx': [364.72, 138.56, 152.18, 71.66, 116.03, 87.31], 'posx': [364.72, 138.56, 52.18, 71.66, 116.03, 87.31]},
        'regrip_preset': 'CUP_SIDE'}
    cc.conf['cell']['presets']['CUP_SIDE'] = {'grip_target_mm': 70.0, 'grip_zero_mm': 10.58, 'grip_force_n': 10}
    cc.up[('SPONGE_BED_C', 'regrip')] = 100.0


def test_regrip_with_zero_watch_descends_straight_and_grips(cc):
    _cup_bed_with_approach(cc)
    cc.conf['f1']['regrip_watch_mm'] = 0
    cc.grip_widths = [70.3]
    r = handling.pick('SPONGE_BED_C', 'CUP')
    assert r.ok and r.width_mm == 70.3
    assert 'contact_down' not in cc.names() and 'force_off' not in cc.names()          # 순응·힘 감시 없음
    assert ('move_rel', 0.0, 0.0, -100.0, 'BASE') in cc.calls                          # 접근점에서 끝점까지 한 번에(완충 설정 없음)
    assert cc.names().index('grip') > cc.calls.index(('move_rel', 0.0, 0.0, -100.0, 'BASE'))


def test_regrip_with_zero_watch_uses_soft_landing_when_set(cc):
    _cup_bed_with_approach(cc)
    cc.conf['f1']['regrip_watch_mm'] = 0
    cc.conf['f1']['land_slow_mm'] = 15
    cc.conf['f1']['land_vel_mm_s'] = 30
    cc.grip_widths = [70.3]
    assert handling.pick('SPONGE_BED_C', 'CUP').ok
    down = [c for c in cc.calls if c[0] == 'move_rel' and c[3] < 0]
    assert down[0][3] == pytest.approx(-85.0) and down[1][3] == -15.0 and down[1][5] == {'vel_mm_s': 30.0}


def test_regrip_zero_watch_grip_fail_returns_to_the_approach_point(cc):
    _cup_bed_with_approach(cc)
    cc.conf['f1']['regrip_watch_mm'] = 0
    cc.grip_widths = [11.0]                                                            # 헛잡음
    cc.conf['cell']['presets']['CUP_SIDE'] = {'grip_width_mm': 59.42, 'grip_zero_mm': 10.58, 'grip_force_n': 10, 'width_tol_mm': 3}
    r = handling.pick('SPONGE_BED_C', 'CUP')
    assert not r.ok and r.code == 'GRIP_FAIL'
    assert ('move_rel', 0.0, 0.0, 100.0, 'BASE') in cc.calls                            # 내려간 만큼 되올라온다


def test_regrip_positive_watch_still_uses_the_contact_descent(cc):
    _cup_bed_with_approach(cc)
    cc.conf['f1']['regrip_watch_mm'] = 45
    cc.contact = (45.0, 2.0)
    cc.grip_widths = [70.3]
    assert handling.pick('SPONGE_BED_C', 'CUP').ok
    assert ('contact_down', 45.0, 15) in cc.calls                                       # 예전 방식(45 mm 감시)도 그대로 된다
