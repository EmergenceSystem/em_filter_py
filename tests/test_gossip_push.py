import json, threading, base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from em_filter.identity import Identity
from em_filter.server import GossipPusher
from em_filter import crypto


class _CapturingHandler(BaseHTTPRequestHandler):
    captured = None
    event = None

    def do_POST(self):
        n = int(self.headers.get("content-length", 0))
        raw = self.rfile.read(n)
        _CapturingHandler.captured = json.loads(raw)
        body = b"{}"
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        _CapturingHandler.event.set()

    def log_message(self, *a):
        pass


def test_gossip_pusher_posts_signed_payload(tmp_path):
    _CapturingHandler.captured = None
    _CapturingHandler.event = threading.Event()

    stub = ThreadingHTTPServer(("127.0.0.1", 0), _CapturingHandler)
    stub_port = stub.server_address[1]
    t = threading.Thread(target=stub.serve_forever, daemon=True)
    t.start()

    ident = Identity("gossiper", str(tmp_path), ["search"])
    pusher = GossipPusher(
        ident,
        seeds=[f"127.0.0.1:{stub_port}"],
        host="9.9.9.9",
        query_port=9600,
        interval=0.05,
    )
    try:
        pusher.start()
        assert _CapturingHandler.event.wait(timeout=2)
        payload = _CapturingHandler.captured
        assert payload["role"] == "filter"
        assert payload["query_port"] == 9600
        assert base64.b64decode(payload["id"]) == ident.id
        assert set(["pubkey", "sig", "capabilities"]).issubset(payload.keys())
        assert crypto.verify(
            crypto.canonical_identity(ident.id, ident.name),
            base64.b64decode(payload["sig"]),
            ident.pubkey,
        )
    finally:
        pusher.stop()
        stub.shutdown()
