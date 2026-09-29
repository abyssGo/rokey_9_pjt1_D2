# -*- coding: utf-8 -*-
"""가짜 F3 접촉 닦기 — 실제는 f3_wipe.wipe (IRD §5).

이름·인자·반환은 cobot_api.F3Api 그대로. 힘 로그는 만들지 않는다(경로는 빈 문자열).
"""
from cobot_api import Result, WipeBowlResult, WipeCupResult

from . import code_for


def soap(count: int, kind: str = None) -> Result:
    """가짜 세제 묻히기 — 주입된 실패 코드가 있으면 그 코드로, 아니면 OK."""
    code = code_for('soap')
    return Result.fail(code) if code else Result()


def wipe_bowl() -> WipeBowlResult:
    """가짜 그릇 닦기 — 주입된 실패 코드가 있으면 그 코드로, 아니면 15 s · 평균 4 N 으로 닦은 것처럼(힘 로그 없음)."""
    code = code_for('wipe_bowl')
    if code:
        return WipeBowlResult.fail(code)
    return WipeBowlResult(force_log_path='', duration_s=15.0, force_mean_n=4.0)


def wipe_cup() -> WipeCupResult:
    """가짜 컵 닦기 — 주입된 실패 코드가 있으면 그 코드로, 아니면 12 s · 90 mm 삽입으로 닦은 것처럼(힘 로그 없음)."""
    code = code_for('wipe_cup')
    if code:
        return WipeCupResult.fail(code)
    return WipeCupResult(force_log_path='', duration_s=12.0, insert_depth_mm=90.0)
