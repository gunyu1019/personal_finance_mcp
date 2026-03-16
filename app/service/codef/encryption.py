from __future__ import annotations
import base64
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_der_public_key


def get_encrypt(value: str, public_key_pem: str) -> str:
    key_der = base64.b64decode(public_key_pem)

    public_key_obj = load_der_public_key(key_der)

    encrypted_bytes = public_key_obj.encrypt(
        value.encode(),
        padding.PKCS1v15(),
    )

    encrypted_base64 = base64.b64encode(encrypted_bytes).decode('utf-8')
    return encrypted_base64
