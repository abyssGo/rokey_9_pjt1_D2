# -*- coding: utf-8 -*-
"""런치 2종이 같이 쓰는 부분. (SDD §10)

런치가 띄우는 것
    flow_node  (f2_sense_flow) — 메인 프로그램. 이 프로세스 안에서 f1·f2·f3 함수가 돈다. 항상 1개
    hmi_bridge (f4_hmi)        — hmi:=true 일 때만. 통합 실행에서는 PC-B 에서 `ros2 run f4_hmi hmi_bridge` 로 따로 띄운다

런치 인자 → 프로그램: 환경변수로 넘긴다 (cobot_common.config 가 읽어 cfg 에 얹는다)
    use_mock:="f1,f3"   → PREWASH_USE_MOCK  → cfg['flow']['use_mock']   (빈 값이면 전부 실제)
    vel_scale:=0.3      → PREWASH_VEL_SCALE → cfg['run']['vel_scale']   (0 초과 1 이하)
  ROS 파라미터로 주지 않는 이유: flow 는 init() 전에 use_mock 을 보고 init(robot=False) 를 정해야 한다.

주의: flow_node 에 name=·namespace= 를 주지 않는다. 런치가 넣는 `-r __node:=…` 는 프로세스 안의 모든 노드에 걸려서,
   cobot_common.init() 이 만드는 통신 노드(flow_node)와 DSR 전용 노드(flow_node_dsr, ns dsr01)의 이름이 같아진다.
"""
from ament_index_python.packages import PackageNotFoundError, get_package_prefix
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from cobot_common import config as cc_config

FLOW = ('f2_sense_flow', 'flow_node')
HMI = ('f4_hmi', 'hmi_bridge')


def _installed(package: str) -> bool:
    try:
        get_package_prefix(package)
        return True
    except PackageNotFoundError:
        return False


def _spawn(context):
    use_mock = LaunchConfiguration('use_mock').perform(context)
    vel_scale = LaunchConfiguration('vel_scale').perform(context)
    hmi = LaunchConfiguration('hmi').perform(context).lower() in ('true', '1', 'yes')
    # 틀린 인자는 프로그램을 띄우기 전에 여기서 멈춘다 (ConfigError)
    mocks = cc_config.parse_use_mock(use_mock)
    scale = cc_config.parse_vel_scale(vel_scale)
    env = {cc_config.ENV_USE_MOCK: ','.join(mocks), cc_config.ENV_VEL_SCALE: str(scale)}

    actions = [LogInfo(msg=f'[prewash] use_mock={mocks or "없음(전부 실제)"} · vel_scale={scale:g} · hmi={hmi}')]
    wanted = [FLOW] + ([HMI] if hmi else [])
    for package, executable in wanted:
        if not _installed(package):
            actions.append(LogInfo(msg=f'[prewash] ⚠️ {package} 패키지가 아직 없어 {executable} 를 건너뛴다 (빌드했는지: cbc)'))
            continue
        actions.append(Node(package=package, executable=executable, output='screen', emulate_tty=True,
                            additional_env=env))      # 주의: name·namespace 를 주지 않는다 (맨 위 설명)
    return actions


def make_description(*, use_mock: str, vel_scale: str, hmi: str) -> LaunchDescription:
    """인자 기본값만 다른 런치 2종을 만든다."""
    return LaunchDescription([
        DeclareLaunchArgument('use_mock', default_value=use_mock,
                              description='가짜 모듈로 바꿀 기능. 예: "f1,f3" · 빈 값이면 전부 실제 · "f1,f2,f3" 이면 드라이버 없이 돈다'),
        DeclareLaunchArgument('vel_scale', default_value=vel_scale,
                              description='속도 배율(0 초과 1 이하). 첫 실기는 0.2~0.3'),
        DeclareLaunchArgument('hmi', default_value=hmi,
                              description='true 면 이 PC 에서 hmi_bridge 도 같이 띄운다 (PC 1대 실행)'),
        OpaqueFunction(function=_spawn),
    ])
