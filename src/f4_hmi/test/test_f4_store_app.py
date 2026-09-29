# -*- coding: utf-8 -*-
"""보관함(StateStore)과 웹 응답(GET /api/state). ROS 불필요. 웹 부품(fastapi)이 없는 PC 에서는 app 시험만 건너뛴다."""
from pathlib import Path

import pytest

from f4_hmi.state_store import FORCE_FRESH_S, RECENT_EVENTS, WEIGH_FRESH_S, StateStore


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def test_store_remembers_step_before_pause():
    # 멈춘 뒤에 연 화면도 "어느 단계에서 멈췄나"를 알도록 브리지가 직전 단계를 든다. 운전으로 돌아가면 지운다
    store = StateStore(2.0, Clock())
    assert store.snapshot()['paused_from'] is None
    store.put_state({'step': 'WIPE'})
    store.put_state({'step': 'PAUSED'})
    assert store.snapshot()['paused_from'] == 'WIPE'
    store.put_state({'step': 'PAUSED'})                      # 멈춤이 이어져도 그대로
    assert store.live()['paused_from'] == 'WIPE'
    store.put_state({'step': 'WIPE'})
    assert store.snapshot()['paused_from'] is None
    store.put_state({'step': 'IDLE'}); store.put_state({'step': 'PAUSED'})   # 운전 중이 아니었으면 모른다
    assert store.snapshot()['paused_from'] is None


def test_store_is_disconnected_until_first_state():
    snap = StateStore(2.0, Clock()).snapshot()
    assert snap['connected'] is False and snap['state'] is None and snap['age_s'] is None and snap['events'] == []


def test_store_connection_follows_age_of_last_state():
    clock = Clock()
    store = StateStore(2.0, clock)
    store.put_state({'step': 'PICK'})
    clock.t += 1.9
    assert store.snapshot()['connected'] is True and store.snapshot()['age_s'] == 1.9
    clock.t += 0.2                                                          # 2 s 넘게 없다 → 끊김. 마지막 값은 남겨 둔다
    snap = store.snapshot()
    assert snap['connected'] is False and snap['state'] == {'step': 'PICK'} and snap['received'] == 1


def test_store_force_is_none_when_not_wiping():
    clock = Clock()
    store = StateStore(2.0, clock)
    store.put_force(5.25)
    assert store.snapshot()['force_n'] == 5.25
    clock.t += FORCE_FRESH_S + 0.01                                         # 닦는 동안만 온다 → 끊기면 '닦는 중 아님'
    assert store.snapshot()['force_n'] is None


def test_store_weigh_keeps_samples_and_median_only_when_done():
    # 무게를 재는 동안: 표본을 읽는 대로 목록이 길어지고, 다 재면 중앙값이 붙는다. 값은 0.1 g 으로 반올림
    clock = Clock()
    store = StateStore(2.0, clock)
    assert store.snapshot()['weigh'] is None
    heard = []
    store.subscribe(lambda kind, payload: heard.append((kind, payload)))
    store.put_weigh({'kind': 'BOWL', 'target_n': 15, 'samples_g': [79.79657745361328, -3.04], 'done': False, 'median_g': 0.0, 'stamp': 1.0})
    w = store.snapshot()['weigh']
    assert w['samples_g'] == [79.8, -3.0] and w['target_n'] == 15 and w['done'] is False and w['median_g'] is None and w['age_s'] == 0.0
    assert heard[-1][0] == 'weigh' and heard[-1][1]['weigh']['samples_g'] == [79.8, -3.0]
    store.put_weigh({'kind': 'BOWL', 'target_n': 15, 'samples_g': [79.8, -3.0, 81.2], 'done': True, 'median_g': 79.84, 'stamp': 2.0})
    w = store.live()['weigh']
    assert w['done'] is True and w['median_g'] == 79.8 and len(w['samples_g']) == 3
    w['samples_g'].append(1.0)                                              # 사본이다
    assert len(store.snapshot()['weigh']['samples_g']) == 3
    clock.t += WEIGH_FRESH_S + 0.1                                          # 지난 측정은 내보내지 않는다
    assert store.snapshot()['weigh'] is None


def test_store_keeps_recent_events_newest_first_and_copies():
    store = StateStore(2.0, Clock())
    for i in range(RECENT_EVENTS + 5):
        store.put_event({'n': i})
    events = store.snapshot()['events']
    assert len(events) == RECENT_EVENTS and events[0] == {'n': RECENT_EVENTS + 4}
    events[0]['n'] = -1                                                     # 꺼낸 사본을 고쳐도 보관함은 그대로
    assert store.snapshot()['events'][0] == {'n': RECENT_EVENTS + 4}
    store.put_gripping(1)
    assert store.snapshot()['gripping'] is True


def test_api_state_and_test_page(tmp_path):
    pytest.importorskip('fastapi', reason='웹 부품은 HMI 전용 상자(~/venvs/hmi)에만 있다 — 그 상자의 파이썬으로 돌리면 실행된다')
    from fastapi.testclient import TestClient
    from f4_hmi.app import create_app
    store = StateStore(2.0)
    cfg = {'flow': {'plan': [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 2}], 'rack_order': {'BOWL': ['RACK_B1', 'RACK_B2']},
                    'consumables': {'sponge_max_uses': 20}}}
    client = TestClient(create_app(store, cfg, web_dir=tmp_path))      # 운영 화면이 없는 PC → / 에 시험 페이지
    body = client.get('/api/state').json()
    assert body['connected'] is False and body['state'] is None and body['plan']['rack_order'] == {'BOWL': ['RACK_B1', 'RACK_B2']}
    store.put_state({'step': 'WIPE', 'kind': 'BOWL', 'done_bowl': 1})
    store.put_gripping(True)
    body = client.get('/api/state').json()
    assert body['connected'] is True and body['state']['step'] == 'WIPE' and body['gripping'] is True
    page = client.get('/')
    assert page.status_code == 200 and '/api/state' in page.text
    assert client.get('/test').text == page.text                   # /test 는 언제나 시험 페이지


def test_operator_screen_is_served_without_hiding_the_api(tmp_path):
    """F4-03: web/out/ 이 있으면 / 는 운영 화면. 그래도 /api · /ws · /test 는 그대로 살아 있어야 한다(가려지면 화면이 값을 못 받는다)."""
    pytest.importorskip('fastapi', reason='웹 부품은 HMI 전용 상자(~/venvs/hmi)에만 있다')
    from fastapi.testclient import TestClient
    from f4_hmi.app import create_app
    (tmp_path / 'index.html').write_text('<html>operator screen</html>', encoding='utf-8')
    (tmp_path / '_next').mkdir()
    (tmp_path / '_next' / 'app.js').write_text('console.log(1)', encoding='utf-8')
    store = StateStore(2.0)
    app = create_app(store, {'flow': {}}, web_dir=tmp_path)
    assert app.state.web is True
    client = TestClient(app)
    assert 'operator screen' in client.get('/').text               # 운영 화면
    assert client.get('/_next/app.js').status_code == 200          # 화면이 쓰는 파일들
    assert '/api/state' in client.get('/test').text                # 시험 페이지는 /test 로
    assert client.get('/api/state').json()['connected'] is False   # API 는 가려지지 않는다
    assert client.post('/api/start').json()['ok'] is False         # 버튼도(시험 모드라 flow 없음 대답)
    with client.websocket_connect('/ws/state') as ws:              # WebSocket 도
        assert ws.receive_json()['type'] == 'state'


def test_get_never_presses_a_button_even_with_the_operator_screen(tmp_path):
    """화면을 / 에 붙이면 나머지 주소를 화면 쪽이 받아 가서, 버튼 주소에 GET 으로 오면 405 대신 404 가 난다.
    어느 쪽이든 중요한 것은 하나 — **GET 으로는 버튼이 눌리지 않는다**(링크·주소창·미리보기가 로봇을 움직이면 안 된다)."""
    pytest.importorskip('fastapi', reason='웹 부품은 HMI 전용 상자(~/venvs/hmi)에만 있다')
    from fastapi.testclient import TestClient
    from f4_hmi.app import create_app, COMMANDS
    (tmp_path / 'index.html').write_text('<html>operator screen</html>', encoding='utf-8')
    pressed = []
    client = TestClient(create_app(StateStore(2.0), {'flow': {}}, lambda n: pressed.append(n) or {'ok': True}, web_dir=tmp_path))
    for name in COMMANDS:
        assert client.get(f'/api/{name}').status_code in (404, 405), name
    assert pressed == []                                             # 하나도 안 눌렸다
    assert client.post('/api/stop').json()['ok'] is True and pressed == ['stop']   # POST 는 그대로 전달


# ------------------------------------------------------------------ F4-02: 구독 · 버튼 · WebSocket
def test_store_tells_listeners_what_changed():
    store = StateStore(2.0, Clock())
    heard = []
    store.subscribe(lambda kind, payload: heard.append((kind, payload)))
    store.put_state({'step': 'PICK'})
    store.put_event({'result': 'DONE'})
    store.put_force(4.236)
    store.put_gripping(True)
    store.put_gripping(True)                                                # 같은 값이 2 Hz 로 계속 와도 바뀔 때만 알린다
    store.put_gripping(False)
    kinds = [k for k, _ in heard]
    assert kinds == ['state', 'event', 'force', 'gripping', 'gripping']
    assert heard[0][1]['state'] == {'step': 'PICK'} and 'events' not in heard[0][1]     # state 몸통에는 이벤트 목록을 싣지 않는다
    assert heard[1][1] == {'event': {'result': 'DONE'}} and heard[2][1] == {'n': 4.24}
    assert [p['value'] for k, p in heard if k == 'gripping'] == [True, False]


def _client(command=None):
    pytest.importorskip('fastapi', reason='웹 부품은 HMI 전용 상자(~/venvs/hmi)에만 있다')
    from fastapi.testclient import TestClient
    from f4_hmi.app import create_app
    store = StateStore(2.0)
    no_web = Path(__file__).resolve().parent / '_no_web_build'          # 없는 폴더 — 이 PC 에 화면을 빌드했든 안 했든 같은 결과가 나오게
    return store, TestClient(create_app(store, {'flow': {}}, command, web_dir=no_web))


def test_buttons_pass_the_flow_answer_through():
    pressed = []

    def command(name):
        pressed.append(name)
        return {'ok': name != 'abort', 'message': f'{name} 받음', 'latency_ms': 3}
    _, client = _client(command)
    for name in ('start', 'stop', 'resume', 'abort'):
        body = client.post(f'/api/{name}').json()
        assert body == {'ok': name != 'abort', 'message': f'{name} 받음', 'latency_ms': 3}
    assert pressed == ['start', 'stop', 'resume', 'abort']
    assert client.post('/api/explode').status_code in (404, 405)            # 없는 버튼
    assert client.get('/api/start').status_code == 405                      # 버튼은 POST 만


def test_buttons_without_flow_link_say_so():
    _, client = _client(None)
    body = client.post('/api/start').json()
    assert body['ok'] is False and body['message']


def test_websocket_sends_everything_first_then_pushes_changes():
    store, client = _client()
    store.put_state({'step': 'IDLE', 'last_code': 'OK'})
    with client.websocket_connect('/ws/state') as ws:
        first = ws.receive_json()
        assert first['type'] == 'state' and first['state']['step'] == 'IDLE' and 'events' in first and 'plan' in first
        store.put_state({'step': 'PICK', 'last_code': 'OK'})                # ROS 스레드에서 들어온 셈 — 다른 스레드에서 넣는다
        msg = ws.receive_json()
        assert msg['type'] == 'state' and msg['state']['step'] == 'PICK' and 'events' not in msg
        store.put_event({'result': 'DONE', 'kind': 'BOWL'})
        assert ws.receive_json() == {'type': 'event', 'event': {'result': 'DONE', 'kind': 'BOWL'}}
        store.put_force(5.5)
        assert ws.receive_json() == {'type': 'force', 'n': 5.5}
        store.put_gripping(True)
        assert ws.receive_json() == {'type': 'gripping', 'value': True}


def test_websocket_reports_lost_connection():
    pytest.importorskip('fastapi')
    from fastapi.testclient import TestClient
    from f4_hmi import app as app_module
    from f4_hmi.app import create_app
    clock = Clock()
    store = StateStore(2.0, clock)
    store.put_state({'step': 'WIPE'})
    app_module.CONN_CHECK_S = 0.05
    try:
        with TestClient(create_app(store, {})).websocket_connect('/ws/state') as ws:
            assert ws.receive_json()['connected'] is True
            clock.t += 5.0                                                  # flow 가 5 s 동안 조용하다
            assert ws.receive_json() == {'type': 'conn', 'connected': False}
            store.put_state({'step': 'WIPE'})                               # 다시 온다
            got = [ws.receive_json(), ws.receive_json()]
            assert {'type': 'conn', 'connected': True} in got
    finally:
        app_module.CONN_CHECK_S = 0.5


def test_hub_drops_oldest_when_a_browser_is_slow():
    import asyncio
    from f4_hmi import hub as hub_module
    from f4_hmi.hub import Hub

    async def scenario():
        h = Hub()
        q = h.join()
        for i in range(hub_module.QUEUE_MAX + 10):
            h._fan_out({'n': i})
        assert q.qsize() == hub_module.QUEUE_MAX and q.get_nowait() == {'n': 10}     # 오래된 10개를 버렸다
        h.leave(q)
        assert h.clients == 0
        h.from_ros('state', {})                                             # 붙은 브라우저가 없으면 아무 일도 없다
    asyncio.run(scenario())


def test_store_counts_runs_and_full_pallets_when_flow_reaches_done():
    """flow 가 계획을 마치고 DONE 으로 넘어가는 순간 = 한 회차. 칸을 다 채우고 끝났으면 팔레트 1장 완료."""
    store = StateStore(2.0, Clock(), rack_slots=4)
    run = lambda b, c, iso=0: [{'step': 'RACK', 'done_bowl': b, 'done_cup': c, 'isolated': iso},
                               {'step': 'DONE', 'done_bowl': b, 'done_cup': c, 'isolated': iso},
                               {'step': 'DONE', 'done_bowl': b, 'done_cup': c, 'isolated': iso},   # DONE 이 1초 동안 여러 번 와도 한 번만
                               {'step': 'IDLE', 'done_bowl': b, 'done_cup': c, 'isolated': iso}]
    for s in run(2, 2) + run(1, 2, 1) + run(2, 2):
        store.put_state(s)
    assert store.snapshot()['totals'] == {'runs': 3, 'pallets': 2, 'bowls': 5, 'cups': 6, 'isolated': 1, 'rack_slots': 4}


def test_store_does_not_count_a_run_it_did_not_see_start():
    store = StateStore(2.0, Clock(), rack_slots=4)
    store.put_state({'step': 'DONE', 'done_bowl': 2, 'done_cup': 2})       # HMI 를 켰더니 이미 DONE — 이 회차는 못 봤다
    store.put_state({'step': 'IDLE', 'done_bowl': 2, 'done_cup': 2})
    assert store.snapshot()['totals']['runs'] == 0
