# -*- coding: utf-8 -*-
"""hmi_bridge 가 웹 부품 상자(venv)를 붙이는 순서. 웹 부품(fastapi)이 없는 PC 에서는 건너뛴다."""
import sys

import pytest

from f4_hmi.hmi_bridge import _ensure_web_parts


def test_venv_parts_come_before_system_parts(tmp_path, monkeypatch):
    # 새 Ubuntu 24.04 에서 ROS 와 함께 깔린 옛 typing_extensions(4.10)가 상자의 새 판보다 먼저 잡히면 웹 서버가 import 중에 죽는다
    pytest.importorskip('fastapi')
    pytest.importorskip('uvicorn')
    sp = tmp_path / 'lib' / 'python3.12' / 'site-packages'
    sp.mkdir(parents=True)
    monkeypatch.setattr(sys, 'path', list(sys.path))
    kept = {k: v for k, v in sys.modules.items() if k.split('.')[0] in ('typing_extensions', 'pydantic', 'pydantic_core')}
    try:
        _ensure_web_parts(tmp_path)
        assert sys.path[0] == str(sp)                         # 상자가 맨 앞 — 시스템 dist-packages 보다 먼저 찾는다
    finally:
        sys.modules.update(kept)                              # 다른 시험이 쓰던 모듈을 그대로 돌려놓는다
