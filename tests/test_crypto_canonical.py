import json, base64, binascii
from pathlib import Path
from em_filter import crypto

FX = json.loads((Path(__file__).parents[1] / "fixtures/crypto_vectors.json").read_text(encoding="utf-8"))
SEED = binascii.unhexlify(FX["privkey_hex"])
PUB  = binascii.unhexlify(FX["pubkey_hex"])

def test_canonical_identity():
    idb = binascii.unhexlify(FX["id_hex"])
    got = crypto.canonical_identity(idb, FX["name"])
    assert got == binascii.unhexlify(FX["canonical_identity_hex"])

def test_selfsig_matches():
    idb = binascii.unhexlify(FX["id_hex"])
    sig = crypto.sign(crypto.canonical_identity(idb, FX["name"]), SEED)
    assert base64.b64encode(sig).decode() == FX["selfsig_b64"]

def test_canonical_response_and_sig():
    cr = crypto.canonical_response(FX["items"])
    assert cr == binascii.unhexlify(FX["canonical_response_hex"])
    sig = crypto.sign(cr, SEED)
    assert base64.b64encode(sig).decode() == FX["response_signature_b64"]
    assert crypto.verify(cr, sig, PUB)
