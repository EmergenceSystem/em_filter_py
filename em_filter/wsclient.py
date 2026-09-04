# em_filter/wsclient.py
from __future__ import annotations
import json, time, logging
import websocket  # websocket-client

log = logging.getLogger(__name__)


class RelayClient:
    """Model B: outbound WebSocket connection to em_disco/em_pop's relay,
    speaking hello / hello_ok / query / result."""

    def __init__(self, identity, handler, disco_url: str, reconnect_s: float = 5.0):
        self.identity = identity
        self.handler = handler
        self.url = disco_url
        self.reconnect_s = reconnect_s
        self._memory: dict = {}

    def run_forever(self):
        while True:
            try:
                self._session()
            except Exception as e:
                log.warning("relay session error: %s", e)
            time.sleep(self.reconnect_s)

    def _session(self):
        ws = websocket.create_connection(self.url, timeout=30)
        try:
            ws.send(json.dumps(self.identity.hello_payload()))
            ack = json.loads(ws.recv())
            if ack.get("action") != "hello_ok":
                raise RuntimeError(f"hello rejected: {ack}")
            while True:
                raw = ws.recv()
                if not raw:
                    break
                msg = json.loads(raw)
                if msg.get("action") != "query":
                    continue
                qid, body = msg.get("id"), msg.get("body", "")
                try:
                    items, self._memory = self.handler(body, self._memory)
                except Exception as e:
                    log.error("handler error: %s", e); items = []
                sid, sig = self.identity.sign_results(items)
                ws.send(json.dumps({"action": "result", "id": qid,
                    "results": items, "signer_id": sid, "signature": sig}))
        finally:
            ws.close()
