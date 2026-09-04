# em_filter/server.py
from __future__ import annotations
import json, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


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
