# -*- coding: utf-8 -*-
"""웹 쪽 입 — 브라우저의 요청에 답하고(REST), 새 값을 밀어 준다(WebSocket). ROS 를 모른다(그래서 ROS 없이 시험할 수 있다).

    GET  /api/state                     지금 값 전부(연결·상태·그리퍼·힘·최근 이벤트·계획)
    POST /api/start|stop|resume|abort   버튼 → flow 의 같은 이름 서비스 → {ok, message, latency_ms} 를 그대로 돌려준다 (F4-02)
    WS   /ws/state                      서버 → 브라우저. 붙자마자 type=state(전부) 1번, 그 뒤로 state · event · force · gripping · conn
    GET  /                              운영 화면(F4-03 · Next.js 로 만든 web/out/) — 아직 안 만들었으면 시험 페이지
    GET  /test                          시험 페이지(F4-01·02 점검용 — 그대로 둔다)      이력(GET /api/history)은 F4-04
응답 모양은 docs/ref/20260920_F4-00_HMI_설계초안.md §2.
"""
import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .hub import Hub

STATIC_DIR = Path(__file__).resolve().parent / 'static'
WEB_DIR = Path(__file__).resolve().parent.parent / 'web' / 'out'   # F4-03 화면 — `cd src/f4_hmi/web && npm run build` 가 만든다(GitHub 에는 안 올림)
COMMANDS = ('start', 'stop', 'resume', 'abort')         # IRD §6 의 /flow/* 서비스 이름과 같다
CONN_CHECK_S = 0.5                                      # 연결 끊김(conn)을 알아채는 간격 — 새 값이 안 와야 끊긴 것이라 기다리다 확인한다


def create_app(store, cfg: dict, command=None, web_dir: Path = WEB_DIR) -> FastAPI:
    """store: StateStore · cfg: config.load() 결과 · command(name) → {ok, message, latency_ms}: 버튼을 flow 에 전하는 함수(RosLink.call).
    web_dir: 운영 화면 파일 묶음(index.html 이 있어야 쓴다 — 없으면 / 에 시험 페이지). 시험에서 바꿔 끼운다."""
    app = FastAPI(title='PreWash-Cell HMI', docs_url='/api/docs', redoc_url=None)

    @app.middleware('http')
    async def _no_cache_html(request, call_next):
        # 🆕 9/27(황인재 지적): npm run build 로 화면을 바꿨는데 브라우저가 옛 index.html·JS 를 캐시에서 보여 줘 "안 바뀌었다" —
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
        return {**store.snapshot(), 'plan': plan}

    @app.get('/api/state')
    def get_state():
        return full()

    def make_button(name):
        def press():                                    # def(동기) → 웹 서버가 작업 스레드에서 돌린다: flow 를 기다려도 다른 요청이 안 막힌다
            if command is None:
                return {'ok': False, 'message': 'flow 와 연결하는 부분이 없다 (시험 모드)', 'latency_ms': 0}
            return command(name)
        return press
    for name in COMMANDS:
        app.post(f'/api/{name}')(make_button(name))

    @app.websocket('/ws/state')
    async def ws_state(ws: WebSocket):
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
