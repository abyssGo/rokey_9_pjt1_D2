# -*- coding: utf-8 -*-
"""가짜 F2 무게·털기·헹굼 — 실제는 f2_sense_flow.sense (IRD §4).

이름·인자·반환은 cobot_api.F2Api 그대로. 로봇을 움직이지 않고 즉시 돌려준다.
런치 prewash_mock.launch.py 가 use_mock='f1,f2,f3' 으로 부르고 config 의 MOCKABLE 에도 f2 가 있어
mock_f1·mock_f3 와 같이 둔다 — 없으면 로봇 없는 런치가 깨진다.

주의: 무게는 0 g(잔반 없음)을 돌려준다 — 진짜 sense.weigh 가 돌려주는 것이
   "측정값" 이 아니라 "잔반 무게"(측정값 − 빈 용기 기준값) 이기 때문이다(SDD §5.3).
   빈 용기 기준값 같은 큰 값을 돌려주면 같은 상황에서 가짜와 진짜가 다르게 동작한다.
   잔반 상황을 만들려면 fail_on 으로 LEFTOVER 계열 코드를 주입한다.
"""
from cobot_api import LeftoverResult, Result, WeighResult

from . import code_for


def weigh(kind: str) -> WeighResult:
    """가짜 무게 재기 — 주입된 실패 코드가 있으면 그 코드로, 아니면 잔반 0 g(진짜 sense.weigh 와 같은 뜻)."""
    code = code_for('weigh')
    if code:
        return WeighResult.fail(code)
    return WeighResult(weight_g=0.0)              # 잔반 0 g (진짜 sense.weigh 와 같은 뜻)


def leftover_loop(kind: str, max_rounds: int) -> LeftoverResult:
    """가짜 잔반 루프 — 통과면 0 g · 0회, 주입된 실패면 임계(50 g)를 넘긴 값(80 → 60 g)으로 max_rounds 만큼 턴 것처럼.

    무게의 뜻은 weigh 와 같다(잔반 g).
    """
    code = code_for('leftover_loop')
    if code:
        return LeftoverResult(ok=False, code=code, weight_before_g=80.0,
                              weight_after_g=60.0, rounds=max_rounds)
    return LeftoverResult(weight_before_g=0.0, weight_after_g=0.0, rounds=0)


def shake(mode: str, count: int, kind: str) -> Result:
    """가짜 털기 — 주입된 실패 코드가 있으면 그 코드로, 아니면 OK."""
    code = code_for('shake')
    return Result.fail(code) if code else Result()


def dip(station: str, count: int, kind: str) -> Result:
    """가짜 담그기 — 주입된 실패 코드가 있으면 그 코드로, 아니면 OK."""
    code = code_for('dip')
    return Result.fail(code) if code else Result()
