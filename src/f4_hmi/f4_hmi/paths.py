# -*- coding: utf-8 -*-
"""상대경로를 **작업 폴더(워크스페이스) 기준**으로 푼다 — 🆕 9/27: hmi_bridge 를 홈에서 켜서 DB 가 ~/prewash.db 에 생기고
   `hmi_db` 는 F4 폴더의 빈 파일을 읽어 "0줄"이 나왔다(황인재). 어디서 켜든 같은 파일을 쓰게 한다.
   기준 = 이 패키지가 들어 있는 워크스페이스 루트(`<ws>/src/f4_hmi/f4_hmi/paths.py` → `<ws>`). 절대경로는 그대로."""
from pathlib import Path

WS_ROOT = Path(__file__).resolve().parents[3]                 # <ws>/src/f4_hmi/f4_hmi → <ws>
if not (WS_ROOT / 'src').is_dir():                            # 설치본만 있는 낯선 배치 → 실행 위치
    WS_ROOT = Path.cwd()


def ws_path(p) -> Path:
    q = Path(str(p)).expanduser()
    return q if q.is_absolute() else WS_ROOT / q
