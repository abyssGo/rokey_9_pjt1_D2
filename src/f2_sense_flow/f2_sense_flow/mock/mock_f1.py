# -*- coding: utf-8 -*-
"""가짜 F1 파지·이송·적재 — 실제는 f1_handling.handling (IRD §3).

이름·인자·반환은 cobot_api.F1Api 그대로. 로봇을 움직이지 않고 즉시 돌려준다.
숫자는 "그럴듯한 값"일 뿐 측정값이 아니다.
"""
from cobot_api import PickResult, PlaceResult, Result, ToolResult

from . import code_for

_WIDTH_MM = {'BOWL': 62.0, 'CUP': 70.0}          # cell.yaml presets 의 예시값과 맞춰 둔 표시용
_TOOL_WIDTH_MM = {'SPONGE': 30.0, 'BRUSH': 22.0}


def pick(zone_id: str, kind: str) -> PickResult:
    """가짜 파지 — 주입된 실패 코드가 있으면 그 코드로(attempts=5), 아니면 첫 슬롯에서 집은 것처럼 돌려준다."""
    code = code_for('pick')
    if code:
        return PickResult.fail(code, attempts=5)
    return PickResult(width_mm=_WIDTH_MM.get(kind, 60.0), attempts=1,
                      offset_x_mm=0.0, offset_y_mm=0.0)


def regrip_top(bed: str, kind: str) -> PickResult:
    """가짜 홈 위 다시 잡기 — 주입된 실패 코드가 있으면 그 코드로, 아니면 잡은 것처럼 돌려준다."""
    code = code_for('regrip_top')
    if code:
        return PickResult.fail(code, attempts=1)
    return PickResult(width_mm=_WIDTH_MM.get(kind, 60.0), attempts=1)


def place(station: str, kind: str = None) -> PlaceResult:
    """가짜 놓기 — 주입된 실패 코드가 있으면 그 코드로, 아니면 보정 없이(offset_mm=0) 놓은 것으로 돌려준다."""
    code = code_for('place')
    if code:
        return PlaceResult.fail(code)
    return PlaceResult(offset_mm=0.0)


def move_to(station: str, carrying: bool, kind: str = None) -> Result:
    """가짜 이동 — 주입된 실패 코드가 있으면 그 코드로, 아니면 OK."""
    code = code_for('move_to')
    return Result.fail(code) if code else Result()


def tool(tool: str, action: str) -> ToolResult:
    """가짜 툴 PICK/RETURN — 주입된 실패 코드가 있으면 그 코드로, 아니면 툴별 표시용 폭으로 OK."""
    code = code_for('tool')
    if code:
        return ToolResult.fail(code)
    return ToolResult(width_mm=_TOOL_WIDTH_MM.get(tool, 25.0))


def rack_place(rack_slot: str, kind: str) -> Result:
    """가짜 팔레트 삽입 — 주입된 실패 코드가 있으면 그 코드로, 아니면 OK."""
    code = code_for('rack_place')
    return Result.fail(code) if code else Result()
