# -*- coding: utf-8 -*-
"""F4-04·05 — SQLite 기록(db.py) · 기록자(recorder.py) · API. ROS 없이 돈다(app 시험은 fastapi 가 있는 상자에서만)."""
import pytest

from f4_hmi.db import HmiDb, ITEMS, TABLES
from f4_hmi.recorder import Recorder, pause_kind
from f4_hmi.state_store import StateStore


class Clock:
    """시험용 시계 — ISO 문자열을 순서대로 낸다."""
    def __init__(self, day='2026-09-29'):
        self.day, self.n = day, 0

    def __call__(self):
        self.n += 1
        return f'{self.day}T10:{self.n // 60:02d}:{self.n % 60:02d}'


def ev(kind='BOWL', result='DONE', before=0.0, after=0.0, dur=60.0, code='OK', slot='RACK_B1', attempts=1):
    return dict(kind=kind, zone_id='RET_B' if kind == 'BOWL' else 'RET_C', rack_slot=slot if result == 'DONE' else '',
                result=result, code=code, attempts=attempts, weight_before_g=before, weight_after_g=after, duration_s=dur)


@pytest.fixture
def db(tmp_path):
    d = HmiDb(tmp_path / 't.db', leftover_threshold_g=50.0, now=Clock())
    yield d
    d.close()


def test_tables_exist_and_event_row_keeps_flow_fields(db):
    assert set(TABLES) == {'events', 'runs', 'pauses', 'commands', 'replacements'}
    db.add_event(ev(before=94.0, after=2.0, dur=71.2))
    row = db.dump('events')[0]
    assert row['kind'] == 'BOWL' and row['result'] == 'DONE' and row['rack_slot'] == 'RACK_B1'
    assert row['weight_before_g'] == 94.0 and row['weight_after_g'] == 2.0 and row['duration_s'] == 71.2
    assert row['waste_g'] == 92.0 and row['ts'].startswith('2026-09-29T')
    assert 'force_log_path' not in row and 'source' not in row              # 황인재 9/27: 뺀 항목


def test_waste_counts_only_when_leftover_was_dumped(db):
    db.add_event(ev(before=30.0, after=0.0))          # 잔반 판정 안 남(≤ 50) → 털지 않았다 → 0
    db.add_event(ev(before=94.0, after=4.0))          # 잔반 → 90 g
    db.add_event(ev(before=94.0, after=4.0, result='SKIPPED'))
    assert [r['waste_g'] for r in db.dump('events')] == [0.0, 90.0, 0.0]
    assert db.usage()['waste_bin']['used_g'] == 90.0


def test_usage_counts_since_last_replacement(db):
    for _ in range(3):
        db.add_event(ev('BOWL'))
    for _ in range(2):
        db.add_event(ev('CUP', slot='RACK_C1'))
    db.add_event(ev('BOWL', result='ISOLATED', code='LEFTOVER_REMAIN'))        # 완료가 아니면 사용으로 안 센다
    u = db.usage()
    assert (u['sponge']['used'], u['brush']['used'], u['soap']['used']) == (3, 2, 5)
    db.add_replacement('sponge', '시험')
    db.add_event(ev('BOWL'))
    u = db.usage()
    assert (u['sponge']['used'], u['brush']['used'], u['soap']['used']) == (1, 2, 6)
    with pytest.raises(ValueError):
        db.add_replacement('bowl')
    assert set(ITEMS) == {'sponge', 'brush', 'soap', 'waste_bin'}


def test_kpi_totals_averages_and_pauses(db):
    rid = db.start_run()
    db.add_event(ev('BOWL', dur=60.0, before=94.0, after=2.0), run_id=rid)
    db.add_event(ev('BOWL', dur=80.0), run_id=rid)
    db.add_event(ev('CUP', dur=40.0, slot='RACK_C1'), run_id=rid)
    db.add_event(ev('CUP', result='ISOLATED', code='FORCE_LIMIT'), run_id=rid)
    db.add_event(ev('CUP', dur=30.0, before=165.0, after=121.0, slot='RACK_C2'), run_id=rid)   # 가짜 flow 처럼 컵에 무게가 있어도 잔반 비율은 그릇만
    pid = db.open_pause(rid, 'WIPE', 'tool_lost', 'TOOL_LOST')
    db.close_pause(pid, 'nudge')
    db.end_run(rid, {'done_bowl': 2, 'done_cup': 1, 'isolated': 1})
    k = db.kpi('run')
    assert (k['total'], k['done_bowl'], k['done_cup'], k['isolated'], k['error'], k['skipped']) == (5, 2, 2, 1, 0, 0)
    assert k['success_pct'] == 80.0 and k['avg_s_bowl'] == 70.0 and k['avg_s_cup'] == 35.0
    assert k['pauses'] == 1 and k['pause_top'] == 'tool_lost' and k['pause_s'] is not None
    assert k['leftover_pct'] == 50.0 and k['waste_g'] == 136.0 and k['runs'] == 1
    assert db.kpi('today')['total'] == 5 and db.kpi('all')['total'] == 5
    run = db.dump('runs')[0]
    assert run['ended_at'] and (run['done_bowl'], run['done_cup'], run['isolated']) == (2, 1, 1)   # runs 는 flow 가 준 상태값 그대로


def test_kpi_pallets_count_runs_that_filled_the_rack(tmp_path):
    # 🆕 9/28 황인재: 처리한 팔레트 수 — 칸(rack_slots)을 다 채우고 끝난 회차만. 기간(run·all)을 따르고, 칸 수를 모르면 0
    d = HmiDb(tmp_path / 'p.db', now=Clock(), rack_slots=4)
    r1 = d.start_run(); d.end_run(r1, {'done_bowl': 2, 'done_cup': 2, 'isolated': 0})
    r2 = d.start_run(); d.end_run(r2, {'done_bowl': 1, 'done_cup': 2, 'isolated': 1})
    assert d.kpi('all')['pallets'] == 1 and d.kpi('today')['pallets'] == 1
    assert d.kpi('run')['pallets'] == 0 and d.kpi('run', run_id=r1)['pallets'] == 1
    r3 = d.start_run()                                                          # 진행 중인 회차는 세지 않는다
    assert d.kpi('all')['pallets'] == 1
    assert HmiDb(tmp_path / 'q.db', now=Clock()).kpi('all')['pallets'] == 0


def test_recent_events_have_stamp_for_the_screen(db):
    db.add_event(ev())
    e = db.recent_events(5)[0]
    assert isinstance(e['stamp'], float) and e['kind'] == 'BOWL'


# ------------------------------------------------------------------ 기록자
def _state(step, **kw):
    base = dict(step=step, kind='BOWL', zone_id='RET_B', done_bowl=0, done_cup=0, isolated=0, last_code='OK', message='')
    base.update(kw)
    return base


def test_recorder_makes_runs_pauses_and_events(db):
    calls = []
    rec = Recorder(db, command=lambda name: calls.append(name) or {'ok': True, 'message': 'x', 'latency_ms': 1}, waste_limit_g=50000)
    store = StateStore(2.0)
    store.subscribe(rec.on_store)
    store.put_state(_state('IDLE'))
    store.put_state(_state('PICK'))                         # 회차 시작
    assert rec.run_id is not None
    store.put_state(_state('WIPE'))
    store.put_state(_state('PAUSED', last_code='TOOL_LOST'))
    rec.record_command('resume', {'ok': True, 'message': '재개합니다', 'latency_ms': 2})
    store.put_state(_state('WIPE'))                         # 멈춤이 풀렸다 — 재개 버튼으로
    store.put_event(ev(before=94.0, after=2.0))
    store.put_state(_state('DONE', done_bowl=1))
    assert rec.run_id is None
    p = db.dump('pauses')[0]
    assert (p['step'], p['kind'], p['code'], p['resolved']) == ('WIPE', 'tool_lost', 'TOOL_LOST', 'resume') and p['ended_at']
    assert db.dump('events')[0]['run_id'] == db.dump('runs')[0]['id']
    assert db.dump('commands')[0]['name'] == 'resume'
    assert calls == []                                      # 잔반통이 안 찼으니 stop 을 보내지 않았다


def test_recorder_closes_run_when_flow_restarts_without_done(db):
    # 🆕 9/28 flow 를 도중에 껐다 켜면(DONE 없이 IDLE) 지난 회차를 마지막 작업 상태로 닫는다 — 다음 회차의 KPI(이번 실행)에 섞이지 않게
    rec = Recorder(db, waste_limit_g=50000)
    store = StateStore(2.0)
    store.subscribe(rec.on_store)
    store.put_state(_state('IDLE')); store.put_state(_state('PICK')); store.put_state(_state('WIPE', done_bowl=1))
    store.put_state(_state('PAUSED', last_code='TOOL_LOST', done_bowl=1))
    r1 = rec.run_id
    store.put_state(_state('IDLE'))                         # flow 재시작 — DONE 없이 IDLE
    assert rec.run_id is None and rec.pause_id is None
    run = [r for r in db.dump('runs') if r['id'] == r1][0]
    assert run['ended_at'] and run['done_bowl'] == 1
    assert db.dump('pauses')[0]['resolved'] == 'restart'
    store.put_state(_state('PICK'))
    assert rec.run_id is not None and rec.run_id != r1


def test_recorder_pause_kind_and_nudge_resolution(db):
    rec = Recorder(db, waste_limit_g=50000)
    assert pause_kind({'last_code': 'ROBOT_ERROR', 'message': '케이블 상태를 확인해주세요'}) == 'cable'
    assert pause_kind({'last_code': 'TOOL_FAIL', 'message': ''}) == 'tool_fail'
    assert pause_kind({'last_code': 'OK', 'message': ''}) == 'operator'
    rec.on_store('state', {'state': _state('PICK')})
    rec.on_store('state', {'state': _state('PAUSED', last_code='ROBOT_ERROR', message='케이블 …')})
    rec.on_store('state', {'state': _state('WEIGH')})       # 버튼 없이 풀렸다 → 넛지(로봇팔 가볍게 밀기)
    assert db.dump('pauses')[0]['resolved'] == 'nudge' and db.dump('pauses')[0]['kind'] == 'cable'
    rec.on_store('state', {'state': _state('PAUSED')})
    rec.on_store('state', {'state': _state('ISOLATE')})     # 중단 버튼 기록이 없어도 격리로 갔으면 abort
    assert db.dump('pauses')[0]['resolved'] == 'abort'


def test_recorder_sends_stop_once_when_waste_bin_is_full_and_resets_on_replace(db):
    calls, done = [], []
    import threading
    got = threading.Event()

    def command(name):
        calls.append(name)
        got.set()
        return {'ok': True, 'message': '즉시 멈춥니다', 'latency_ms': 1}

    rec = Recorder(db, command=command, waste_limit_g=150.0)
    rec.on_store('event', {'event': ev(before=94.0, after=2.0)})          # 92 g
    assert rec.notices()['waste_full'] is False and calls == []
    rec.on_store('event', {'event': ev(before=94.0, after=2.0)})          # 184 g ≥ 150 → stop 1번
    assert got.wait(2.0) and calls == ['stop'] and rec.notices()['waste_full'] is True
    rec.on_store('event', {'event': ev(before=94.0, after=2.0)})          # 이미 가득 — 또 보내지 않는다
    assert calls == ['stop']
    for _ in range(20):                                                   # stop 기록이 스레드에서 끝날 때까지
        if any(c['name'] == 'stop' for c in db.dump('commands')):
            break
        import time; time.sleep(0.05)
    assert any('[잔반통 가득]' in c['message'] for c in db.dump('commands'))
    rec.on_store('state', {'state': _state('RACK')})
    rec.on_store('state', {'state': _state('PAUSED')})                    # HMI 가 보낸 일시 정지 → 원인 = 잔반통
    assert db.dump('pauses')[0]['kind'] == 'waste_bin'
    rec.replace('waste_bin')
    assert rec.notices()['waste_full'] is False and db.usage()['waste_bin']['used_g'] == 0.0
    rec2 = Recorder(db, command=command, waste_limit_g=150.0)             # 껐다 켜도 교체 뒤라 가득이 아니다
    assert rec2.waste_full is False


def test_store_preload_puts_newest_first():
    store = StateStore(2.0)
    store.preload_events([{'n': 3}, {'n': 2}, {'n': 1}])   # DB 가 주는 순서(최근 것이 앞)
    assert [e['n'] for e in store.snapshot()['events']] == [3, 2, 1]
    store.put_event({'n': 4})
    assert [e['n'] for e in store.snapshot()['events']][:2] == [4, 3]


# ------------------------------------------------------------------ API (fastapi 가 있는 상자에서만)
def test_api_usage_kpi_replace_and_db(tmp_path):
    pytest.importorskip('fastapi', reason='웹 부품은 HMI 전용 상자(~/venvs/hmi)에만 있다')
    from fastapi.testclient import TestClient
    from f4_hmi.app import create_app
    db = HmiDb(tmp_path / 'a.db', now=Clock())
    calls = []
    rec = Recorder(db, command=lambda n: calls.append(n) or {'ok': True, 'message': 'ok', 'latency_ms': 1}, waste_limit_g=50000)
    store = StateStore(2.0)
    store.subscribe(rec.on_store)
    cfg = {'flow': {'plan': [], 'rack_order': {'BOWL': ['RACK_B1']}, 'consumables': {'sponge_max_uses': 100, 'soap_max_dips': 60}}}
    client = TestClient(create_app(store, cfg, command=lambda n: calls.append(n) or {'ok': True, 'message': 'ok', 'latency_ms': 1},
                                   web_dir=tmp_path, recorder=rec))
    store.put_event(ev(before=94.0, after=2.0))
    body = client.get('/api/state').json()
    assert body['usage']['sponge']['used'] == 1 and body['limits']['brush'] == 100 and body['notices']['waste_full'] is False
    assert client.get('/api/kpi?period=all').json()['done_bowl'] == 1
    assert client.get('/api/kpi?period=week').status_code == 400
    r = client.post('/api/replace/sponge').json()
    assert r['ok'] and r['usage']['sponge']['used'] == 0
    assert client.post('/api/replace/bowl').status_code == 400
    assert client.get('/api/db/replacements').json()['rows'][0]['item'] == 'sponge'
    assert client.get('/api/db/nope').status_code == 400
    client.post('/api/resume')
    assert client.get('/api/db/commands').json()['rows'][0]['name'] == 'resume'
    assert client.get('/api/history?limit=5').json()['events'][0]['kind'] == 'BOWL'
    plain = TestClient(create_app(StateStore(2.0), cfg, web_dir=tmp_path))
    assert plain.get('/api/usage').status_code == 503                    # 기록 없이 띄운 서버(시험)는 503


def test_ws_path_resolves_relative_to_workspace_root(tmp_path, monkeypatch):
    """🆕 9/27 — 홈에서 켜도 DB 는 워크스페이스의 파일(황인재: 홈에 생긴 DB 와 F4 폴더의 빈 DB 가 달랐다)."""
    from f4_hmi import paths
    monkeypatch.chdir(tmp_path)
    assert paths.ws_path('prewash.db') == paths.WS_ROOT / 'prewash.db'
    assert (paths.WS_ROOT / 'src' / 'f4_hmi').is_dir()
    assert paths.ws_path('/tmp/x.db') == __import__('pathlib').Path('/tmp/x.db')
    assert paths.ws_path('~/y.db').is_absolute()


def test_recorder_pause_kind_cable_needs_robot_error_code():
    """케이블 복구 뒤 남은 '케이블 정상 확인' 문구로 다음 멈춤(일시 정지·툴 놓침)을 케이블로 적지 않는다 — 화면과 같은 규칙."""
    from f4_hmi.recorder import pause_kind
    assert pause_kind({'last_code': 'ROBOT_ERROR', 'message': '케이블 상태를 확인해주세요.'}) == 'cable'
    assert pause_kind({'last_code': 'OK', 'message': '케이블 정상 확인 — 작업을 재개합니다'}) == 'operator'
    assert pause_kind({'last_code': 'TOOL_LOST', 'message': '케이블 정상 확인 — 작업을 재개합니다'}) == 'tool_lost'

