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

test('알람 — 멈춤은 원인별 안내(제목·할 일)를 가지고, 로봇 오류만 붉은색', () => {
  const a = D.alarm(d(st({ step: 'PAUSED', last_code: 'TOOL_LOST' })));
  assert.equal(a.level, 'pause'); assert.equal(a.kind, 'tool_lost'); assert.match(a.guide.title, /툴 놓침/); assert.ok(a.guide.steps.length >= 2);
  const re = D.alarm(d(st({ step: 'PAUSED', last_code: 'ROBOT_ERROR', message: 'x — 로봇 오류 · 그리퍼에 용기이(가) 있습니다.' })));
  assert.equal(re.level, 'error'); assert.equal(re.guide.title, '로봇 오류'); assert.match(re.guide.steps.join(' '), /그리퍼가 열림/);   // 신호 1
  assert.match(D.robotErrorGuide('그리퍼를 열었습니다 — …').title, /받아 주세요/);      // 신호 2 = 재개 버튼(E54)
  assert.equal(D.robotErrorGuide('x — 로봇 오류 · 빈손.').title, '로봇 오류');        // 빈손도 같은 안내(경우 합침 · 9/27)
  assert.match(D.robotErrorGuide('HOME 복귀 실패(1/3)').title, /HOME/);
  for (const k of Object.keys(D.GUIDE_KO)) { const g = D.GUIDE_KO[k]; assert.ok(!g.what && g.steps.length <= 3 && g.steps.every((x) => x.length <= 24), `${k} 안내가 길다`); }
  assert.ok(D.HIDE_FLOW_MSG.includes('robot_error') && D.HIDE_FLOW_MSG.includes('cable'));
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

