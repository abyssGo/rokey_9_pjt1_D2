"""PreWash-Cell 기능 함수의 약속(정본). 문서: docs/02_인터페이스_IRD.md v3.0

    from cobot_api import PickResult, EMPTY_ZONE, BOWL, check_api, F1Api

이 패키지에는 로봇 코드가 없다. 약속을 바꾸면 IRD 와 이 패키지를 같이 고친다.
"""
from .contracts import *          # noqa: F401,F403
from .contracts import __all__    # noqa: F401
