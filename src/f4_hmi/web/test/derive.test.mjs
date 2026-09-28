// derive.js 순수 함수 시험 — 실행: cd src/f4_hmi/web && node --test test/   (Node 18 내장 test runner · 설치 없음)
// derive.js 는 ESM(export)인데 package.json 에 type=module 이 없어 .js 를 그대로 import 하지 못한다 → 파일을 읽어 data: URL 모듈로 불러온다.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const src = await readFile(join(here, '..', 'app', 'lib', 'derive.js'), 'utf8');
const D = await import('data:text/javascript;base64,' + Buffer.from(src).toString('base64'));

const st = (over) => ({ step: 'IDLE', kind: '', zone_id: '', done_bowl: 0, done_cup: 0, isolated: 0, target_bowl: 2, target_cup: 2,
  sponge_uses: 0, soap_dips: 0, rinse_dips: 0, last_code: 'OK', message: '', ...over });
const d = (state, connected = true) => ({ connected, state, events: [], plan: { rack_order: { BOWL: ['RACK_B1', 'RACK_B2'], CUP: ['RACK_C1', 'RACK_C2'] }, plan: [] } });

test('버튼 — 시작은 IDLE 에서만 · 정지는 운전 중 · 재개·중단은 멈춤에서(SDD §6)', () => {
  assert.deepEqual(D.buttons(d(st({ step: 'IDLE' }))), { start: true, stop: false, resume: false, abort: false });
  assert.deepEqual(D.buttons(d(st({ step: 'WIPE' }))), { start: false, stop: true, resume: false, abort: false });
  assert.deepEqual(D.buttons(d(st({ step: 'PAUSED' }))), { start: false, stop: false, resume: true, abort: true });
  assert.deepEqual(D.buttons(d(st({ step: 'DONE' }))), { start: false, stop: false, resume: false, abort: false });
});

test('버튼 — 연결이 끊기면 전부 비활성(SDD §6 연결)', () => {
  assert.deepEqual(D.buttons(d(st({ step: 'PAUSED' }), false)), { start: false, stop: false, resume: false, abort: false });
});

test('버튼 — 로봇 오류 멈춤은 중단 불가(사람 복구) · 케이블 이상 멈춤은 코드가 ROBOT_ERROR 라도 중단 가능', () => {
  assert.equal(D.buttons(d(st({ step: 'PAUSED', last_code: 'ROBOT_ERROR', message: '후퇴 실패' }))).abort, false);
  assert.equal(D.buttons(d(st({ step: 'PAUSED', last_code: 'ROBOT_ERROR', message: '케이블 상태를 확인해주세요' }))).abort, true);
});

test('멈춤 원인 갈래 — 코드·문구로 8가지를 가른다', () => {
  assert.equal(D.pauseKind(st({ step: 'PAUSED' })), 'operator');
  assert.equal(D.pauseKind(st({ step: 'PAUSED', last_code: 'TOOL_LOST' })), 'tool_lost');
  assert.equal(D.pauseKind(st({ step: 'PAUSED', last_code: 'TOOL_FAIL' })), 'tool_fail');       // 🆕 E52
  assert.equal(D.pauseKind(st({ step: 'PAUSED', last_code: 'LEFTOVER_REMAIN' })), 'leftover');
  assert.equal(D.pauseKind(st({ step: 'PAUSED', last_code: 'GRIP_FAIL' })), 'grip');
  assert.equal(D.pauseKind(st({ step: 'PAUSED', last_code: 'RACK_FULL' })), 'rack_full');
  assert.equal(D.pauseKind(st({ step: 'PAUSED', last_code: 'ROBOT_ERROR' })), 'robot_error');
  assert.equal(D.pauseKind(st({ step: 'PAUSED', last_code: 'ROBOT_ERROR', message: '케이블 상태를 확인해주세요.' })), 'cable');
  assert.equal(D.pauseKind(st({ step: 'WIPE', last_code: 'TOOL_LOST' })), null);
});

test('알람 — 멈춤은 원인별 안내(제목·할 일) · 로봇 오류도 주황(별도 예외 X · 9/27)', () => {
  const a = D.alarm(d(st({ step: 'PAUSED', last_code: 'TOOL_LOST' })));
  assert.equal(a.level, 'pause'); assert.equal(a.kind, 'tool_lost'); assert.match(a.guide.title, /툴 놓침/); assert.ok(a.guide.steps.length >= 2);
  const re = D.alarm(d(st({ step: 'PAUSED', last_code: 'ROBOT_ERROR', message: 'x — 로봇 오류 · 그리퍼에 용기이(가) 있습니다.' })));
  assert.equal(re.level, 'pause'); assert.match(re.guide.title, /멈춤 — 로봇 확인/); assert.match(re.guide.steps.join(' '), /그리퍼 열림/);   // 신호 1
  assert.match(D.robotErrorGuide('그리퍼를 열었습니다 — …').title, /받아 주세요/);      // 신호 2 = 재개 버튼(E54)
  assert.match(D.robotErrorGuide('x — 로봇 오류 · 빈손.').title, /로봇 확인/);        // 빈손도 같은 안내(경우 합침 · 9/27)
  assert.match(D.robotErrorGuide('HOME 복귀 실패(1/3)').title, /HOME/);
  for (const k of Object.keys(D.GUIDE_KO)) { const g = D.GUIDE_KO[k]; assert.ok(!g.what && g.steps.length <= 3 && g.steps.every((x) => x.length <= 24), `${k} 안내가 길다`); }
  assert.ok(D.HIDE_FLOW_MSG.includes('robot_error') && D.HIDE_FLOW_MSG.includes('cable') && D.HIDE_FLOW_MSG.includes('waste_bin'));
  assert.match(D.alarm(d(st({ step: 'PAUSED', last_code: 'TOOL_FAIL' }))).guide.title, /툴 집기 실패/);
  assert.equal(D.alarm(d(st({ step: 'PAUSED', last_code: 'ROBOT_ERROR', message: '케이블 …' }))).level, 'pause');
  assert.equal(D.alarm(d(st({ step: 'WIPE', last_code: 'TOOL_LOST' }))).level, 'warn');       // 재개해 진행 중 — 노란 경고
  assert.equal(D.alarm(d(st({ step: 'WIPE' }))), null);
});

test('이력 원인 — 운영자 중단은 코드 OK 라도 "운영자 중단" · SKIPPED 는 빈 구역', () => {
  assert.equal(D.why({ result: 'ISOLATED', code: 'OK' }), '운영자 중단');
  assert.equal(D.why({ result: 'ISOLATED', code: 'LEFTOVER_REMAIN' }), '잔반이 남음');
  assert.equal(D.why({ result: 'SKIPPED', code: 'EMPTY_ZONE' }), '빈 구역');
  assert.equal(D.why({ result: 'ERROR', code: 'TOOL_LOST' }), '툴 놓침');
});

test('팔레트 칸 — 끝난 수만큼 앞에서 채우고 적재 중인 칸을 표시한다', () => {
  const cells = D.pallet(d(st({ step: 'RACK', kind: 'BOWL', done_bowl: 1 })));
  assert.deepEqual(cells.map((c) => [c.slot, c.filled, c.loading]), [['RACK_B1', true, false], ['RACK_B2', false, true], ['RACK_C1', false, false], ['RACK_C2', false, false]]);
});

test('다음 할 일 — 멈춤은 재개 또는 중단 · 적재 뒤는 다음 용기 또는 완료', () => {
  assert.equal(D.nextStep('PAUSED', { finished: 0, total: 4 }), '재개 또는 중단');
  assert.equal(D.nextStep('RACK', { finished: 3, total: 4 }), '마지막 — 완료');
  assert.equal(D.nextStep('RACK', { finished: 1, total: 4 }), '다음 용기 집기');
});

test('소모품 — 수세미는 그릇 수 · 솔은 컵 수 · 같은 한도 100 · 헹굼은 없다(황인재 9/27)', () => {
  const dd = d(st({ done_bowl: 90, done_cup: 100, soap_dips: 570 }));   // soap_dips(담금 수)는 안 쓴다 — 세제 = 용기 수 190
  dd.plan.consumables = { sponge_max_uses: 100, soap_max_dips: 60 };
  const c = D.consumables(dd);
  assert.equal(c.sponge.left, 10); assert.equal(c.sponge.level, 'warn');
  assert.equal(c.brush.left, 0); assert.equal(c.brush.level, 'bad');
  assert.equal(c.soap.left, 0); assert.equal(c.soap.used, 190); assert.equal(c.rinse, undefined);
});

test('소모품 — DB 값(usage)이 있으면 그것을 쓰고 잔반통은 g/한도 · 잔반통 가득이면 일시 정지 카드는 잔반통 교체', () => {
  const dd = d(st({ step: 'PAUSED', done_bowl: 1 }));
  dd.usage = { sponge: { used: 40 }, brush: { used: 100 }, soap: { used: 10 }, waste_bin: { used_g: 48000 } };
  dd.limits = { sponge: 100, brush: 100, soap: 60, waste_bin_g: 50000 };
  dd.notices = { waste_full: false };
  const c = D.consumables(dd);
  assert.ok(c.fromDb); assert.equal(c.sponge.left, 60); assert.equal(c.brush.level, 'bad'); assert.equal(c.waste.left_g, 2000); assert.equal(c.waste.level, 'warn');
  assert.equal(D.alarm(dd).kind, 'operator');
  dd.notices = { waste_full: true };
  assert.equal(D.alarm(dd).kind, 'waste_bin'); assert.match(D.alarm(dd).guide.title, /잔반통/);
  const cards = D.kpiCards({ period: 'run', total: 4, done_bowl: 2, done_cup: 1, isolated: 1, error: 0, skipped: 0, success_pct: 75, avg_s_bowl: 70, avg_s_cup: 40, per_hour: null, pauses: 1, pause_s: 12, pause_top: 'tool_lost', leftover_pct: 50, waste_g: 92, runs: 1 });
  assert.equal(cards.length, 6); assert.equal(cards[0].value, '3개'); assert.match(cards[4].sub, /툴 놓침/);
  assert.ok(cards.every((c) => typeof c.help === 'string' && c.help.length > 10));                 // KPI 칸 도움말
  assert.doesNotMatch(cards[0].sub, /팔레트/);                                     // 옛 서버(pallets 없음)면 숨긴다
  assert.match(D.kpiCards({ done_bowl: 2, done_cup: 2, isolated: 0, error: 0, skipped: 0, pauses: 0, pallets: 1 })[0].sub, /팔레트 1장/);
  assert.equal(D.kpiCards(null).length, 0);
  // 🆕 9/28 팔레트 카드의 누적 칸 — DB 전체 기록이 있으면 그것, 없으면 브리지 메모리 누적
  const life = D.lifetime({ kpiAll: { pallets: 3, done_bowl: 7, done_cup: 6, isolated: 2, runs: 4 }, totals: { pallets: 0, bowls: 1 } });
  assert.deepEqual(life, { fromDb: true, pallets: 3, bowls: 7, cups: 6, isolated: 2, runs: 4 });
  assert.deepEqual(D.lifetime({ totals: { pallets: 1, bowls: 2, cups: 2, isolated: 0, runs: 1 } }), { fromDb: false, pallets: 1, bowls: 2, cups: 2, isolated: 0, runs: 1 });
  assert.equal(D.lifetime({}).pallets, 0);
  // 멈춤 기록 창(9/28) — DB pauses 행 → 화면 줄 · 문제만에 집기 재시도 포함
  const pr = D.pauseRows([{ id: 2, started_at: '2026-09-28T15:10:03.1', ended_at: null, duration_s: null, step: 'SOAP', kind: 'tool_fail', code: 'TOOL_FAIL', resolved: null },
                          { id: 1, started_at: '2026-09-28T15:07:19', ended_at: '2026-09-28T15:07:31', duration_s: 12.4, step: 'WIPE', kind: 'tool_lost', code: 'TOOL_LOST', resolved: 'nudge' }]);
  assert.deepEqual(pr[1], { id: 1, time: '15:07:19', step: '닦기', cause: '툴 놓침', code: 'TOOL_LOST', resolved: '넛지', open: false, duration: '12 s' });
  assert.equal(pr[0].resolved, '진행 중'); assert.ok(pr[0].open); assert.equal(pr[0].step, '세제');
  assert.equal(D.problems({ events: [{ result: 'DONE', attempts: 2 }, { result: 'DONE', attempts: 1 }, { result: 'ISOLATED' }] }).length, 2);
  // 빈 구역 알림(9/28) — 건너뜀 이벤트만
  assert.deepEqual(D.skipToast({ result: 'SKIPPED', kind: 'BOWL', zone_id: 'RET_B' }), { tone: 'warn', text: '빈 구역 — 그릇 반납 구역(RET_B)에 용기가 없습니다', sub: '건너뛰고 다음 구역으로 갑니다' });
  assert.equal(D.skipToast({ result: 'DONE', kind: 'BOWL' }), null); assert.equal(D.skipToast(null), null);
});

test('알림창 — 원인 아이콘은 용기 종류를 따르고, 풀림 토스트는 버튼/넛지·중단을 가른다(9/28)', () => {
  assert.equal(D.causeIcon('tool_lost', 'CUP'), 'brush'); assert.equal(D.causeIcon('tool_fail', 'BOWL'), 'sponge'); assert.equal(D.causeIcon('waste_bin', 'BOWL'), 'bin');
  assert.equal(D.causeIcon('cable', 'BOWL'), 'cable'); assert.equal(D.causeIcon('robot_error', 'CUP'), 'robot'); assert.equal(D.causeIcon('nope', 'BOWL'), 'timer');
  assert.match(D.resumeToast(false, 'WIPE', 'WIPE').text, /넛지\(로봇팔 가볍게 밀기\)/); assert.ok(D.GUIDE_KO.tool_lost.steps[1] === D.NUDGE.step && !/톡/.test(D.NUDGE.step)); assert.match(D.resumeToast(false, 'WIPE', 'WIPE').sub, /닦기 단계부터/);
  assert.match(D.resumeToast(true, 'SOAP', 'SOAP').text, /재개 버튼/);
  assert.match(D.resumeToast(true, 'SOAP', 'ISOLATE').text, /중단/);
});

test('케이블 카드는 코드 ROBOT_ERROR + 케이블 문구일 때만 · 재검증 실패는 이상 지속 카드 · 운전 중 띠 문구(9/29)', () => {
  const P = (last_code, message) => ({ step: 'PAUSED', last_code, message });
  assert.equal(D.pauseKind(P('ROBOT_ERROR', '케이블 상태를 확인해주세요.')), 'cable');
  assert.equal(D.pauseKind(P('OK', '케이블 정상 확인 — 작업을 재개합니다')), 'operator');       // ① 뒤 ② 일시 정지
  assert.equal(D.pauseKind(P('TOOL_LOST', '케이블 정상 확인 — 작업을 재개합니다')), 'tool_lost'); // ① 뒤 ③ 툴 놓침
  const again = D.alarm({ state: P('ROBOT_ERROR', '케이블 이상 지속(떨림 90 g > 상한 80 g): 케이블 확인 후 다시 로봇팔을 가볍게 밀어 주세요') });
  assert.equal(again.kind, 'cable'); assert.equal(again.guide.title, '케이블 이상 지속');
  assert.ok(D.NUDGE_KINDS.includes('tool_fail') && !D.NUDGE_KINDS.includes('operator'));
  const plan = { policy: { FORCE_LIMIT: 'retry:1->isolate', TIMEOUT: 'retry:1->isolate', RACK_JAM: 'retry:1->isolate', TOOL_FAIL: 'pause', LEFTOVER_REMAIN: 'isolate' } };
  const R = (step, last_code) => ({ step, last_code });
  assert.match(D.runningNote(R('WIPE', 'FORCE_LIMIT'), plan, null), /자동으로 한 번 다시 시도/);
  assert.match(D.runningNote(R('ISOLATE', 'FORCE_LIMIT'), plan, null), /격리하는 중/);
  assert.match(D.runningNote(R('ISOLATE', 'LEFTOVER_REMAIN'), plan, null), /격리하는 중/);
  assert.match(D.runningNote(R('WIPE', 'TOOL_LOST'), plan, 'TOOL_LOST'), /재개해 진행 중/);
  assert.match(D.runningNote(R('SOAP', 'TOOL_FAIL'), plan, null), /^진행 중/);                  // 멈춘 적 없으면 '재개해' 라고 하지 않는다
  assert.match(D.runningNote(R('WIPE', 'TIMEOUT'), {}, null), /자동으로 한 번/);                 // 옛 서버(policy 없음) → params 와 같은 목록
  assert.match(D.runningNote(R('WIPE', 'TIMEOUT'), { policy: { TIMEOUT: 'retry:3->isolate' } }, null), /최대 3번/);
});

test('넛지 안내는 넛지로 풀리는 멈춤에만 — 로봇 오류 신호 2 · HOME 복귀 실패는 재개 버튼만(9/29)', () => {
  const A = (last_code, message) => D.alarm({ state: { step: 'PAUSED', last_code, message } });
  assert.ok(D.nudgeOk(A('TOOL_LOST', '')));
  assert.ok(D.nudgeOk(A('ROBOT_ERROR', 'f2.dip: 드라이버 응답 없음 — 로봇 오류 · 그리퍼에 용기이(가) 있습니다.')));
  assert.ok(!D.nudgeOk(A('ROBOT_ERROR', '그리퍼를 열었습니다 — 받아서 치운 뒤 화면의 재개 버튼')));
  assert.ok(!D.nudgeOk(A('ROBOT_ERROR', 'HOME 복귀 실패 — 펜던트로 옮긴 뒤 재개')));
  assert.ok(!D.nudgeOk(A('OK', '일시 정지 — 운영자 요청')));
});

