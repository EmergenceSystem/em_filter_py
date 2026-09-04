# em_filter/server.py
from __future__ import annotations
import json, logging, threading, time, urllib.error, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger(__name__)


class AgentServer:
    """Model A: direct HTTP server exposing signed /agent/query, /pop/gossip
    and /health, mirroring em_pop's agent-facing HTTP API."""

    def __init__(self, identity, handler, host="0.0.0.0", port=9600):
        self.identity = identity
        self.handler = handler
        self._memory: dict = {}
        ident, hfn = identity, handler
        outer = self

        class H(BaseHTTPRequestHandler):
            def _json(self, code, obj):
                b = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(b)))
                self.end_headers(); self.wfile.write(b)

            def do_GET(self):
                if self.path == "/health":
                    self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
                else:
                    self.send_response(404); self.end_headers()

            def do_POST(self):
                n = int(self.headers.get("content-length", 0))
                raw = self.rfile.read(n)
                if self.path == "/agent/query":
                    try:
                        q = json.loads(raw)["query"]
                    except Exception:
                        return self._json(400, {"error": "bad query"})
                    try:
                        items, outer._memory = hfn(q, outer._memory)
                    except Exception as e:
                        return self._json(500, {"error": str(e)})
                    sid, sig = ident.sign_results(items)
                    return self._json(200, {"results": items,
                                            "signer_id": sid, "signature": sig})
                elif self.path == "/pop/gossip":
                    # minimal: accept, reply own self-payload
                    return self._json(200, ident.gossip_payload(
                        host=outer.advertise_host, query_port=outer.port))
                self.send_response(404); self.end_headers()

            def log_message(self, *a): pass

        self._server = ThreadingHTTPServer((host, port), H)
        self.port = self._server.server_address[1]
        self.advertise_host = host

    def start(self):
        self._t = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._t.start()

    def stop(self):
        self._server.shutdown()


class GossipPusher:
    """Model A: periodically POSTs this identity's gossip payload to each
    seed disco node's /pop/gossip, so it is discoverable for direct queries."""

    def __init__(self, identity, seeds: list[str], host: str, query_port: int,
                 interval: float = 10.0):
        self.identity = identity
        self.seeds = seeds
        self.host = host
        self.query_port = query_port
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _push_once(self):
        payload = json.dumps(self.identity.gossip_payload(
            host=self.host, query_port=self.query_port)).encode()
        for seed in self.seeds:
            url = f"http://{seed}/pop/gossip"
            req = urllib.request.Request(
                url, data=payload, method="POST",
                headers={"content-type": "application/json"})
            try:
                urllib.request.urlopen(req, timeout=5).read()
            except urllib.error.URLError as e:
                log.warning("gossip push to %s failed: %s", seed, e)

    def _run(self):
        while not self._stop.is_set():
            self._push_once()
            self._stop.wait(self.interval)

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
