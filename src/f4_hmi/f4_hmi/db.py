# -*- coding: utf-8 -*-
"""SQLite 기록 — HMI 서버가 적는 표 5개. ROS·웹 부품을 모른다(그래서 어디서나 시험된다). 파일은 params.yaml hmi.db_path.

    events        용기 1개 = 1줄  (/flow/event 그대로 + 실행 번호 + 버린 잔반 g)
    runs          시작 버튼 1번(한 회차) = 1줄
    pauses        멈춤 1번 = 1줄  (상태가 PAUSED 로 들어갔다 나올 때 · 원인 갈래 · 어떻게 풀렸나)
    commands      버튼 1번 = 1줄
    replacements  소모품·잔반통 교체 1번 = 1줄 — 사용량은 마지막 교체 뒤의 events 로 계산한다(usage) → HMI 를 껐다 켜도 이어진다

    사용량 셈: 수세미 = 그릇 완료 수 · 솔 = 컵 완료 수 · 세제 = 완료 용기 수(용기당 1회) · 잔반통 = 버린 잔반 g 합.
    버린 잔반 = 무게 전 − 무게 후, 잔반 판정(전 > leftover_threshold_g)이 났을 때만(털지 않았으면 0).
표기 — E-nn: 팀 결정 번호(docs/decisions/20260919_결정기록_DSN-03.md) · V-nn/INT-nn: 검증 항목(docs/test-reports/) · TS-nn: 트러블슈팅(docs/troubleshooting/)
"""
import sqlite3
import threading
from datetime import datetime

ITEMS = ('sponge', 'brush', 'soap', 'waste_bin')
TABLES = ('events', 'runs', 'pauses', 'commands', 'replacements')
_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, ts TEXT NOT NULL, run_id INTEGER,
  kind TEXT, zone_id TEXT, rack_slot TEXT, result TEXT, code TEXT,
  attempts INTEGER, weight_before_g REAL, weight_after_g REAL, duration_s REAL, waste_g REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT,
  done_bowl INTEGER DEFAULT 0, done_cup INTEGER DEFAULT 0, isolated INTEGER DEFAULT 0, errors INTEGER DEFAULT 0, skipped INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS pauses (
  id INTEGER PRIMARY KEY, run_id INTEGER, started_at TEXT NOT NULL, ended_at TEXT, duration_s REAL,
  step TEXT, kind TEXT, code TEXT, resolved TEXT);
CREATE TABLE IF NOT EXISTS commands (
  id INTEGER PRIMARY KEY, ts TEXT NOT NULL, name TEXT, ok INTEGER, message TEXT, latency_ms REAL);
CREATE TABLE IF NOT EXISTS replacements (
  id INTEGER PRIMARY KEY, ts TEXT NOT NULL, item TEXT NOT NULL, note TEXT);
"""


def _now():
    return datetime.now().isoformat(timespec='seconds')


class HmiDb:
    """표 5개를 가진 SQLite 파일 하나 — 연결 1개를 락으로 지켜 ROS 스레드(기록)와 웹 스레드(조회)가 같이 쓴다."""

    def __init__(self, path, leftover_threshold_g=50.0, now=_now, rack_slots=0):
        """path: 파일 경로 · leftover_threshold_g: 잔반 판정 기준(g) — 이보다 무거웠던 그릇만 버린 잔반을 센다 · now: 시각 함수(시험용)
        · rack_slots: 팔레트 한 장의 칸 수 — 칸을 다 채우고 끝난 회차를 팔레트 1장으로 센다(kpi.pallets · 0 이면 세지 않는다)."""
        self.path = str(path)
        self.leftover_threshold_g = float(leftover_threshold_g)
        self.rack_slots = int(rack_slots or 0)              # 팔레트 한 장의 칸 수 — 칸을 다 채우고 끝난 회차 = 팔레트 1장(kpi.pallets)
        self._now = now
        self._lock = threading.Lock()                       # ROS 스레드(기록)와 웹 스레드(조회)가 같이 쓴다
        self._con = sqlite3.connect(self.path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        with self._lock:
            self._con.executescript(_SCHEMA)

    def close(self):
        """연결을 닫는다."""
        with self._lock:
            self._con.close()

    # ------------------------------------------------------------------ 적기
    def add_event(self, ev: dict, run_id=None, ts=None) -> int:
        """events 1줄 — 버린 잔반(waste_g) = 무게 전 − 후, 잔반 판정이 났고 건너뜀이 아닐 때만. 새 줄의 id 를 돌려준다."""
        before = float(ev.get('weight_before_g') or 0.0)
        after = float(ev.get('weight_after_g') or 0.0)
        waste = max(0.0, before - after) if (before > self.leftover_threshold_g and ev.get('result') != 'SKIPPED') else 0.0
        with self._lock:
            cur = self._con.execute(
                'INSERT INTO events (ts, run_id, kind, zone_id, rack_slot, result, code, attempts, weight_before_g, weight_after_g, duration_s, waste_g)'
                ' VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (ts or self._now(), run_id, ev.get('kind') or '', ev.get('zone_id') or '', ev.get('rack_slot') or '',
                 ev.get('result') or '', ev.get('code') or '', int(ev.get('attempts') or 0), before, after,
                 float(ev.get('duration_s') or 0.0), round(waste, 1)))
            self._con.commit()
            return int(cur.lastrowid)

    def start_run(self, ts=None) -> int:
        """runs 1줄(시작 시각) — run_id 를 돌려준다."""
        with self._lock:
            cur = self._con.execute('INSERT INTO runs (started_at) VALUES (?)', (ts or self._now(),))
            self._con.commit()
            return int(cur.lastrowid)

    def end_run(self, run_id, state: dict, ts=None):
        """회차 끝 — 완료·격리 수는 마지막 state 에서, 오류·건너뜀 수는 그 회차의 events 에서 센다."""
        with self._lock:
            n = self._con.execute('SELECT result, COUNT(*) c FROM events WHERE run_id=? GROUP BY result', (run_id,)).fetchall()
            by = {r['result']: r['c'] for r in n}
            self._con.execute('UPDATE runs SET ended_at=?, done_bowl=?, done_cup=?, isolated=?, errors=?, skipped=? WHERE id=?',
                              (ts or self._now(), int(state.get('done_bowl') or 0), int(state.get('done_cup') or 0),
                               int(state.get('isolated') or 0), int(by.get('ERROR', 0)), int(by.get('SKIPPED', 0)), run_id))
            self._con.commit()

    def open_pause(self, run_id, step, kind, code, ts=None) -> int:
        """pauses 1줄 시작(멈춘 단계·원인 갈래·코드) — pause_id 를 돌려준다."""
        with self._lock:
            cur = self._con.execute('INSERT INTO pauses (run_id, started_at, step, kind, code) VALUES (?,?,?,?,?)',
                                    (run_id, ts or self._now(), step or '', kind or '', code or ''))
            self._con.commit()
            return int(cur.lastrowid)

    def close_pause(self, pause_id, resolved, ts=None):
        """멈춤 끝 — 끝 시각·걸린 초·풀린 방법(resolved: resume / abort / nudge)을 적는다."""
        end = ts or self._now()
        with self._lock:
            row = self._con.execute('SELECT started_at FROM pauses WHERE id=?', (pause_id,)).fetchone()
            dur = None
            if row:
                try:
                    dur = round((datetime.fromisoformat(end) - datetime.fromisoformat(row['started_at'])).total_seconds(), 1)
                except ValueError:
                    dur = None
            self._con.execute('UPDATE pauses SET ended_at=?, duration_s=?, resolved=? WHERE id=?', (end, dur, resolved or '', pause_id))
            self._con.commit()

    def add_command(self, name, ok, message='', latency_ms=None, ts=None):
        """commands 1줄 — 버튼 1번과 flow 의 대답."""
        with self._lock:
            self._con.execute('INSERT INTO commands (ts, name, ok, message, latency_ms) VALUES (?,?,?,?,?)',
                              (ts or self._now(), name, 1 if ok else 0, message or '', latency_ms))
            self._con.commit()

    def add_replacement(self, item, note='', ts=None):
        """replacements 1줄 — 교체 완료. item 은 ITEMS 중 하나."""
        if item not in ITEMS:
            raise ValueError(f'모르는 교체 항목 {item!r} — {ITEMS} 중 하나')
        with self._lock:
            self._con.execute('INSERT INTO replacements (ts, item, note) VALUES (?,?,?)', (ts or self._now(), item, note or ''))
            self._con.commit()

    # ------------------------------------------------------------------ 읽기
    def _last_replacement(self, item):
        """item 의 마지막 교체 시각(없으면 '')."""
        row = self._con.execute('SELECT ts FROM replacements WHERE item=? ORDER BY id DESC LIMIT 1', (item,)).fetchone()
        return row['ts'] if row else ''

    def usage(self) -> dict:
        """마지막 교체 뒤의 사용량 — {'sponge': {'used': n, 'since': ts}, 'brush': …, 'soap': …, 'waste_bin': {'used_g': g, 'since': ts}}"""
        with self._lock:
            out = {}
            for item, where in (('sponge', "kind='BOWL' AND result='DONE'"), ('brush', "kind='CUP' AND result='DONE'"), ('soap', "result='DONE'")):
                since = self._last_replacement(item)
                n = self._con.execute(f'SELECT COUNT(*) c FROM events WHERE {where} AND ts>?', (since,)).fetchone()['c']
                out[item] = {'used': int(n), 'since': since}
            since = self._last_replacement('waste_bin')
            g = self._con.execute('SELECT COALESCE(SUM(waste_g),0) g FROM events WHERE ts>?', (since,)).fetchone()['g']
            out['waste_bin'] = {'used_g': round(float(g), 1), 'since': since}
            return out

    def recent_events(self, limit=50) -> list:
        """최근 events(최근 것이 앞) — 화면 이력용(stamp 초 단위 포함)."""
        with self._lock:
            rows = self._con.execute('SELECT * FROM events ORDER BY id DESC LIMIT ?', (int(limit),)).fetchall()
            return [self._event_view(r) for r in rows]

    @staticmethod
    def _event_view(r) -> dict:
        """events 줄 → 화면용 dict(ts 를 stamp 초로도 넣는다)."""
        d = dict(r)
        try:
            d['stamp'] = datetime.fromisoformat(d['ts']).timestamp()          # 화면(clock())이 초 단위 stamp 를 쓴다
        except (ValueError, TypeError):
            d['stamp'] = None
        return d

    def dump(self, table, limit=200) -> list:
        """표 내용(최근 것이 앞) — 터미널(hmi_db)·/api/db 용."""
        if table not in TABLES:
            raise ValueError(f'모르는 표 {table!r} — {TABLES} 중 하나')
        with self._lock:
            rows = self._con.execute(f'SELECT * FROM {table} ORDER BY id DESC LIMIT ?', (int(limit),)).fetchall()
            return [dict(r) for r in rows]

    def kpi(self, period='all', run_id=None) -> dict:
        """period: 'run'(run_id 또는 마지막 회차) · 'today' · 'all'. 값이 없으면 0/None."""
        with self._lock:
            if period == 'run':
                rid = run_id
                if rid is None:
                    row = self._con.execute('SELECT id FROM runs ORDER BY id DESC LIMIT 1').fetchone()
                    rid = row['id'] if row else None
                where, args = ('run_id=?', (rid,)) if rid is not None else ('0', ())
                pwhere, pargs = where, args
                rwhere, rargs = ('id=?', (rid,)) if rid is not None else ('0', ())
            elif period == 'today':
                day = self._now()[:10]
                where, args = ("substr(ts,1,10)=?", (day,))
                pwhere, pargs = ("substr(started_at,1,10)=?", (day,))
                rwhere, rargs = pwhere, pargs
            else:
                where, args, pwhere, pargs = '1', (), '1', ()
                rwhere, rargs = '1', ()
            q = lambda sql, a=(): self._con.execute(sql, a).fetchone()          # noqa: E731
            counts = {r['k']: r['c'] for r in self._con.execute(
                f"SELECT result || '_' || kind k, COUNT(*) c FROM events WHERE {where} GROUP BY k", args).fetchall()}
            total = q(f'SELECT COUNT(*) c FROM events WHERE {where}', args)['c']
            by_result = {r['result']: r['c'] for r in self._con.execute(
                f'SELECT result, COUNT(*) c FROM events WHERE {where} GROUP BY result', args).fetchall()}
            avg = {}
            for kind in ('BOWL', 'CUP'):
                r = q(f"SELECT AVG(duration_s) a FROM events WHERE {where} AND result='DONE' AND kind=? AND duration_s>0", args + (kind,))
                avg[kind] = round(float(r['a']), 1) if r and r['a'] is not None else None
            span = q(f'SELECT MIN(ts) a, MAX(ts) b FROM events WHERE {where}', args)
            per_hour = None
            if span and span['a'] and span['b']:
                try:
                    hours = (datetime.fromisoformat(span['b']) - datetime.fromisoformat(span['a'])).total_seconds() / 3600.0
                    done = by_result.get('DONE', 0)
                    if hours >= 5 / 60 and done:
                        per_hour = round(done / hours, 1)
                except ValueError:
                    per_hour = None
            bowls = q(f"SELECT COUNT(*) c FROM events WHERE {where} AND kind='BOWL' AND result!='SKIPPED'", args)['c']
            leftover = q(f"SELECT COUNT(*) c FROM events WHERE {where} AND kind='BOWL' AND waste_g>0", args)['c']   # 무게는 그릇만 잰다(E25)
            att = q(f"SELECT AVG(attempts) a FROM events WHERE {where} AND attempts>0", args)['a']
            pn = q(f'SELECT COUNT(*) c, COALESCE(SUM(duration_s),0) s FROM pauses WHERE {pwhere}', pargs)
            top = self._con.execute(f'SELECT kind, COUNT(*) c FROM pauses WHERE {pwhere} GROUP BY kind ORDER BY c DESC LIMIT 1', pargs).fetchone()
            runs = q(f"SELECT COUNT(*) c FROM runs WHERE {pwhere if period != 'run' else '1'}", pargs if period != 'run' else ())['c']
            # 처리한 팔레트 수 — 칸(rack_slots)을 다 채우고 끝난 회차만 센다(화면 '이번 팔레트' 카드의 누적과 같은 기준 · 껐다 켜도 남는다)
            pallets = (q(f"SELECT COUNT(*) c FROM runs WHERE {rwhere} AND ended_at IS NOT NULL AND done_bowl + done_cup >= ?", rargs + (self.rack_slots,))['c']
                       if self.rack_slots > 0 else 0)
            return {
                'period': period,
                'total': int(total),
                'done_bowl': int(counts.get('DONE_BOWL', 0)), 'done_cup': int(counts.get('DONE_CUP', 0)),
                'isolated': int(by_result.get('ISOLATED', 0)), 'error': int(by_result.get('ERROR', 0)), 'skipped': int(by_result.get('SKIPPED', 0)),
                'success_pct': round(100.0 * by_result.get('DONE', 0) / total, 1) if total else None,
                'avg_s_bowl': avg['BOWL'], 'avg_s_cup': avg['CUP'],
                'per_hour': per_hour,
                'pauses': int(pn['c']), 'pause_s': round(float(pn['s']), 1), 'pause_top': (top['kind'] if top else ''),
                'leftover_pct': round(100.0 * leftover / bowls, 1) if bowls else None,
                'avg_attempts': round(float(att), 2) if att is not None else None,
                'runs': int(runs), 'pallets': int(pallets),
                'waste_g': round(float(q(f'SELECT COALESCE(SUM(waste_g),0) g FROM events WHERE {where}', args)['g']), 1),
            }
