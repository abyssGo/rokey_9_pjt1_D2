# -*- coding: utf-8 -*-
"""rig_int12.py 의 로봇 없는 부분 — 호출 순서가 flow.py 와 같은지 · 빈 껍데기 판정 · 로봇 없는 probe · 좌표 점검.

실제 통합은 실기(INT-12a·12b)가 한다. 여기는 그 시험대가 **엉뚱한 순서·인자로 부르지 않는지** 와
**빈 껍데기를 성공으로 오해하지 않는지** 만 본다.
"""
import importlib.util
from pathlib import Path

import pytest
from cobot_api import PickResult, Result
from cobot_common import config

SRC_CONFIG = Path(__file__).resolve().parents[2] / 'cobot_common' / 'config'


@pytest.fixture(scope='module')
def rig():
    spec = importlib.util.spec_from_file_location('rig_int12', Path(__file__).resolve().parent / 'rig_int12.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)                    # 모듈 맨 위는 ROS 를 부르지 않는다 (cobot_common 은 main 안에서)
    return m


@pytest.fixture(scope='module')
def cfg():
    return config.load(SRC_CONFIG)


# ────────────────────────────────── 호출 순서 = flow.py 의 steps 와 같다
def test_steps_a_is_pick_weigh_leftover(rig, cfg):
    got = rig.steps_for('a', 'BOWL', cfg)
    rounds = int(cfg['flow']['leftover_max_rounds'])
    assert got == [('PICK', 'f1', 'pick', ('RET_B', 'BOWL')),
                   ('WEIGH', 'f2', 'leftover_loop', ('BOWL', rounds))]


def test_steps_b_is_regrip_dip_shake_rack_home(rig, cfg):
    got = rig.steps_for('b', 'CUP', cfg)
    n = cfg['flow']['counts']
    assert got == [('RINSE', 'f1', 'pick', ('SPONGE_BED_C', 'CUP')),
                   ('RINSE', 'f2', 'dip', ('RINSE', int(n['rinse_dips']), 'CUP')),
                   ('RINSE', 'f2', 'shake', ('RINSE', int(n['rinse_shakes']), 'CUP')),
                   ('RACK', 'f1', 'rack_place', ('RACK_C1', 'CUP')),
                   ('RACK', 'f1', 'move_to', ('HOME', False))]


def test_steps_zone_slot_override(rig, cfg):
    assert rig.steps_for('a', 'CUP', cfg, zone='RET_X')[0] == ('PICK', 'f1', 'pick', ('RET_X', 'CUP'))
    assert rig.steps_for('b', 'BOWL', cfg, slot='RACK_B2')[3] == ('RACK', 'f1', 'rack_place', ('RACK_B2', 'BOWL'))


def test_steps_unknown_which(rig, cfg):
    with pytest.raises(ValueError):
        rig.steps_for('c', 'BOWL', cfg)


# ────────────────────────────────── 빈 껍데기 판정
def test_stub_pick_result_is_detected(rig):
    assert rig.looks_like_stub(PickResult())                              # main 의 빈 껍데기가 돌려주는 그대로


def test_real_pick_results_are_not_stub(rig):
    assert not rig.looks_like_stub(PickResult(width_mm=2.15, attempts=1))  # 그릇을 쥐었다
    assert not rig.looks_like_stub(PickResult(width_mm=78.0, attempts=1))  # 컵 고정 폭 (E19)
    assert not rig.looks_like_stub(PickResult.fail('EMPTY_ZONE', attempts=3))  # 해 보고 실패한 것
    # 🔔 맨 Result() 는 width_mm·attempts 가 없어 기본값(0.0·0)으로 '빈 껍데기' 로 보인다.
    #    그래서 rig 는 이 판정을 **pick 의 반환에만** 건다(_round 에서 fname == 'pick' 일 때만).
    assert rig.looks_like_stub(Result())


def test_probe_classifies_stub_and_impl(rig):
    def stub(*_):
        return PickResult()

    def raises(*_):
        raise RuntimeError('cobot_common.init() 을 먼저 부른다')

    def fails(*_):
        return PickResult.fail('EMPTY_ZONE', attempts=2)

    assert rig.probe(stub, ('RET_B', 'BOWL'))[0] == 'stub'
    assert rig.probe(raises, ('RET_B', 'BOWL'))[0] == 'impl'
    assert rig.probe(fails, ('RET_B', 'BOWL'))[0] == 'impl'


def test_probe_runs_against_real_f1_without_robot(rig):
    """진짜 f1 을 로봇 없이 probe 해도 죽지 않는다 — 빈 껍데기면 skip 으로 알려 주고, 구현이면 통과.

    🚨 "빈 껍데기다" 를 assert 하지 않는다 — 그러면 pick() 이 구현되는 순간 **이 시험이 깨진다**.
       빈 껍데기 여부는 실기 전에 `rig_int12.py check` 가 사람에게 알린다.
    """
    handling = pytest.importorskip('f1_handling.handling')
    kind, why = rig.probe(handling.pick, ('RET_B', 'BOWL'))
    assert kind in ('stub', 'impl'), why
    if kind == 'stub':
        pytest.skip('f1.pick 은 아직 빈 껍데기 — INT-12a 전에 check 로 확인한다')


# ────────────────────────────────── 좌표 점검
def test_missing_coords_is_empty_on_team_config(rig, cfg):
    for kind in ('BOWL', 'CUP'):
        assert rig.missing_coords(cfg, kind) == [], kind                  # 빈 자세 0개


def test_missing_coords_reports_key_names(rig, cfg):
    import copy
    c = copy.deepcopy(cfg)
    del c['cell']['stations']['RINSE']
    del c['cell']['rack']['slots']['RACK_B1']
    miss = rig.missing_coords(c, 'BOWL')
    assert 'stations.RINSE.BOWL' in miss
    assert 'rack.slots.RACK_B1' in miss
