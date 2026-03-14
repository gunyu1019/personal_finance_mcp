# src/api/finance/sync.py

"""
마이데이터 동기화 API.

CODEF 마이데이터를 조회하여 해시/마스킹 처리 후 DB에 저장합니다.
관리자 인증이 필요하며, 원본 번호는 저장 직후 메모리에서 즉시 파기됩니다.
"""

import logging
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.auth import get_current_admin
from src.core.database import AsyncSessionFactory
from src.core.security import hash_data, mask_account_no, mask_card_no
from src.dto.bank_account_dto import BankAccountUpsertData
from src.dto.card_account_dto import CardAccountUpsertData
from src.repository.bank_account_repository import BankAccountRepository
from src.repository.card_account_repository import CardAccountRepository
from src.repository.system_repository import SystemRepository
from src.schema.finance import SyncRequest, SyncResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/finance", tags=["finance"])

# ─────────────────────────────────────────────────────────────
# CODEF 모킹 레이어
# ─────────────────────────────────────────────────────────────

class _MockBankRawAccount:
    """CODEF bank_account_list 응답의 개별 계좌를 모사합니다."""

    def __init__(self, raw_account_no: str) -> None:
        self.raw_account_no = raw_account_no


class _MockCardRawAccount:
    """CODEF card_account_list 응답의 개별 카드를 모사합니다."""

    def __init__(self, raw_card_no: str) -> None:
        self.raw_card_no = raw_card_no


async def _fetch_bank_accounts(
    company_code: str,
    login_data: dict[str, Any],
) -> list[_MockBankRawAccount]:
    """
    [모킹] CODEF bank_account_list 를 호출하여 은행 계좌 목록을 가져옵니다.

    실제 연동 시 이 함수 내부를 아래와 같이 대체하세요::

        from src.service.codef.client import CodefClient
        from src.core.config import settings

        client = CodefClient(
            public_key_pem=settings.CODEF_PUBLIC_KEY,
            client_id=settings.CODEF_CLIENT_ID,
            client_secret=settings.CODEF_CLIENT_SECRET,
        )
        result = await client.bank_account_list(
            organization=company_code,
            connected_id=login_data["connected_id"],
            birth_date=login_data.get("birthDate"),
            withdraw_account_no=login_data.get("withdrawAccountNo"),
            withdraw_account_password=login_data.get("withdrawAccountPassword"),
        )
        accounts = result.data.res_deposit_trust or []
        return [_MockBankRawAccount(raw_account_no=a.res_account) for a in accounts]

    Args:
        company_code: CODEF 기관 코드
        login_data: 폼 입력 데이터

    Returns:
        원본 계좌번호를 담은 mock 객체 리스트
    """
    logger.info(
        "[MOCK] bank_account_list 호출 — company_code=%s login_data_keys=%s",
        company_code,
        list(login_data.keys()),
    )
    # 모킹: 빈 리스트 반환 (실제 연동 시 위 주석 코드로 대체)
    return []


async def _fetch_card_accounts(
    company_code: str,
    login_data: dict[str, Any],
) -> list[_MockCardRawAccount]:
    """
    [모킹] CODEF card_account_list 를 호출하여 카드 목록을 가져옵니다.

    실제 연동 시 이 함수 내부를 아래와 같이 대체하세요::

        from src.service.codef.client import CodefClient
        from src.core.config import settings

        client = CodefClient(
            public_key_pem=settings.CODEF_PUBLIC_KEY,
            client_id=settings.CODEF_CLIENT_ID,
            client_secret=settings.CODEF_CLIENT_SECRET,
        )
        result = await client.card_account_list(
            organization=company_code,
            connected_id=login_data["connected_id"],
            birth_date=login_data.get("birthDate"),
            card_no=login_data.get("cardNo"),
            card_password=login_data.get("cardPassword"),
        )
        cards = result.data if isinstance(result.data, list) else [result.data]
        return [_MockCardRawAccount(raw_card_no=c.res_card_no) for c in cards]

    Args:
        company_code: CODEF 카드사 코드
        login_data: 폼 입력 데이터

    Returns:
        원본 카드번호를 담은 mock 객체 리스트
    """
    logger.info(
        "[MOCK] card_account_list 호출 — company_code=%s login_data_keys=%s",
        company_code,
        list(login_data.keys()),
    )
    # 모킹: 빈 리스트 반환 (실제 연동 시 위 주석 코드로 대체)
    return []


# ─────────────────────────────────────────────────────────────
# 엔드포인트
# ─────────────────────────────────────────────────────────────

@router.post(
    "/sync",
    response_model=SyncResponse,
    status_code=status.HTTP_200_OK,
    summary="마이데이터 동기화",
    description=(
        "CODEF 마이데이터를 조회하여 해시/마스킹 처리 후 DB에 저장합니다. "
        "관리자 인증(Bearer JWT)이 필요합니다. "
        "원본 계좌/카드 번호는 DB 저장 직후 메모리에서 즉시 파기됩니다."
    ),
)
async def sync_finance_data(
    body: SyncRequest,
    _admin: Annotated[str, Depends(get_current_admin)],
) -> SyncResponse:
    """
    마이데이터 동기화 엔드포인트.

    흐름:
    1. CODEF 모킹 호출 → 원본 계좌/카드 리스트 획득
    2. SystemRepository 로 hash_salt 조회
    3. 원본 번호를 hash_data() + mask_*() 처리
    4. BankAccountRepository 또는 CardAccountRepository 로 upsert_many
    5. 원본 번호 메모리 파기 (del)
    6. 저장 완료 건수 반환

    Args:
        body: 동기화 요청 본문
        _admin: get_current_admin 의존성 (관리자 인증 검증용)

    Returns:
        SyncResponse: 동기화 결과
    """
    if body.org_type == "bank":
        synced_count = await _sync_bank(body.company_code, body.login_data)
    elif body.org_type == "card":
        synced_count = await _sync_card(body.company_code, body.login_data)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"지원하지 않는 org_type: {body.org_type!r}",
        )

    logger.info(
        "마이데이터 동기화 완료 — org_type=%s company_code=%s synced=%d",
        body.org_type,
        body.company_code,
        synced_count,
    )
    return SyncResponse(
        org_type=body.org_type,
        company_code=body.company_code,
        synced_count=synced_count,
    )


# ─────────────────────────────────────────────────────────────
# 내부 동기화 헬퍼
# ─────────────────────────────────────────────────────────────

async def _get_hash_salt() -> str:
    """
    SystemRepository 를 통해 DB 에서 hash_salt 를 조회합니다.

    Returns:
        str: 64자 hex 솔트 문자열
    """
    system_repo = SystemRepository()
    system_repo.set_factory(AsyncSessionFactory)
    async with system_repo as repo:
        config = await repo.get_or_create_config()
        return config.hash_salt


async def _sync_bank(company_code: str, login_data: dict[str, Any]) -> int:
    """
    은행 계좌 동기화 내부 로직.

    Args:
        company_code: CODEF 기관 코드
        login_data: 폼 입력 데이터

    Returns:
        int: upsert 된 계좌 건수
    """
    raw_accounts = await _fetch_bank_accounts(company_code, login_data)
    if not raw_accounts:
        return 0

    salt = await _get_hash_salt()

    upsert_records: list[BankAccountUpsertData] = []
    for raw in raw_accounts:
        raw_no: str = raw.raw_account_no
        try:
            record = BankAccountUpsertData(
                bank_code=company_code,
                hashed_account_no=hash_data(raw_no, salt),
                masked_account_no=mask_account_no(raw_no),
            )
            upsert_records.append(record)
        finally:
            # 보안: 원본 번호를 메모리에서 즉시 파기
            del raw_no

    bank_repo = BankAccountRepository()
    bank_repo.set_factory(AsyncSessionFactory)
    async with bank_repo as repo:
        results = await repo.upsert_many(upsert_records)

    return len(results)


async def _sync_card(company_code: str, login_data: dict[str, Any]) -> int:
    """
    카드 동기화 내부 로직.

    Args:
        company_code: CODEF 카드사 코드
        login_data: 폼 입력 데이터

    Returns:
        int: upsert 된 카드 건수
    """
    raw_cards = await _fetch_card_accounts(company_code, login_data)
    if not raw_cards:
        return 0

    salt = await _get_hash_salt()

    upsert_records: list[CardAccountUpsertData] = []
    for raw in raw_cards:
        raw_no: str = raw.raw_card_no
        try:
            record = CardAccountUpsertData(
                card_code=company_code,
                hashed_card_no=hash_data(raw_no, salt),
                masked_card_no=mask_card_no(raw_no),
            )
            upsert_records.append(record)
        finally:
            # 보안: 원본 번호를 메모리에서 즉시 파기
            del raw_no

    card_repo = CardAccountRepository()
    card_repo.set_factory(AsyncSessionFactory)
    async with card_repo as repo:
        results = await repo.upsert_many(upsert_records)

    return len(results)
