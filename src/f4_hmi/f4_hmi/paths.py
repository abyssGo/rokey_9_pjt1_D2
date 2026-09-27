# -*- coding: utf-8 -*-
"""상대경로를 작업 폴더(워크스페이스) 기준으로 푼다 — 실행 위치 기준이면 hmi_bridge 와 hmi_db 를 다른 폴더에서 켰을 때
   서로 다른 DB 파일을 보게 된다(홈에서 켜면 ~/prewash.db 가 생긴다). 어디서 켜든 같은 파일을 쓰게 한다.
   기준 = 이 패키지가 들어 있는 워크스페이스 루트(`<ws>/src/f4_hmi/f4_hmi/paths.py` → `<ws>`). 절대경로는 그대로."""
from pathlib import Path

WS_ROOT = Path(__file__).resolve().parents[3]                 # <ws>/src/f4_hmi/f4_hmi → <ws>
if not (WS_ROOT / 'src').is_dir():                            # 설치본만 있는 낯선 배치 → 실행 위치
    WS_ROOT = Path.cwd()


def ws_path(p) -> Path:
    """p 가 상대경로면 WS_ROOT 아래로, 절대경로(~ 포함)면 그대로."""
    q = Path(str(p)).expanduser()
    return q if q.is_absolute() else WS_ROOT / q
