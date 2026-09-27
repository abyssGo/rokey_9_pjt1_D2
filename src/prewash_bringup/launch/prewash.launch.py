# -*- coding: utf-8 -*-
"""PC-A 실행 — flow_node 프로세스 1개 (안에서 f1·f2·f3·cobot_common 함수가 돈다). SDD §10

    sod && sodreal                                                       # 터미널 1: 실기 브링업 (Virtual 은 sodvir)
    soc && ros2 launch prewash_bringup prewash.launch.py                 # 터미널 2: 기본 vel_scale 0.3
    soc && ros2 launch prewash_bringup prewash.launch.py use_mock:="f3"  # L2 통합: F3 만 가짜
    PC-B:  soc && ros2 run f4_hmi hmi_bridge          (PC 1대로 할 때는 여기에 hmi:=true)

주의: 실기 로봇이 움직인다. 팀 확인 뒤에만, 첫 실기는 vel_scale 0.2~0.3 (AGENTS.md §3 규칙 1).
   끌 때는 멈춰 있을 때 Ctrl+C 한 번. 급하면 Ctrl+C 가 아니라 E-Stop.
"""
from prewash_bringup.launch_common import make_description


def generate_launch_description():
    return make_description(use_mock='', vel_scale='0.3', hmi='false')
