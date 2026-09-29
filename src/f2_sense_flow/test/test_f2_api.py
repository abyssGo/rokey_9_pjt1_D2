"""F2 함수가 cobot_api 의 약속(F2Api)과 같은지 자동으로 지킨다 (PKG-01 완료 기준).

손으로 확인하면 나중에 누가 인자를 바꿔도 모른다. colcon test 가 계속 지켜 준다.
"""
from cobot_api import ROBOT_ERROR, F2Api, LeftoverResult, Result, WeighResult, check_api
from f2_sense_flow import sense


def test_sense_matches_f2api():
    assert check_api(sense, F2Api) == []


def test_return_types():
    assert isinstance(sense.weigh('BOWL'), WeighResult)
    assert isinstance(sense.leftover_loop('BOWL', 2), LeftoverResult)
    assert isinstance(sense.shake('WASTE', 4, 'BOWL'), Result)
    assert isinstance(sense.dip('RINSE', 1, 'CUP'), Result)


def test_no_robot_becomes_robot_error_not_crash():
    """🚨 로봇·설정이 없으면 **예외가 아니라 Result.fail(ROBOT_ERROR)** 여야 한다.

    F2-01·F2-02 로 속을 채우기 전에는 "전부 ok=True" 를 봤지만, 이제 실제로 로봇을 부른다.
    여기서 보는 것은 "되는가" 가 아니라 **"예외가 밖으로 새지 않는가"** 다 —
    기능 함수 하나의 예외가 셀 전체를 죽이면 안 된다(SDD §5.1).
    실제 동작 확인은 test_f2_sense.py(가짜 로봇)와 rig_f2.py(실기)가 한다.
    """
    for r in (sense.weigh('BOWL'), sense.leftover_loop('CUP', 1),
              sense.shake('RINSE', 3, 'CUP'), sense.dip('RINSE', 1, 'BOWL')):
        assert not r.ok and r.code == ROBOT_ERROR
