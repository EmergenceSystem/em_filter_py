import os
import pytest
from em_filter.config import AgentConfig, DiscoNode, _parse_conf, _parse_nodes

def test_default_resolves_localhost(monkeypatch):
    monkeypatch.delenv("EM_DISCO_HOST", raising=False)
    monkeypatch.delenv("EM_DISCO_PORT", raising=False)
    nodes = AgentConfig().resolve_nodes()
    assert len(nodes) == 1
    assert nodes[0].host == "localhost"
    assert nodes[0].port == 8080
    assert nodes[0].tls is False

def test_env_host_and_port(monkeypatch):
    monkeypatch.setenv("EM_DISCO_HOST", "disco.example.com")
    monkeypatch.setenv("EM_DISCO_PORT", "443")
    nodes = AgentConfig().resolve_nodes()
    assert nodes[0].host == "disco.example.com"
    assert nodes[0].port == 443
    assert nodes[0].tls is True

def test_env_host_only_remote(monkeypatch):
    monkeypatch.setenv("EM_DISCO_HOST", "disco.example.com")
    monkeypatch.delenv("EM_DISCO_PORT", raising=False)
    nodes = AgentConfig().resolve_nodes()
    assert nodes[0].port == 443
    assert nodes[0].tls is True

def test_env_host_only_localhost(monkeypatch):
    monkeypatch.setenv("EM_DISCO_HOST", "localhost")
    monkeypatch.delenv("EM_DISCO_PORT", raising=False)
    nodes = AgentConfig().resolve_nodes()
    assert nodes[0].port == 8080
    assert nodes[0].tls is False

def test_explicit_nodes_override_env(monkeypatch):
    monkeypatch.setenv("EM_DISCO_HOST", "ignored.com")
    config = AgentConfig(disco_nodes=[DiscoNode("myhost.com", 9000, False)])
    nodes = config.resolve_nodes()
    assert len(nodes) == 1
    assert nodes[0].host == "myhost.com"

def test_localhost_never_tls():
    from em_filter.config import _infer_tls
    assert _infer_tls("localhost", 443) is False
    assert _infer_tls("127.0.0.1", 443) is False
    assert _infer_tls("::1", 443) is False

def test_remote_port_443_is_tls():
    from em_filter.config import _infer_tls
    assert _infer_tls("example.com", 443) is True

def test_remote_other_port_no_tls():
    from em_filter.config import _infer_tls
    assert _infer_tls("example.com", 8080) is False

def test_parse_conf_single_node():
    content = "[em_disco]\nnodes = localhost:8080\n"
    nodes = _parse_conf(content)
    assert len(nodes) == 1
    assert nodes[0].host == "localhost"
    assert nodes[0].port == 8080

def test_parse_conf_two_nodes():
    content = "[em_disco]\nnodes = localhost:8080, disco.example.com\n"
    nodes = _parse_conf(content)
    assert len(nodes) == 2
    assert nodes[1].host == "disco.example.com"
    assert nodes[1].port == 443

def test_parse_conf_comments_ignored():
    content = "; comment\n[em_disco]\n# another\nnodes = localhost:9000\n"
    nodes = _parse_conf(content)
    assert nodes[0].port == 9000

def test_parse_conf_last_nodes_wins():
    content = "[em_disco]\nnodes = localhost:8080\nnodes = localhost:9090\n"
    nodes = _parse_conf(content)
    assert nodes[0].port == 9090

def test_parse_nodes_ipv6():
    nodes = _parse_nodes("[::1]:9000")
    assert nodes[0].host == "::1"
    assert nodes[0].port == 9000
    assert nodes[0].tls is False

def test_resolve_jwt_from_struct(monkeypatch):
    monkeypatch.delenv("EM_FILTER_JWT_TOKEN", raising=False)
    config = AgentConfig(jwt_token="mytoken")
    assert config.resolve_jwt() == "mytoken"

def test_resolve_jwt_from_env(monkeypatch):
    monkeypatch.setenv("EM_FILTER_JWT_TOKEN", "envtoken")
    config = AgentConfig()
    assert config.resolve_jwt() == "envtoken"

def test_resolve_jwt_none(monkeypatch):
    monkeypatch.delenv("EM_FILTER_JWT_TOKEN", raising=False)
    assert AgentConfig().resolve_jwt() is None
