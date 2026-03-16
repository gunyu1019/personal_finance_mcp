# app/mcp/card_tool.py

"""
카드 목록 및 승인내역 MCP Tool.

이 파일은 FastMCP 인스턴스를 직접 import 하지 않습니다.
파일 하단의 setup(mcp) 함수가 ImportSupporter 에 의해 호출되며,
mcp 인스턴스를 주입받아 @mcp.tool() 데코레이터로 Tool 을 등록합니다.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
import datetime

from sqlalchemy import select

from app.core.config import settings, CARD_MAPPING, CARD_PASSWORD_REQUIRED_CODES
from app.core.crypto import decrypt_sensitive_data
from app.core.database import AsyncSessionFactory
from app.model.card_account import CardAccount
from app.repository.card_account_repository import CardAccountRepository
from app.repository.system_repository import SystemRepository
from app.schema.mcp_responses import (
    CardAccountListResponse,
    CardTransactionListResponse,
    CardAccountInfo,
    CardTransactionRecord,
    MCPErrorResponse,
)
from app.service.codef.client import CodefClient
from app.service.codef.property import DEMO_DOMAIN, API_DOMAIN, SANDBOX_DOMAIN

if TYPE_CHECKING:
    from fastmcp import FastMCP


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 내부 헬퍼: DB 에서 is_mcp_enabled == True 인 카드만 조회
# ─────────────────────────────────────────────────────────────

async def _get_enabled_cards() -> list[CardAccount]:
    """is_mcp_enabled == True 인 카드 목록을 반환합니다."""
    repo = CardAccountRepository()
    repo.set_factory(AsyncSessionFactory)
    async with repo:
        result = await repo._session.execute(
            select(CardAccount).where(CardAccount.is_mcp_enabled.is_(True))
        )
        return result.scalars().all()


async def _get_card_by_masked_no(masked_card_no: str) -> CardAccount | None:
    """마스킹된 카드번호로 단건 조회합니다."""
    repo = CardAccountRepository()
    repo.set_factory(AsyncSessionFactory)
    async with repo:
        result = await repo._session.execute(
            select(CardAccount).where(
                CardAccount.masked_card_no == masked_card_no
            )
        )
        return result.scalars().first()


# ─────────────────────────────────────────────────────────────
# CODEF 카드 승인내역 조회 (실제 연동)
# ─────────────────────────────────────────────────────────────

async def _fetch_real_card_transactions(
    company_code: str,
    card: CardAccount,
) -> list[CardTransactionRecord]:
    """
    CODEF API를 호출하여 실제 카드 승인내역을 조회합니다.

    - DB의 codef_connected_id를 connected_id로 사용합니다.
    - encrypted_card_no를 복호화한 원본 번호를 card_no로 전달합니다.
    - CARD_PASSWORD_REQUIRED_CODES 카드사는 encrypted_card_password도 복호화하여 전달합니다.
    - 복호화된 민감 정보는 API 호출 인자로만 사용되며 로그·반환값에 포함되지 않습니다.
    """
    if settings.CODEF_MODE == "live":
        base_url = API_DOMAIN
    elif settings.CODEF_MODE == "sandbox":
        base_url = SANDBOX_DOMAIN
    else:
        base_url = DEMO_DOMAIN

    # ── connected_id 조회 ───────────────────────────────────
    system_repo = SystemRepository()
    system_repo.set_factory(AsyncSessionFactory)
    async with system_repo as repo:
        connected_id = await repo.get_connected_id()

    if not connected_id:
        raise ValueError(
            "Codef connected_id가 등록되어 있지 않습니다. "
            "설정 페이지에서 기관 연결을 먼저 수행해 주세요."
        )

    # ── 카드번호 복호화 (in-memory only) ─────────────────────
    if not card.encrypted_card_no:
        raise ValueError("암호화된 카드번호가 없습니다. 데이터 동기화를 다시 수행해주세요.")

    try:
        real_card_no = decrypt_sensitive_data(card.encrypted_card_no)
    except Exception as e:
        logger.error("카드번호 복호화 실패 — card_code=%s", company_code)
        raise ValueError("카드번호 복호화에 실패했습니다.") from e

    # ── 비밀번호 필수 카드사: 저장된 카드 비밀번호 복호화 ────
    real_card_password: str | None = None
    if company_code in CARD_PASSWORD_REQUIRED_CODES and card.encrypted_card_password:
        try:
            real_card_password = decrypt_sensitive_data(card.encrypted_card_password)
        except Exception as e:
            logger.error("카드 비밀번호 복호화 실패 — card_code=%s", company_code)
            raise ValueError("카드 비밀번호 복호화에 실패했습니다.") from e

    client = CodefClient(
        public_key_pem=settings.CODEF_PUBLIC_KEY,
        client_id=settings.CODEF_CLIENT_ID,
        client_secret=settings.CODEF_CLIENT_SECRET,
        base_url=base_url,
    )

    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=30)

    try:
        res = await client.card_approval_list(
            organization=company_code,
            connected_id=connected_id,          # DB의 codef_connected_id 사용
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            card_no=real_card_no,               # 복호화된 원본 카드번호
            card_password=real_card_password,   # 복호화된 카드 비밀번호 (필수 카드사만 non-None)
        )
        if res.result.code != "CF-00000":
            logger.error("CODEF API 오류 — code=%s message=%s", res.result.code, res.result.message)
            raise ValueError(f"CODEF API Error: {res.result.message}")

        transactions: list[CardTransactionRecord] = []
        if res.data:
            data_list = res.data if isinstance(res.data, list) else [res.data]
            for item in data_list:
                transactions.append(CardTransactionRecord(
                    date=item.res_used_date,
                    time=item.res_used_time or "",
                    merchant=item.res_member_store_name or "",
                    amount=item.res_used_amount,
                    currency=item.res_account_currency,
                    status="취소" if item.res_cancel_yn == "1" else "승인",
                    installment=item.res_installment_month or "일시불",
                ))
        return transactions
    except Exception as e:
        logger.error("[_fetch_real_card_transactions] 조회 실패 — card_code=%s", company_code)
        raise
    finally:
        await client.close()


# ─────────────────────────────────────────────────────────────
# ImportSupporter 진입점
# ─────────────────────────────────────────────────────────────

def setup(mcp: FastMCP) -> None:
    """
    FastMCP 인스턴스를 주입받아 카드 관련 Tool 을 등록합니다.

    ImportSupporter(mcp).load_modules("app.mcp") 에 의해 자동 호출됩니다.

    Args:
        mcp: app/core/mcp_middleware.py 에서 생성된 FastMCP 인스턴스
    """

    @mcp.tool()
    async def get_enabled_cards() -> CardAccountListResponse:
        """
        MCP 에이전트에게 노출된 카드 목록을 반환합니다.

        is_mcp_enabled 가 True 인 카드만 조회되며,
        민감 정보 보호를 위해 마스킹된 정보만 포함됩니다.

        Returns:
            CardAccountListResponse: 타입 안전한 카드 목록 응답
        """
        cards = await _get_enabled_cards()
        card_infos = []
        
        for card in cards:
            # 카드사명 매핑 (코드 → 한글명)
            card_company = CARD_MAPPING.get(card.card_code, f"카드사({card.card_code})")
            
            card_infos.append(CardAccountInfo(
                card_company=card_company,
                company_code=card.card_code,
                masked_card_no=card.masked_card_no,
                card_name=card.card_name,
                card_image_url=card.card_image_url,
            ))
        
        return CardAccountListResponse(cards=card_infos)

    @mcp.tool()
    async def get_card_transactions(masked_card_no: str) -> CardTransactionListResponse | MCPErrorResponse:
        """
        특정 카드의 최근 30일 승인내역을 조회합니다.

        DB 에서 해당 카드를 찾지 못하거나 is_mcp_enabled == False 인 경우
        에러 응답을 반환합니다.

        Args:
            masked_card_no: 마스킹된 카드번호 (예: 1234-****-****-5678)

        Returns:
            CardTransactionListResponse | MCPErrorResponse: 타입 안전한 승인내역 응답 또는 에러 응답
        """
        card = await _get_card_by_masked_no(masked_card_no)

        if card is None or not card.is_mcp_enabled:
            return MCPErrorResponse(
                message="접근 권한이 없거나 존재하지 않는 정보입니다.",
                error_code="CARD_NOT_FOUND_OR_DISABLED"
            )

        try:
            transactions = await _fetch_real_card_transactions(
                company_code=card.card_code,
                card=card,
            )
            
            # 카드 정보 구성
            card_company = CARD_MAPPING.get(card.card_code, f"카드사({card.card_code})")
            card_info = CardAccountInfo(
                card_company=card_company,
                company_code=card.card_code,
                masked_card_no=card.masked_card_no,
                card_name=card.card_name,
                card_image_url=card.card_image_url,
            )
            
            return CardTransactionListResponse(
                card_info=card_info,
                transactions=transactions,
                total_count=len(transactions)
            )
            
        except Exception as e:
            logger.error("승인내역 조회 실패: %s", e)
            return MCPErrorResponse(
                message=f"금융기관 통신 지연으로 내역을 불러오지 못했습니다. ({str(e)})",
                error_code="CODEF_API_ERROR"
            )

    logger.info("카드 Tool 등록 완료: get_enabled_cards, get_card_transactions")
