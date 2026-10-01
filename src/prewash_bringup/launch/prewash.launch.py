# -*- coding: utf-8 -*-
"""GPU PC(로봇 제어) 실행 — flow_node 프로세스 1개 (안에서 f1·f2·f3·cobot_common 함수가 돈다). SDD §10

    sod && sodreal                                                       # 터미널 1: 실기 브링업 (Virtual 은 sodvir)
    soc && ros2 launch prewash_bringup prewash.launch.py                 # 터미널 2: 기본 vel_scale 1.0
    soc && ros2 launch prewash_bringup prewash.launch.py use_mock:="f3"  # L2 통합: F3 만 가짜
    화면 PC:  soc && ros2 run f4_hmi hmi_bridge       (PC 1대로 할 때는 여기에 hmi:=true · 두 PC 연결은 Discovery Server — README 실행 방법 5-4 · SDD §10)

주의: 실기 로봇이 움직인다. 기본 배속은 1.0(E67). 처음 켜는 셀·재티칭 뒤에는 vel_scale:=0.3 으로 낮춰 먼저 돌려 본다.
   끌 때는 멈춰 있을 때 Ctrl+C 한 번. 급하면 Ctrl+C 가 아니라 E-Stop.
"""
from prewash_bringup.launch_common import make_description


def generate_launch_description():
    return make_description(use_mock='', vel_scale='1.0', hmi='false')
