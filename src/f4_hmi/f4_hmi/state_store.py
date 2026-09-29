# -*- coding: utf-8 -*-
""""마지막으로 들은 값" 보관함 — ROS 스레드가 넣고(put_*), 웹 스레드가 꺼낸다(snapshot). ROS·웹 부품을 쓰지 않는다.

    ROS 콜백 → put_state() · put_event() · put_weigh() · put_force() · put_gripping()      (값 저장만 — 콜백에서 다른 일은 하지 않는다)
    GET /api/state → snapshot()                                                (그 순간의 사본 — 락 안에서 복사한다)
    WS /ws/state   → subscribe(fn): 값이 들어올 때마다 fn(type, payload) — ROS 스레드에서 불린다. fn 은 넘겨주기만 하고 바로 돌아와야 한다.
연결 판정: /flow/state 가 hmi.disconnect_after_s 넘게 안 오면 connected = False (IRD §6 "2 s 이상 안 오면 연결 끊김").
"""
import threading
import time
from collections import deque

RECENT_EVENTS = 50              # 메모리에 들고 있는 최근 이벤트 수(화면 이력) — 전체는 SQLite(db.py)
RUNNING_STEPS = ('PICK', 'WEIGH', 'SHAKE', 'SEAT', 'SOAP', 'WIPE', 'RINSE', 'RACK', 'ISOLATE')   # 멈추기 직전 단계(paused_from)를 기억하는 데 쓴다
FORCE_FRESH_S = 0.5             # /cell/force 는 닦는 동안만 온다 → 이 시간 넘게 없으면 '지금은 닦지 않는다'(None)
WEIGH_FRESH_S = 30.0            # /flow/weigh 는 무게를 재는 동안만 온다 → 마지막 값이 이보다 오래됐으면 지난 측정이라 내보내지 않는다(None)


class StateStore:
    """마지막으로 들은 값의 보관함 — 락 하나로 ROS 스레드의 put_* 와 웹 스레드의 snapshot() 을 지킨다. 회차 누적(totals)도 여기서 센다."""

    def __init__(self, disconnect_after_s, clock=time.monotonic, rack_slots=0):
        """disconnect_after_s: 이만큼 /flow/state 가 안 오면 끊김 · clock: 시각 함수(시험용) ·
        rack_slots: 팔레트 한 장의 칸 수(params.yaml flow.rack_order 의 합) — 한 회차가 이만큼 채우고 끝나면 팔레트 1장 완료."""
        self._limit = float(disconnect_after_s)
        self._clock = clock
        self._lock = threading.Lock()
        self._state, self._state_at = None, None
        self._gripping = None
        self._force, self._force_at = None, None
        self._weigh, self._weigh_at = None, None            # 재는 중인 무게(표본 목록 · 중앙값) — /flow/weigh
        self._events = deque(maxlen=RECENT_EVENTS)
        self._count = 0                                     # 받은 /flow/state 수 (시험·진단용)
        # 누적 — flow 가 계획을 마치고 DONE 으로 넘어가는 순간 한 회차로 센다. HMI 를 켠 뒤부터(끄면 사라진다 · 저장은 SQLite · db.py)
        self._rack_slots = int(rack_slots)
        self._totals = {'runs': 0, 'pallets': 0, 'bowls': 0, 'cups': 0, 'isolated': 0}
        self._paused_from = None                            # 멈춤(PAUSED·ERROR) 직전에 하던 단계 — 멈춘 뒤에 연 화면(태블릿·새 탭)도 "닦기 단계에서 멈춤"을 안다
        self._listeners = []

    def subscribe(self, fn):
        """값이 들어올 때마다 fn(kind, payload) 를 부른다 — ROS 스레드에서 불리므로 fn 은 바로 돌아와야 한다."""
        self._listeners.append(fn)

    def preload_events(self, events):
        """켤 때 DB 의 최근 이력을 채운다(최근 것이 앞인 목록을 받는다). 화면이 켜자마자 지난 용기를 본다."""
        with self._lock:
            self._events.clear()
            for e in reversed(list(events)[:RECENT_EVENTS]):
                self._events.appendleft(dict(e))

    def _tell(self, kind, payload):
        """듣는 쪽 전부에 (kind, payload) 를 넘긴다."""
        for fn in list(self._listeners):                    # 락 밖에서 부른다 — 듣는 쪽이 snapshot() 을 불러도 막히지 않게
            fn(kind, payload)

    # ------------------------------------------------------------------ ROS 스레드
    def put_state(self, fields: dict):
        """/flow/state 1건 — 저장하고 'state' 로 알린다. step 이 DONE 으로 바뀌는 순간 회차 누적을 더한다."""
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
        """DONE 으로 넘어간 회차 1건을 totals 에 더한다 — 칸 수(rack_slots)를 다 채웠으면 팔레트 1장."""
        t = self._totals
        bowls, cups = int(s.get('done_bowl') or 0), int(s.get('done_cup') or 0)
        t['runs'] += 1
        t['bowls'] += bowls
        t['cups'] += cups
        t['isolated'] += int(s.get('isolated') or 0)
        if self._rack_slots and bowls + cups >= self._rack_slots:     # 칸을 다 채우고 끝났다 → 팔레트 1장
            t['pallets'] += 1

    def put_event(self, fields: dict):
        """/flow/event 1건 — 최근 목록 앞에 넣고 'event' 로 알린다."""
        with self._lock:
            self._events.appendleft(dict(fields))           # 최근 것이 앞
        self._tell('event', {'event': dict(fields)})

    def put_weigh(self, fields: dict):
        """/flow/weigh 1건 — 재는 중인 무게. 표본 하나를 읽을 때마다 온다(지금까지 읽은 값 전부가 들어 있다) → 저장하고 'weigh' 로 알린다."""
        w = self._weigh_view(fields)
        with self._lock:
            self._weigh, self._weigh_at = w, self._clock()
        self._tell('weigh', {'weigh': dict(w)})

    @staticmethod
    def _weigh_view(fields: dict) -> dict:
        """화면으로 보낼 모양 — 값은 0.1 g 으로 반올림한다(float32 의 긴 꼬리를 없앤다). median_g 는 다 쟀을 때만 값, 그 전에는 None."""
        done = bool(fields.get('done'))
        return {
            'kind': str(fields.get('kind') or ''),
            'target_n': int(fields.get('target_n') or 0),
            'samples_g': [round(float(v), 1) for v in (fields.get('samples_g') or [])],
            'done': done,
            'median_g': round(float(fields.get('median_g') or 0.0), 1) if done else None,
            'stamp': fields.get('stamp'),
        }

    def put_force(self, newton: float):
        """/cell/force 1건 — 값과 시각을 저장하고 'force' 로 알린다."""
        with self._lock:
            self._force, self._force_at = float(newton), self._clock()
        self._tell('force', {'n': round(float(newton), 2)})

    def put_gripping(self, value: bool):
        """/cell/gripping 1건 — 값이 바뀔 때만 'gripping' 으로 알린다."""
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
        """그 순간의 사본(dict) — 락 안에서 복사한다.
            connected: /flow/state 를 disconnect_after_s 안에 받았는가 · age_s: 마지막 state 뒤 지난 초(없으면 None) · received: 받은 state 수
            state: 마지막 FlowState 필드(없으면 None) · gripping: 마지막 /cell/gripping(없으면 None) · force_n: FORCE_FRESH_S 안에 온 힘(N), 아니면 None
            weigh: WEIGH_FRESH_S 안에 온 무게 측정({kind, target_n, samples_g, done, median_g, stamp, age_s}), 아니면 None
            events: 최근 이벤트 목록(최근 것이 앞 · RECENT_EVENTS 개) · totals: 누적(runs·pallets·bowls·cups·isolated) + rack_slots"""
        with self._lock:
            now = self._clock()
            age = None if self._state_at is None else now - self._state_at
            fresh = self._force_at is not None and now - self._force_at <= FORCE_FRESH_S
            weigh_age = None if self._weigh_at is None else now - self._weigh_at
            weigh = None
            if weigh_age is not None and weigh_age <= WEIGH_FRESH_S:
                weigh = {**self._weigh, 'samples_g': list(self._weigh['samples_g']), 'age_s': round(weigh_age, 2)}
            return {
                'connected': age is not None and age <= self._limit,
                'age_s': None if age is None else round(age, 2),
                'received': self._count,
                'state': None if self._state is None else dict(self._state),
                'gripping': self._gripping,
                'force_n': round(self._force, 2) if fresh else None,
                'weigh': weigh,
                'events': [dict(e) for e in self._events],
                'totals': {**self._totals, 'rack_slots': self._rack_slots},
                'paused_from': self._paused_from,
            }
