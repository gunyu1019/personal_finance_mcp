# src/api/finance/form.py

"""
동적 로그인 폼 API.

기관 코드(company_code)와 기관 유형(org_type)에 따라
CODEF 마이데이터 연동 시 필요한 입력 필드 목록을 반환합니다.
"""

from typing import Literal

from fastapi import APIRouter, HTTPException, status

from src.schema.finance import FormField, FormResponse

router = APIRouter(prefix="/api/finance", tags=["finance"])

# ─────────────────────────────────────────────────────────────
# 필드 정의 상수
# ─────────────────────────────────────────────────────────────

# 모든 기관 공통 기본 필드
_BASE_FIELDS: list[FormField] = [
    FormField(name="id",       label="아이디",   type="text"),
    FormField(name="password", label="비밀번호", type="password"),
]

# 단순 추가 필드 정의
_FIELD_BIRTH_DATE = FormField(
    name="birthDate", label="생년월일 (YYYYMMDD)", type="text"
)
_FIELD_WITHDRAW_ACCOUNT_NO = FormField(
    name="withdrawAccountNo", label="출금계좌번호", type="text"
)
_FIELD_WITHDRAW_ACCOUNT_PASSWORD = FormField(
    name="withdrawAccountPassword", label="출금계좌비밀번호", type="password"
)
_FIELD_CARD_NO = FormField(
    name="cardNo", label="카드번호", type="text"
)
_FIELD_CARD_PASSWORD = FormField(
    name="cardPassword", label="카드비밀번호", type="password"
)


# ─────────────────────────────────────────────────────────────
# 기관 코드 → 추가 필드 매핑
# ─────────────────────────────────────────────────────────────

# 은행 : company_code → 추가 FormField 리스트
# 씨티(0027), SC제일(0023), 신한(0088), K뱅크(0089) → birthDate
# 대구(0031) → birthDate + 출금계좌번호 + 출금계좌비밀번호
_BANK_EXTRA_FIELDS: dict[str, list[FormField]] = {
    "0023": [_FIELD_BIRTH_DATE],                              # SC제일은행
    "0027": [_FIELD_BIRTH_DATE],                              # 한국씨티은행
    "0031": [                                                  # 대구은행
        _FIELD_BIRTH_DATE,
        _FIELD_WITHDRAW_ACCOUNT_NO,
        _FIELD_WITHDRAW_ACCOUNT_PASSWORD,
    ],
    "0088": [_FIELD_BIRTH_DATE],                              # 신한은행
    "0089": [_FIELD_BIRTH_DATE],                              # K뱅크
}

# 카드 : company_code → 추가 FormField 리스트
# KB국민(0301), 현대(0302) → cardNo + cardPassword
# 롯데(0311) → birthDate
_CARD_EXTRA_FIELDS: dict[str, list[FormField]] = {
    "0301": [_FIELD_CARD_NO, _FIELD_CARD_PASSWORD],           # KB국민카드
    "0302": [_FIELD_CARD_NO, _FIELD_CARD_PASSWORD],           # 현대카드
    "0311": [_FIELD_BIRTH_DATE],                              # 롯데카드
}


# ─────────────────────────────────────────────────────────────
# 엔드포인트
# ─────────────────────────────────────────────────────────────

@router.get(
    "/form/{org_type}/{company_code}",
    response_model=FormResponse,
    summary="동적 로그인 폼 조회",
    description=(
        "기관 유형(`bank` 또는 `card`)과 기관 코드(`company_code`)를 받아 "
        "마이데이터 연동에 필요한 입력 필드 목록을 반환합니다."
    ),
)
async def get_form(
    org_type: Literal["bank", "card"],
    company_code: str,
) -> FormResponse:
    """
    기관별 동적 로그인 폼을 반환합니다.

    - 기본 필드: `id`(아이디), `password`(비밀번호)
    - 기관 코드에 따라 추가 필드가 동적으로 포함됩니다.

    Args:
        org_type: 기관 유형 (`"bank"` 또는 `"card"`)
        company_code: 4자리 CODEF 기관 코드 (예: `"0088"`)

    Returns:
        FormResponse: 표시할 폼 필드 목록
    """
    if org_type == "bank":
        extra = _BANK_EXTRA_FIELDS.get(company_code, [])
    elif org_type == "card":
        extra = _CARD_EXTRA_FIELDS.get(company_code, [])
    else:
        # Literal 타입이 FastAPI 레벨에서 검증하지만 방어 코드 추가
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"지원하지 않는 org_type: {org_type!r}. 'bank' 또는 'card' 만 허용합니다.",
        )

    return FormResponse(fields=_BASE_FIELDS + extra)
