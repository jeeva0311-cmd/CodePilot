"""
Simple in-process event bus for SSE streaming.
The agent loop publishes events; the SSE endpoint reads them.
"""
import asyncio
import json
from typing import Dict, List, AsyncGenerator
from collections import deque


class EventBus:
    def __init__(self):
        # task_id → list of asyncio.Queue
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        # task_id → recent event buffer (last 100)
        self._history: Dict[str, deque] = {}

    def subscribe(self, task_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        if task_id not in self._subscribers:
            self._subscribers[task_id] = []
        self._subscribers[task_id].append(q)
        # Replay history
        for event in list(self._history.get(task_id, [])):
            q.put_nowait(event)
        return q

    def unsubscribe(self, task_id: str, q: asyncio.Queue):
        subs = self._subscribers.get(task_id, [])
        if q in subs:
            subs.remove(q)

    def publish(self, task_id: str, event_type: str, data: dict):
        payload = json.dumps({"type": event_type, "task_id": task_id, **data})
        # Buffer
        if task_id not in self._history:
            self._history[task_id] = deque(maxlen=200)
        self._history[task_id].append(payload)
        # Distribute to live subscribers
        for q in list(self._subscribers.get(task_id, [])):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    async def stream(self, task_id: str) -> AsyncGenerator[str, None]:
        q = self.subscribe(task_id)
        try:
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), timeout=25.0)
                    yield f"data: {item}\n\n"
                    # Stop streaming after terminal events
                    data = json.loads(item)
                    if data.get("type") in ("task_completed", "task_failed", "task_cancelled"):
                        break
                except asyncio.TimeoutError:
                    yield "data: {\"type\": \"heartbeat\"}\n\n"
        finally:
            self.unsubscribe(task_id, q)


event_bus = EventBus()
