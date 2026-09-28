# -*- coding: utf-8 -*-
"""웹 쪽 입 — 브라우저의 요청에 답하고(REST), 새 값을 밀어 준다(WebSocket). ROS 를 모른다(그래서 ROS 없이 시험할 수 있다).

    GET  /api/state                     지금 값 전부(연결·상태·그리퍼·힘·최근 이벤트·계획)
    POST /api/start|stop|resume|abort   버튼 → flow 의 같은 이름 서비스 → {ok, message, latency_ms} 를 그대로 돌려준다
    WS   /ws/state                      서버 → 브라우저. 붙자마자 type=state(전부) 1번, 그 뒤로 state · event · force · gripping · conn
    GET  /                              운영 화면(Next.js 로 만든 web/out/) — 아직 안 만들었으면 시험 페이지
    GET  /test                          시험 페이지(브리지 점검용 — 그대로 둔다)
    GET  /api/usage · /api/kpi?period=  소모품·잔반통 사용량(마지막 교체 뒤) · 누적 KPI(run/today/all)      (SQLite)
    POST /api/replace/{item}            교체 완료(sponge/brush/soap/waste_bin) → 사용량 0 부터
    GET  /api/db/{table}?limit=         표 내용(events/runs/pauses/commands/replacements) · /api/history = events
응답 모양은 src/f4_hmi/README.md(REST·WS 계약) 과 docs/02_인터페이스_IRD.md §6·§7.
"""
import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import ITEMS, TABLES
from .hub import Hub

ITEM_KO = {'sponge': '수세미', 'brush': '솔', 'soap': '세제', 'waste_bin': '잔반통'}

STATIC_DIR = Path(__file__).resolve().parent / 'static'
WEB_DIR = Path(__file__).resolve().parent.parent / 'web' / 'out'   # 운영 화면 — `cd src/f4_hmi/web && npm run build` 가 만든다(GitHub 에는 안 올림)
COMMANDS = ('start', 'stop', 'resume', 'abort')         # IRD §6 의 /flow/* 서비스 이름과 같다
CONN_CHECK_S = 0.5                                      # 연결 끊김(conn)을 알아채는 간격 — 새 값이 안 와야 끊긴 것이라 기다리다 확인한다


def create_app(store, cfg: dict, command=None, web_dir: Path = WEB_DIR, recorder=None) -> FastAPI:
    """store: StateStore · cfg: config.load() 결과 · command(name) → {ok, message, latency_ms}: 버튼을 flow 에 전하는 함수(RosLink.call).
    web_dir: 운영 화면 파일 묶음(index.html 이 있어야 쓴다 — 없으면 / 에 시험 페이지). 시험에서 바꿔 끼운다.
    recorder: Recorder — 있으면 버튼을 기록하고 /api/usage·kpi·replace·db 가 산다. 없으면(시험) 그 주소들은 503."""
    app = FastAPI(title='PreWash-Cell HMI', docs_url='/api/docs', redoc_url=None)

    @app.middleware('http')
    async def _no_cache_html(request, call_next):
        # npm run build 로 화면을 바꿔도 브라우저가 옛 index.html·JS 를 캐시에서 보여 줄 수 있다 —
        #    HTML 과 /api 는 캐시 금지. 해시가 붙은 /_next/static 파일은 그대로(내용이 바뀌면 이름도 바뀐다).
        resp = await call_next(request)
        path = request.url.path
        if path == '/' or path.endswith('.html') or path.startswith('/api'):
            resp.headers['Cache-Control'] = 'no-store'
        return resp
    flow = cfg.get('flow') or {}
    plan = {'plan': flow.get('plan') or [], 'rack_order': flow.get('rack_order') or {},
            'consumables': flow.get('consumables') or {}}
    hub = Hub()
    store.subscribe(hub.from_ros)
    app.state.hub = hub

    def full():
        """/api/state 와 WS 첫 메시지의 몸통 — store.snapshot() + 계획(plan) + (기록이 있으면) 사용량·알림·한도."""
        extra = {}
        if recorder is not None:
            extra = {'usage': recorder.usage_view(), 'notices': recorder.notices(),
                     'limits': {'sponge': plan['consumables'].get('sponge_max_uses'), 'brush': plan['consumables'].get('sponge_max_uses'),
                                'soap': plan['consumables'].get('soap_max_dips'), 'waste_bin_g': recorder.waste_limit_g}}
        return {**store.snapshot(), 'plan': plan, **extra}

    @app.get('/api/state')
    def get_state():
        return full()

    def make_button(name):
        """버튼 이름 → POST 핸들러. 기록자가 있으면 대답까지 commands 표에 적는다."""
        def press():                                    # def(동기) → 웹 서버가 작업 스레드에서 돌린다: flow 를 기다려도 다른 요청이 안 막힌다
            if command is None:
                return {'ok': False, 'message': 'flow 와 연결하는 부분이 없다 (시험 모드)', 'latency_ms': 0}
            r = command(name)
            if recorder is not None:
                recorder.record_command(name, r)         # commands 표 + 멈춤이 어떻게 풀렸는지
            return r
        return press
    for name in COMMANDS:
        app.post(f'/api/{name}')(make_button(name))

    def _need_recorder():
        """기록(DB)이 꺼진 시험 서버면 503."""
        if recorder is None:
            raise HTTPException(status_code=503, detail='기록(DB)이 꺼져 있다 — hmi_bridge 로 띄우면 산다')
        return recorder

    @app.get('/api/usage')
    def get_usage():
        rec = _need_recorder()
        return {'usage': rec.usage_view(), 'notices': rec.notices(), 'limits': full()['limits']}

    @app.get('/api/kpi')
    def get_kpi(period: str = 'all'):
        if period not in ('run', 'today', 'all'):
            raise HTTPException(status_code=400, detail='period 는 run · today · all')
        return _need_recorder().kpi(period)

    @app.post('/api/replace/{item}')
    def post_replace(item: str):
        rec = _need_recorder()
        if item not in ITEMS:
            raise HTTPException(status_code=400, detail=f'item 은 {ITEMS} 중 하나')
        usage = rec.replace(item, note='화면 버튼')
        return {'ok': True, 'message': f'{ITEM_KO.get(item, item)} 교체 완료 — 0 부터 다시 센다', 'usage': usage, 'notices': rec.notices()}

    @app.get('/api/db/{table}')
    def get_table(table: str, limit: int = 100):
        rec = _need_recorder()
        if table not in TABLES:
            raise HTTPException(status_code=400, detail=f'table 은 {TABLES} 중 하나')
        return {'table': table, 'rows': rec.db.dump(table, max(1, min(int(limit), 500)))}

    @app.get('/api/history')
    def get_history(limit: int = 100):
        return {'events': _need_recorder().db.recent_events(max(1, min(int(limit), 500)))}

    @app.websocket('/ws/state')
    async def ws_state(ws: WebSocket):
        """붙자마자 전부(type=state) 1번 → 큐에서 꺼내 보내며, CONN_CHECK_S 마다 연결 여부가 바뀌었으면 type=conn 을 보낸다."""
        await ws.accept()
        q = hub.join()
        try:
            first = full()
            connected = first['connected']
            await ws.send_json({'type': 'state', **first})
            while True:
                try:
                    await ws.send_json(await asyncio.wait_for(q.get(), timeout=CONN_CHECK_S))
                except asyncio.TimeoutError:
                    pass
                now = store.snapshot()['connected']
                if now != connected:                    # flow 가 끊겼다 / 다시 붙었다
                    connected = now
                    await ws.send_json({'type': 'conn', 'connected': now})
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            hub.leave(q)

    @app.get('/test')
    def test_page():
        return FileResponse(STATIC_DIR / 'test.html')

    app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')
    app.state.web = (web_dir / 'index.html').is_file()
    if app.state.web:                                   # 운영 화면 — 위의 /api · /ws · /test · /static 에 안 걸린 주소를 전부 여기서 찾는다
        app.mount('/', StaticFiles(directory=web_dir, html=True), name='web')
    else:                                               # 아직 빌드 안 함 → 시험 페이지로 대신한다(hmi_bridge 는 그대로 뜬다)
        @app.get('/')
        def index():
            return FileResponse(STATIC_DIR / 'test.html')
    return app
