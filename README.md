# em_filter_py

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Python SDK for building [Emergence](https://github.com/EmergenceSystem) network agents.

`em_filter_py` lets any Python process join the Emergence discovery mesh as a
**filter agent** — a service that receives search queries from `em_pop` /
`em_disco`, processes them (web search, DNS lookup, LLM call, database
query, …), and returns **signed, structured results**.

This is the reference SDK for the current signed mesh protocol: ed25519
identity, byte-identical canonical forms to the Erlang `em_pop_crypto`
reference, and both transports the mesh supports. See [PROTOCOL.md](PROTOCOL.md)
for the wire-level detail.

---

## How it works

Every agent has an ed25519 keypair (`node_ed25519.key`, created on first run)
and signs every result it returns. The mesh verifies that signature against
the agent's gossip-bound public key, so a relay hop can never forge a result.

Two transports, selected by `EM_FILTER_MODE`:

- **`relay` (default, NAT-friendly)** — the SDK opens one outbound WebSocket
  to `wss://<disco>/ws/filter` and never needs an inbound port. The disco
  relays queries to it and forwards its signed results unchanged.
- **`direct`** — the SDK runs a small HTTP server (`/agent/query`,
  `/pop/gossip`, `/health`) and periodically gossips its own signed
  self-payload to each configured seed, so Emquest can query it directly at
  `host:query_port`.
- **`both`** — runs the HTTP server + gossip loop *and* the relay WS
  concurrently, under the same identity (the direct path takes priority when
  reachable; relay is a NAT-friendly fallback).

```
                          EM_FILTER_MODE=relay (default)
 ┌──────────┐   outbound WS "hello"    ┌───────────────┐
 │  disco   │ ◄──────────────────────  │ FilterRunner  │
 │ /ws/filter│  "query" / "result"  ──► │ (your agent)  │
 └──────────┘                          └───────────────┘

                          EM_FILTER_MODE=direct
 ┌──────────┐  POST /pop/gossip (self-payload, every 5s)
 │  disco   │ ◄──────────────────────  ┌───────────────┐
 └──────────┘                          │ FilterRunner  │
 ┌──────────┐  POST /agent/query       │ (HTTP server) │
 │ Emquest  │ ───────────────────────► └───────────────┘
 └──────────┘  ◄── signed results
```

---

## Requirements

Python 3.10+, [`pynacl`](https://pypi.org/project/pynacl/) (ed25519) and
[`websocket-client`](https://pypi.org/project/websocket-client/) (relay mode):

```bash
pip install -e ".[dev]"   # or: pip install pynacl websocket-client
```

---

## Quick start

```python
from em_filter import FilterRunner

def handle(body: str, memory: dict) -> tuple:
    results = [{
        "url": "https://example.com",
        "title": f"Result for: {body}",
        "resume": f"Handled query: {body}",
    }]
    return results, memory

if __name__ == "__main__":
    FilterRunner("my_filter", handle, capabilities=["search", "query"]).run()
```

By default the agent runs in `relay` mode against `localhost:8080`. Override
via environment variables or an `AgentConfig` — see [Configuration](#configuration).

A handler can also be an object with a `handle(self, body, memory)` method
and an optional `capabilities(self)` method, instead of a plain function.

---

## Try the built-in example

```bash
python examples/echo_filter.py                                        # relay (default)
EM_FILTER_MODE=direct EM_FILTER_QUERY_PORT=9600 python examples/echo_filter.py  # direct
```

With a custom broker:

```bash
EM_DISCO_HOST=disco.example.com EM_DISCO_PORT=443 python examples/echo_filter.py
```

---

## The handler contract

`handle(body, memory)` returns `(result, new_memory)`. `result` is a
JSON-serialisable list of items — either flat or with a `properties`
sub-object — read by the shared `canonical_response` signer:

| Field | Read from (first match wins) |
|-------|-------------------------------|
| URL   | `url` |
| Title | `title`, `label` |
| Resume | `resume`, `value`, `description` |

An empty list `[]` (or `None`) means "no results for this query". Every
non-empty `result` your handler returns is signed automatically before it
leaves the SDK — you never construct the signature yourself.

### Capabilities

Advertised capabilities route queries to your agent (§5 of the mesh spec).
Pass them explicitly (`FilterRunner(..., capabilities=[...])`), via a
handler object's `capabilities()` method, or accept the default
`["search", "query"]`.

---

## Configuration

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EM_FILTER_MODE` | `relay` | `relay` \| `direct` \| `both` |
| `EM_FILTER_KEY_DIR` | `./empop_key_<name>/` | Directory holding `node_ed25519.key` |
| `EM_FILTER_QUERY_PORT` | `9600` | Direct-mode HTTP listen port |
| `EM_FILTER_ADVERTISE_HOST` | `0.0.0.0` | Direct-mode host advertised in gossip |
| `EM_FILTER_GOSSIP_INTERVAL_S` | `5` | Direct-mode gossip push interval (seconds) |
| `EM_DISCO_HOST` | — | Disco/pop hostname |
| `EM_DISCO_PORT` | — | Disco/pop port |

### Node resolution order

1. `AgentConfig.disco_nodes` — explicit list (highest priority)
2. `EM_DISCO_HOST` / `EM_DISCO_PORT` env vars
3. `[em_disco] nodes = …` in `emergence.conf`
4. `localhost:8080` — built-in default

Relay mode connects to the *first* resolved node; direct mode gossips to
*every* resolved node (its seed list).

### TLS inference

| Host | Port | Transport |
|------|------|-----------|
| `localhost`, `127.0.0.1`, `::1` | any | `ws://` / `http://` (plain) |
| any other | 443 | `wss://` / `https://` (TLS) |
| any other | other | `ws://` / `http://` (plain) |

### `emergence.conf`

```ini
[em_disco]
nodes = localhost:8080, disco.example.com, [::1]:9000
```

Platform paths:
- **Linux / macOS:** `~/.config/emergence/emergence.conf`
- **Windows:** `%APPDATA%\emergence\emergence.conf`

### Programmatic configuration

```python
from em_filter import FilterRunner, AgentConfig, DiscoNode

config = AgentConfig(
    disco_nodes=[DiscoNode(host="disco.example.com", port=443, tls=True)],
)
FilterRunner("my_filter", handle, config=config, mode="direct").run()
```

---

## Identity & signing

Every agent has an ed25519 keypair, persisted as `node_ed25519.key`
(`pubkey(32 bytes) ‖ privkey(32 bytes)`) — portable across every Emergence
SDK implementation. `em_filter.Identity` builds and signs the wire payloads;
`em_filter.crypto` is the low-level, fixture-verified module (`id_of`,
`canonical_identity`, `canonical_response`, `sign`, `verify`,
`sign_response`) shared by both transports. See [PROTOCOL.md](PROTOCOL.md).

---

## HTML utilities

Helpers for processing web pages in scraper filters:

```python
from em_filter import (
    strip_scripts, get_text, extract_elements,
    extract_attribute, decode_html_entities, should_skip_link,
)

html   = fetch_page(url)
clean  = strip_scripts(html)              # remove <script>…</script>
text   = get_text(clean)                  # strip all tags → plain text
links  = extract_elements(html, "li.b_algo")   # CSS selector extraction
href   = extract_attribute('<a href="/page">link</a>', "href")  # → "/page"
decoded = decode_html_entities("caf&eacute; &amp; croissant")   # → "café & croissant"
skip   = should_skip_link("https://ads.example.com", ["ads.example.com"])  # → True
```

---

## License

[MIT](LICENSE)
