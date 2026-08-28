import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from .config import settings


def generate_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    public_key = private_key.public_key()

    os.makedirs(settings.DATA_DIR, exist_ok=True)
    priv_path = os.path.join(settings.DATA_DIR, "node_key.pem")
    pub_path = os.path.join(settings.DATA_DIR, "node_key.pub")

    with open(priv_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    with open(pub_path, "wb") as f:
        f.write(
            public_key.public_bytes(
                encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )
    return private_key, public_key


def load_identity():
    priv_path = os.path.join(settings.DATA_DIR, "node_key.pem")
    if not os.path.exists(priv_path):
        return None, None
    with open(priv_path, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())
    return private_key, private_key.public_key()


def get_or_create_identity():
    priv, pub = load_identity()
    if priv is None:
        priv, pub = generate_keypair()
    return priv, pub


def get_public_key_pem(public_key):
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")


def sign_message(private_key, message: bytes):
    return private_key.sign(
        message, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256()
    )
