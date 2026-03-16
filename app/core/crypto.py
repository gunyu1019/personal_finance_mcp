# src/core/crypto.py

"""
AES-256 대칭키 암호화 유틸리티 (양방향 암호화).

Fernet을 사용하여 민감한 계좌번호, 카드번호, 비밀번호 등을 안전하게 암호화/복호화합니다.
암호화 키는 환경변수 ENCRYPTION_SECRET_KEY에서 읽어오며, 설정되지 않은 경우 자동 생성됩니다.

이 모듈은 다음 두 가지 기능을 제공합니다:
1. RSA 비대칭 암호화 (클라이언트↔서버 통신용, 기존 유지)
2. AES-256 대칭키 암호화 (서버 내부 데이터 보호용, 신규 추가)
"""
from __future__ import annotations

import base64
import logging

from cryptography.fernet import Fernet
from app.core.config import settings
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# RSA 키 생성 (기존 기능 유지)
# ─────────────────────────────────────────────────────────────

_private_key: rsa.RSAPrivateKey = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)
_public_key = _private_key.public_key()

logger.info("RSA-2048 키 쌍 생성 완료 (메모리 저장)")

# ─────────────────────────────────────────────────────────────
# AES-256 Fernet 초기화
# ─────────────────────────────────────────────────────────────

def _get_or_generate_encryption_key() -> bytes:
    """
    설정에서 암호화 키를 읽거나 없으면 새로 생성합니다.

    ENCRYPTION_SECRET_KEY에는 Fernet.generate_key()가 출력하는
    urlsafe Base64 문자열을 그대로 넣습니다 (추가 인코딩 없음).

    Returns:
        bytes: Fernet에서 사용할 키 (urlsafe Base64 인코딩된 bytes)
    """
    key_str = (settings.ENCRYPTION_SECRET_KEY or "").strip()

    if key_str:
        key_bytes = key_str.encode("utf-8")
        try:
            # 유효한 Fernet 키인지 검증
            Fernet(key_bytes)
            return key_bytes
        except Exception as e:
            logger.warning(
                "ENCRYPTION_SECRET_KEY가 유효한 Fernet 키가 아닙니다. 새 키를 생성합니다. (%s)",
                e,
            )

    # 새 키 생성 (Fernet 형식의 urlsafe Base64 키)
    new_key = Fernet.generate_key()
    key_for_env = new_key.decode("utf-8")

    logger.warning("=" * 60)
    logger.warning("🔐 새로운 암호화 키가 생성되었습니다!")
    logger.warning("아래 키를 .env 파일의 ENCRYPTION_SECRET_KEY에 그대로 저장하세요:")
    logger.warning("ENCRYPTION_SECRET_KEY=%s", key_for_env)
    logger.warning("=" * 60)

    return new_key

# Fernet 인스턴스 초기화
_encryption_key = _get_or_generate_encryption_key()
_fernet = Fernet(_encryption_key)

logger.info("AES-256 Fernet 암호화 모듈 초기화 완료")


# ─────────────────────────────────────────────────────────────
# 공개 인터페이스 (기존 RSA 기능 유지)
# ─────────────────────────────────────────────────────────────

def get_public_key_pem() -> str:
    """
    RSA 공개키를 PEM 형식의 문자열로 반환합니다.

    클라이언트(JSEncrypt)가 이 공개키를 사용하여 민감 데이터를 암호화합니다.

    Returns:
        str: BEGIN PUBLIC KEY 형식의 PEM 문자열
    """
    pem_bytes = _public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return pem_bytes.decode("utf-8")


def decrypt_data(encrypted_text: str) -> str:
    """
    클라이언트가 RSA 공개키로 암호화한 Base64 인코딩 문자열을 복호화합니다.

    JSEncrypt 라이브러리는 PKCS#1 v1.5 패딩을 기본 사용합니다.
    이를 Python cryptography 의 PKCS1v15 패딩으로 복호화합니다.

    Args:
        encrypted_text: JSEncrypt가 생성한 Base64 인코딩 암호화 문자열

    Returns:
        str: 복호화된 평문 문자열

    Raises:
        ValueError: Base64 디코딩 실패 또는 복호화 실패 시
    """
    try:
        encrypted_bytes = base64.b64decode(encrypted_text)
    except Exception as exc:
        raise ValueError(f"암호문 Base64 디코딩 실패: {exc}") from exc

    try:
        decrypted_bytes = _private_key.decrypt(
            encrypted_bytes,
            padding.PKCS1v15(),
        )
    except Exception as exc:
        raise ValueError(f"RSA 복호화 실패: {exc}") from exc

    return decrypted_bytes.decode("utf-8")


# ─────────────────────────────────────────────────────────────
# 신규 AES-256 대칭키 암호화 인터페이스
# ─────────────────────────────────────────────────────────────

def encrypt_sensitive_data(plaintext: str) -> str:
    """
    평문 문자열을 AES-256으로 암호화합니다.
    
    계좌번호, 카드번호, 비밀번호 등 민감한 데이터를 DB에 저장할 때 사용합니다.
    
    Args:
        plaintext: 암호화할 평문 문자열
        
    Returns:
        str: Base64로 인코딩된 암호화 문자열
        
    Raises:
        ValueError: 암호화 실패 시
    """
    if not plaintext:
        return ""
        
    try:
        plaintext_bytes = plaintext.encode('utf-8')
        encrypted_bytes = _fernet.encrypt(plaintext_bytes)
        return base64.b64encode(encrypted_bytes).decode('utf-8')
    except Exception as exc:
        raise ValueError(f"AES 암호화 실패: {exc}") from exc


def decrypt_sensitive_data(encrypted_text: str) -> str:
    """
    AES-256으로 암호화된 문자열을 복호화합니다.
    
    DB에서 읽어온 암호화된 데이터를 원본으로 복원할 때 사용합니다.
    
    Args:
        encrypted_text: Base64로 인코딩된 암호화 문자열
        
    Returns:
        str: 복호화된 평문 문자열
        
    Raises:
        ValueError: 복호화 실패 시
    """
    if not encrypted_text:
        return ""
        
    try:
        encrypted_bytes = base64.b64decode(encrypted_text)
        decrypted_bytes = _fernet.decrypt(encrypted_bytes)
        return decrypted_bytes.decode('utf-8')
    except Exception as exc:
        raise ValueError(f"AES 복호화 실패: {exc}") from exc
