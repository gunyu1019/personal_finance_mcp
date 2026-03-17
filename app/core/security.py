# app/core/security.py

"""
통합 보안 모듈: 암호화, 해싱, 마스킹 기능을 제공합니다.

이 모듈은 다음 기능들을 통합 제공합니다:
1. RSA 비대칭 암호화 (클라이언트↔서버 통신용)
2. AES-256 대칭키 암호화 (서버 내부 데이터 보호용)
3. 단방향 해시 (SHA-256 + salt)
4. 마스킹 유틸리티 (계좌번호, 카드번호)
5. 조건부 카드번호 암호화 로직
"""
from __future__ import annotations

import base64
import hashlib
import logging
import re
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.core.config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# RSA 키 생성 (클라이언트↔서버 통신용)
# ─────────────────────────────────────────────────────────────

_private_key: rsa.RSAPrivateKey = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)
_public_key = _private_key.public_key()

logger.info("RSA-2048 키 쌍 생성 완료 (메모리 저장)")

# ─────────────────────────────────────────────────────────────
# AES-256 Fernet 초기화 (서버 내부 데이터 보호용)
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
# RSA 공개 인터페이스 (클라이언트↔서버 통신용)
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
# AES-256 대칭키 암호화 인터페이스 (서버 내부 데이터 보호용)
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

# ─────────────────────────────────────────────────────────────
# 조건부 카드번호 암호화 로직 (신규 추가)
# ─────────────────────────────────────────────────────────────

def is_plain_card_number(card_no: str) -> bool:
    """
    카드번호가 순수 평문인지 확인합니다.
    
    정규식을 사용하여 다음 형태와 일치하는지 검사합니다:
    - 0123-4567-7890-123 (15자리)
    - 0123-4567-7890-1234 (16자리)
    
    Args:
        card_no: 검사할 카드번호 문자열
        
    Returns:
        bool: 순수 평문 카드번호 형태이면 True, 그렇지 않으면 False
    """
    if not card_no:
        return False
    
    # 숫자와 하이픈만 추출
    digits_only = re.sub(r"[^0-9-]", "", card_no)
    
    # 15자리 또는 16자리 카드번호 패턴 (4-4-4-3 또는 4-4-4-4)
    pattern_15 = r"^\d{4}-\d{4}-\d{4}-\d{3}$"
    pattern_16 = r"^\d{4}-\d{4}-\d{4}-\d{4}$"
    
    return bool(re.match(pattern_15, digits_only) or re.match(pattern_16, digits_only))


def encrypt_card_number_conditionally(card_no: str) -> str:
    """
    카드번호를 조건부로 암호화합니다.
    
    순수 평문 카드번호(0123-4567-7890-123* 형태)일 때만 암호화하고,
    이미 암호화된 것으로 보이는 데이터는 그대로 반환합니다.
    
    Args:
        card_no: 처리할 카드번호 문자열
        
    Returns:
        str: 암호화된 카드번호 또는 기존 값 (조건에 따라)
    """
    if not card_no:
        return ""
    
    if is_plain_card_number(card_no):
        logger.debug("순수 평문 카드번호 감지 - 암호화 적용")
        return encrypt_sensitive_data(card_no)
    else:
        logger.debug("이미 처리된 카드번호 - 암호화 생략")
        return card_no

# ─────────────────────────────────────────────────────────────
# 단방향 해시 (SHA-256 + salt)
# ─────────────────────────────────────────────────────────────

def hash_data(data: str, salt: str) -> str:
    """
    입력 문자열에 salt 를 결합한 뒤 SHA-256 해시값(hex)을 반환합니다.

    Args:
        data: 원본 문자열 (계좌번호, 카드번호 등)
        salt: DB 에서 관리되는 랜덤 솔트 값

    Returns:
        64자리 소문자 hex 문자열
    """
    combined = (data + salt).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()

# ─────────────────────────────────────────────────────────────
# 마스킹 유틸리티
# ─────────────────────────────────────────────────────────────

def mask_account_no(account_no: str) -> str:
    """
    계좌번호를 앞 3자리·뒤 3자리만 남기고 중간을 '*' 로 마스킹합니다.

    원본에 구분자('-', ' ')가 포함된 경우 해당 구분자 위치를 그대로 유지하며
    마스킹합니다. 구분자가 없을 경우 3-{middle}-3 포맷으로 반환합니다.

    Examples::
        "110-222-333789" → "110-***-***789"
        "1102223337890"  → "110-*******-890"

    Args:
        account_no: 원본 계좌번호 문자열

    Returns:
        마스킹된 계좌번호 문자열
    """
    digits_only = re.sub(r"[^0-9]", "", account_no)
    n = len(digits_only)

    if n <= 6:
        return "*" * n

    prefix = digits_only[:3]
    suffix = digits_only[-3:]
    middle_masked = "*" * (n - 6)
    masked_digits = prefix + middle_masked + suffix

    # 원본에 구분자가 있으면 자리를 유지한 채 마스킹 숫자 삽입
    sep_chars = set("-_ ")
    if any(ch in sep_chars for ch in account_no):
        result: list[str] = []
        digit_idx = 0
        for ch in account_no:
            if ch in sep_chars:
                result.append(ch)
            else:
                result.append(masked_digits[digit_idx])
                digit_idx += 1
        return "".join(result)

    # 구분자가 없으면 3-{middle}-3 포맷
    return f"{prefix}-{middle_masked}-{suffix}"


def mask_card_no(card_no: str) -> str:
    """
    카드번호를 앞 4자리·뒤 4자리만 남기고 중간을 '*' 로 마스킹합니다.

    Examples::
        "1234-5678-9012-5678" → "1234-****-****-5678"
        "1234567890125678"    → "1234-****-****-5678"

    Args:
        card_no: 원본 카드번호 문자열 (구분자 포함/미포함 모두 허용)

    Returns:
        마스킹된 카드번호 문자열 (xxxx-****-****-xxxx 형태)
    """
    digits_only = re.sub(r"[^0-9]", "", card_no)
    n = len(digits_only)

    if n < 8:
        return "*" * n

    prefix = digits_only[:4]
    suffix = digits_only[-4:]
    middle_len = n - 8
    middle_masked = "*" * middle_len

    # 표준 4-4-4-4 포맷으로 반환
    masked_raw = prefix + middle_masked + suffix
    # 4자리씩 분할하여 '-' 로 연결
    groups = [masked_raw[i:i + 4] for i in range(0, len(masked_raw), 4)]
    return "-".join(groups)