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

from nacl.exceptions import BadSignatureError

def canonical_identity(id_bytes: bytes, name: str) -> bytes:
    return id_bytes + b"\x00" + name.encode("utf-8")

def _pick(props: dict, keys: list[str]) -> bytes:
    for k in keys:
        v = props.get(k)
        if isinstance(v, str):
            return v.encode("utf-8")
    return b""

def _item_line(item) -> bytes:
    props = item.get("properties") if isinstance(item, dict) else None
    p = props if isinstance(props, dict) else (item if isinstance(item, dict) else {})
    u = _pick(p, ["url"])
    t = _pick(p, ["title", "label"])
    r = _pick(p, ["resume", "value", "description"])
    return u + b"\x00" + t + b"\x00" + r + b"\n"

def canonical_response(items) -> bytes:
    if not isinstance(items, list):
        return b""
    return b"".join(_item_line(i) for i in items)

def sign(msg: bytes, seed: bytes) -> bytes:
    return SigningKey(seed).sign(msg).signature  # 64 bytes

def verify(msg: bytes, sig: bytes, pubkey: bytes) -> bool:
    try:
        VerifyKey(pubkey).verify(msg, sig)
        return True
    except (BadSignatureError, ValueError):
        return False
