import base64, binascii, json
from pathlib import Path
from em_filter import crypto

FX = json.loads((Path(__file__).parents[1] / "fixtures/crypto_vectors.json").read_text(encoding="utf-8"))

def test_sign_response_shape():
    pub = binascii.unhexlify(FX["pubkey_hex"]); seed = binascii.unhexlify(FX["privkey_hex"])
    signer_id, sig = crypto.sign_response(FX["items"], pub, seed)
    assert signer_id == FX["signer_id_b64"]
    assert sig == FX["response_signature_b64"]
