import json, base64, binascii
from pathlib import Path
from em_filter import crypto

FX = json.loads((Path(__file__).parents[1] / "fixtures/crypto_vectors.json").read_text())

def test_id_of_matches_fixture():
    pub = binascii.unhexlify(FX["pubkey_hex"])
    assert crypto.id_of(pub) == binascii.unhexlify(FX["id_hex"])
    assert base64.b64encode(crypto.id_of(pub)).decode() == FX["signer_id_b64"]
