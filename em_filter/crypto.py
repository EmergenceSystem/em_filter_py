# em_filter/crypto.py
from __future__ import annotations
import hashlib, os
from pathlib import Path
from nacl.signing import SigningKey, VerifyKey

def id_of(pubkey: bytes) -> bytes:
    """Peer id = SHA-256(pubkey)[0:16]."""
    return hashlib.sha256(pubkey).digest()[:16]

def load_or_create(key_dir: str | os.PathLike) -> tuple[bytes, bytes]:
    """Return (pubkey32, seed32). File layout = pub(32) || seed(32), matching Erlang."""
    p = Path(key_dir) / "node_ed25519.key"
    if p.exists():
        raw = p.read_bytes()
        return raw[:32], raw[32:64]
    sk = SigningKey.generate()
    pub = bytes(sk.verify_key)
    seed = bytes(sk)  # 32-byte seed
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(pub + seed)
    return pub, seed
