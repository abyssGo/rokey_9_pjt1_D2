# -*- coding: utf-8 -*-
"""기록자 — 보관함(StateStore)이 알려 주는 값을 듣고 DB 에 적는다. 잔반통이 차면 flow 에 일시 정지를 보낸다.

    state  : 단계가 바뀔 때만 본다 — IDLE→작업 = 회차 시작(runs) · DONE = 회차 끝 · PAUSED 들어감/나감 = 멈춤 1줄(pauses)
    event  : 용기 1개 끝남 → events 1줄 → 잔반통 누적을 확인 → 한도(hmi.waste_bin_limit_g)에 닿으면 한 번만 stop(일시 정지)
    버튼   : app 이 record_command 로 알려 준다(commands) — 멈춤이 어떻게 풀렸는지(재개/중단)도 여기서 안다
주의: store 의 콜백은 ROS 스레드에서 온다 — 여기서 flow 서비스를 직접 부르면(같은 스레드) 막힐 수 있어 stop 은 다른 스레드로 보낸다.
"""
import threading

# 멈춤 원인 갈래 — 화면(derive.js pauseKind)과 같은 규칙
_KIND_BY_CODE = {'ROBOT_ERROR': 'robot_error', 'TOOL_LOST': 'tool_lost', 'TOOL_FAIL': 'tool_fail',
                 'LEFTOVER_REMAIN': 'leftover', 'GRIP_FAIL': 'grip', 'RACK_FULL': 'rack_full'}
_WORKING_END = ('IDLE', 'DONE', None, '')


def pause_kind(state: dict) -> str:
    """state → 멈춤 원인 갈래 — message 에 '케이블' 이 있으면 cable, 아니면 last_code 로(모르면 operator)."""
    if '케이블' in str(state.get('message') or ''):
        return 'cable'
    return _KIND_BY_CODE.get(str(state.get('last_code') or ''), 'operator')


class Recorder:
    """StateStore 콜백을 받아 DB 에 적고, 잔반통 누적이 한도에 닿으면 stop 을 보낸다. 진행 중인 회차(run_id)·멈춤(pause_id)을 들고 있다."""

    def __init__(self, db, command=None, waste_limit_g=50000.0, log=None):
        """db: HmiDb · command(name): 버튼을 flow 로 보내는 함수(RosLink.call) · waste_limit_g: 잔반통 한도(g) · log: rclpy 로거(없으면 print)."""
        self.db = db
        self.command = command
        self.waste_limit_g = float(waste_limit_g)
        self.log = log
        self.run_id = None
        self.pause_id = None
        self._prev_step = None
        self._last_work = None                          # 마지막으로 본 작업 중 상태 — DONE 없이 끝난 회차(flow 재시작·Ctrl+C)를 이 값으로 닫는다
        self._cmd_in_pause = None
        self._lock = threading.Lock()
        self.waste_full = self.db.usage()['waste_bin']['used_g'] >= self.waste_limit_g   # 껐다 켜도 "가득" 은 이어진다(교체 완료 전까지)

    # ------------------------------------------------------------------ store 콜백(ROS 스레드)
    def on_store(self, kind, payload):
        """StateStore 가 부르는 콜백(ROS 스레드) — state·event 만 본다. 기록 예외는 삼키고 경고만 남긴다."""
        try:
            if kind == 'state':
                self._on_state(payload.get('state') or {})
            elif kind == 'event':
                self._on_event(payload.get('event') or {})
        except Exception as e:                              # noqa: BLE001 — 기록이 터져도 화면·로봇은 계속
            self._warn(f'기록 실패 — {e!r}')

    def _on_state(self, s):
        """step 이 바뀔 때만 — 회차 시작/끝(runs) · PAUSED 들어감/나감(pauses)을 적는다."""
        step = s.get('step')
        prev = self._prev_step
        if step == prev:
            return
        with self._lock:
            if step not in _WORKING_END:
                self._last_work = s
            elif step != 'DONE' and prev not in _WORKING_END and self.run_id is not None:   # 작업 중 → IDLE: flow 가 DONE 없이 끝났다(재시작) — 회차를 닫아 다음 회차와 섞이지 않게
                self.db.end_run(self.run_id, self._last_work or s)
                self.run_id = None
            if prev in _WORKING_END and step not in _WORKING_END and self.run_id is None:
                self.run_id = self.db.start_run()
            if step == 'PAUSED' and self.pause_id is None:
                kind = pause_kind(s)
                if kind == 'operator' and self.waste_full:       # 우리가 잔반통 때문에 보낸 일시 정지 — 화면(derive.alarm)과 같은 규칙
                    kind = 'waste_bin'
                self.pause_id = self.db.open_pause(self.run_id, prev, kind, s.get('last_code'))
                self._cmd_in_pause = None
            elif prev == 'PAUSED' and step != 'PAUSED' and self.pause_id is not None:
                resolved = self._cmd_in_pause or ('abort' if step == 'ISOLATE' else 'restart' if step in _WORKING_END else 'nudge')
                self.db.close_pause(self.pause_id, resolved)
                self.pause_id = None
            if step == 'DONE' and self.run_id is not None:
                self.db.end_run(self.run_id, s)
                self.run_id = None
            self._prev_step = step

    def _on_event(self, ev):
        """용기 1개 끝 → events 1줄 → 잔반통 누적 확인."""
        with self._lock:
            self.db.add_event(ev, self.run_id)
        self._check_waste()

    # ------------------------------------------------------------------ 버튼(웹 스레드)
    def record_command(self, name, result: dict):
        """버튼 1번 → commands 1줄. 멈춤 중에 성공한 resume/abort 는 멈춤이 풀린 방법으로 기억한다."""
        r = result or {}
        with self._lock:
            self.db.add_command(name, bool(r.get('ok')), str(r.get('message') or ''), r.get('latency_ms'))
            if self.pause_id is not None and name in ('resume', 'abort') and r.get('ok'):
                self._cmd_in_pause = name

    def replace(self, item, note=''):
        """교체 완료 기록 — 잔반통이면 '가득' 을 푼다. 새 사용량을 돌려준다."""
        with self._lock:
            self.db.add_replacement(item, note)
            if item == 'waste_bin':
                self.waste_full = False
        return self.usage_view()

    # ------------------------------------------------------------------ 읽기(웹 스레드)
    def usage_view(self) -> dict:
        """마지막 교체 뒤 사용량(db.usage)."""
        return self.db.usage()

    def notices(self) -> dict:
        """화면 알림 — 잔반통 가득 여부와 한도."""
        return {'waste_full': bool(self.waste_full), 'waste_limit_g': self.waste_limit_g}

    def kpi(self, period='all') -> dict:
        """period 별 KPI — run 이면 지금 진행 중인 회차(run_id)."""
        rid = self.run_id if period == 'run' else None
        return self.db.kpi(period, run_id=rid)

    # ------------------------------------------------------------------ 잔반통
    def _check_waste(self):
        """잔반통 누적이 한도에 닿으면 한 번만 '가득' 으로 바꾸고 다른 스레드에서 stop 을 보낸다."""
        used = self.db.usage()['waste_bin']['used_g']
        if used < self.waste_limit_g or self.waste_full:
            return
        self.waste_full = True
        self._warn(f'잔반통 누적 {used:.0f} g ≥ 한도 {self.waste_limit_g:.0f} g — 일시 정지를 보낸다(교체 뒤 교체 완료 → 재개)')
        if self.command is not None:
            threading.Thread(target=self._send_stop, name='waste-stop', daemon=True).start()

    def _send_stop(self):
        """(별도 스레드) /flow/stop 을 보내고 commands 에 '[잔반통 가득]' 표시를 붙여 적는다."""
        try:
            r = self.command('stop')
            self.record_command('stop', dict(r or {}, message='[잔반통 가득] ' + str((r or {}).get('message') or '')))
        except Exception as e:                              # noqa: BLE001
            self._warn(f'잔반통 가득 — 일시 정지 요청 실패: {e!r}')

    def _warn(self, msg):
        """로거가 있으면 warn, 없으면 print."""
        if self.log is not None:
            try:
                self.log.warn(msg)
                return
            except Exception:                               # noqa: BLE001
                pass
        print(f'[recorder] {msg}')
