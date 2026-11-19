"""
In-process approval signalling — allows the agent loop (running in a thread)
to block on asyncio.Event and wake up when the user decides.
"""
import asyncio
import threading
from typing import Dict, Tuple


class ApprovalService:
    def __init__(self):
        self._lock = threading.Lock()
        # approval_id → (threading.Event, decision_holder)
        self._pending: Dict[str, Tuple[threading.Event, list]] = {}

    def register(self, approval_id: str):
        """Called by the agent loop before waiting for a decision."""
        event = threading.Event()
        holder = [None]  # mutable list so signal() can write into it
        with self._lock:
            self._pending[approval_id] = (event, holder)

    def wait(self, approval_id: str, timeout: float = 300.0) -> str:
        """
        Block until the user decides (or timeout).
        Returns 'approved', 'rejected', or 'timeout'.
        """
        with self._lock:
            entry = self._pending.get(approval_id)
        if not entry:
            return "timeout"
        event, holder = entry
        fired = event.wait(timeout=timeout)
        with self._lock:
            self._pending.pop(approval_id, None)
        if not fired:
            return "timeout"
        return holder[0] or "rejected"

    def signal(self, approval_id: str, decision: str):
        """Called by the API endpoint when the user decides."""
        with self._lock:
            entry = self._pending.get(approval_id)
        if entry:
            event, holder = entry
            holder[0] = decision
            event.set()


approval_service = ApprovalService()
