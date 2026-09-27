# -*- coding: utf-8 -*-
"""기록자(F4-04·05) — 보관함(StateStore)이 알려 주는 값을 듣고 DB 에 적는다. 잔반통이 차면 flow 에 일시 정지를 보낸다(황인재 9/27).

    state  : 단계가 바뀔 때만 본다 — IDLE→작업 = 회차 시작(runs) · DONE = 회차 끝 · PAUSED 들어감/나감 = 멈춤 1줄(pauses)
    event  : 용기 1개 끝남 → events 1줄 → 잔반통 누적을 확인 → 한도(hmi.waste_bin_limit_g)에 닿으면 **한 번만** stop(일시 정지)
    버튼   : app 이 record_command 로 알려 준다(commands) — 멈춤이 어떻게 풀렸는지(재개/중단)도 여기서 안다
🚨 store 의 콜백은 ROS 스레드에서 온다 — 여기서 flow 서비스를 직접 부르면(같은 스레드) 막힐 수 있어 stop 은 **다른 스레드**로 보낸다.
"""
import threading

# 멈춤 원인 갈래 — 화면(derive.js pauseKind)과 같은 규칙
_KIND_BY_CODE = {'ROBOT_ERROR': 'robot_error', 'TOOL_LOST': 'tool_lost', 'TOOL_FAIL': 'tool_fail',
                 'LEFTOVER_REMAIN': 'leftover', 'GRIP_FAIL': 'grip', 'RACK_FULL': 'rack_full'}
_WORKING_END = ('IDLE', 'DONE', None, '')


def pause_kind(state: dict) -> str:
    if '케이블' in str(state.get('message') or ''):
        return 'cable'
    return _KIND_BY_CODE.get(str(state.get('last_code') or ''), 'operator')


class Recorder:
    def __init__(self, db, command=None, waste_limit_g=50000.0, log=None):
        self.db = db
        self.command = command
        self.waste_limit_g = float(waste_limit_g)
        self.log = log
        self.run_id = None
        self.pause_id = None
        self._prev_step = None
        self._cmd_in_pause = None
        self._lock = threading.Lock()
        self.waste_full = self.db.usage()['waste_bin']['used_g'] >= self.waste_limit_g   # 껐다 켜도 "가득" 은 이어진다(교체 완료 전까지)

    # ------------------------------------------------------------------ store 콜백(ROS 스레드)
    def on_store(self, kind, payload):
        try:
            if kind == 'state':
                self._on_state(payload.get('state') or {})
            elif kind == 'event':
                self._on_event(payload.get('event') or {})
        except Exception as e:                              # noqa: BLE001 — 기록이 터져도 화면·로봇은 계속
            self._warn(f'기록 실패 — {e!r}')

    def _on_state(self, s):
        step = s.get('step')
        prev = self._prev_step
        if step == prev:
            return
        with self._lock:
            if prev in _WORKING_END and step not in _WORKING_END and self.run_id is None:
                self.run_id = self.db.start_run()
            if step == 'PAUSED' and self.pause_id is None:
                kind = pause_kind(s)
                if kind == 'operator' and self.waste_full:       # 우리가 잔반통 때문에 보낸 일시 정지 — 화면(derive.alarm)과 같은 규칙
                    kind = 'waste_bin'
                self.pause_id = self.db.open_pause(self.run_id, prev, kind, s.get('last_code'))
                self._cmd_in_pause = None
            elif prev == 'PAUSED' and step != 'PAUSED' and self.pause_id is not None:
                resolved = self._cmd_in_pause or ('abort' if step == 'ISOLATE' else 'nudge')
                self.db.close_pause(self.pause_id, resolved)
                self.pause_id = None
            if step == 'DONE' and self.run_id is not None:
                self.db.end_run(self.run_id, s)
                self.run_id = None
            self._prev_step = step

    def _on_event(self, ev):
        with self._lock:
            self.db.add_event(ev, self.run_id)
        self._check_waste()

    # ------------------------------------------------------------------ 버튼(웹 스레드)
    def record_command(self, name, result: dict):
        r = result or {}
        with self._lock:
            self.db.add_command(name, bool(r.get('ok')), str(r.get('message') or ''), r.get('latency_ms'))
            if self.pause_id is not None and name in ('resume', 'abort') and r.get('ok'):
                self._cmd_in_pause = name

    def replace(self, item, note=''):
        with self._lock:
            self.db.add_replacement(item, note)
            if item == 'waste_bin':
                self.waste_full = False
        return self.usage_view()

    # ------------------------------------------------------------------ 읽기(웹 스레드)
    def usage_view(self) -> dict:
        return self.db.usage()

    def notices(self) -> dict:
        return {'waste_full': bool(self.waste_full), 'waste_limit_g': self.waste_limit_g}

    def kpi(self, period='all') -> dict:
        rid = self.run_id if period == 'run' else None
        return self.db.kpi(period, run_id=rid)

    # ------------------------------------------------------------------ 잔반통
    def _check_waste(self):
        used = self.db.usage()['waste_bin']['used_g']
        if used < self.waste_limit_g or self.waste_full:
            return
        self.waste_full = True
        self._warn(f'잔반통 누적 {used:.0f} g ≥ 한도 {self.waste_limit_g:.0f} g — 일시 정지를 보낸다(교체 뒤 교체 완료 → 재개)')
        if self.command is not None:
            threading.Thread(target=self._send_stop, name='waste-stop', daemon=True).start()

    def _send_stop(self):
        try:
            r = self.command('stop')
            self.record_command('stop', dict(r or {}, message='[잔반통 가득] ' + str((r or {}).get('message') or '')))
        except Exception as e:                              # noqa: BLE001
            self._warn(f'잔반통 가득 — 일시 정지 요청 실패: {e!r}')

    def _warn(self, msg):
        if self.log is not None:
            try:
                self.log.warn(msg)
                return
            except Exception:                               # noqa: BLE001
                pass
        print(f'[recorder] {msg}')
