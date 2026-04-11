# em_filter_py

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Python SDK for building [Emergence](https://github.com/EmergenceSystem) network agents.

`em_filter_py` lets any Python process join the Emergence distributed discovery network
as a **filter agent** — a service that receives search queries from the `em_disco`
broker, processes them (web search, DNS lookup, LLM call, database query, …), and
returns structured results.

This library is the Python equivalent of the Erlang `em_filter` library: same WebSocket
protocol, same configuration contract, idiomatic Python API.

---

## How it works

```
 ┌─────────────┐    WebSocket     ┌───────────────┐    WebSocket     ┌─────────────┐
 │  em_disco   │ ◄─────────────── │ FilterRunner  │ ───────────────► │  em_disco   │
 │  (broker)   │  query / result  │ (your agent)  │  (multi-node)    │  (replica)  │
 └─────────────┘                  └───────────────┘                  └─────────────┘
                                         │
                               threading.Thread per node
                                         │
                                  ┌──────┴──────┐
                                  │ your handler│
                                  │  function   │
                                  └─────────────┘
```

1. `FilterRunner` resolves disco nodes and spawns one thread per node.
2. Each thread maintains a persistent WebSocket connection with automatic reconnection.
3. On a `query` frame, the thread calls your handler and sends back a `result` frame.

---

## Requirements

Python 3.9+ and [`websocket-client`](https://pypi.org/project/websocket-client/):

```bash
pip install websocket-client
```

---

## Quick start

```python
from em_filter import FilterRunner

class MyFilter:
    def handle(self, body: str, memory: dict) -> tuple:
        result = [{
            "type": "url",
            "properties": {
                "url":   "https://example.com",
                "title": f"Result for: {body}",
            }
        }]
        return result, memory

    def capabilities(self) -> list[str]:
        return ["search", "query"]

if __name__ == "__main__":
    FilterRunner("my_filter", MyFilter()).run()
```

By default the agent connects to `localhost:8080`. Override via environment
variables or `AgentConfig` — see [Configuration](#configuration).

---

## Try the built-in example

```bash
python examples/echo_filter.py
```

Expected output once connected:

```
[em_filter] echo_filter connecting to ws://localhost:8080/ws
[em_filter] echo_filter registered — entering message loop
```

With a custom broker:

```bash
EM_DISCO_HOST=disco.example.com \
EM_DISCO_PORT=443 \
EM_FILTER_JWT_TOKEN=eyJ... \
python examples/echo_filter.py
```

---

## The handler contract

The handler can be any object with a `handle` method — no base class required:

```python
class MyFilter:
    def handle(self, body: str, memory: dict) -> tuple:
        # body:   raw query string, e.g. "erlang otp"
        # memory: persists between queries within a connection (resets on reconnect)
        new_memory = {**memory, "last_query": body}
        result = [{"type": "text", "properties": {"content": f"Processed: {body}"}}]
        return result, new_memory

    def capabilities(self) -> list[str]:
        # em_disco uses these to route queries to this agent
        return ["search", "query", "my_capability"]
```

A plain callable is also accepted:

```python
def my_handler(body: str, memory: dict) -> tuple:
    return [{"type": "text", "properties": {"content": body}}], memory

FilterRunner("my_filter", my_handler).run()
```

### Result format

`handle` returns `(result, new_memory)`. `result` is a JSON-serialisable value —
typically a list of **embryo** objects:

| Type | Required properties |
|------|---------------------|
| `"url"` | `url`, `title` |
| `"dns"` | `domain`, `ips` |
| `"text"` | `content` |

An empty list `[]` or `None` means "no results for this query".

### Capabilities

`capabilities()` returns the list of capabilities your agent advertises.
`em_disco` uses this to route queries. Default: `["search", "query"]`.

---

## Configuration

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EM_DISCO_HOST` | — | Disco broker hostname |
| `EM_DISCO_PORT` | — | Disco broker port |
| `EM_FILTER_JWT_TOKEN` | — | JWT for authenticated brokers |
| `EM_FILTER_RECONNECT_MS` | `5000` | Reconnect delay in milliseconds |

### Node resolution order

1. `AgentConfig.disco_nodes` — explicit list (highest priority)
2. `EM_DISCO_HOST` / `EM_DISCO_PORT` env vars
3. `[em_disco] nodes = …` in `emergence.conf`
4. `localhost:8080` — built-in default

### TLS inference

| Host | Port | Transport |
|------|------|-----------|
| `localhost`, `127.0.0.1`, `::1` | any | `ws://` (plain) |
| any other | 443 | `wss://` (TLS) |
| any other | other | `ws://` (plain) |

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
    jwt_token="eyJ...",
    disco_nodes=[
        DiscoNode(host="disco.example.com",  port=443, tls=True),
        DiscoNode(host="disco2.example.com", port=443, tls=True),
    ],
)
FilterRunner("my_filter", MyFilter(), config).run()
```

---

## Multi-node

`FilterRunner` connects to all resolved nodes simultaneously, one thread per node.
Memory is local to each connection — each thread starts with an empty dict on connect
and resets on reconnect (same as Erlang `em_filter` RAM mode).

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

## WebSocket protocol

The agent speaks a minimal JSON-over-WebSocket protocol to `em_disco`.

**Agent → Disco:**
```json
{ "action": "register",    "name": "<agent_name>" }
{ "action": "agent_hello", "capabilities": ["search", "query"] }
{ "action": "result",      "id": "<query_id>", "data": <result> }
```

**Disco → Agent:**
```json
{ "action": "query", "id": "<query_id>", "body": "<query_string>" }
```

The library handles the handshake and reconnection automatically.
Your code only implements the handler.

---

## License

[MIT](LICENSE)
