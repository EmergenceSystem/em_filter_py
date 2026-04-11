from __future__ import annotations
import json
import logging
import os
import threading
import time
from typing import Any, Callable

import websocket

from .config import DiscoNode

logger = logging.getLogger(__name__)

# handle(body, memory) -> (result, new_memory)
HandleFn = Callable[[str, dict], tuple[Any, dict]]


class Connection(threading.Thread):
    """Persistent WebSocket connection to one em_disco node.

    Mirrors the Erlang em_filter_server gen_server:
    - one process (here: thread) per disco node
    - memory persists across reconnections (reset only if thread is killed)
    - reconnects automatically with a fixed delay
    """

    def __init__(
        self,
        name: str,
        node: DiscoNode,
        handler: HandleFn,
        capabilities: list[str],
        jwt_token: str | None,
        reconnect_ms: int,
    ) -> None:
        super().__init__(daemon=True, name=f"{name}@{node.host}:{node.port}")
        self._agent_name = name
        self._node = node
        self._handler = handler
        self._capabilities = capabilities
        self._jwt_token = jwt_token
        self._reconnect_ms = reconnect_ms
        # Memory persists across reconnections within this thread's lifetime.
        self._memory: dict = {}

    def run(self) -> None:
        delay = self._reconnect_ms / 1000.0
        while True:
            try:
                self._connect_once()
                logger.info("[em_filter] %s disconnected from %s:%d — reconnecting",
                            self._agent_name, self._node.host, self._node.port)
            except Exception as exc:
                logger.warning("[em_filter] %s connection error (%s:%d): %s",
                               self._agent_name, self._node.host, self._node.port, exc)
            time.sleep(delay)

    def _connect_once(self) -> None:
        url = self._ws_url()
        logger.info("[em_filter] %s connecting to %s", self._agent_name, url)

        ws = websocket.WebSocket()
        ws.connect(url)

        # Step 1 — register
        ws.send(json.dumps({"action": "register", "name": self._agent_name}))
        # Step 2 — agent_hello (always sent, even with empty capabilities)
        ws.send(json.dumps({"action": "agent_hello",
                            "capabilities": self._capabilities}))

        logger.info("[em_filter] %s registered — entering message loop",
                    self._agent_name)

        while True:
            raw = ws.recv()
            if not raw:
                break
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("[em_filter] %s invalid JSON frame, skipping",
                               self._agent_name)
                continue

            if msg.get("action") != "query":
                # registered / agent_registered acks are silently ignored.
                continue

            query_id = msg.get("id")
            if not query_id:
                logger.warning("[em_filter] %s query frame missing 'id', skipping",
                               self._agent_name)
                continue

            body = msg.get("body", "").strip()
            logger.info("[em_filter] %s query %s: %s",
                        self._agent_name, query_id, body)

            try:
                result, self._memory = self._handler(body, self._memory)
            except Exception as exc:
                logger.error("[em_filter] %s handler error for query %s: %s",
                             self._agent_name, query_id, exc)
                result = None

            ws.send(json.dumps({
                "action": "result",
                "id": query_id,
                "data": result,
            }))

        ws.close()

    def _ws_url(self) -> str:
        scheme = "wss" if self._node.tls else "ws"
        base = f"{scheme}://{self._node.host}:{self._node.port}/ws"
        if self._jwt_token:
            return f"{base}?token={self._jwt_token}"
        return base
