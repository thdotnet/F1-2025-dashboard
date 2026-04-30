"""
WebSocket Connection Manager - handles per-client queues and broadcasting.
"""

import asyncio
import logging
from typing import Any, Dict

logger = logging.getLogger("f1dashboard.websocket")


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""

    def __init__(self):
        self.active_connections: Dict[Any, asyncio.Queue] = {}
        self._writer_tasks: Dict[Any, asyncio.Task] = {}

    def connect(self, ws):
        queue = asyncio.Queue(maxsize=1)
        self.active_connections[ws] = queue
        self._writer_tasks[ws] = asyncio.create_task(self._writer(ws))
        logger.info("Client connected. Total: %d", len(self.active_connections))

    def disconnect(self, ws):
        self.active_connections.pop(ws, None)
        task = self._writer_tasks.pop(ws, None)
        if task and not task.done():
            task.cancel()
        logger.info("Client disconnected. Total: %d", len(self.active_connections))

    async def _writer(self, ws):
        """Per-client writer loop: sends latest message from queue."""
        queue = self.active_connections.get(ws)
        if not queue:
            return
        try:
            while ws in self.active_connections:
                message = await asyncio.wait_for(queue.get(), timeout=5.0)
                await ws.send(message)
        except asyncio.TimeoutError:
            # No messages for a while, check if still connected
            if ws in self.active_connections:
                asyncio.create_task(self._writer(ws))
        except asyncio.CancelledError:
            pass
        except Exception:
            self.disconnect(ws)

    async def broadcast(self, message: str):
        if not self.active_connections:
            return
        disconnected = []
        for ws, queue in list(self.active_connections.items()):
            try:
                # Drop old message if queue is full, replace with latest
                if queue.full():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                queue.put_nowait(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.active_connections.pop(ws, None)
