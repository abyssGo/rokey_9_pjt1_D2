# -*- coding: utf-8 -*-
"""f2 시험 공통 준비.

🚨 시험은 **저장소에 파일을 만들지 않는다.** FLOW-02 로 flow 가 `records.csv` 를 남기게
   되면서, 시험을 한 번 돌릴 때마다 저장소 뿌리에 기록 파일이 생겼다.
   경로는 상대경로라 "실행한 자리" 에 생기므로,
   시험하는 동안만 일회용 폴더로 옮겨 둔다. 시험이 끝나면 pytest 가 지운다.
"""
import pytest


@pytest.fixture(autouse=True)
def _scratch_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
