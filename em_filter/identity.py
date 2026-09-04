# em_filter/identity.py
from __future__ import annotations
import base64
from em_filter import crypto


class Identity:
    """Holds an agent's ed25519 keypair, name and capabilities, and builds
    the signed wire payloads shared by both transports (Model A / Model B)."""

    def __init__(self, name: str, key_dir: str, capabilities: list[str]):
        self.name = name
        self.capabilities = capabilities
        self.pubkey, self.seed = crypto.load_or_create(key_dir)
        self.id = crypto.id_of(self.pubkey)

    def _selfsig_b64(self) -> str:
        sig = crypto.sign(crypto.canonical_identity(self.id, self.name), self.seed)
        return base64.b64encode(sig).decode()

    def hello_payload(self) -> dict:
        return {"action": "hello", "name": self.name,
                "pubkey": base64.b64encode(self.pubkey).decode(),
                "sig": self._selfsig_b64(), "capabilities": self.capabilities}

    def gossip_payload(self, host: str, query_port: int) -> dict:
        return {"id": base64.b64encode(self.id).decode(), "name": self.name,
                "host": host, "query_port": query_port,
                "pubkey": base64.b64encode(self.pubkey).decode(),
                "sig": self._selfsig_b64(), "capabilities": self.capabilities,
                "role": "filter"}

    def sign_results(self, items) -> tuple[str, str]:
        return crypto.sign_response(items, self.pubkey, self.seed)
