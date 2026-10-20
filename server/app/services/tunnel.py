"""Broker for the worker inference tunnel.

Workers keep one outbound WebSocket to the control plane. The gateway sends a ``request`` frame for each
customer request; the worker forwards it to its own managed runtime and streams ``response_start``,
``chunk`` and ``response_end`` (or ``error``) frames back. Nodes never accept inbound connections and
customers never learn node addresses.

The registry is in-process. With several API replicas, a request must reach the replica holding the
worker's socket; that needs a shared router (e.g. Redis pub/sub) and is not implemented yet.
"""

import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

MAX_FRAME_BYTES = 1024 * 1024


class NodeUnavailable(Exception):  # noqa: N818
    pass


@dataclass
class WorkerConnection:
    node_id: uuid.UUID
    send_json: Callable[[dict], Awaitable[Any]]
    close: Callable[[], Awaitable[Any]]
    pending: dict[str, asyncio.Queue] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def send(self, frame: dict) -> None:
        async with self.lock:
            await self.send_json(frame)

    def dispatch(self, frame: dict) -> None:
        queue = self.pending.get(str(frame.get("id")))
        if queue is not None:
            queue.put_nowait(frame)

    def fail_all(self, message: str) -> None:
        for queue in self.pending.values():
            queue.put_nowait({"type": "error", "code": "node_disconnected", "message": message})


class TunnelBroker:
    def __init__(self):
        self._connections: dict[uuid.UUID, WorkerConnection] = {}

    def is_connected(self, node_id) -> bool:
        return node_id in self._connections

    async def register(self, conn: WorkerConnection) -> None:
        old = self._connections.get(conn.node_id)
        self._connections[conn.node_id] = conn
        if old is not None and old is not conn:
            old.fail_all("Worker reconnected")
            try:
                await old.close()
            except Exception:  # noqa: BLE001
                pass

    def unregister(self, conn: WorkerConnection) -> None:
        if self._connections.get(conn.node_id) is conn:
            del self._connections[conn.node_id]
        conn.fail_all("Worker disconnected")

    async def open_request(self, node_id, frame: dict) -> tuple[WorkerConnection, str, asyncio.Queue]:
        conn = self._connections.get(node_id)
        if conn is None:
            raise NodeUnavailable("Node is not connected")
        request_id = frame["id"]
        queue: asyncio.Queue = asyncio.Queue()
        conn.pending[request_id] = queue
        try:
            await conn.send(frame)
        except Exception as exc:
            conn.pending.pop(request_id, None)
            raise NodeUnavailable("Could not reach node") from exc
        return conn, request_id, queue

    @staticmethod
    def close_request(conn: WorkerConnection, request_id: str) -> None:
        conn.pending.pop(request_id, None)

    async def handle_messages(self, conn: WorkerConnection, receive_text: Callable[[], Awaitable[str]]) -> None:
        """Read frames from a worker until it disconnects."""
        while True:
            text = await receive_text()
            if len(text) > MAX_FRAME_BYTES:
                logger.warning("Dropping oversized tunnel frame from node %s", conn.node_id)
                continue
            try:
                frame = json.loads(text)
            except ValueError:
                continue
            if isinstance(frame, dict) and frame.get("type") in ("response_start", "chunk", "response_end", "error"):
                conn.dispatch(frame)


broker = TunnelBroker()
