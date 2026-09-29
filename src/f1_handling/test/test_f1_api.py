"""F1 약속(F1Api) 일치 시험 — 로봇 없이 돈다. pick·rack_place·tool(F1-03)까지 전부 구현돼 골격 시험은 없앴다.  실행: python3 -m pytest -q src/f1_handling
파일 이름에 패키지 이름을 넣는다 — 같은 이름이 두 패키지에 있으면 한 번에 돌릴 때 수집이 깨진다."""
from cobot_api import F1Api, check_api
from f1_handling import handling


def test_handling_matches_f1api():
    assert check_api(handling, F1Api) == []

