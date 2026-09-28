# -*- coding: utf-8 -*-
""""마지막으로 들은 값" 보관함 — ROS 스레드가 넣고(put_*), 웹 스레드가 꺼낸다(snapshot). ROS·웹 부품을 쓰지 않는다.

    ROS 콜백 → put_state() · put_event() · put_force() · put_gripping()      (값 저장만 — 콜백에서 다른 일은 하지 않는다)
    GET /api/state → snapshot()                                                (그 순간의 사본 — 락 안에서 복사한다)
    WS /ws/state   → subscribe(fn): 값이 들어올 때마다 fn(type, payload) — **ROS 스레드에서** 불린다(F4-02). fn 은 넘겨주기만 하고 바로 돌아와야 한다.
연결 판정: /flow/state 가 hmi.disconnect_after_s 넘게 안 오면 connected = False (IRD §6 "2 s 이상 안 오면 연결 끊김").
"""
import threading
import time
from collections import deque

RECENT_EVENTS = 50              # 메모리에 들고 있는 최근 이벤트 수(화면 이력) — 전체는 SQLite(F4-04 · db.py)
RUNNING_STEPS = ('PICK', 'WEIGH', 'SHAKE', 'SEAT', 'SOAP', 'WIPE', 'RINSE', 'RACK', 'ISOLATE')   # 🆕 9/28 멈추기 직전 단계(paused_from)를 기억하는 데 쓴다
FORCE_FRESH_S = 0.5             # /cell/force 는 닦는 동안만 온다 → 이 시간 넘게 없으면 '지금은 닦지 않는다'(None)


class StateStore:
    def __init__(self, disconnect_after_s, clock=time.monotonic, rack_slots=0):
        """rack_slots: 팔레트 한 장의 칸 수(params.yaml flow.rack_order 의 합) — 한 회차가 이만큼 채우고 끝나면 팔레트 1장 완료."""
        self._limit = float(disconnect_after_s)
        self._clock = clock
        self._lock = threading.Lock()
        self._state, self._state_at = None, None
        self._gripping = None
        self._force, self._force_at = None, None
        self._events = deque(maxlen=RECENT_EVENTS)
        self._count = 0                                     # 받은 /flow/state 수 (시험·진단용)
        # 누적 — flow 가 계획을 마치고 DONE 으로 넘어가는 순간 한 회차로 센다. HMI 를 켠 뒤부터(끄면 사라진다 · 저장은 F4-04 SQLite)
        self._rack_slots = int(rack_slots)
        self._totals = {'runs': 0, 'pallets': 0, 'bowls': 0, 'cups': 0, 'isolated': 0}
        self._paused_from = None                            # 🆕 9/28 멈춤(PAUSED·ERROR) 직전에 하던 단계 — 멈춘 뒤에 연 화면(태블릿·새 탭)도 "닦기 단계에서 멈춤"을 안다
        self._listeners = []

    def subscribe(self, fn):
        self._listeners.append(fn)

    def preload_events(self, events):
        """🆕 F4-04 — 켤 때 DB 의 최근 이력을 채운다(최근 것이 앞인 목록을 받는다). 화면이 켜자마자 지난 용기를 본다."""
        with self._lock:
            self._events.clear()
            for e in reversed(list(events)[:RECENT_EVENTS]):
                self._events.appendleft(dict(e))

    def _tell(self, kind, payload):
        for fn in list(self._listeners):                    # 락 밖에서 부른다 — 듣는 쪽이 snapshot() 을 불러도 막히지 않게
            fn(kind, payload)

    # ------------------------------------------------------------------ ROS 스레드
    def put_state(self, fields: dict):
        with self._lock:
            before = self._state.get('step') if self._state else None
            if before is not None and before != 'DONE' and fields.get('step') == 'DONE':   # 회차가 끝났다(처음 받은 값이 DONE 이면 세지 않는다 — 못 본 회차)
                self._count_run(fields)
            if fields.get('step') in ('PAUSED', 'ERROR'):
                if before in RUNNING_STEPS:
                    self._paused_from = before
            else:
                self._paused_from = None
            self._state, self._state_at = dict(fields), self._clock()
            self._count += 1
        self._tell('state', self.live())

    def _count_run(self, s):
        t = self._totals
        bowls, cups = int(s.get('done_bowl') or 0), int(s.get('done_cup') or 0)
        t['runs'] += 1
        t['bowls'] += bowls
        t['cups'] += cups
        t['isolated'] += int(s.get('isolated') or 0)
        if self._rack_slots and bowls + cups >= self._rack_slots:     # 칸을 다 채우고 끝났다 → 팔레트 1장
            t['pallets'] += 1

    def put_event(self, fields: dict):
        with self._lock:
            self._events.appendleft(dict(fields))           # 최근 것이 앞
        self._tell('event', {'event': dict(fields)})

    def put_force(self, newton: float):
        with self._lock:
            self._force, self._force_at = float(newton), self._clock()
        self._tell('force', {'n': round(float(newton), 2)})

    def put_gripping(self, value: bool):
        with self._lock:
            changed = self._gripping != bool(value)
            self._gripping = bool(value)
        if changed:                                         # 2 Hz 로 계속 오지만 화면에는 바뀔 때만 알린다
            self._tell('gripping', {'value': bool(value)})

    # ------------------------------------------------------------------ 웹 스레드
    def live(self) -> dict:
        """자주 바뀌는 값만 — WS 의 type=state 몸통. (snapshot 에서 최근 이벤트 목록을 뺀 것)"""
        snap = self.snapshot()
        snap.pop('events')
        return snap

    def snapshot(self) -> dict:
        with self._lock:
            now = self._clock()
            age = None if self._state_at is None else now - self._state_at
            fresh = self._force_at is not None and now - self._force_at <= FORCE_FRESH_S
            return {
                'connected': age is not None and age <= self._limit,
                'age_s': None if age is None else round(age, 2),
                'received': self._count,
                'state': None if self._state is None else dict(self._state),
                'gripping': self._gripping,
                'force_n': round(self._force, 2) if fresh else None,
                'events': [dict(e) for e in self._events],
                'totals': {**self._totals, 'rack_slots': self._rack_slots},
                'paused_from': self._paused_from,
            }
