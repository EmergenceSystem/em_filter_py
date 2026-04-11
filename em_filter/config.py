from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DiscoNode:
    host: str
    port: int
    tls: bool


@dataclass
class AgentConfig:
    jwt_token: Optional[str] = None
    disco_nodes: list[DiscoNode] = field(default_factory=list)

    def resolve_nodes(self) -> list[DiscoNode]:
        if self.disco_nodes:
            return self.disco_nodes

        host_env = os.environ.get("EM_DISCO_HOST")
        port_env = os.environ.get("EM_DISCO_PORT")

        if host_env and port_env:
            port = _parse_port(port_env, 8080)
            return [DiscoNode(host_env, port, _infer_tls(host_env, port))]
        if host_env:
            port, tls = _default_port_tls(host_env)
            return [DiscoNode(host_env, port, tls)]
        if port_env:
            port = _parse_port(port_env, 8080)
            return [DiscoNode("localhost", port, False)]

        conf = _read_conf_nodes()
        if conf:
            return conf

        return [DiscoNode("localhost", 8080, False)]

    def resolve_jwt(self) -> Optional[str]:
        return self.jwt_token or os.environ.get("EM_FILTER_JWT_TOKEN")


def _infer_tls(host: str, port: int) -> bool:
    if host in ("localhost", "127.0.0.1", "::1"):
        return False
    return port == 443


def _default_port_tls(host: str) -> tuple[int, bool]:
    if host in ("localhost", "127.0.0.1", "::1"):
        return 8080, False
    return 443, True


def _parse_port(s: str, fallback: int) -> int:
    try:
        return int(s)
    except ValueError:
        return fallback


def _conf_path() -> Optional[Path]:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "emergence" / "emergence.conf"
    home = os.environ.get("HOME")
    if home:
        return Path(home) / ".config" / "emergence" / "emergence.conf"
    return None


def _read_conf_nodes() -> list[DiscoNode]:
    path = _conf_path()
    if path is None or not path.exists():
        return []
    try:
        return _parse_conf(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _parse_conf(content: str) -> list[DiscoNode]:
    section = ""
    last_nodes_str: Optional[str] = None
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if section == "em_disco" and "=" in line:
            key, _, val = line.partition("=")
            if key.strip() == "nodes":
                last_nodes_str = val.strip()
    if last_nodes_str is not None:
        return _parse_nodes(last_nodes_str)
    return []


def _parse_nodes(s: str) -> list[DiscoNode]:
    nodes: list[DiscoNode] = []
    for entry in s.split(","):
        entry = entry.strip()
        if not entry:
            continue
        # IPv6 bracket notation: [::1]:9000
        m = re.match(r'^\[([^\]]+)\]:(\d+)$', entry)
        if m:
            host, port = m.group(1), int(m.group(2))
            nodes.append(DiscoNode(host, port, _infer_tls(host, port)))
            continue
        if ":" in entry:
            host, _, port_str = entry.rpartition(":")
            try:
                port = int(port_str)
                nodes.append(DiscoNode(host, port, _infer_tls(host, port)))
            except ValueError:
                pass
        else:
            port, tls = _default_port_tls(entry)
            nodes.append(DiscoNode(entry, port, tls))
    return nodes
