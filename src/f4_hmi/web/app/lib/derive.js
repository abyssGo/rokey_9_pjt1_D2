// 받은 값 → 화면에 그릴 값. 전부 순수 함수(화면·통신과 무관).
// 팔레트 칸·반납 구역은 메시지에 없어서 계획(plan)과 수량으로 파생한다 — SDD §6 · IRD §6.
// 표기 — E-nn: 팀 결정 번호(docs/meetings/20260919_결정기록_DSN-03.md) · V-nn/INT-nn: 검증 항목(docs/test_logs/) · TS-nn: 트러블슈팅(docs/troubleshooting/)

export const FLOW = ['PICK', 'WEIGH', 'SHAKE', 'SEAT', 'SOAP', 'WIPE', 'RINSE', 'RACK'];   // 용기 1개의 순서(IRD §8)
export const RUNNING = [...FLOW, 'ISOLATE'];

export const STEP_KO = {
  IDLE: '대기', PICK: '집기', WEIGH: '무게', SHAKE: '털기', SEAT: '안착', SOAP: '세제',
  WIPE: '닦기', RINSE: '헹굼', RACK: '적재', ISOLATE: '격리', DONE: '완료', ERROR: '오류', PAUSED: '일시 정지',
};
export const KIND_KO = { BOWL: '그릇', CUP: '컵' };
export const RESULT_KO = { DONE: '완료', ISOLATED: '격리', ERROR: '오류', SKIPPED: '건너뜀' };
export const CODE_KO = {                             // cobot_api CODES (IRD §2)
  OK: '정상', GRIP_FAIL: '집기 실패', EMPTY_ZONE: '빈 구역', LEFTOVER: '잔반 있음', LEFTOVER_REMAIN: '잔반이 남음',
  SEAT_FAIL: '안착 실패', TOOL_FAIL: '툴 집기 실패', FORCE_LIMIT: '힘 상한 초과', TIMEOUT: '시간 초과',
  RACK_JAM: '적재 걸림', RACK_FULL: '팔레트 가득 참', ROBOT_ERROR: '로봇 오류', STOPPED: '멈춤',
  TOOL_LOST: '툴 놓침',                              // E37 — 닦는 중 수세미·솔이 그리퍼에서 빠짐
};

// 멈춤(PAUSED)의 원인 갈래 — flow 가 보내는 last_code 와 message 로 가른다(시연 예외 6개에 맞춤).
//   'cable' 만 message 로 본다: 케이블 이상은 코드가 아니라 flow 가 last_code=ROBOT_ERROR 에 케이블 안내 문구를 얹어 보낸다(flow.handle_cable_tight).
export function pauseKind(s) {
  if (!s || s.step !== 'PAUSED') return null;
  // 케이블 멈춤은 flow 가 last_code=ROBOT_ERROR 에 케이블 문구를 얹어 보낸다(flow.handle_cable_tight). 코드까지 봐야 한다 —
  //    재개 뒤 남는 '재개 — 무게를 다시 재며 케이블을 확인합니다' 문구 때문에 다음 멈춤(일시 정지·툴 놓침)이 케이블로 보이지 않게.
  //    밀기를 알아챈 뒤 멈춘 채 바뀌는 '케이블 — 밀기 확인 …' 문구는 코드가 ROBOT_ERROR 그대로라 케이블 카드로 남는다.
  if (s.last_code === 'ROBOT_ERROR' && (s.message || '').includes('케이블')) return 'cable';
  switch (s.last_code) {
    case 'ROBOT_ERROR': return 'robot_error';
    case 'TOOL_LOST': return 'tool_lost';
    case 'TOOL_FAIL': return 'tool_fail';         // E52 — 홀더에서 못 집음 → 멈춤(격리 X) · 홀더 확인 → 넛지
    case 'LEFTOVER_REMAIN': return 'leftover';
    case 'GRIP_FAIL': return 'grip';
    case 'RACK_FULL': return 'rack_full';
    default: return 'operator';                      // 일시 정지 버튼 · 빈 구역 뒤 HOME 실패 등
  }
}

// 넛지(Nudge · 로봇팔을 힘 15 N 넘게 가볍게 밀면 재개 신호) 를 화면에서 부르는 말 — 한곳에서 바꾼다.
//   step: 안내 카드의 할 일 한 줄 · done: 풀렸을 때 토스트 · word: 이름
export const NUDGE = { step: '로봇팔 가볍게 밀기 (또는 재개)', done: '넛지(로봇팔 가볍게 밀기)', word: '넛지' };

// 멈춤 원인별 운영자 안내 — 제목 + 할 일 2~3줄, 각 줄 몇 단어. 설명 문장 없음(what 은 비워 둔다 · 있으면 한 줄).
//    설명·근거는 SDD §7 · 대본에. 로봇 오류는 신호 1(확인 → 넛지/재개) · 신호 2(받아 치움 → 재개) · HOME 실패 세 장만(경우를 합쳤다).
export const GUIDE_KO = {
  operator: { title: '일시 정지', steps: ['재개 — 이어서', '중단 — 이 용기 격리'] },
  cable: { title: '케이블 확인', steps: ['케이블 정리', NUDGE.step] },
  tool_lost: { title: '툴 놓침', steps: ['홀더에 다시 꽂기', NUDGE.step] },
  tool_fail: { title: '툴 집기 실패', steps: ['홀더에 툴 바로 꽂기', NUDGE.step] },
  leftover: { title: '잔반 남음', steps: ['잔반 덜어내기', '재개 (또는 중단)'] },
  grip: { title: '집기 실패', steps: ['용기 위치 확인', '재개 (또는 중단)'] },
  rack_full: { title: '팔레트 가득', steps: ['새 팔레트로 교체', '재개'] },
  waste_bin: { title: '잔반통 교체', steps: ['잔반통 비우기', '소모품 칸의 교체 완료 누르기', '재개'] },   // 잔반통 한도(hmi.waste_bin_limit_g)에 닿아 HMI 가 보낸 일시 정지
  // 로봇 오류는 설계한 예외가 아니라 컨트롤러 오류를 받는 그물 — 화면에서 별도 예외로 내세우지 않고 일반 멈춤 카드(주황)로만 보인다
  robot_error: { title: '멈춤 — 로봇 확인', steps: ['로봇·주변 확인', '재개 — 쥔 것이 있으면 그리퍼 열림', '받아 치우고 다시 재개'] },
  robot_error_release: { title: '멈춤 — 받아 주세요', steps: ['받아서 치우기 (홈의 용기도)', '물러나서 재개'] },
  robot_error_home: { title: '멈춤 — HOME 복귀 실패', steps: ['펜던트로 팔 옮기기', '재개'] },
};
// flow 문구를 화면에 같이 보이지 않는 갈래 — 안내가 이미 그 내용이라 겹치면 글이 너무 길다
export const HIDE_FLOW_MSG = ['cable', 'tool_lost', 'tool_fail', 'robot_error', 'waste_bin'];   // 잔반통 멈춤은 HMI 가 보낸 stop 이라 flow 문구('운영자 요청')가 어긋난다

// 로봇 오류 멈춤의 안내 — flow 의 message 로 신호 2(그리퍼 열림) · HOME 복귀 실패 · 신호 1(그 밖)을 가른다
export function robotErrorGuide(message) {
  const m = message || '';
  if (m.includes('그리퍼를 열었습니다')) return GUIDE_KO.robot_error_release;   // 신호 2 — 받아 치운 뒤 재개 버튼(E54)
  if (m.includes('HOME 복귀 실패')) return GUIDE_KO.robot_error_home;
  return GUIDE_KO.robot_error;                                                   // 신호 1 — 쥔 것 유무와 관계없이 같은 할 일
}

const doneOf = (s, kind) => (kind === 'BOWL' ? s.done_bowl : s.done_cup) || 0;

// 버튼을 누를 수 있는가 — 시험 페이지와 같은 규칙(IRD §6)
export function buttons(d) {
  const s = d.state;
  const step = s ? s.step : null;
  const c = !!d.connected;
  return {
    start: c && step === 'IDLE',
    stop: c && RUNNING.includes(step),
    resume: c && step === 'PAUSED',
    abort: c && step === 'PAUSED' && pauseKind(s) !== 'robot_error',   // 로봇 오류면 사람이 복구한다 — 중단(격리)으로 덮지 않는다. 케이블 이상은 코드가 ROBOT_ERROR 여도 중단 가능(flow.handle_cable_tight)
  };
}

// 이번 회차의 이벤트 — 이벤트 목록에는 지난 회차 것도 섞여 있다(가짜 flow 는 대본을 반복한다).
// 끝난 용기 1개 = DONE 또는 ISOLATED 이벤트 1건이므로, 최근 것부터 (done_bowl + done_cup + isolated) 건까지가 이번 회차다.
export function currentRun(d) {
  const s = d.state || {};
  let need = (s.done_bowl || 0) + (s.done_cup || 0) + (s.isolated || 0);
  const out = [];
  for (const e of d.events || []) {
    if (need <= 0) break;
    out.push(e);
    if (e.result === 'DONE' || e.result === 'ISOLATED') need -= 1;
  }
  return out;
}

// 팔레트 칸 — rack_order 앞에서부터 done 개가 찼다(SDD §6 · IRD §6). 지금 적재 중인 칸은 표시한다.
export function pallet(d) {
  const order = (d.plan && d.plan.rack_order) || {};
  const s = d.state || {};
  const out = [];
  for (const kind of ['BOWL', 'CUP']) {
    const done = doneOf(s, kind);
    (order[kind] || []).forEach((slot, i) => out.push({
      slot, kind, n: i + 1,                           // n = 그 종류에서 몇 번째로 넣는 칸(그릇 1·2 · 컵 1·2)
      filled: i < done,
      loading: i === done && s.step === 'RACK' && s.kind === kind,
    }));
  }
  return out;
}

// 반납 구역 — 계획 수에서 끝난 수(완료 + 격리)를 뺀 것이 남은 용기. E9: 구역마다 집는 자리는 1개(내리막 공급)
export function zones(d) {
  const plan = (d.plan && d.plan.plan) || [];
  const s = d.state || {};
  const run = currentRun(d);
  const running = RUNNING.includes(s.step) || s.step === 'PAUSED';
  const perKind = (k) => plan.filter((q) => q.kind === k).length;
  return plan.map((p) => {
    // 목표 수량은 flow 가 보내는 값(target_*)이 기준 — 설정 파일의 계획과 다를 수 있다(가짜 대본 · 계획을 바꾼 실행).
    // 한 종류에 구역이 하나면 그 값을 그대로 쓴다.
    const target = kind => (kind === 'BOWL' ? s.target_bowl : s.target_cup);
    const count = s && target(p.kind) != null && perKind(p.kind) === 1 ? target(p.kind) : p.count;
    const isolated = run.filter((e) => e.result === 'ISOLATED' && e.zone_id === p.zone).length;
    const finished = Math.min(count, doneOf(s, p.kind) + isolated);
    // 빈 구역(EMPTY_ZONE) — flow 는 그 구역을 건너뛰고(SKIPPED 이벤트) 바로 다음 구역으로 간다. 상태는 1초 남짓만 스친다
    // → 이벤트로도 본다. 건너뛴 구역에는 더 집을 용기가 없다(남음 0).
    const empty = (s.last_code === 'EMPTY_ZONE' && s.zone_id === p.zone)
      || run.some((e) => e.result === 'SKIPPED' && e.zone_id === p.zone);
    const active = running && s.zone_id === p.zone && !empty;
    return {
      zone: p.zone, kind: p.kind, count,
      left: empty ? 0 : count - finished,
      status: active ? '처리 중' : empty ? '비었음' : count === 0 ? '계획 없음' : finished >= count ? '완료' : '대기',
    };
  });
}

// 사이클 타임 — 이번 회차에 끝난 용기의 소요 시간. recent = 최근 8개(오래된 것 → 최근 것, 작은 막대 그림용)
export function cycle(d) {
  const ds = currentRun(d).filter((e) => e.result === 'DONE' || e.result === 'ISOLATED').map((e) => e.duration_s || 0);
  if (!ds.length) return null;
  return { last: ds[0], mean: ds.reduce((a, b) => a + b, 0) / ds.length, n: ds.length, recent: ds.slice(0, 8).reverse() };
}

// 몇 번째 용기인가 — 끝난 용기(완료 + 격리) 수와 계획 수
export function progress(d) {
  const s = d.state || {};
  return {
    finished: (s.done_bowl || 0) + (s.done_cup || 0) + (s.isolated || 0),
    total: (s.target_bowl || 0) + (s.target_cup || 0),
  };
}

// 다음 할 일 — "지금 하는 일" 칸의 한 줄. 적재 뒤에는 다음 용기(남았으면) 또는 끝
export function nextStep(step, p) {
  if (step === 'IDLE') return '시작 누르기';
  if (step === 'DONE') return '팔레트 확인';
  if (step === 'PAUSED') return '재개 또는 중단';
  if (step === 'ERROR') return '운영자 복구';
  if (step === 'WEIGH') return '털기 또는 안착';               // 잔반(50 g 이상)이 있을 때만 턴다
  const i = FLOW.indexOf(step);
  if (i >= 0 && i < FLOW.length - 1) return STEP_KO[FLOW[i + 1]];
  return p.finished + 1 < p.total ? '다음 용기 집기' : '마지막 — 완료';
}

// 소모품 — 교체까지 남은 횟수. 한도의 15 % 이하로 남으면 warn(곧 교체), 0 이면 bad(교체 필요)
function remain(used, max) {
  if (used == null) return null;
  if (!max) return { used, max: null, left: null, level: 'ok' };
  const left = Math.max(0, max - used);
  const level = left === 0 ? 'bad' : left <= Math.max(1, Math.round(max * 0.15)) ? 'warn' : 'ok';
  return { used, max, left, level };
}
function wasteRemain(usedG, limitG) {
  if (usedG == null) return null;
  if (!limitG) return { used_g: usedG, max_g: null, left_g: null, level: 'ok' };
  const left = Math.max(0, limitG - usedG);
  const level = left === 0 ? 'bad' : left <= limitG * 0.15 ? 'warn' : 'ok';
  return { used_g: usedG, max_g: limitG, left_g: left, level };
}
export function consumables(d) {
  const s = d.state || {};
  const c = (d.plan && d.plan.consumables) || {};
  if (d.usage) {   // DB 기준(마지막 교체 뒤) — HMI·flow 를 껐다 켜도 이어진다. 한도는 서버가 준다(limits)
    const L = d.limits || {};
    return { fromDb: true,
      sponge: remain(d.usage.sponge.used, L.sponge ?? c.sponge_max_uses), brush: remain(d.usage.brush.used, L.brush ?? c.sponge_max_uses),
      soap: remain(d.usage.soap.used, L.soap ?? c.soap_max_dips), waste: wasteRemain(d.usage.waste_bin.used_g, L.waste_bin_g) };
  }
  // 서버 기록이 없을 때 — 수세미·솔은 같은 교체 주기(sponge_max_uses · 100회) · 툴마다 따로 센다: 그릇 완료 수 = 수세미 사용, 컵 완료 수 = 솔 사용
  //    (flow 의 sponge_uses 는 둘을 합친 수라 화면엔 안 쓴다) · 헹굼 물은 세지 않는다(표시 제외)
  //    세제는 담금 횟수(용기당 3)가 아니라 세제 묻히는 행위 1회 = 용기 1개 — 완료 용기 수(그릇+컵)로 센다 · 한도 soap_max_dips(60) = 용기 60개
  return { fromDb: false, sponge: remain(s.done_bowl, c.sponge_max_uses), brush: remain(s.done_cup, c.sponge_max_uses),
           soap: remain((s.done_bowl || 0) + (s.done_cup || 0), c.soap_max_dips), waste: null };
}

// 알람 — 멈춤(PAUSED)이면 원인 갈래(pauseKind)별 안내(level=pause · 로봇 오류도 같은 주황) · 운전 중이면 마지막 코드가 정상이 아닐 때 노란 경고
export function alarm(d) {
  const s = d.state;
  if (!s) return null;
  let kind = pauseKind(s);
  if (kind === 'operator' && d.notices && d.notices.waste_full) kind = 'waste_bin';   // 잔반통이 차서 HMI 가 보낸 일시 정지
  if (kind) {
    const guide = kind === 'robot_error' ? robotErrorGuide(s.message) : GUIDE_KO[kind];
    return { level: 'pause', kind, guide, code: s.last_code, message: s.message };
  }   // 로봇 오류도 주황(별도 예외 X)
  if (s.last_code && s.last_code !== 'OK') return { level: 'warn', kind: null, guide: null, code: s.last_code, message: s.message };   // 재개해 진행 중 — 최근 원인만
  return null;
}

// 넛지(로봇팔 가볍게 밀기)로도 풀리는 멈춤 — flow._NUDGE_CODES(툴 놓침 · 툴 집기 실패 · 로봇 오류)와 케이블. 일시 정지 버튼 멈춤 등은 재개 버튼만
export const NUDGE_KINDS = ['cable', 'tool_lost', 'tool_fail', 'robot_error'];
// 이 멈춤이 넛지로 풀리는가 — 로봇 오류의 신호 2(받아 치운 뒤)와 HOME 복귀 실패는 재개 버튼만 받는다(flow._robot_error_pause · E54)
export function nudgeOk(a) {
  if (!a || !NUDGE_KINDS.includes(a.kind)) return false;
  return !(a.guide === GUIDE_KO.robot_error_release || a.guide === GUIDE_KO.robot_error_home);
}

// 자동 재시도 원인 — params.yaml flow.policy 에서 'retry:N->isolate' 인 코드(서버가 plan.policy 로 넘겨준다).
//    설정이 안 오면(옛 서버) params.yaml 과 같은 목록을 쓴다: FORCE_LIMIT · TIMEOUT · RACK_JAM = retry:1->isolate
export function retryPolicy(plan) {
  const pol = (plan && plan.policy) || null;
  if (!pol) return { FORCE_LIMIT: 1, TIMEOUT: 1, RACK_JAM: 1 };
  const out = {};
  for (const [code, v] of Object.entries(pol)) {
    const m = /^retry:(\d+)/.exec(String(v));
    if (m) out[code] = Number(m[1]);
  }
  return out;
}

// 운전 중 노란 띠의 한 줄 — 상황에 맞는 말만(추측으로 '재개해 진행 중' 이라고 하지 않는다)
//    resumedCode = 화면이 마지막으로 본 멈춤의 원인 코드(Monitor 가 기억 · 회차가 끝나면 지운다)
export function runningNote(s, plan, resumedCode) {
  if (!s) return '';
  if (s.step === 'ISOLATE') return '이 용기를 격리하는 중입니다 — 끝나면 다음 용기로 갑니다';
  if (resumedCode && s.last_code === resumedCode) return '재개해 진행 중입니다 — 다시 멈추면 위 안내가 뜹니다';
  const n = retryPolicy(plan)[s.last_code];
  if (n) return `자동으로 ${n === 1 ? '한 번' : `최대 ${n}번`} 다시 시도하는 중입니다 — 또 실패하면 이 용기는 격리합니다`;
  return '진행 중입니다 — 다시 멈추면 위 안내가 뜹니다';
}

// 최근 문제 — 완료가 아닌 이벤트(격리·오류·건너뜀)와 집기를 다시 시도한 용기, 최근 5건
export function problems(d) {
  return (d.events || []).filter((e) => (e.result && e.result !== 'DONE') || (e.attempts || 0) > 1).slice(0, 5);   // 집기를 다시 시도한 용기도 문제로 본다(FR-03)
}

// 멈춤 기록 — DB pauses 표(/api/db/pauses · 최근 것부터)를 화면 줄로. 언제 · 어느 단계 · 원인 · 코드 · 어떻게 풀렸나 · 걸린 시간
export const RESOLVED_KO = { resume: '재개 버튼', abort: '중단', nudge: '넛지', restart: '재시작' };
export function pauseRows(rows) {
  return (rows || []).map((r) => ({
    id: r.id,
    time: clockIso(r.started_at),
    step: STEP_KO[r.step] || r.step || '-',
    cause: PAUSE_KO[r.kind] || r.kind || '-',
    code: r.code && r.code !== 'OK' ? r.code : '',
    resolved: r.ended_at ? (RESOLVED_KO[r.resolved] || r.resolved || '-') : '진행 중',
    open: !r.ended_at,
    duration: r.duration_s != null ? `${Math.round(r.duration_s)} s` : '-',
  }));
}
// 빈 구역 알림 — flow 는 멈추지 않고 건너뛰므로(SKIPPED 이벤트) 확인 창 대신 몇 초 뜨는 주황 알림
export function skipToast(e) {
  if (!e || e.result !== 'SKIPPED') return null;
  const kind = KIND_KO[e.kind] ? `${KIND_KO[e.kind]} ` : '';
  return { tone: 'warn', text: `빈 구역 — ${kind}반납 구역${e.zone_id ? `(${e.zone_id})` : ''}에 용기가 없습니다`, sub: '건너뛰고 다음 구역으로 갑니다' };
}
export function clockIso(iso) {          // DB 의 시각 문자열(YYYY-MM-DDTHH:MM:SS…) → HH:MM:SS
  const m = /T(\d{2}:\d{2}:\d{2})/.exec(iso || '');
  return m ? m[1] : (iso || '-');
}

// 이벤트의 원인 — 운영자가 중단(/flow/abort)하면 flow 는 ISOLATED 에 그때의 last_code 를 붙인다.
// 일시 정지 → 중단이면 그 값이 OK 라서 "격리 · 정상" 으로 보인다 → "운영자 중단" 으로 풀어 쓴다(flow.py abort_container)
export function why(e) {
  if (e.result === 'ISOLATED' && (!e.code || e.code === 'OK' || e.code === 'STOPPED')) return '운영자 중단';
  return CODE_KO[e.code] || e.code || '-';
}

// stamp(epoch 초) → 'HH:MM:SS' 현지 시각. 없으면 '-'
export function clock(stamp) {
  if (!stamp) return '-';
  const t = new Date(stamp * 1000);
  return [t.getHours(), t.getMinutes(), t.getSeconds()].map((v) => String(v).padStart(2, '0')).join(':');
}

// 누적 KPI — /api/kpi 응답을 화면 칸 6개로. 값이 없으면 '-'
export const PAUSE_KO = { operator: '일시 정지', cable: '케이블', tool_lost: '툴 놓침', tool_fail: '툴 집기 실패', leftover: '잔반 남음', grip: '집기 실패', rack_full: '팔레트 가득', robot_error: '로봇 확인', waste_bin: '잔반통' };
export const PERIOD_KO = { run: '이번 실행', today: '오늘', all: '전체' };
export function kpiCards(k) {
  if (!k) return [];
  const n = (v, unit = '') => (v == null ? '-' : `${v}${unit}`);
  const kg = (g) => (g == null ? '-' : g >= 1000 ? `${(g / 1000).toFixed(1)} kg` : `${Math.round(g)} g`);
  return [
    { label: '처리량', value: n(k.done_bowl + k.done_cup, '개'), sub: `그릇 ${k.done_bowl} · 컵 ${k.done_cup}${k.pallets != null ? ` · 팔레트 ${k.pallets}장` : ''}`,
      help: '완료(적재까지 끝난) 용기 수 = 그릇 + 컵. 팔레트 1장 = 칸 4개를 다 채우고 끝난 실행 1번.' },
    { label: '처리율', value: n(k.success_pct, '%'), sub: `격리 ${k.isolated} · 오류 ${k.error} · 건너뜀 ${k.skipped}`, tone: k.success_pct != null && k.success_pct < 90 ? 'warn' : '',
      help: '완료 ÷ (완료 + 격리 + 오류 + 건너뜀) × 100. 90 % 아래면 주황.' },
    { label: '용기당 평균', value: `${n(k.avg_s_bowl, 's')} / ${n(k.avg_s_cup, 's')}`, sub: '그릇 / 컵', help: '완료한 용기 1개에 걸린 평균 시간(집기 → 적재). 그릇과 컵을 따로 낸다.' },
    { label: '시간당', value: n(k.per_hour, '개'), sub: k.per_hour == null ? '5분 넘게 돌면 계산' : '완료 기준', help: '완료 수 ÷ (첫 용기부터 마지막 용기까지 걸린 시간). 5분 넘게 돌아야 낸다.' },
    { label: '멈춤', value: n(k.pauses, '회'), sub: k.pauses ? `${Math.round(k.pause_s)}초 · 잦은 원인 ${PAUSE_KO[k.pause_top] || k.pause_top || '-'}` : '없음', tone: k.pauses ? 'warn' : '',
      help: '멈춤(PAUSED)에 들어간 횟수, 멈춰 있던 시간의 합, 가장 잦은 원인.' },
    { label: '잔반', value: n(k.leftover_pct, '%'), sub: `그릇 중 잔반 있던 비율 · 버린 양 ${kg(k.waste_g)}`, help: '무게를 잰 그릇 중 잔반(50 g 이상)이 있던 비율과, 털어서 버린 잔반 무게의 합.' },
  ];
}

// '이번 팔레트' 카드 아래 누적 칸. DB 전체 기록(/api/kpi?period=all)이 있으면 그것(껐다 켜도 남는다),
//    없으면 브리지 메모리 누적(totals · HMI 를 켠 뒤부터). 팔레트 = 칸을 다 채우고 끝난 실행 수(db.kpi.pallets · state_store._count_run 과 같은 기준)
export function lifetime(d) {
  const k = d.kpiAll;
  if (k) return { fromDb: true, pallets: k.pallets || 0, bowls: k.done_bowl || 0, cups: k.done_cup || 0, isolated: k.isolated || 0, runs: k.runs || 0 };
  const t = d.totals || {};
  return { fromDb: false, pallets: t.pallets || 0, bowls: t.bowls || 0, cups: t.cups || 0, isolated: t.isolated || 0, runs: t.runs || 0 };
}

// 예외 알림창 — 원인 아이콘(public/illust/icons/*.svg 이름) · 멈춤이 풀렸을 때 토스트 문구
export function causeIcon(kind, containerKind) {
  const tool = containerKind === 'CUP' ? 'brush' : 'sponge';
  const vessel = containerKind === 'CUP' ? 'cup' : 'bowl';
  return { cable: 'cable', tool_lost: tool, tool_fail: tool, leftover: 'bowl', grip: vessel, rack_full: 'pallet',
           waste_bin: 'bin', robot_error: 'robot', operator: 'timer' }[kind] || 'timer';
}
export function resumeToast(viaButton, pausedStep, nextStep) {
  if (nextStep === 'ISOLATE') return { text: '중단 — 이 용기를 격리 구역으로 보냅니다', sub: '정리가 끝나면 다음 용기로 갑니다' };
  const how = viaButton ? '재개 버튼' : NUDGE.done;
  const from = STEP_KO[nextStep] ? `${STEP_KO[nextStep]} 단계부터 이어 갑니다` : '이어 갑니다';
  return { text: `재개되었습니다 — ${how}`, sub: from };
}

