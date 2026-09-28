'use client';
// 운영 화면 1장 — HMI 설계초안 §3. HMI 는 보여 주고 전달만 한다(흐름·복구 판단·로봇 동작은 하지 않는다).
import { useEffect, useRef, useState } from 'react';
import { useHmi } from './lib/useHmi';
import { VIEW, ORDER, BASE, FRONT, DIV, SLOT, BADGE } from './lib/palletArt';
import {
  FLOW, RUNNING, STEP_KO, KIND_KO, RESULT_KO, CODE_KO,
  buttons, pallet, zones, cycle, alarm, problems, clock, why, progress, nextStep, consumables, pauseKind, HIDE_FLOW_MSG,
  kpiCards, PERIOD_KO, causeIcon, resumeToast, lifetime,
} from './lib/derive';

// 그림 — web/illust/build.py 가 코드로 그린 등각 일러스트. public/illust/ 에 있다
const stepArt = (step, kind) => `/illust/steps/${step}-${kind}.svg`;
const iconArt = (name) => `/illust/icons/${name}.svg`;
const CIRCLED = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧'];

const BTN_KO = { start: '시작', stop: '일시 정지', resume: '재개', abort: '중단' };
const KEY = 'prewash.lastStep';
function recall() { try { return sessionStorage.getItem(KEY) || ''; } catch { return ''; } }   // 개인 창·막힌 저장소에서도 화면은 뜬다
function remember(v) { try { sessionStorage.setItem(KEY, v); } catch { /* 없어도 된다 */ } }

let audioCtx = null;
// 짧은 비프 1번 — Web Audio 로 freq Hz 사각파를 duration 초 울린다(기본 1000 Hz · 0.18 s · 음량 0.7). 오디오가 없거나 막힌 브라우저면 조용히 넘어간다
//   끝 0.02 s 는 음량을 0 으로 내려 '딱' 하는 클릭음을 막는다 · audioCtx 는 브라우저 정책상 사용자가 버튼을 누른 뒤에만 켜진다
function playBeep(freq = 1000, duration = 0.18, type = 'square', vol = 0.7) {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    if (!audioCtx) audioCtx = new AudioContext();
    if (audioCtx.state === 'suspended') audioCtx.resume();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    const now = audioCtx.currentTime;
    gain.gain.setValueAtTime(vol, now);
    gain.gain.setValueAtTime(vol, now + duration - 0.02);
    gain.gain.linearRampToValueAtTime(0.001, now + duration);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start(now);
    osc.stop(now + duration);
  } catch {
    /* 오디오 미지원 또는 차단 환경 */
  }
}

// 짧은 두 음(1200 Hz 0.09 s → 120 ms 뒤 1600 Hz 0.11 s) — 멈춤이 풀렸다는 신호
function playDoubleBeep() {
  playBeep(1200, 0.09, 'square', 0.7);
  setTimeout(() => playBeep(1600, 0.11, 'square', 0.7), 120);
}

export default function Monitor() {
  const { d, mode, press, replace, period, setPeriod } = useHmi();
  const [reply, setReply] = useState(null);
  // 일시 정지됐을 때 "어느 단계에서" 를 보여 주려고 기억한다 — flow 가 보내는 값(FlowState)에는 그 칸이 없다.
  // 같은 탭에서 새로고침해도 잊지 않게 탭 저장소(sessionStorage)에도 둔다. 멈춘 뒤에 새 탭으로 열면 모른다.
  const lastRunning = useRef(null);
  const lastSoundMsg = useRef('');
  const s = d.state;
  if (lastRunning.current === null) lastRunning.current = recall();
  // 멈춘 뒤에 연 화면(새 탭·태블릿)은 멈춘 단계를 못 봤다 → 브리지가 기억한 직전 단계(paused_from)를 쓴다
  if (s && (s.step === 'PAUSED' || s.step === 'ERROR') && !lastRunning.current && d.paused_from) { lastRunning.current = d.paused_from; remember(d.paused_from); }
  if (s && RUNNING.includes(s.step) && lastRunning.current !== s.step) { lastRunning.current = s.step; remember(s.step); }
  if (s && (s.step === 'IDLE' || s.step === 'DONE') && lastRunning.current) { lastRunning.current = ''; remember(''); }

  // 톡톡(넛지) 재개 감지 시 비프(1500 Hz · 0.16 s) — 케이블 경로에서 flow 가 '재개 요청 감지' 문구를 보낸다
  useEffect(() => {
    const msg = s?.message || '';
    if (msg.includes('재개 요청 감지') && lastSoundMsg.current !== msg) {
      playBeep(1500, 0.16, 'square', 0.75);
    }
    lastSoundMsg.current = msg;
  }, [s?.message]);
  // 멈춤이 풀리면(PAUSED → 운전) 짧은 두 음 — 툴 놓침 넛지처럼 문구 없이 재개되는 경로도 소리로 알린다
  const wasPaused = useRef(false);
  // 멈추면 알림창(원인 그림 + 할 일) → 사람이 처리하고 확인 → 재개 버튼. 톡(넛지)으로 풀리면 알림창이 닫히며 '재개되었습니다' 토스트
  const [modal, setModal] = useState(null);
  const [toast, setToast] = useState(null);
  const pauseSeq = useRef(0);
  const lastResumePress = useRef(0);
  const toastTimer = useRef(null);
  const dRef = useRef(d);
  dRef.current = d;
  const showToast = (t) => { setToast(t); clearTimeout(toastTimer.current); toastTimer.current = setTimeout(() => setToast(null), 6000); };
  useEffect(() => {
    const step = s?.step;
    if (step === 'PAUSED' && !wasPaused.current) {                       // 멈춤 시작 → 알림창(내용은 그릴 때 alarm(d) 로 — 잔반통 알림처럼 원인이 한 박자 늦게 와도 따라간다)
      pauseSeq.current += 1;
      setModal({ seq: pauseSeq.current, step: lastRunning.current || '', kind: s.kind || 'BOWL' });
    }
    if (wasPaused.current && step && step !== 'PAUSED') {              // 멈춤이 풀렸다(버튼·톡·중단)
      setModal(null);
      showToast(resumeToast(Date.now() - lastResumePress.current < 15000, lastRunning.current || '', step));
      if (RUNNING.includes(step)) playDoubleBeep();
    }
    wasPaused.current = step === 'PAUSED';
  }, [s?.step]);

  const can = buttons(d);
  const ITEM_KO = { sponge: '수세미', brush: '솔', soap: '세제', waste_bin: '잔반통' };
  async function onReplace(item) {
    if (!window.confirm(`${ITEM_KO[item]}을(를) 새것으로 바꿨습니까? 사용량을 0부터 다시 셉니다.`)) return;
    const r = await replace(item);
    setReply({ ok: r.ok, text: `${r.ok ? '✔' : '✖'} ${r.message || ''}` });
  }
  async function onPress(name) {
    try {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
    } catch {}
    if (name === 'abort' && !window.confirm('이 용기를 격리 구역으로 보내고 다음 용기로 넘어갑니다.\n중단할까요?')) return;
    if (name === 'resume') lastResumePress.current = Date.now();      // 토스트에 '재개 버튼'/'톡' 을 가르는 근거
    setReply({ pending: true, text: `${BTN_KO[name]} 보내는 중…` });
    const r = await press(name);
    setReply({ ok: r.ok, text: `${r.ok ? '✔' : '✖'} ${BTN_KO[name]}: ${r.message}${r.latency_ms != null ? ` (${r.latency_ms} ms)` : ''}` });
  }

  return (
    <div className="page">
      {modal && alarm(d)?.level === 'pause' && <AlertModal m={modal} a={alarm(d)} onClose={() => setModal(null)} />}
      {toast && <div className="toast" role="status">✔ {toast.text}{toast.sub && <div className="toast-sub">{toast.sub}</div>}</div>}
      <TopBar d={d} can={can} onPress={onPress} />
      <Alarm d={d} step={lastRunning.current || null} />
      <Controls can={can} onPress={onPress} reply={reply} />
      <StepBar d={d} paused={s && s.step === 'PAUSED' ? lastRunning.current || null : null} />
      <div className="grid">
        <Now d={d} last={lastRunning.current || null} />
        <Pallet d={d} />
        <Stats d={d} onReplace={onReplace} />
      </div>
      <Kpi d={d} period={period} setPeriod={setPeriod} />
      <History d={d} />
      <footer className="dim small">
        받는 방식: {mode} · 받은 상태 메시지 {d.received}건 · 점검용 <a href="/test">시험 페이지</a>
      </footer>
    </div>
  );
}

// 맨 위 줄 — 제품 이름 · 연결 상태 알약(서버 → flow 순으로 판정) · 일시 정지 버튼(운전 중에만 활성)
function TopBar({ d, can, onPress }) {
  const conn = !d.server ? { cls: 'bad', text: 'HMI 서버에 닿지 않는다' }
    : d.connected ? { cls: 'ok', text: 'flow 연결됨' }
    : d.state ? { cls: 'bad', text: 'flow 연결 끊김 — 마지막 값을 보여 주는 중' }
    : { cls: 'bad', text: 'flow 의 방송을 아직 못 받았다' };
  return (
    <header className="top">
      <div className="brand">PreWash-Cell</div>
      <div className={`pill ${conn.cls}`}><span className="dot" />{conn.text}</div>
      <div className="spacer" />
      <div className="stopbox">
        <button className="btn stop" disabled={!can.stop} onClick={() => onPress('stop')}>일시 정지</button>
        <div className="dim tiny">즉시 멈춘다 · 재개하면 이어서 · 급하면 로봇 E-Stop</div>
      </div>
    </header>
  );
}

// 알람 상자 — 멈춤이면 원인별 제목·할 일(derive.alarm → GUIDE_KO), 운전 중이면 최근 원인 경고. 없으면 그리지 않는다
function Alarm({ d, step }) {
  const a = alarm(d);
  if (!a) return null;
  const label = CODE_KO[a.code] || a.code;
  if (a.level === 'error' || a.level === 'pause') {           // 멈춤 — 원인 갈래별 제목·설명·할 일(derive.GUIDE_KO)
    const g = a.guide;
    const where = step ? ` — ${STEP_KO[step]} 단계에서` : '';
    return (
      <section className={`alarm ${a.level}`}>
        <div className="alarm-title">{a.level === 'error' ? '🚨 ' : ''}{g.title}{where}</div>
        {(g.what || (a.message && a.kind !== 'operator' && !HIDE_FLOW_MSG.includes(a.kind))) && <div className="alarm-msg">{g.what || ''}{a.message && a.kind !== 'operator' && !HIDE_FLOW_MSG.includes(a.kind) ? ` ${a.message}` : ''}</div>}
        <ol className="alarm-steps">{g.steps.map((t, i) => <li key={i}>{t}</li>)}</ol>
        {a.code && a.code !== 'OK' && a.kind !== 'cable' ? <div className="dim small">코드 {a.code} · {label}</div> : null}
      </section>
    );
  }
  return (
    <section className="alarm warn">
      <div className="alarm-title">⚠ 최근 원인: {label}</div>
      {a.message && <div className="alarm-msg">{a.message}</div>}
      <div className="dim small">재개해 진행 중입니다 — 다시 멈추면 위 안내가 뜹니다</div>
    </section>
  );
}

// 예외 알림창 — 멈춤 원인 아이콘 + 멈춘 단계 그림 + 할 일 · 확인을 누르면 닫히고(안내 띠는 남는다) 재개 버튼(또는 톡)으로 이어 간다
function AlertModal({ m, a, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  const g = a.guide;
  const where = m.step && STEP_KO[m.step] ? `${STEP_KO[m.step]} 단계에서 멈춤` : '멈춤';
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={g.title} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <img src={iconArt(causeIcon(a.kind, m.kind))} alt="" />
          <div><div className="modal-title">{g.title}</div><div className="dim">{where}{a.code && a.code !== 'OK' && a.kind !== 'cable' ? ` · 코드 ${a.code}` : ''}</div></div>
        </div>
        <div className="modal-body">
          {m.step && STEP_KO[m.step] ? <img className="modal-art" src={stepArt(m.step, m.kind)} alt="" /> : <div className="modal-art" />}
          <ol className="modal-steps">{g.steps.map((t, i) => <li key={i}>{t}</li>)}</ol>
        </div>
        <div className="modal-foot">
          <div className="dim small">처리한 뒤 <b>확인</b> → 화면의 <b>재개</b> 버튼(또는 손목 톡). 톡으로 풀리면 이 창은 저절로 닫힙니다.</div>
          <button className="btn go" onClick={onClose} autoFocus>확인</button>
        </div>
      </div>
    </div>
  );
}

// 버튼 줄 — 시작 · 재개 · 중단과 flow 의 대답(reply)
function Controls({ can, onPress, reply }) {
  return (
    <section className="controls">
      <button className="btn go" disabled={!can.start} onClick={() => onPress('start')}>시작</button>
      <button className={`btn go ${can.resume ? 'attn' : ''}`} disabled={!can.resume} onClick={() => onPress('resume')}>재개</button>
      <button className="btn warn" disabled={!can.abort} onClick={() => onPress('abort')}>중단</button>
      <div className={`reply ${reply ? (reply.pending ? 'dim' : reply.ok ? 'ok' : 'bad') : 'dim'}`}>
        {reply ? reply.text : '버튼을 누르면 flow 의 대답이 여기에 나온다'}
      </div>
    </section>
  );
}

// 단계 표시줄 — 그림 카드 8장(+ 격리). 지금 단계 = 파랑 · 끝난 단계 = ✓ 초록(흐리게) · 남은 단계 = 옅게 · 일시 정지 = 주황
//   그림 속 용기는 지금 처리 중인 종류(그릇/컵)를 따라간다. 처리 중인 용기가 없으면 그릇.
function StepBar({ d, paused }) {
  const s = d.state;
  const step = s ? s.step : null;
  const kind = s && s.kind === 'CUP' ? 'CUP' : 'BOWL';
  const at = paused || step;                         // 일시 정지 중이면 멈춘 단계를 가리킨다
  const idx = FLOW.indexOf(at);
  const finished = step === 'DONE';
  const broken = false;                                         // 로봇 오류를 별도 예외로 보이지 않는다 — 붉은 단계 카드 없음(멈춤 카드는 주황 하나)
  // 좁은 화면(태블릿)에서는 단계 줄이 옆으로 밀린다 — 지금 단계 카드가 가운데 오게 줄만 민다(화면 전체는 움직이지 않는다)
  const bar = useRef(null);
  useEffect(() => {
    const el = bar.current;
    const card = el && el.querySelector('.stepcard.now');
    if (!card || el.scrollWidth <= el.clientWidth) return;
    el.scrollTo({ left: card.offsetLeft - el.offsetLeft - (el.clientWidth - card.clientWidth) / 2 });
  }, [at, step]);
  return (
    <section className="stepbar" ref={bar}>
      {FLOW.map((name, i) => {
        const past = finished || (idx >= 0 && i < idx);
        const now = !finished && i === idx;
        const cls = past ? 'past' : now ? (broken ? 'now error' : paused ? 'now paused' : 'now') : 'next';
        return (
          <div key={name} className={`stepcard ${cls}`}>
            <img src={stepArt(name, kind)} alt="" width="128" height="96" />
            <div className="stepcard-label"><span className="mark">{past ? '✓' : i + 1}</span>{STEP_KO[name]}</div>
          </div>
        );
      })}
      <div className={`stepcard iso ${step === 'ISOLATE' ? 'now isolate' : 'next'}`}>
        <img src={stepArt('ISOLATE', kind)} alt="" width="128" height="96" />
        <div className="stepcard-label"><span className="mark">!</span>격리</div>
      </div>
    </section>
  );
}

// 지금 하는 일 — 지금 단계를 큰 그림으로. 설명 한 줄 + 이번 용기 경과 · 몇 번째 · 다음 할 일
const DESC = {                                        // [그릇, 컵]
  WEIGH: ['들고 있는 채로 무게를 잰다 — 50 g 이상이면 털기', '들고 있는 채로 무게를 잰다 — 50 g 이상이면 털기'],
  SHAKE: ['잔반통 위에서 기울여 3~5회 털고 다시 잰다', '잔반통 위에서 기울여 3~5회 털고 다시 잰다'],
  SEAT: ['스펀지 고정틀 홈에 내려놓는다', '스펀지 고정틀 홈에 내려놓는다'],
  SOAP: ['수세미 툴을 비눗물 홀더에 담근다', '솔 툴을 비눗물 홀더에 담근다'],
  WIPE: ['안쪽만 수세미로 돌려 닦는다', '안쪽만 솔로 위아래 문지른다'],
  RINSE: ['헹굼 물에 담갔다 뺀다', '헹굼 물에 담갔다 뺀다'],
  ISOLATE: ['털어도 잔반이 남거나 실패한 용기를 격리 구역으로 옮긴다', '털어도 잔반이 남거나 실패한 용기를 격리 구역으로 옮긴다'],
};

// 이번 용기 경과 — 끝난 용기 수가 바뀐 때부터 잰다(메시지에 용기 시작 시각이 없다). 화면을 도중에 열면 그때부터
function useElapsed(s) {
  const [, setTick] = useState(0);
  const mark = useRef({ key: null, at: null });
  const busy = !!s && (RUNNING.includes(s.step) || s.step === 'PAUSED');
  const key = s ? `${s.done_bowl}-${s.done_cup}-${s.isolated}` : null;
  if (!busy) mark.current = { key: null, at: null };
  else if (mark.current.key !== key) mark.current = { key, at: Date.now() };
  useEffect(() => {
    if (!busy) return undefined;
    const t = setInterval(() => setTick((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, [busy]);
  return busy && mark.current.at ? (Date.now() - mark.current.at) / 1000 : null;
}

function Now({ d, last }) {
  const s = d.state;
  const elapsed = useElapsed(s);
  const p = progress(d);
  const step = s ? s.step : null;
  const kind = s && s.kind === 'CUP' ? 'CUP' : 'BOWL';
  const k = kind === 'CUP' ? 1 : 0;
  const shown = step === 'PAUSED' || step === 'ERROR' ? last : step;       // 멈춘 단계의 그림을 그대로 보여 준다
  const running = RUNNING.includes(step);

  let tone = '', pill = '진행 중', title = STEP_KO[shown] || '-', art = shown, desc = '', num = FLOW.indexOf(shown) + 1;
  if (!s) { pill = '연결 대기'; tone = 'idle'; title = '대기'; art = 'PICK'; desc = 'flow 의 방송을 기다린다'; }
  else if (step === 'IDLE') { pill = '대기'; tone = 'idle'; title = '대기'; art = 'PICK'; desc = '시작을 누르면 반납 구역부터 차례로 처리한다'; num = 0; }
  else if (step === 'DONE') { pill = '완료'; tone = 'idle'; title = '완료'; art = 'RACK'; desc = '계획한 용기를 모두 처리했다 — 팔레트를 확인한다'; num = 0; }
  else if (step === 'PAUSED' && pauseKind(s) === 'robot_error') { pill = '멈춤 — 로봇 확인'; tone = 'paused'; }   // 일반 멈춤과 같은 색
  else if (step === 'PAUSED') { pill = { cable: '멈춤 — 케이블 확인', tool_lost: '멈춤 — 툴 놓침', tool_fail: '멈춤 — 툴 집기 실패', leftover: '멈춤 — 잔반 남음', grip: '멈춤 — 집기 실패', rack_full: '멈춤 — 팔레트 가득' }[pauseKind(s)] || '일시 정지'; tone = 'paused'; }
  else if (step === 'ERROR') { pill = '오류'; tone = 'error'; }
  else if (step === 'ISOLATE') { pill = '격리 중'; tone = 'isolate'; num = '!'; }
  if (!art) { art = 'PICK'; title = STEP_KO[step] || '-'; }

  if (!desc && shown) {
    if (shown === 'PICK') desc = `반납 구역 ${s.zone_id || ''} 에서 ${k ? '컵 몸통을 통째로' : '그릇 벽을 세로로'} 잡아 올린다`;
    else if (shown === 'RACK') {
      const cells = pallet(d);
      const i = cells.findIndex((c) => c.loading || (!c.filled && c.kind === kind));
      desc = i >= 0 ? `${KIND_KO[cells[i].kind]} ${cells[i].n} 을 팔레트 ${CIRCLED[i]} 칸에 ${k ? '똑바로' : '세워'} 넣는다` : '팔레트 칸에 넣는다';
    } else desc = (DESC[shown] || [])[k] || '';
    if (tone === 'error' && s.message) desc = s.message;
  }
  const nth = !s ? '-' : step === 'IDLE' ? `0 / ${p.total}` : step === 'DONE' ? `${p.finished} / ${p.total}` : `${Math.min(p.finished + 1, p.total)} / ${p.total}`;

  return (
    <section className={`card now-card ${tone}`}>
      <div className="card-head"><h2>지금 하는 일</h2><span className={`state-pill ${tone}`}><span className="dot" />{pill}</span></div>
      <div className={`now-art ${running || step === 'PAUSED' || step === 'ERROR' ? '' : 'dimmed'}`}>
        <img src={stepArt(art, kind)} alt={`${title} 그림`} width="320" height="240" />
      </div>
      <div className="now-title">
        {num ? <span className="now-num">{num}</span> : null}
        <span className="now-name">{title}</span>
        {s && s.kind ? <span className="kind-chip">{KIND_KO[s.kind]}</span> : null}
      </div>
      <div className="now-desc">{desc}</div>
      <div className="tiles">
        <div title="끝난 용기 수가 바뀐 때부터 — 화면을 도중에 열면 그때부터 잰다"><span>이번 용기</span><b>{elapsed != null ? `${elapsed.toFixed(0)} s` : '-'}</b></div>
        <div><span>몇 번째</span><b>{nth}</b></div>
        <div><span>다음</span><b className="text">{s ? nextStep(step, p) : '-'}</b></div>
      </div>
    </section>
  );
}

// 팔레트 — 실제 배치를 비스듬히 위에서 본 입체 그림
//   넣는 순서 그릇 1 → 그릇 2 → 컵 1 → 컵 2 = params.yaml flow.rack_order. 칸 상태마다 그림 조각(palletArt.js)을 골라 뒤 → 앞으로 겹친다.
//   적재됨 = 흰 그릇·컵 + ✓ · 넣는 중 = 파란 반투명 + ↓ · 비어 있음 = 점선 자리 + 넣는 순서 번호
function Pallet({ d }) {
  const cells = pallet(d);
  const stateOf = {};
  cells.forEach((c) => { stateOf[`${c.kind}-${c.n}`] = c.filled ? 'done' : c.loading ? 'now' : 'empty'; });
  const st = (key) => stateOf[key] || 'empty';
  const art = [BASE, ...ORDER.map((key) => DIV[key] || SLOT[key][st(key)]), FRONT, ...Object.keys(BADGE).map((key) => BADGE[key][st(key)])].join('');
  const filled = cells.filter((c) => c.filled).length;
  const full = cells.length > 0 && filled >= cells.length;       // 이번 회차가 칸을 다 채웠다 → 사람이 팔레트를 바꾼다
  const loading = cells.some((c) => c.loading);
  const t = lifetime(d);                                          // 누적은 DB 전체 기록(없으면 메모리)
  return (
    <section className={`card pallet-card ${full ? 'full' : ''}`}>
      <h2>이번 팔레트</h2>
      <div className="rack-head">
        <span className="rack-count">{filled} / {cells.length}</span>
        {full ? <span className="rack-full">가득 참 — 식기세척기로 옮기고 새 팔레트를 놓는다</span>
          : <span className="dim">칸{loading ? ' · 1칸 넣는 중' : ''}</span>}
      </div>
      <div className="chips">
        {cells.map((c, i) => (
          <span key={c.slot} className="chip-wrap">
            {i > 0 && <span className="dim tiny">→</span>}
            <span className={`chip ${c.filled ? 'done' : c.loading ? 'now' : ''}`} title={c.slot}>{CIRCLED[i]} {KIND_KO[c.kind]} {c.n}</span>
          </span>
        ))}
      </div>
      <div className="segs">{cells.map((c) => <i key={c.slot} className={c.filled ? 'done' : c.loading ? 'now' : ''} />)}</div>
      <svg viewBox={`${VIEW.x} ${VIEW.y} ${VIEW.w} ${VIEW.h}`} className="rack-art" role="img" aria-label="팔레트 적재 상태"
        dangerouslySetInnerHTML={{ __html: art }} />
      <h2 className="gap">지금까지 처리 — 전체</h2>
      <div className="tiles four">
        <div><span>팔레트</span><b>{t.pallets}<small> 장</small></b></div>
        <div><span>그릇</span><b>{t.bowls}</b></div>
        <div><span>컵</span><b>{t.cups}</b></div>
        <div><span>격리</span><b className={t.isolated ? 'warn' : ''}>{t.isolated}</b></div>
      </div>
      <div className="dim tiny">{t.fromDb ? '전체 기록(SQLite) · 껐다 켜도 이어진다' : 'HMI 를 켠 뒤부터(기록 없음)'} · 실행 {t.runs}회 · 팔레트 = 칸 {cells.length || 4}개를 다 채우고 끝난 실행</div>
    </section>
  );
}

// 숫자 패널 — 숫자마다 그림 아이콘을 붙인다(무엇을 세는지 그림으로 바로). 반납 구역 남은 수는 그릇·컵 줄에 합쳤다
function Row({ icon, title, value, sub, children, tone = '' }) {
  return (
    <div className={`srow ${tone}`}>
      <img src={iconArt(icon)} alt="" width="46" height="46" />
      <div className="srow-body">
        <div className="srow-top"><span className="srow-title">{title}</span>{value}</div>
        {sub && <div className="srow-sub">{sub}</div>}
        {children}
      </div>
    </div>
  );
}

// 큰 숫자 — v 뒤에 '/of' 와 단위를 붙인다
function Big({ v, of, unit, cls = '' }) {
  return <span className={`big ${cls}`}>{v}{of != null && <span className="of">/{of}</span>}{unit && <span className="unit"> {unit}</span>}</span>;
}

// 가로 막대 — value/max 비율(%)만큼 채운다. max 가 없으면 0
function Bar({ value, max, cls = '' }) {
  const pct = max ? Math.min(100, (value / max) * 100) : 0;
  return <div className="bar"><i style={{ width: `${pct}%` }} className={cls} /></div>;
}

function Stats({ d, onReplace }) {
  const s = d.state || {};
  const zs = zones(d);
  const cy = cycle(d);
  const cs = consumables(d);
  const zoneText = (kind) => {
    const z = zs.filter((q) => q.kind === kind);
    return z.length ? z.map((q) => `반납 구역 ${q.zone} · 남음 ${q.left} · ${q.status}`).join(' / ') : '계획 없음';
  };
  const done = (kind) => (kind === 'BOWL' ? s.done_bowl : s.done_cup);
  const target = (kind) => (kind === 'BOWL' ? s.target_bowl : s.target_cup);
  const kindRow = (kind, icon) => {
    const all = target(kind) != null && done(kind) >= target(kind) && target(kind) > 0;
    const busy = s.kind === kind && RUNNING.includes(s.step);
    return (
      <Row icon={icon} title={KIND_KO[kind]} value={<Big v={done(kind) ?? '-'} of={target(kind) ?? '-'} cls={all ? 'ok' : ''} />} sub={zoneText(kind)}>
        <Bar value={done(kind) || 0} max={target(kind)} cls={all ? '' : busy ? 'now' : ''} />
      </Row>
    );
  };
  const replaceBtn = (item) => (cs.fromDb && onReplace ? <button className="btn mini" onClick={() => onReplace(item)}>교체 완료</button> : null);
  const spare = (c, name, icon, every, item) => {
    if (!c) return <Row icon={icon} title={name} value={<Big v="-" />} />;
    if (c.max == null) return <Row icon={icon} title={name} value={<Big v={c.used} unit="회" />} sub="교체 한도 설정 없음" />;
    const blocks = c.max <= 30;
    return (
      <Row icon={icon} tone={c.level} title={<>{name}{c.level !== 'ok' && <span className="tag">{c.level === 'bad' ? '교체 필요' : '곧 교체'}</span>}{replaceBtn(item)}</>}
        value={<Big v={c.left} unit="회 남음" cls={c.level} />} sub={blocks ? null : `${every} ${c.max}회마다 간다 · 지금까지 ${c.used}회`}>
        {blocks
          ? <div className="blocks">{Array.from({ length: c.max }, (_, i) => <i key={i} className={i < c.left ? c.level : ''} />)}</div>
          : <Bar value={c.left} max={c.max} cls={c.level === 'ok' ? '' : c.level} />}
      </Row>
    );
  };
  const top = cy ? Math.max(...cy.recent) || 1 : 1;
  return (
    <section className="card stats-card">
      <h2>진행</h2>
      {kindRow('BOWL', 'bowl')}
      {kindRow('CUP', 'cup')}
      <Row icon="crate" title="격리" value={<Big v={s.isolated ?? '-'} cls={s.isolated ? 'warn' : ''} />} sub="잔반이 남거나 실패해 뺀 용기" />
      <h2 className="gap">사이클 타임</h2>
      <Row icon="timer" title="용기 1개" value={<Big v={cy ? cy.last.toFixed(1) : '-'} unit="s" />} sub={cy ? `평균 ${cy.mean.toFixed(1)} s · ${cy.n}개` : '아직 끝난 용기가 없다'}>
        {cy && <div className="minibars">{cy.recent.map((v, i) => <i key={i} style={{ height: `${Math.max(12, (v / top) * 100)}%` }} className={i === cy.recent.length - 1 ? 'last' : ''} />)}</div>}
      </Row>
      <h2 className="gap">소모품 — 교체까지</h2>
      {spare(cs.sponge, '수세미', 'sponge', '그릇', 'sponge')}
      {spare(cs.brush, '솔', 'brush', '컵', 'brush')}
      {spare(cs.soap, '세제', 'soap', '용기', 'soap')}
      {cs.waste && (
        <Row icon="tank" tone={cs.waste.level} title={<>잔반통{cs.waste.level !== 'ok' && <span className="tag">{cs.waste.level === 'bad' ? '교체 필요' : '곧 교체'}</span>}{replaceBtn('waste_bin')}</>}
          value={<Big v={(cs.waste.used_g / 1000).toFixed(1)} unit={cs.waste.max_g ? `/ ${cs.waste.max_g >= 10000 ? Math.round(cs.waste.max_g / 1000) : (cs.waste.max_g / 1000).toFixed(1)} kg` : 'kg'} cls={cs.waste.level} />}
          sub={cs.waste.max_g ? '버린 잔반 무게 합 · 한도에 닿으면 일시 정지' : '한도 설정 없음'}>
          {cs.waste.max_g ? <Bar value={cs.waste.used_g} max={cs.waste.max_g} cls={cs.waste.level === 'ok' ? '' : cs.waste.level} /> : null}
        </Row>
      )}
      <div className="dim tiny gap-top">{cs.fromDb ? '마지막 교체 완료 뒤부터 센다 · 껐다 켜도 이어진다(SQLite)' : '이번 실행에서 센 값(서버 기록 없음)'}</div>
    </section>
  );
}

// 누적 KPI — DB(/api/kpi) 값 · 기간 전환(이번 실행 · 오늘 · 전체)
function Kpi({ d, period, setPeriod }) {
  const cards = kpiCards(d.kpi);
  return (
    <section className="card">
      <div className="history-head">
        <h2>누적 <span className="dim tiny">{d.kpi ? `${PERIOD_KO[d.kpi.period] || ''} · 용기 ${d.kpi.total}개 · 실행 ${d.kpi.runs}회` : '기록 없음(서버가 DB 없이 떠 있음)'}</span></h2>
        <div className="tabs">{Object.keys(PERIOD_KO).map((p) => <button key={p} className={period === p ? 'on' : ''} onClick={() => setPeriod(p)}>{PERIOD_KO[p]}</button>)}</div>
      </div>
      {!cards.length ? <div className="dim">아직 값이 없다</div> : (
        <div className="kpi-grid">
          {cards.map((c) => (
            <div key={c.label} className={`kpi ${c.tone || ''}`}>
              <div className="dim small">{c.label}</div>
              <div className="kpi-v">{c.value}</div>
              <div className="dim tiny">{c.sub}</div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

// 이력 — 끝난 용기 1개 = /flow/event 1건. 최근 것부터 20건.
//   브리지가 들고 있는 최근 50건(켤 때 SQLite 에서 미리 채운다) — 전체는 터미널 hmi_db dump events.
//   [전체 / 문제만] — 문제만 = 완료가 아닌 것(격리 · 오류 · 건너뜀).
const HISTORY_ROWS = 20;

function History({ d }) {
  const [onlyProblems, setOnlyProblems] = useState(false);
  const all = d.events || [];
  const rows = (onlyProblems ? problems({ events: all, state: d.state }) : all).slice(0, HISTORY_ROWS);
  const nProblems = all.filter((e) => e.result && e.result !== 'DONE').length;
  return (
    <section className="card">
      <div className="history-head">
        <h2>이력 <span className="dim tiny">끝난 용기마다 한 줄 · 최근 것부터</span></h2>
        <div className="tabs">
          <button className={onlyProblems ? '' : 'on'} onClick={() => setOnlyProblems(false)}>전체 {all.length}</button>
          <button className={onlyProblems ? 'on' : ''} onClick={() => setOnlyProblems(true)}>문제만 {nProblems}</button>
        </div>
      </div>
      {!rows.length ? (
        <div className="dim">{onlyProblems ? '문제 있던 용기가 없다' : '아직 끝난 용기가 없다'}</div>
      ) : (
        <div className="scroll-x"><table className="list history">
          <thead>
            <tr><th>시각</th><th>종류</th><th>구역 → 칸</th><th>무게 전 → 후</th><th>결과</th><th>원인</th><th>소요</th><th>시도</th></tr>
          </thead>
          <tbody>
            {rows.map((e, i) => (
              <tr key={`${e.stamp}-${i}`} className={e.result === 'ERROR' ? 'bad' : e.result === 'DONE' ? '' : 'warn'}>
                <td>{clock(e.stamp)}</td>
                <td>{KIND_KO[e.kind] || e.kind || '-'}</td>
                <td>{e.zone_id || '-'} → {e.rack_slot ? e.rack_slot.replace('RACK_', '') : e.result === 'ISOLATED' ? '격리' : '-'}</td>
                <td className="num">{e.weight_before_g || e.weight_after_g ? `${Math.round(e.weight_before_g)} → ${Math.round(e.weight_after_g)} g` : '-'}</td>
                <td>{RESULT_KO[e.result] || e.result}</td>
                <td>{e.result === 'DONE' ? '-' : why(e)}</td>
                <td className="num">{e.duration_s ? `${e.duration_s.toFixed(1)} s` : '-'}</td>
                <td className="num">{e.attempts || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
      <div className="dim tiny gap-top">최근 50건 · 전체는 SQLite 기록(터미널 `ros2 run f4_hmi hmi_db dump events`)</div>
    </section>
  );
}
