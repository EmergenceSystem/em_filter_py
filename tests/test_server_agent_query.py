import json, base64, urllib.request
from em_filter.identity import Identity
from em_filter.server import AgentServer
from em_filter import crypto

def handler(body, memory):
    return ([{"url": "https://x/1", "title": "T", "resume": "R"}], memory)

def test_agent_query_signed(tmp_path):
    ident = Identity("srv", str(tmp_path), ["search"])
    srv = AgentServer(ident, handler, host="127.0.0.1", port=0)
    srv.start()
    try:
        url = f"http://127.0.0.1:{srv.port}/agent/query"
        req = urllib.request.Request(url, data=b'{"query":"hi"}',
              headers={"content-type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=2).read())
        assert base64.b64decode(resp["signer_id"]) == ident.id
        items = resp["results"]
        assert crypto.verify(crypto.canonical_response(items),
                             base64.b64decode(resp["signature"]), ident.pubkey)
    finally:
        srv.stop()

def test_health(tmp_path):
    ident = Identity("srv2", str(tmp_path), ["search"])
    srv = AgentServer(ident, handler, host="127.0.0.1", port=0)
    srv.start()
    try:
        url = f"http://127.0.0.1:{srv.port}/health"
        body = urllib.request.urlopen(url, timeout=2).read()
        assert body == b"ok"
    finally:
        srv.stop()

def test_pop_gossip_returns_self_payload(tmp_path):
    ident = Identity("srv3", str(tmp_path), ["search"])
    srv = AgentServer(ident, handler, host="127.0.0.1", port=0)
    srv.start()
    try:
        url = f"http://127.0.0.1:{srv.port}/pop/gossip"
        req = urllib.request.Request(url, data=b"{}", method="POST",
              headers={"content-type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=2).read())
        assert resp["role"] == "filter"
        assert base64.b64decode(resp["id"]) == ident.id
        assert crypto.verify(crypto.canonical_identity(ident.id, ident.name),
                              base64.b64decode(resp["sig"]), ident.pubkey)
    finally:
        srv.stop()
