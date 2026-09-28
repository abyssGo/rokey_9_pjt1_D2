'use client';
// 값 받기 — hmi_bridge 하고만 이야기한다(로봇·ROS 를 모른다). 계약: src/f4_hmi/README.md(REST·WS) · docs/02_인터페이스_IRD.md §6·§7
//   ① WebSocket /ws/state — 서버가 먼저 밀어 준다. 붙자마자 전부 1번, 그 뒤 state · event · conn (force · gripping 은 안 쓴다)
//   ② 끊기면 2초 뒤 다시 걸고, 그동안은 GET /api/state 를 0.5초마다 물어본다(시험 페이지와 같은 방식)
// 표기 — E-nn: 팀 결정 번호(docs/meetings/20260919_결정기록_DSN-03.md) · V-nn/INT-nn: 검증 항목(docs/test_logs/) · TS-nn: 트러블슈팅(docs/troubleshooting/)
import { useCallback, useEffect, useRef, useState } from 'react';

const POLL_MS = 500;
const RETRY_MS = 2000;
const MAX_EVENTS = 50;          // 화면에 들고 있는 최근 이벤트 수

const EXTRA_MS = 15000;         // 소모품·KPI(DB 값)를 다시 물어보는 간격 — 이벤트가 오면 바로 다시 본다
const EMPTY = { connected: false, server: true, state: null, events: [], plan: {}, received: 0, age_s: null, ready: false, usage: null, kpi: null, kpiAll: null, notices: null, limits: null };

// 화면이 쓰는 값 d 와 버튼 함수(press · replace), 받는 방식(mode), KPI 기간(period)을 돌려주는 훅
export function useHmi() {
  const [d, setD] = useState(EMPTY);
  const [mode, setMode] = useState('연결 중');
  const [period, setPeriod] = useState('run');       // KPI 기간 — run(이번 실행) · today · all
  const periodRef = useRef('run');
  periodRef.current = period;
  const ws = useRef(null);

  // 소모품·잔반통 사용량과 KPI 는 DB 에서 온다(/api/usage · /api/kpi). 실패하면 그냥 지난 값을 둔다
  const fetchExtra = useCallback(async () => {
    try {
      const [u, k, ka] = await Promise.all([fetch('/api/usage', { cache: 'no-store' }), fetch(`/api/kpi?period=${periodRef.current}`, { cache: 'no-store' }),
                                          fetch('/api/kpi?period=all', { cache: 'no-store' })]);   // 전체 누적(팔레트 카드) — 기간 전환과 무관
      if (u.ok) { const uj = await u.json(); setD((prev) => ({ ...prev, usage: uj.usage, notices: uj.notices, limits: uj.limits })); }
      if (k.ok) { const kj = await k.json(); setD((prev) => ({ ...prev, kpi: kj })); }
      if (ka.ok) { const aj = await ka.json(); setD((prev) => ({ ...prev, kpiAll: aj })); }
    } catch {}
  }, []);
  useEffect(() => { fetchExtra(); }, [period, fetchExtra]);

  useEffect(() => {
    let closed = false;
    let retry = null;
    const merge = (body) => setD((prev) => ({ ...prev, ...body, server: true, ready: true }));

    function connect() {
      const sock = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/state`);
      ws.current = sock;
      sock.onopen = () => { setMode('실시간'); fetchExtra(); };
      sock.onmessage = (m) => {
        const msg = JSON.parse(m.data);
        if (msg.type === 'state') {                   // 첫 번째만 events·plan 이 온다 — 그 뒤엔 빠진 몸통이라 합친다
          const { type, ...body } = msg;
          merge(body);
        } else if (msg.type === 'event') {
          setD((prev) => ({ ...prev, events: [msg.event, ...prev.events].slice(0, MAX_EVENTS) }));
          fetchExtra();                                    // 용기가 끝났다 → 소모품·KPI 갱신
        } else if (msg.type === 'conn') {                // force·gripping 은 받지 않는다 — 화면에 그 칸이 없어 뺐다
          setD((prev) => ({ ...prev, connected: msg.connected }));
        }
      };
      sock.onclose = () => {
        ws.current = null;
        if (closed) return;
        setMode('0.5초마다 물어보기');
        retry = setTimeout(connect, RETRY_MS);
      };
    }

    async function pollOnce() {
      if (ws.current && ws.current.readyState === WebSocket.OPEN) return;
      try {
        merge(await (await fetch('/api/state', { cache: 'no-store' })).json());
      } catch {
        setD((prev) => ({ ...prev, connected: false, server: false }));
      }
    }

    connect();
    const poll = setInterval(pollOnce, POLL_MS);
    const extra = setInterval(fetchExtra, EXTRA_MS);
    return () => { closed = true; clearTimeout(retry); clearInterval(poll); clearInterval(extra); if (ws.current) ws.current.close(); };
  }, [fetchExtra]);

  // 버튼 → POST /api/{name}. X-PreWash 헤더: 이 PC 에서 연 다른 웹페이지가 몰래 누르지 못하게(E10) — 서버가 아직 안 봐도 해가 없다
  const press = useCallback(async (name) => {
    try {
      const r = await fetch(`/api/${name}`, { method: 'POST', headers: { 'X-PreWash': '1' } });
      return await r.json();
    } catch {
      return { ok: false, message: 'HMI 서버에 닿지 않는다', latency_ms: 0 };
    }
  }, []);

  // 교체 완료 → POST /api/replace/{item} → 사용량 0 부터
  const replace = useCallback(async (item) => {
    try {
      const r = await (await fetch(`/api/replace/${item}`, { method: 'POST', headers: { 'X-PreWash': '1' } })).json();
      if (r.usage) setD((prev) => ({ ...prev, usage: r.usage, notices: r.notices || prev.notices }));
      return r;
    } catch {
      return { ok: false, message: 'HMI 서버에 닿지 않는다' };
    }
  }, []);

  return { d, mode, press, replace, period, setPeriod };
}
