# -*- coding: utf-8 -*-
"""기록(records.csv)과 소모품 임계 — FLOW-02 · SR-16 · TC-12 의 바탕.

TC-12 통과 기준(SDD §9.3): 용기 4개를 돌리면 **4행**, **필드 누락 0**.
🚨 로봇·ROS 없이 돈다. conftest 가 일회용 폴더로 옮겨 주므로 저장소에 파일이 안 생긴다.
"""
import csv

import pytest

from f2_sense_flow import mock
from f2_sense_flow.flow import Flow, load_features
from f2_sense_flow.logger import COLUMNS, Consumables, Records

from test_f2_policy import CFG, AutoResume, Quiet


@pytest.fixture(autouse=True)
def _clean():
    yield
    mock.reset()


def _run(fail_on=(), cfg=None):
    """가짜 기능으로 plan 한 바퀴 돌리고 records.csv 를 읽어 돌려준다."""
    mock.configure(list(fail_on))
    f = Flow(cfg or CFG, Quiet(), publish_event=lambda ev: None)
    f.f = load_features(['f1', 'f2', 'f3'])
    f.run_plan(AutoResume())
    with open('records.csv', encoding='utf-8') as fh:
        return list(csv.DictReader(fh)), f


# ────────────────────────────────────────────── TC-12
def test_four_containers_make_four_rows():
    """🔴 TC-12 — 용기 4개 → 4행, 열 누락 0."""
    rows, f = _run()
    assert len(rows) == 4, [r['result'] for r in rows]
    assert (f.done_bowl, f.done_cup) == (2, 2)
    for r in rows:
        assert list(r.keys()) == COLUMNS          # 열 이름·순서가 SDD §4.2 그대로
        for col in ('ts', 'kind', 'zone_id', 'rack_slot', 'result', 'code'):
            assert r[col] != '', f'{col} 이 비었다: {r}'


def test_rows_carry_each_steps_values():
    """단계마다 나온 값이 그 용기의 행에 들어간다 (mock 값 기준)."""
    rows, _ = _run()
    first = rows[0]
    assert first['kind'] == 'BOWL' and first['zone_id'] == 'RET_B'
    assert first['rack_slot'] == 'RACK_B1'
    assert first['result'] == 'DONE' and first['code'] == 'OK'
    assert int(first['attempts']) >= 1            # f1.pick 이 시도한 슬롯 수
    assert first['leftover_rounds'] != ''         # f2.leftover_loop
    assert first['seat_offset_mm'] != ''          # f1.place (안착)
    assert first['wipe_duration_s'] != ''         # f3.wipe_bowl
    assert float(first['duration_s']) >= 0.0


def test_isolated_container_is_recorded_too():
    """🚨 격리된 용기도 기록에 남는다 — "어디까지 갔나" 가 있어야 나중에 본다."""
    rows, f = _run(['place:SEAT_FAIL'])
    assert len(rows) == 4 and f.isolated == 4
    for r in rows:
        assert r['result'] == 'ISOLATED' and r['code'] == 'SEAT_FAIL'
        assert r['rack_slot'] == ''               # 팔레트에 안 들어갔다
        assert r['attempts'] != ''                # 실패 전까지 간 단계의 값은 남는다


def test_skipped_zone_is_recorded():
    """구역을 통째로 건너뛴 것도 남는다 (EMPTY_ZONE → SKIPPED)."""
    rows, _ = _run(['pick:EMPTY_ZONE'])
    assert [r['result'] for r in rows] == ['SKIPPED', 'SKIPPED']


def test_appends_across_runs():
    """🚨 다시 띄워도 앞 기록이 지워지지 않는다 — 시연 날 여러 번 돌린다."""
    rows1, _ = _run()
    mock.reset()
    rows2, _ = _run()
    assert len(rows1) == 4 and len(rows2) == 8    # 머리줄은 한 번만


# ────────────────────────────────────────────── 기록이 실패해도 공정은 계속된다
def test_write_failure_does_not_stop_the_cell(tmp_path):
    """🚨 디스크가 차거나 경로가 막혀도 용기 처리는 끝까지 간다."""
    cfg = {'flow': dict(CFG['flow'], records_path=str(tmp_path / '없는폴더' / 'r.csv'))}
    mock.configure([])
    f = Flow(cfg, Quiet(), publish_event=lambda ev: None)
    f.f = load_features(['f1', 'f2', 'f3'])
    f.run_plan(AutoResume())
    assert (f.done_bowl, f.done_cup) == (2, 2)    # 기록만 못 남기고 공정은 정상


def test_records_write_returns_false_and_warns_once(tmp_path):
    seen = []

    class L:
        def warn(self, m): seen.append(m)

    r = Records(str(tmp_path / '없는폴더' / 'r.csv'), L())
    assert r.write({'kind': 'BOWL'}) is False
    assert r.write({'kind': 'CUP'}) is False
    assert len(seen) == 1                         # 매 줄마다 외치지 않는다


def test_column_count_is_fixed_even_with_odd_rows(tmp_path):
    """🚨 열 개수는 항상 같다 — 모르는 키는 버리고, 빠진 값은 빈 칸."""
    p = tmp_path / 'r.csv'
    rec = Records(str(p))
    rec.write({'kind': 'BOWL', '엉뚱한키': 1})
    with open(p, encoding='utf-8') as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == COLUMNS
    assert len(rows[1]) == len(COLUMNS)


# ────────────────────────────────────────────── 소모품
def test_consumable_limit_key_matches_config_names():
    """카운터 이름(FlowState) ↔ 설정 키(flow.consumables) 짝."""
    assert Consumables.limit_key('sponge_uses') == 'sponge_max_uses'
    assert Consumables.limit_key('soap_dips') == 'soap_max_dips'


def test_consumable_warns_once_at_threshold():
    seen = []

    class L:
        def warn(self, m): seen.append(m)

    c = Consumables({'sponge_max_uses': 2}, L())
    assert c.check({'sponge_uses': 1}) == []
    assert c.check({'sponge_uses': 2}) == ['sponge_uses']
    assert c.check({'sponge_uses': 3}) == []      # 이미 알렸다
    assert len(seen) == 1


def test_consumable_without_limit_is_ignored():
    """임계가 없는 항목(rinse_dips)은 아무 말도 하지 않는다."""
    c = Consumables({'sponge_max_uses': 20}, None)
    assert c.check({'rinse_dips': 9999}) == []


def test_consumables_counted_during_run():
    """소모품 카운트가 용기 수만큼 올라간다 (HMI 가 /flow/state 로 본다)."""
    _, f = _run()
    assert f.sponge_uses == 4
    assert f.soap_dips == 4                      # 🔄 9/27 용기당 1회(담금 횟수 3 과 무관)
    assert f.rinse_dips == 4 * CFG['flow']['counts']['rinse_dips']
