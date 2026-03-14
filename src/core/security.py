# src/core/security.py

import hashlib
import re


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
