import base64
from em_filter.identity import Identity

def test_hello_and_gossip_payload(tmp_path):
    ident = Identity(name="t", key_dir=str(tmp_path), capabilities=["search"])
    h = ident.hello_payload()
    assert h["action"] == "hello" and h["name"] == "t"
    assert base64.b64decode(h["pubkey"]) == ident.pubkey
    # self-sig verifies
    from em_filter import crypto
    assert crypto.verify(
        crypto.canonical_identity(ident.id, "t"),
        base64.b64decode(h["sig"]), ident.pubkey)
    g = ident.gossip_payload(host="1.2.3.4", query_port=9600)
    assert g["query_port"] == 9600 and g["role"] == "filter"
