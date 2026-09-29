#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2 넛지(Nudge · 로봇팔 가볍게 밀기) 감지 단독 시험대.

🚨 로봇 팔을 움직이지 않습니다 (cc.init(robot=True) 로 힘 센서만 읽음).
두산 실기 브링업(sod && sodreal)이 떠 있는 상태에서 실행합니다.

용도: 로봇팔을 손으로 가볍게 밀었을 때 넛지로 감지되는지 단독 확인
    (케이블 멈춤·툴 놓침 멈춤과 같은 감지기 — sense.wait_for_nudge → cc.check_nudge).
    케이블 멈춤은 밀면 그 자리에서 다시 재지 않고 바로 재개한다(flow.handle_cable_tight).

실행:
    soc && python3 src/f2_sense_flow/test/rig_nudge.py
"""
import sys
import time
from pathlib import Path

# cobot_common 및 f2_sense_flow 경로 자동 추가
REPO_ROOT = Path(__file__).resolve().parents[3]
COMMON_DIR = REPO_ROOT / 'src' / 'cobot_common'
F2_DIR = REPO_ROOT / 'src' / 'f2_sense_flow'
for p in (str(COMMON_DIR), str(F2_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import cobot_common as cc
from f2_sense_flow import sense


def main():
    print('=' * 60)
    print('  [F2] 넛지(Nudge · 로봇팔 가볍게 밀기) 감지 단독 시험대')
    print('  🚨 로봇 모션 없음 — 툴 힘센서만 읽습니다.')
    print('=' * 60)

    try:
        cc.init('rig_nudge', robot=True)
    except Exception as e:
        print(f'❌ cobot_common 초기화 실패: {e}')
        print('   실기 브링업(sod && sodreal)이 떠 있는지 확인하세요.')
        return 1

    f2_cfg = sense._f2()
    thresh = float(((f2_cfg.get('nudge') or {}).get('force_threshold_n')) or 15.0)   # 표시용 — wait_for_nudge 와 같은 기본값(E48)

    print(f'\n넛지(로봇팔 가볍게 밀기) 감지 대기 중... (감지 임계값: {thresh:.1f} N)')
    print('👉 로봇 말단/그리퍼 부근을 손으로 가볍게 밀어 보세요! (종료: Ctrl+C)')

    res = sense.wait_for_nudge(conf=f2_cfg, timeout_s=60.0)

    if res == 'nudge':
        print('\n' + '🎉' * 20)
        print('  ✅ 넛지(로봇팔 가볍게 밀기) 감지 성공!')
        print('🎉' * 20 + '\n')
    elif res is None:
        print('\n⚠️ 60초 타임아웃 — 밀기가 감지되지 않았습니다.')
        return 0
    else:
        print(f'\n신호 수신: {res}')

    print('시험 완료!')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\n시험 중단 (Ctrl+C)')
        sys.exit(0)

