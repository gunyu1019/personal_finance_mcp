import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes

def get_encrypt(value: str, public_key_pem: str) -> str:
    public_key = serialization.load_pem_public_key(
        public_key_pem.encode('utf-8')
    )

    encrypted_bytes = public_key.encrypt(
        value.encode('utf-8'),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    encrypted_base64 = base64.b64encode(encrypted_bytes).decode('utf-8')
    return encrypted_base64
