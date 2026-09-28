# -*- coding: utf-8 -*-
"""WebSocket 전화 교환기 — ROS 스레드에서 들어온 값을 열려 있는 모든 브라우저에 밀어 준다.

    ROS 스레드: store.put_*() → Hub.from_ros(type, payload) → loop.call_soon_threadsafe(…)      (스레드를 건너가는 유일한 자리)
    웹 루프   : 브라우저마다 큐 1개 → /ws/state 핸들러가 큐에서 꺼내 보낸다
브라우저가 느려 큐가 차면 그 브라우저의 오래된 것부터 버린다(힘 값 10 Hz 가 밀려도 최신 상태가 중요하다). ROS 쪽은 절대 기다리지 않는다.
"""
import asyncio

QUEUE_MAX = 200


class Hub:
    """브라우저(WebSocket)마다 큐 1개를 두고, ROS 스레드가 준 메시지를 웹 루프로 건네 전부에 뿌린다."""

    def __init__(self):
        self.loop = None                    # 웹 서버의 이벤트 루프 — 첫 브라우저가 붙을 때 잡는다
        self._queues = set()

    # ------------------------------------------------------------------ 웹 루프에서
    def join(self) -> asyncio.Queue:
        """브라우저가 붙었다 — 그 브라우저 전용 큐를 만들어 돌려준다(웹 루프에서 부른다 · 루프도 여기서 잡는다)."""
        self.loop = asyncio.get_running_loop()
        q = asyncio.Queue(maxsize=QUEUE_MAX)
        self._queues.add(q)
        return q

    def leave(self, q):
        """브라우저가 떠났다 — 큐를 뺀다."""
        self._queues.discard(q)

    @property
    def clients(self) -> int:
        """붙어 있는 브라우저 수."""
        return len(self._queues)

    def _fan_out(self, message):
        """(웹 루프) 모든 큐에 넣는다 — 찬 큐는 가장 오래된 것 하나를 버리고 넣는다."""
        for q in list(self._queues):
            if q.full():
                q.get_nowait()              # 오래된 것 하나를 버린다
            q.put_nowait(message)

    # ------------------------------------------------------------------ ROS 스레드에서
    def from_ros(self, kind, payload):
        """(ROS 스레드) {'type': kind, **payload} 를 웹 루프로 넘긴다. 브라우저가 없으면 아무것도 안 하고, 서버가 닫히는 중이면 버린다."""
        if self.loop is None or not self._queues:
            return                          # 붙어 있는 브라우저가 없다
        try:
            self.loop.call_soon_threadsafe(self._fan_out, {'type': kind, **payload})
        except RuntimeError:                # 서버가 꺼지는 중(루프가 닫혔다)
            pass
