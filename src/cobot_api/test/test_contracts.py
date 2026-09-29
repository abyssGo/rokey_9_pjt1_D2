import types
from cobot_api import (F1Api, F2Api, F3Api, PickResult, Result, check_api, CODES, EMPTY_ZONE, SEAT_FAIL)


def test_result_defaults_and_fail():
    r = PickResult(width_mm=61.5, attempts=2)
    assert r.ok and r.code == 'OK' and r.as_dict()['attempts'] == 2
    f = PickResult.fail(EMPTY_ZONE, attempts=5)
    assert not f.ok and f.code == EMPTY_ZONE and f.attempts == 5
    assert SEAT_FAIL in CODES


def test_check_api_detects_missing_and_wrong_args():
    m = types.SimpleNamespace(
        pick=lambda zone_id, kind: PickResult(), place=lambda station, kind=None: Result(),   # place·move_to 에 kind 선택 인자
        regrip_top=lambda bed, kind: PickResult(),
        move_to=lambda station: Result(),                      # carrying 빠짐
        tool=lambda tool, action: Result())                    # rack_place 없음
    p = check_api(m, F1Api)
    assert any('move_to' in x for x in p) and any('rack_place' in x for x in p) and len(p) == 2
    assert {len([n for n in dir(a) if not n.startswith('_')]) for a in (F2Api, F3Api)} == {4, 3}
