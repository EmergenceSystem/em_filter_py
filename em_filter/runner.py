from __future__ import annotations
import os
from typing import Any

from .config import AgentConfig
from .connection import Connection, HandleFn


class FilterRunner:
    """Starts one Connection thread per resolved disco node.

    The handler can be:
    - a plain callable: ``handle(body: str, memory: dict) -> (result, new_memory)``
    - an object with a ``handle(self, body, memory)`` method and optional
      ``capabilities() -> list[str]`` method.

    This mirrors em_filter:start_agent/3 — one call starts all node connections.
    """

    def __init__(
        self,
        name: str,
        handler: Any,
        config: AgentConfig | None = None,
    ) -> None:
        self._name = name
        self._config = config or AgentConfig()

        if hasattr(handler, "handle"):
            obj = handler
            self._handler_fn: HandleFn = lambda body, mem: obj.handle(body, mem)
            caps_fn = getattr(obj, "capabilities", None)
            self._capabilities: list[str] = caps_fn() if callable(caps_fn) else ["search", "query"]
        else:
            self._handler_fn = handler
            self._capabilities = ["search", "query"]

    def run(self) -> None:
        """Start all connection threads and block until they all exit (never in normal operation)."""
        nodes = self._config.resolve_nodes()
        jwt = self._config.resolve_jwt()
        reconnect_ms = int(os.environ.get("EM_FILTER_RECONNECT_MS", "5000"))

        threads = []
        for node in nodes:
            conn = Connection(
                name=self._name,
                node=node,
                handler=self._handler_fn,
                capabilities=self._capabilities,
                jwt_token=jwt,
                reconnect_ms=reconnect_ms,
            )
            conn.start()
            threads.append(conn)

        for t in threads:
            t.join()
