# -*- coding: utf-8 -*-
"""E60 흐름 단위 — 닦기 힘 상한·시간 초과(retry:1->isolate) 두 갈래와 HMI DB 기록.

f3 시험(test_f3_wipe_bowl · test_f3_soap_cup)은 "닦기 함수 안"(즉시 정지 → 힘 끄기 → 곧게 위로)을 본다.
여기서는 그 결과 코드를 받은 **flow** 가
  ① 1회 초과 → 곧게 후퇴 → 같은 닦기 재시도 OK → DONE
  ② 2회 초과 → 격리 정리 → ISOLATED(code = 원인)
로 가는지, 그 이벤트가 HMI 기록자(StateStore → Recorder → HmiDb)의 events 표에 어떤 code 로 남는지 본다.
로봇·ROS 없이 돈다(가짜 기능 f1·f2·f3). 검증 수준: 자동 시험(가짜) — 실기 아님.
"""
import csv

import pytest

from cobot_api import F3Api, FORCE_LIMIT, OK, PICK, TIMEOUT, TOOL_LOST, WipeBowlResult
from f2_sense_flow import flow as flow_module
from f2_sense_flow import mock
from f2_sense_flow.flow import load_features

from test_f2_policy import PauseWatcher, _ns, _one_bowl, _spy_f1

HmiDb = pytest.importorskip('f4_hmi.db').HmiDb                  # f4_hmi 가 경로에 없으면 이 파일만 건너뛴다
Recorder = pytest.importorskip('f4_hmi.recorder').Recorder
StateStore = pytest.importorskip('f4_hmi.state_store').StateStore

#              종류     구역     닦기 함수     툴        스펀지 홈
_E60_KINDS = [('BOWL', 'RET_B', 'wipe_bowl', 'SPONGE', 'SPONGE_BED_B'),
              ('CUP', 'RET_C', 'wipe_cup', 'BRUSH', 'SPONGE_BED_C')]


@pytest.fixture(autouse=True)
def _clean():
    yield
    mock.reset()


def _e60_flow(kind, zone, wipe_fn, fail_on, tmp_path):
    """용기 1개 흐름 + 순서 기록 + HMI 기록자. (flow, events, order, db, store) 를 돌려준다.

    order: f1 호출 (이름, 인자) · 닦기 (함수, 결과 코드) · 후퇴 ('retreat',) 가 불린 순서대로 쌓인다.
    HMI: flow_node 대신 publish_event → StateStore.put_event,
         /flow/state(2 Hz) 대신 기능 함수 앞뒤와 PAUSED 진입 때 put_state(멈춤이 pauses 에 잡히게).
    """
    mock.configure(fail_on)
    mods = load_features(['f1', 'f2', 'f3'])
    order = []
    f1 = _spy_f1(mods, order)
    f3 = _ns(F3Api, mods['f3'])
    real_wipe = getattr(mods['f3'], wipe_fn)

    def wipe():
        r = real_wipe()
        order.append((wipe_fn, r.code))
        return r
    setattr(f3, wipe_fn, wipe)

    f, events, _ = _one_bowl(f1=f1, f3=f3)
    f.plan = [{'zone': zone, 'kind': kind, 'count': 1}]
    f._safe_retreat = lambda: order.append(('retreat',))

    db = HmiDb(tmp_path / 'hmi.db')
    store = StateStore(2.0)
    store.subscribe(Recorder(db, waste_limit_g=1e9).on_store)

    def publish(ev):
        events.append(ev)
        store.put_event(ev)
    f._publish_event = publish

    call_fn, to_paused = f.call_fn, f.to_paused

    def call_fn_with_state(mod, fname, *a):
        store.put_state(f.snapshot())
        r = call_fn(mod, fname, *a)
        store.put_state(f.snapshot())
        return r

    def to_paused_with_state(*a, **kw):
        to_paused(*a, **kw)
        store.put_state(f.snapshot())
    f.call_fn, f.to_paused = call_fn_with_state, to_paused_with_state
    store.put_state(f.snapshot())                                   # IDLE
    return f, events, order, db, store


@pytest.mark.parametrize('code', [FORCE_LIMIT, TIMEOUT])
@pytest.mark.parametrize('kind,zone,wipe_fn,tool_id,bed', _E60_KINDS)
def test_e60_wipe_fails_once_then_retry_ok_is_done(tmp_path, code, kind, zone, wipe_fn, tool_id, bed):
    """(a)·(c) 닦기 1회차 FORCE_LIMIT/TIMEOUT → flow 가 곧게 후퇴(safe_retreat) → 같은 닦기 1번 더 → OK → 툴 반납부터 이어서 DONE.
    사람을 부르지 않는다(PAUSED 0) · 격리하지 않는다 · 앞 단계(툴 집기·세제)로 되돌아가지 않는다."""
    f, events, order, db, store = _e60_flow(kind, zone, wipe_fn, [f'{wipe_fn}:{code}:1'], tmp_path)
    sig = PauseWatcher()
    f.run_plan(sig)
    store.put_state(f.snapshot())

    assert [o for o in order if o[0] in (wipe_fn, 'retreat')] == [(wipe_fn, code), ('retreat',), (wipe_fn, OK)], order
    k = order.index((wipe_fn, OK))
    assert order[k + 1] == ('tool', (tool_id, 'RETURN')), f'재시도 성공 뒤 다음 단계(툴 반납)로 가야 한다: {order[k + 1:k + 3]}'
    assert order.count(('tool', (tool_id, PICK))) == 1, '툴을 다시 집지 않는다(앞 단계로 되돌아가지 않는다)'
    assert ('place', ('ISOLATE', kind)) not in order
    assert sig.resumes == 0 and f.isolated == 0
    assert [(e['result'], e['code'], e['rack_slot']) for e in events] == [('DONE', OK, f'RACK_{kind[0]}1')]
    # HMI DB — events 1줄(DONE · OK) · 멈춤 0줄
    assert [(r['kind'], r['result'], r['code']) for r in db.dump('events')] == [(kind, 'DONE', OK)]
    assert db.dump('pauses') == []


@pytest.mark.parametrize('code', [FORCE_LIMIT, TIMEOUT])
@pytest.mark.parametrize('kind,zone,wipe_fn,tool_id,bed', _E60_KINDS)
def test_e60_wipe_fails_twice_isolates_and_hmi_db_keeps_the_code(tmp_path, code, kind, zone, wipe_fn, tool_id, bed):
    """(b)·(c) 닦기 2회(1회차 + 재시도) 모두 FORCE_LIMIT/TIMEOUT → 재시도 소진(retry:1->isolate) → 사람 없이 격리 정리:
    곧게 위로 → HOME → 툴 반납 → (스펀지 홈의 용기 처리) → 격리 구역 → HOME → 이벤트 ISOLATED · code = 원인.
    HMI DB events 에 (ISOLATED, 원인 코드) 1줄 · 멈춤 0줄.
    스펀지 홈 위 용기를 다시 집는 갈래 자체는 test_f2_policy 의 격리 정리 시험이 본다 — 여기서는 앞뒤 순서만 못 박는다."""
    f, events, order, db, store = _e60_flow(kind, zone, wipe_fn, [f'{wipe_fn}:{code}'], tmp_path)
    sig = PauseWatcher()
    f.run_plan(sig)
    store.put_state(f.snapshot())

    k = max(i for i, o in enumerate(order) if o[0] == wipe_fn)
    assert [o for o in order[:k + 1] if o[0] in (wipe_fn, 'retreat')] == [(wipe_fn, code), ('retreat',), (wipe_fn, code)]
    tail = order[k + 1:]
    assert tail[:3] == [('retreat',), ('move_to', ('HOME', True)), ('tool', (tool_id, 'RETURN'))], tail
    assert tail[-2:] == [('place', ('ISOLATE', kind)), ('move_to', ('HOME', False))], tail
    assert sig.resumes == 0, '재시도 소진은 사람을 부르지 않는다(E52 · isolate)'
    assert f.isolated == 1 and f.holding is None and f.holding_tool is None and f.on_bed is False
    assert [(e['result'], e['code'], e['rack_slot']) for e in events] == [('ISOLATED', code, '')]
    assert [(r['kind'], r['result'], r['code']) for r in db.dump('events')] == [(kind, 'ISOLATED', code)]
    assert db.dump('pauses') == []
    assert db.kpi('all')['isolated'] == 1


@pytest.mark.parametrize('code', [FORCE_LIMIT, TIMEOUT])
def test_e60_first_failure_leaves_no_code_in_event_records_or_hmi_db(tmp_path, code):
    """(d) 1회차 초과 뒤 재시도가 성공하면 이벤트 code 는 마지막 값(OK)이다(emit_event 가 last_code 를 싣는다).
    1회차 초과는 /flow/event · records.csv · HMI DB(events·pauses) 어디에도 코드로 남지 않고 로그(warn)에만 남는다.
    지금 동작을 못 박아 둔다 — 팀이 '남긴다' 로 정하면 이 시험을 바꾼다."""
    f, events, order, db, store = _e60_flow('BOWL', 'RET_B', 'wipe_bowl', [f'wipe_bowl:{code}:1'], tmp_path)
    warns = []

    class Log:
        def info(self, m): pass
        def warn(self, m): warns.append(m)
        def error(self, m): pass
    f.log = Log()
    f.run_plan(PauseWatcher())
    store.put_state(f.snapshot())

    assert ('wipe_bowl', code) in order, '1회차 초과가 주입되지 않았다'
    assert [e['code'] for e in events] == [OK]
    with open('records.csv', encoding='utf-8') as fh:               # conftest 가 일회용 폴더로 옮겨 둔 자리
        rows = list(csv.DictReader(fh))
    assert [(r['result'], r['code']) for r in rows] == [('DONE', OK)]
    assert all(r['code'] != code for t in ('events', 'pauses') for r in db.dump(t))
    assert any(f'f3.wipe_bowl 실패 → {code}' in w for w in warns), warns


@pytest.mark.xfail(strict=True, reason='재시도 결과는 _collect 하지 않는다(flow.py process_one 재시도 루프) — '
                                       '기록의 닦기 시간·힘 로그 경로가 실패한 1회차 값으로 남는다')
def test_e60_retry_success_records_the_successful_wipe_values(tmp_path):
    """재시도가 성공하면 records.csv 의 닦기 시간은 성공한 시도의 값이어야 한다(_collect 주석: '나중 값이 이긴다').
    고치면(재시도 루프에서도 _collect) 이 시험이 XPASS → strict 라 실패로 알려 준다 → xfail 표시를 지운다."""
    f, events, order, db, store = _e60_flow('BOWL', 'RET_B', 'wipe_bowl', ['wipe_bowl:FORCE_LIMIT:1'], tmp_path)
    f.run_plan(PauseWatcher())
    with open('records.csv', encoding='utf-8') as fh:
        row = list(csv.DictReader(fh))[0]
    assert float(row['wipe_duration_s']) == 15.0                    # 가짜 wipe_bowl 성공값(mock_f3) — 지금은 0.0


def test_e60_force_limit_then_tool_lost_on_retry_pauses_as_tool_lost(tmp_path, monkeypatch):
    """툴 놓침 연출(사람이 닦는 도중 툴을 뺀다) — 당기는 힘이 먼저 누름 상한을 넘으면 1회차는 FORCE_LIMIT 이다.
    재시도에서 TOOL_LOST 가 나면 flow 는 **새 코드의 정책(pause)** 으로 멈추고, 재개 뒤 툴을 다시 집어 DONE 까지 간다.
    첫 코드(FORCE_LIMIT)의 정책(격리)으로 치우면 안 된다."""
    monkeypatch.setattr(flow_module.cc, 'start_nudge_watch', lambda: None)
    monkeypatch.setattr(flow_module.cc, 'check_nudge', lambda *a: False)       # 여기선 HMI 재개(AutoResume)만 본다
    f, events, order, db, store = _e60_flow('BOWL', 'RET_B', 'wipe_bowl', [], tmp_path)
    ok_wipe = f.f['f3'].wipe_bowl
    codes = iter([FORCE_LIMIT, TOOL_LOST])

    def wipe_bowl():
        c = next(codes, None)
        if c is None:
            return ok_wipe()
        order.append(('wipe_bowl', c))
        return WipeBowlResult.fail(c)
    f.f['f3'].wipe_bowl = wipe_bowl
    sig = PauseWatcher()
    f.run_plan(sig)
    store.put_state(f.snapshot())

    assert [o for o in order if o[0] in ('wipe_bowl', 'retreat')][:3] == [
        ('wipe_bowl', FORCE_LIMIT), ('retreat',), ('wipe_bowl', TOOL_LOST)]
    assert sig.resumes == 1, f'TOOL_LOST 로 한 번 멈춰야 한다 ({sig.resumes})'
    assert order.count(('tool', ('SPONGE', PICK))) == 2, '처음 1 + 놓친 뒤 다시 집기 1'
    assert ('place', ('ISOLATE', 'BOWL')) not in order and f.isolated == 0
    assert [(e['result'], e['code']) for e in events] == [('DONE', OK)]
    assert [(p['kind'], p['code']) for p in db.dump('pauses')] == [('tool_lost', TOOL_LOST)]


def test_e60_force_limit_then_robot_error_on_retry_stops_in_place(tmp_path, monkeypatch):
    """재시도 전 툴 쥠 확인(E61 · flow._tool_held)이 판단을 못 하는 경우(폭을 못 읽음 · 여기 시험 설정처럼 프리셋이 없음)엔
    재시도를 그대로 한다. 그 재시도가 기능 함수 안에서 터지면(ROBOT_ERROR) flow 는 격리하지 않고 로봇 오류 절차:
    그 자리 멈춤 → 신호 1(그리퍼만 열기) → 신호 2(재개 버튼) → 곧게 위로 → HOME → ERROR.
    폭을 읽을 수 있고 툴이 없으면 재시도 없이 툴 놓침 멈춤으로 간다 — test_f2_policy 의 E61 시험이 본다."""
    released = []
    monkeypatch.setattr(flow_module.cc, 'release', lambda: released.append(1))
    monkeypatch.setattr(flow_module.cc, 'start_nudge_watch', lambda: None)
    monkeypatch.setattr(flow_module.cc, 'check_nudge', lambda *a: False)
    f, events, order, db, store = _e60_flow('BOWL', 'RET_B', 'wipe_bowl', [], tmp_path)
    codes = iter([FORCE_LIMIT])

    def wipe_bowl():
        c = next(codes, None)
        if c is None:
            order.append(('wipe_bowl', 'BOOM'))
            raise RuntimeError('바닥을 못 찾았다')                  # 실제 wipe_bowl 은 이걸 잡아 ROBOT_ERROR 로 돌려준다
        order.append(('wipe_bowl', c))
        return WipeBowlResult.fail(c)
    f.f['f3'].wipe_bowl = wipe_bowl
    sig = PauseWatcher()
    f.run_plan(sig)

    assert [o for o in order if o[0] in ('wipe_bowl', 'retreat')][:3] == [
        ('wipe_bowl', FORCE_LIMIT), ('retreat',), ('wipe_bowl', 'BOOM')]
    assert sig.resumes == 2 and released == [1], '툴을 쥔 것으로 기록돼 있어 신호 2번 · 그리퍼 한 번 열기'
    assert ('place', ('ISOLATE', 'BOWL')) not in order and f.isolated == 0
    assert [(e['result'], e['code']) for e in events] == [('ERROR', 'ROBOT_ERROR')]
