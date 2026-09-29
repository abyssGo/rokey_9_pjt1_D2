# -*- coding: utf-8 -*-
"""런치 2종 시험 — 프로그램을 실제로 띄우지 않고, 런치가 무엇을 어떤 환경변수로 띄우려 하는지만 본다.
실행: soc && python3 -m pytest src/prewash_bringup/test
"""
from pathlib import Path

import pytest
from launch import LaunchContext
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

from cobot_common import config as cc_config
from prewash_bringup import launch_common

LAUNCH_DIR = Path(__file__).resolve().parent.parent / 'launch'


def _defaults(name):
    ld = PythonLaunchDescriptionSource(str(LAUNCH_DIR / name)).get_launch_description(LaunchContext())
    args = {e.name: e for e in ld.entities if isinstance(e, DeclareLaunchArgument)}
    return {k: ''.join(s.text for s in v.default_value) for k, v in args.items()}, ld


def _spawn(monkeypatch, installed, **cfg):
    """_spawn 을 인자 cfg 로 돌려 보고 (Node 목록, 전체 액션) 을 돌려준다."""
    monkeypatch.setattr(launch_common, '_installed', lambda pkg: pkg in installed)
    ctx = LaunchContext()
    ctx.launch_configurations.update(cfg)
    actions = launch_common._spawn(ctx)
    return [a for a in actions if isinstance(a, Node)], actions


def test_launch_defaults():
    real, ld = _defaults('prewash.launch.py')
    assert real == {'use_mock': '', 'vel_scale': '1.0', 'hmi': 'false'}      # 실기 기본은 1.0(E67) · flow 만
    assert any(isinstance(e, OpaqueFunction) for e in ld.entities)
    mock, _ = _defaults('prewash_mock.launch.py')
    assert mock == {'use_mock': 'f1,f2,f3', 'vel_scale': '1.0', 'hmi': 'true'}


def test_flow_only_and_env(monkeypatch):
    nodes, _ = _spawn(monkeypatch, {'f2_sense_flow', 'f4_hmi'}, use_mock='f1, f3', vel_scale='0.3', hmi='false')
    assert len(nodes) == 1                                                   # PC-A: flow_node 프로세스 1개
    flow = nodes[0]
    assert (flow.node_package, flow.node_executable) == launch_common.FLOW
    env = {''.join(s.text for s in k): ''.join(s.text for s in v) for k, v in flow.additional_env}
    assert env == {cc_config.ENV_USE_MOCK: 'f1,f3', cc_config.ENV_VEL_SCALE: '0.3'}
    # 주의: 이름·네임스페이스를 주면 프로세스 안의 두 노드(flow_node · flow_node_dsr) 이름이 같아진다
    assert flow._Node__node_name is None and flow._Node__node_namespace is None


def test_mock_launch_adds_hmi(monkeypatch):
    nodes, _ = _spawn(monkeypatch, {'f2_sense_flow', 'f4_hmi'}, use_mock='f1,f2,f3', vel_scale='1.0', hmi='true')
    assert [(n.node_package, n.node_executable) for n in nodes] == [launch_common.FLOW, launch_common.HMI]


def test_missing_packages_are_skipped(monkeypatch):
    nodes, actions = _spawn(monkeypatch, set(), use_mock='f1,f2,f3', vel_scale='1.0', hmi='true')
    assert nodes == [] and len(actions) == 3                                 # 안내 1 + 건너뜀 경고 2


@pytest.mark.parametrize('cfg', [dict(use_mock='f9', vel_scale='0.3'), dict(use_mock='', vel_scale='2')])
def test_bad_arguments_stop_the_launch(monkeypatch, cfg):
    with pytest.raises(cc_config.ConfigError):
        _spawn(monkeypatch, {'f2_sense_flow'}, hmi='false', **cfg)
