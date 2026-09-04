import asyncio, base64, json, threading
import websockets
from em_filter.identity import Identity
from em_filter.wsclient import RelayClient
from em_filter import crypto


def handler(body, memory):
    return ([{"url": "https://x/1", "title": "T", "resume": body}], memory)


def test_relay_client_hello_query_result(tmp_path):
    captured = {}
    ready = threading.Event()
    done = threading.Event()
    port_box = {}

    def run_server():
        async def handle(ws):
            hello = json.loads(await ws.recv())
            assert hello["action"] == "hello"
            await ws.send(json.dumps({"action": "hello_ok"}))
            await ws.send(json.dumps({"action": "query", "id": "q1", "body": "hi"}))
            result = json.loads(await ws.recv())
            captured["result"] = result
            done.set()
            await ws.close()

        async def main():
            async with websockets.serve(handle, "127.0.0.1", 0) as server:
                port_box["port"] = server.sockets[0].getsockname()[1]
                ready.set()
                while not done.is_set():
                    await asyncio.sleep(0.05)

        asyncio.run(main())

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    assert ready.wait(timeout=2)

    ident = Identity("relay-agent", str(tmp_path), ["search"])
    client = RelayClient(ident, handler, f"ws://127.0.0.1:{port_box['port']}")

    def run_client():
        try:
            client._session()
        except Exception:
            pass  # server closes the socket after the exchange; that's expected

    client_thread = threading.Thread(target=run_client, daemon=True)
    client_thread.start()

    assert done.wait(timeout=5)
    client_thread.join(timeout=2)
    server_thread.join(timeout=2)

    result = captured["result"]
    assert result["action"] == "result"
    assert result["id"] == "q1"
    items = result["results"]
    assert items[0]["resume"] == "hi"
    assert base64.b64decode(result["signer_id"]) == ident.id
    assert crypto.verify(crypto.canonical_response(items),
                          base64.b64decode(result["signature"]), ident.pubkey)
