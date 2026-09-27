// 받은 값 → 화면에 그릴 값. 전부 순수 함수(화면·통신과 무관).
// 팔레트 칸·반납 구역은 메시지에 없어서 계획(plan)과 수량으로 **파생**한다 — F4-00 §4.

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
  TOOL_LOST: '툴 놓침',                              // 🆕 E37(9/23) — 닦는 중 수세미·솔이 그리퍼에서 빠짐
};

// 멈춤(PAUSED)의 원인 갈래 — flow 가 보내는 last_code 와 message 로 가른다(F4 9/25 · 시연 예외 6개에 맞춤).
//   'cable' 만 message 로 본다: 케이블 이상은 코드가 아니라 flow 가 last_code=ROBOT_ERROR 에 케이블 안내 문구를 얹어 보낸다(flow.handle_cable_tight).
export function pauseKind(s) {
  if (!s || s.step !== 'PAUSED') return null;
  if ((s.message || '').includes('케이블')) return 'cable';
  switch (s.last_code) {
    case 'ROBOT_ERROR': return 'robot_error';
    case 'TOOL_LOST': return 'tool_lost';
    case 'TOOL_FAIL': return 'tool_fail';         // 🆕 E52(9/25) — 홀더에서 못 집음 → 멈춤(격리 X) · 홀더 확인 → 톡
    case 'LEFTOVER_REMAIN': return 'leftover';
    case 'GRIP_FAIL': return 'grip';
    case 'RACK_FULL': return 'rack_full';
    default: return 'operator';                      // 일시 정지 버튼 · 빈 구역 뒤 HOME 실패 등
  }
}

// 멈춤 원인별 운영자 안내 — 🔄 9/27 황인재 2차: **제목 + 할 일 2~3줄, 각 줄 몇 단어.** 설명 문장 없음(what 은 비워 둔다 · 있으면 한 줄).
//    설명·근거는 SDD §7 · 대본에. 로봇 오류는 신호 1(확인 → 톡/재개) · 신호 2(받아 치움 → 재개) · HOME 실패 세 장만(경우를 합쳤다).
export const GUIDE_KO = {
  operator: { title: '일시 정지', steps: ['재개 — 이어서', '중단 — 이 용기 격리'] },
  cable: { title: '케이블 확인', steps: ['케이블 정리', '손목 톡 (또는 재개)'] },
  tool_lost: { title: '툴 놓침', steps: ['홀더에 다시 꽂기', '손목 톡 (또는 재개)'] },
  tool_fail: { title: '툴 집기 실패', steps: ['홀더에 툴 바로 꽂기', '손목 톡 (또는 재개)'] },
  leftover: { title: '잔반 남음', steps: ['잔반 덜어내기', '재개 (또는 중단)'] },
  grip: { title: '집기 실패', steps: ['용기 위치 확인', '재개 (또는 중단)'] },
  rack_full: { title: '팔레트 가득', steps: ['새 팔레트로 교체', '재개'] },
  robot_error: { title: '로봇 오류', steps: ['로봇·주변 확인', '손목 톡 (또는 재개)', '쥔 것이 있으면 그리퍼가 열림 — 받을 준비'] },
  robot_error_release: { title: '로봇 오류 — 받아 주세요', steps: ['받아서 치우기 (홈의 용기도)', '물러나서 재개'] },
  robot_error_home: { title: '로봇 오류 — HOME 실패', steps: ['펜던트로 팔 옮기기', '재개'] },
};
// flow 문구를 화면에 같이 보이지 않는 갈래 — 안내가 이미 그 내용이다(황인재 9/27 "글이 너무 길다")
export const HIDE_FLOW_MSG = ['cable', 'tool_lost', 'tool_fail', 'robot_error'];

export function robotErrorGuide(message) {
  const m = message || '';
  if (m.includes('그리퍼를 열었습니다')) return GUIDE_KO.robot_error_release;   // 신호 2 — 받아 치운 뒤 재개 버튼(E54)
  if (m.includes('HOME 복귀 실패')) return GUIDE_KO.robot_error_home;
  return GUIDE_KO.robot_error;                                                   // 신호 1 — 쥔 것 유무와 관계없이 같은 할 일
}

const doneOf = (s, kind) => (kind === 'BOWL' ? s.done_bowl : s.done_cup) || 0;

// 버튼을 누를 수 있는가 — 시험 페이지(F4-02)와 같은 규칙(IRD §6)
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

// 팔레트 칸 — rack_order 앞에서부터 done 개가 찼다(F4-00 §4). 지금 적재 중인 칸은 표시한다.
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
export function consumables(d) {
  const s = d.state || {};
  const c = (d.plan && d.plan.consumables) || {};
  // 🔄 9/27 황인재: 수세미·솔은 같은 교체 주기(sponge_max_uses · 100회) · 툴마다 따로 센다 — 그릇 완료 수 = 수세미 사용, 컵 완료 수 = 솔 사용
  //    (flow 의 sponge_uses 는 둘을 합친 수라 화면엔 안 쓴다) · 헹굼 물은 세지 않는다(표시 제외)
  return { sponge: remain(s.done_bowl, c.sponge_max_uses), brush: remain(s.done_cup, c.sponge_max_uses), soap: remain(s.soap_dips, c.soap_max_dips) };
}

// 알람 — 멈춤(PAUSED)이면 원인 갈래(pauseKind)로 붉은색(로봇 오류)/주황(그 밖) · 운전 중이면 마지막 코드가 정상이 아닐 때 노란 경고
export function alarm(d) {
  const s = d.state;
  if (!s) return null;
  const kind = pauseKind(s);
  if (kind) return { level: kind === 'robot_error' ? 'error' : 'pause', kind, guide: kind === 'robot_error' ? robotErrorGuide(s.message) : GUIDE_KO[kind], code: s.last_code, message: s.message };
  if (s.last_code && s.last_code !== 'OK') return { level: 'warn', kind: null, guide: null, code: s.last_code, message: s.message };   // 재개해 진행 중 — 최근 원인만
  return null;
}

// 최근 문제 — 완료가 아닌 이벤트(격리·오류·건너뜀) 최근 5건
export function problems(d) {
  return (d.events || []).filter((e) => e.result && e.result !== 'DONE').slice(0, 5);
}

// 이벤트의 원인 — 운영자가 중단(/flow/abort)하면 flow 는 ISOLATED 에 **그때의 last_code** 를 붙인다.
// 일시 정지 → 중단이면 그 값이 OK 라서 "격리 · 정상" 으로 보인다 → "운영자 중단" 으로 풀어 쓴다(flow.py abort_container)
export function why(e) {
  if (e.result === 'ISOLATED' && (!e.code || e.code === 'OK' || e.code === 'STOPPED')) return '운영자 중단';
  return CODE_KO[e.code] || e.code || '-';
}

export function clock(stamp) {
  if (!stamp) return '-';
  const t = new Date(stamp * 1000);
  return [t.getHours(), t.getMinutes(), t.getSeconds()].map((v) => String(v).padStart(2, '0')).join(':');
}
