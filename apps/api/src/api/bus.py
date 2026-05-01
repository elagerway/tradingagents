"""In-process pub/sub bus with ring-buffered replay for SSE reconnect."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Any

BUFFER_SIZE = 200
QUEUE_MAX_SIZE = 512
SENTINEL: Any = object()


@dataclass(frozen=True)
class BusEvent:
    id: int
    data: dict[str, Any]


class Bus:
    """In-process pub/sub bound to a single run_id.

    Producers call publish() (cheap, sync). Subscribers call subscribe() to
    get an asyncio.Queue and consume events. close() ends all subscribers.
    The last BUFFER_SIZE events are kept for Last-Event-ID replay.
    """

    def __init__(self) -> None:
        self._buffer: deque[BusEvent] = deque(maxlen=BUFFER_SIZE)
        self._subscribers: list[asyncio.Queue] = []
        self._counter: int = 0
        self._closed: bool = False

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def publish(self, data: dict[str, Any]) -> BusEvent:
        if self._closed:
            raise RuntimeError("Bus is closed")
        self._counter += 1
        event = BusEvent(id=self._counter, data=data)
        self._buffer.append(event)
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # slow subscriber drops a message; ring buffer still has it
        return event

    def replay_since(self, last_event_id: int | None) -> list[BusEvent]:
        if last_event_id is None:
            return []
        return [e for e in self._buffer if e.id > last_event_id]

    def close(self) -> None:
        self._closed = True
        for q in list(self._subscribers):
            try:
                q.put_nowait(SENTINEL)
            except asyncio.QueueFull:
                pass

    @property
    def closed(self) -> bool:
        return self._closed


class BusRegistry:
    """Process-wide registry of Bus instances keyed by run_id."""

    def __init__(self) -> None:
        self._buses: dict[str, Bus] = {}

    def get_or_create(self, run_id: str) -> Bus:
        if run_id not in self._buses:
            self._buses[run_id] = Bus()
        return self._buses[run_id]

    def get(self, run_id: str) -> Bus | None:
        return self._buses.get(run_id)

    def drop(self, run_id: str) -> None:
        self._buses.pop(run_id, None)


# Process-wide singleton — wired into the FastAPI app at startup.
registry = BusRegistry()
