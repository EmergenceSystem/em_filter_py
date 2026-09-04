from em_filter.runner import FilterRunner
from em_filter.server import AgentServer, GossipPusher
from em_filter.wsclient import RelayClient


def handler(body, memory):
    return ([], memory)


def _close_server(components):
    server = components.get("server")
    if server is not None:
        server._server.server_close()


def test_direct_mode_builds_server_and_pusher(tmp_path, monkeypatch):
    monkeypatch.setenv("EM_FILTER_KEY_DIR", str(tmp_path))
    monkeypatch.setenv("EM_FILTER_QUERY_PORT", "0")
    monkeypatch.setenv("EM_FILTER_MODE", "direct")
    runner = FilterRunner("t1", handler)
    components = runner.build()
    try:
        assert isinstance(components["server"], AgentServer)
        assert isinstance(components["pusher"], GossipPusher)
        assert "relay" not in components
    finally:
        _close_server(components)


def test_relay_mode_builds_relay_client(tmp_path, monkeypatch):
    monkeypatch.setenv("EM_FILTER_KEY_DIR", str(tmp_path))
    monkeypatch.setenv("EM_FILTER_MODE", "relay")
    runner = FilterRunner("t2", handler)
    components = runner.build()
    assert isinstance(components["relay"], RelayClient)
    assert "server" not in components


def test_default_mode_is_relay(tmp_path, monkeypatch):
    monkeypatch.setenv("EM_FILTER_KEY_DIR", str(tmp_path))
    monkeypatch.delenv("EM_FILTER_MODE", raising=False)
    runner = FilterRunner("t3", handler)
    components = runner.build()
    assert isinstance(components["relay"], RelayClient)


def test_both_mode_builds_all_three(tmp_path, monkeypatch):
    monkeypatch.setenv("EM_FILTER_KEY_DIR", str(tmp_path))
    monkeypatch.setenv("EM_FILTER_QUERY_PORT", "0")
    monkeypatch.setenv("EM_FILTER_MODE", "both")
    runner = FilterRunner("t4", handler)
    components = runner.build()
    try:
        assert isinstance(components["server"], AgentServer)
        assert isinstance(components["pusher"], GossipPusher)
        assert isinstance(components["relay"], RelayClient)
    finally:
        _close_server(components)


def test_relay_url_uses_resolved_disco_node(tmp_path, monkeypatch):
    monkeypatch.setenv("EM_FILTER_KEY_DIR", str(tmp_path))
    monkeypatch.setenv("EM_FILTER_MODE", "relay")
    monkeypatch.setenv("EM_DISCO_HOST", "disco.example.com")
    monkeypatch.setenv("EM_DISCO_PORT", "9443")
    runner = FilterRunner("t5", handler)
    components = runner.build()
    assert components["relay"].url == "ws://disco.example.com:9443/ws/filter"
