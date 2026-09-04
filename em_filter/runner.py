from __future__ import annotations
import os
import time
from typing import Any

from .config import AgentConfig
from .identity import Identity
from .server import AgentServer, GossipPusher
from .wsclient import RelayClient


class FilterRunner:
    """Mode dispatcher for an em_filter agent.

    The handler can be:
    - a plain callable: ``handle(body: str, memory: dict) -> (result, new_memory)``
    - an object with a ``handle(self, body, memory)`` method and optional
      ``capabilities() -> list[str]`` method.

    ``EM_FILTER_MODE`` (default ``relay``) selects the transport:
    - ``relay``  — Model B: outbound WS to ``wss://<disco>/ws/filter`` (NAT-friendly).
    - ``direct`` — Model A: local HTTP server (``/agent/query``, ``/pop/gossip``,
      ``/health``) plus a gossip push loop advertising it to each disco seed.
    - ``both``   — runs the HTTP server + gossip pusher *and* the relay WS
      concurrently, under the same identity.
    """

    def __init__(
        self,
        name: str,
        handler: Any,
        config: AgentConfig | None = None,
        mode: str | None = None,
        capabilities: list[str] | None = None,
    ) -> None:
        self._name = name
        self._config = config or AgentConfig()

        if hasattr(handler, "handle"):
            obj = handler
            self._handler_fn = lambda body, mem: obj.handle(body, mem)
            caps_fn = getattr(obj, "capabilities", None)
            default_caps = caps_fn() if callable(caps_fn) else ["search", "query"]
        else:
            self._handler_fn = handler
            default_caps = ["search", "query"]

        self._capabilities = capabilities or default_caps
        self._mode = mode or os.environ.get("EM_FILTER_MODE", "relay")

        key_dir = os.environ.get("EM_FILTER_KEY_DIR") or f"./empop_key_{name}/"
        self._identity = Identity(name=name, key_dir=key_dir, capabilities=self._capabilities)

    @property
    def identity(self) -> Identity:
        return self._identity

    def build(self) -> dict[str, Any]:
        """Construct (without starting) the transport(s) selected by ``mode``.

        Returns a dict with any of ``server``/``pusher``/``relay`` keys,
        depending on the mode. Does not open any network connections beyond
        the local HTTP listen socket a Model A server binds on construction.
        """
        nodes = self._config.resolve_nodes()
        components: dict[str, Any] = {}

        if self._mode in ("direct", "both"):
            query_port = int(os.environ.get("EM_FILTER_QUERY_PORT", "9600"))
            advertise_host = os.environ.get("EM_FILTER_ADVERTISE_HOST", "0.0.0.0")
            gossip_interval = float(os.environ.get("EM_FILTER_GOSSIP_INTERVAL_S", "5"))

            server = AgentServer(self._identity, self._handler_fn, host="0.0.0.0", port=query_port)
            seeds = [f"{n.host}:{n.port}" for n in nodes]
            pusher = GossipPusher(
                self._identity, seeds=seeds, host=advertise_host,
                query_port=server.port, interval=gossip_interval,
            )
            components["server"] = server
            components["pusher"] = pusher

        if self._mode in ("relay", "both"):
            if nodes:
                node = nodes[0]
                scheme = "wss" if node.tls else "ws"
                url = f"{scheme}://{node.host}:{node.port}/ws/filter"
                components["relay"] = RelayClient(self._identity, self._handler_fn, url)

        if self._mode not in ("direct", "relay", "both"):
            raise ValueError(f"unknown EM_FILTER_MODE: {self._mode!r}")

        return components

    def run(self) -> None:
        """Start the configured transport(s) and block forever."""
        components = self.build()

        server = components.get("server")
        pusher = components.get("pusher")
        if server is not None:
            server.start()
        if pusher is not None:
            pusher.start()

        relay = components.get("relay")
        if relay is not None:
            relay.run_forever()  # blocks
        else:
            # direct-only: server/pusher run in background threads.
            try:
                while True:
                    time.sleep(3600)
            except KeyboardInterrupt:
                if server is not None:
                    server.stop()
                if pusher is not None:
                    pusher.stop()
