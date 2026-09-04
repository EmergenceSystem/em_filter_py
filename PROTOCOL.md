# em_filter_py — wire protocol

This is the current signed mesh protocol implemented by `em_filter_py`,
byte-identical to the Erlang `em_pop_crypto` reference. It supersedes the
old `/ws` register/agent_hello handshake (retired — no signatures, no
identity binding).

All values below MUST reproduce `fixtures/crypto_vectors.json`, generated
from the Erlang reference. See `tests/test_crypto_canonical.py` and
`tests/test_sign_response.py`.

---

## 1. Identity & crypto

- **Keypair:** ed25519, generated with `pynacl`. Persisted to
  `node_ed25519.key` as raw `pubkey(32 bytes) ‖ privkey/seed(32 bytes)` —
  the same file layout as the Erlang `load_or_create/1`, so a key file is
  portable across implementations.
  - Directory resolution: `EM_FILTER_KEY_DIR` env, else `./empop_key_<name>/`.
- **Peer id:** `id = SHA-256(pubkey)[0:16]` — the first 16 raw bytes of the
  SHA-256 of the 32-byte public key.
- **On-wire id:** `signer_id = base64(id)` (standard base64, padded).
- **canonical_identity(id, name):** raw bytes `id ‖ 0x00 ‖ name`, `name`
  UTF-8. Self-signature `sig = Ed25519_sign(canonical_identity, priv)`,
  `base64(sig)` on the wire. Deliberately excludes host/port so a hub may
  rewrite a leaf's routing fields without invalidating the self-signature.
- **canonical_response(items):** concatenation, in list order, of one line
  per item:
  - Let `P` be the item's `properties` sub-object if present and a dict,
    else the item itself (if a dict).
  - `U` = `P["url"]` if a string, else empty.
  - `T` = first string among `P["title"]`, `P["label"]`, else empty.
  - `R` = first string among `P["resume"]`, `P["value"]`, `P["description"]`,
    else empty.
  - Line bytes: `U ‖ 0x00 ‖ T ‖ 0x00 ‖ R ‖ 0x0A`.
  - A non-dict item (or an empty dict) yields `0x00 ‖ 0x00 ‖ 0x0A`.
  - Strings are emitted as raw UTF-8 bytes, no escaping.
  - A non-list `items` value produces empty bytes.
- **Response signature:** `signature = base64(Ed25519_sign(canonical_response(results), priv))`,
  `signer_id = base64(id)`.

Implemented in `em_filter/crypto.py`: `id_of`, `load_or_create`,
`canonical_identity`, `canonical_response`, `sign`, `verify`,
`sign_response`. `em_filter/identity.py`'s `Identity` wraps these into the
wire payloads below and is shared by both transports.

---

## 2. Model A — direct (`EM_FILTER_MODE=direct`)

The SDK runs a minimal HTTP server (`em_filter/server.py`, `AgentServer`):

- **`POST /agent/query`** — body `{"query": "..."}`. Runs the handler,
  replies `{"results": <items>, "signer_id": "<b64>", "signature": "<b64>"}`.
  Malformed/absent query → 400. Handler error → 500.
- **`GET /health`** — liveness check, replies `ok`.
- **`POST /pop/gossip`** — accepts a remote gossip payload, replies with this
  agent's own self-payload (minimal peer awareness only — no cosine routing
  is run by the SDK).

**Gossip push loop** (`GossipPusher`) — every `EM_FILTER_GOSSIP_INTERVAL_S`
(default 5s), `POST`s this JSON to `http://<seed>/pop/gossip` for each
configured seed:

```json
{
  "id": "<b64 id>", "name": "<name>",
  "host": "<advertised host>", "query_port": <int>,
  "pubkey": "<b64>", "sig": "<b64 selfsig>",
  "capabilities": ["search", "query", "..."],
  "role": "filter"
}
```

The disco TOFU-binds the pubkey, derives a routing vector from
`capabilities`, and relays the peer into the mesh. Emquest then
direct-queries `host:query_port/agent/query` and verifies the signature.

**Cost:** the filter must be reachable at `host:query_port` (public IP,
port-forward, or a tunnel) — set via `EM_FILTER_QUERY_PORT` /
`EM_FILTER_ADVERTISE_HOST`.

---

## 3. Model B — WS relay (`EM_FILTER_MODE=relay`, default)

The SDK (`em_filter/wsclient.py`, `RelayClient`) opens one outbound
WebSocket to `wss://<disco>/ws/filter` (`ws://` if the resolved disco node
is not TLS) and never needs inbound reachability.

**Handshake** (filter → disco):

```json
{"action": "hello", "name": "<name>", "pubkey": "<b64>",
 "sig": "<b64 selfsig>", "capabilities": ["..."]}
```

Disco verifies `id == SHA-256(pubkey)[0:16]` and the self-signature,
TOFU-binds the pubkey, and injects a gossip peer with `query_port = null`,
`relay_via = <disco id>`. Ack:

```json
{"action": "hello_ok", "id": "<b64 id>"}
```

(or `{"action": "error", "reason": "..."}` on rejection.)

**Query** (disco → filter):

```json
{"action": "query", "id": "<qid>", "body": "<query>"}
```

**Result** (filter → disco):

```json
{"action": "result", "id": "<qid>", "results": <items>,
 "signer_id": "<b64>", "signature": "<b64>"}
```

The filter signs `canonical_response(results)` itself; the disco relays
`{results, signer_id, signature}` to Emquest unchanged — it never holds the
private key, so it cannot forge a result for that id.

`RelayClient.run_forever()` reconnects with a fixed delay
(`reconnect_s`, default 5s) on any session error.

---

## 4. Mode selection

`EM_FILTER_MODE` = `relay` (default) | `direct` | `both`. `both` runs the
HTTP server + gossip loop and the relay WS concurrently, advertising the
same id — the direct peer entry carries a real `query_port`; the relay path
is a NAT-friendly fallback. See `em_filter/runner.py`, `FilterRunner`.
