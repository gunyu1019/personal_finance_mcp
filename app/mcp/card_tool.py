# app/mcp/card_tool.py

"""
카드 목록 및 승인내역 MCP Tool.

이 파일은 FastMCP 인스턴스를 직접 import 하지 않습니다.
파일 하단의 setup(mcp) 함수가 ImportSupporter 에 의해 호출되며,
mcp 인스턴스를 주입받아 @mcp.tool() 데코레이터로 Tool 을 등록합니다.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional
import datetime

from fastmcp.tools import tool

from app.core.config import settings
from app.service.codef.card.company import CardCompany
from app.core.security import decrypt_sensitive_data
from app.core.mcp_component import MCPComponent
from app.model.card_account import CardAccount
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


class CardTool(MCPComponent):
    """
    카드 관련 MCP Tool.
    
    의존성 주입 패턴을 적용하여 Repository와 외부 서비스 클라이언트를 주입받아 사용합니다.
    이를 통해 결합도를 낮추고 테스트 용이성을 향상시킵니다.
    """

    def __init__(self, card_repo_factory=None, system_repo_factory=None, codef_client_factory=None):
        """
        의존성 주입을 위한 생성자.
        
        Args:
            card_repo_factory: CardAccountRepository 생성 팩토리
            system_repo_factory: SystemRepository 생성 팩토리  
            codef_client_factory: CodefClient 생성 팩토리
        """
        # DI 컨테이너에서 의존성을 주입받음 (기본값은 런타임에서 설정)
        self._card_repo_factory = card_repo_factory
        self._system_repo_factory = system_repo_factory
        self._codef_client_factory = codef_client_factory

    async def _get_enabled_cards(self) -> list[CardAccount]:
        """
        MCP에 노출 허용된 카드 목록을 반환합니다.
        
        DI 적용: 주입받은 Repository 팩토리를 사용하여 결합도 감소
        """
        if self._card_repo_factory:
            async with self._card_repo_factory() as repo:
                return await repo.get_enabled_accounts()
        
        # 기본 구현 (하위 호환성)
        from app.core.database import AsyncSessionFactory
        from app.repository.card_account_repository import CardAccountRepository
        
        repo = CardAccountRepository()
        repo.set_factory(AsyncSessionFactory)
        async with repo:
            return await repo.get_enabled_accounts()

    async def _get_card_by_masked_no(self, masked_card_no: str) -> CardAccount | None:
        """
        마스킹된 카드번호로 단건 조회합니다.
        
        DI 적용: 주입받은 Repository 팩토리를 사용하여 결합도 감소
        """
        if self._card_repo_factory:
            async with self._card_repo_factory() as repo:
                return await repo.get_by_masked_card_no(masked_card_no)
        
        # 기본 구현 (하위 호환성)
        from app.core.database import AsyncSessionFactory
        from app.repository.card_account_repository import CardAccountRepository
        
        repo = CardAccountRepository()
        repo.set_factory(AsyncSessionFactory)
        async with repo:
            return await repo.get_by_masked_card_no(masked_card_no)


    # ─────────────────────────────────────────────────────────────
    # CODEF 카드 승인내역 조회 (실제 연동)
    # ─────────────────────────────────────────────────────────────

    async def _fetch_real_card_transactions(
        self,
        company_code: str,
        card: CardAccount,
        start_date: str,
        end_date: str,
    ) -> list[CardTransactionRecord]:
        """
        CODEF API를 호출하여 실제 카드 승인내역을 조회합니다.

        DI 적용: 주입받은 SystemRepository와 CodefClient 팩토리를 사용하여 
        외부 의존성과의 결합도를 낮춤으로써 테스트 용이성 및 유지보수성 향상

        - DB의 codef_connected_id를 connected_id로 사용합니다.
        - encrypted_card_no를 복호화한 원본 번호를 card_no로 전달합니다.
        - 비밀번호 필수 카드사는 encrypted_card_password도 복호화하여 전달합니다.
        - 복호화된 민감 정보는 API 호출 인자로만 사용되며 로그·반환값에 포함되지 않습니다.
        """
        # ── connected_id 조회 (DI 적용) ───────────────────────────────────
        connected_id = None
        if self._system_repo_factory:
            async with self._system_repo_factory() as system_repo:
                connected_id = await system_repo.get_connected_id()
        else:
            # 기본 구현 (하위 호환성)
            from app.core.database import AsyncSessionFactory
            from app.repository.system_repository import SystemRepository
            
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

        real_card_no = card.encrypted_card_no

        # ── 비밀번호 필수 카드사: 저장된 카드 비밀번호 복호화 ────
        real_card_password: str | None = None
        card_company = CardCompany.from_code(company_code)
        if card_company and card_company.requires_password() and card.encrypted_card_password:
            try:
                real_card_password = decrypt_sensitive_data(card.encrypted_card_password)
            except Exception as e:
                logger.error("카드 비밀번호 복호화 실패 — card_code=%s", company_code)
                raise ValueError("카드 비밀번호 복호화에 실패했습니다.") from e

        # ── CODEF API 호출 (DI 적용) ────────────────────────────────────
        if self._codef_client_factory:
            async with self._codef_client_factory() as client:
                return await self._execute_card_api_call(
                    client, company_code, connected_id, start_date, end_date, 
                    real_card_no, real_card_password
                )
        else:
            # 기본 구현 (하위 호환성)
            if settings.CODEF_MODE == "live":
                base_url = API_DOMAIN
            elif settings.CODEF_MODE == "sandbox":
                base_url = SANDBOX_DOMAIN
            else:
                base_url = DEMO_DOMAIN

            client = CodefClient(
                public_key_pem=settings.CODEF_PUBLIC_KEY,
                client_id=settings.CODEF_CLIENT_ID,
                client_secret=settings.CODEF_CLIENT_SECRET,
                base_url=base_url,
            )

            try:
                return await self._execute_card_api_call(
                    client, company_code, connected_id, start_date, end_date, 
                    real_card_no, real_card_password
                )
            finally:
                await client.close()

    async def _execute_card_api_call(
        self,
        client: CodefClient,
        company_code: str,
        connected_id: str,
        start_date: str,
        end_date: str,
        real_card_no: str,
        real_card_password: str | None,
    ) -> list[CardTransactionRecord]:
        """
        실제 CODEF API 호출 로직을 분리하여 중복 제거 및 테스트 용이성 향상
        """
        try:
            res = await client.card_approval_list(
                organization=company_code,
                connected_id=connected_id,          # DB의 codef_connected_id 사용
                start_date=start_date,              # 파라미터로 전달받은 시작일
                end_date=end_date,                  # 파라미터로 전달받은 종료일
                card_no=real_card_no,               # 복호화된 원본 카드번호
                card_password=real_card_password,   # 복호화된 카드 비밀번호 (필수 카드사만 non-None)
            )
            if res.result.code != "CF-00000":
                logger.error("CODEF API 오류 — code=%s message=%s", res.result.code, res.result.message)
                raise ValueError(f"CODEF API Error: {res.result.message}")

            transactions: list[CardTransactionRecord] = []
            if res.data:
                data_list = res.data if isinstance(res.data, list) else [res.data]
                transactions = [
                    CardTransactionRecord(
                        date=item.res_used_date,
                        time=item.res_used_time or "",
                        merchant=item.res_member_store_name or "",
                        amount=item.res_used_amount,
                        currency=item.res_account_currency,
                        status="취소" if item.res_cancel_yn == "1" else "승인",
                        installment=item.res_installment_month or "일시불",
                    )
                    for item in data_list
                ]
            return transactions
        except Exception as e:
            logger.error("[_fetch_real_card_transactions] 조회 실패 — card_code=%s", company_code)
            raise

    @tool()
    async def get_enabled_cards(self) -> CardAccountListResponse:
        """
        MCP 에이전트에게 노출된 카드 목록을 반환합니다.

        is_mcp_enabled 가 True 인 카드만 조회되며,
        민감 정보 보호를 위해 마스킹된 정보만 포함됩니다.

        Returns:
            CardAccountListResponse: 타입 안전한 카드 목록 응답
        """
        cards = await self._get_enabled_cards()
        card_infos = []

        for card in cards:
            # 카드사명 매핑 (Enum 기반으로 타입 안전하게)
            card_company = CardCompany.get_korean_name(card.card_code)

            card_infos.append(CardAccountInfo(
                card_company=card_company,
                company_code=card.card_code,
                masked_card_no=card.masked_card_no,
                card_name=card.card_name,
                card_image_url=card.card_image_url,
            ))

        return CardAccountListResponse(cards=card_infos)

    @tool()
    async def get_card_transactions(
        self,
        masked_card_no: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> CardTransactionListResponse | MCPErrorResponse:
        """
        특정 카드의 승인내역을 조회합니다.

        DB 에서 해당 카드를 찾지 못하거나 is_mcp_enabled == False 인 경우
        에러 응답을 반환합니다.

        Args:
            masked_card_no: 마스킹된 카드번호 (예: 1234-****-****-5678)
            start_date: 조회 시작일 (YYYYMMDD, 기본값: 30일 전)
            end_date: 조회 종료일 (YYYYMMDD, 기본값: 오늘)

        Returns:
            CardTransactionListResponse | MCPErrorResponse: 타입 안전한 승인내역 응답 또는 에러 응답
        """
        # 날짜 파라미터 기본값 설정
        if end_date is None:
            end_date = datetime.date.today().strftime("%Y%m%d")
        if start_date is None:
            start_date_obj = datetime.date.today() - datetime.timedelta(days=30)
            start_date = start_date_obj.strftime("%Y%m%d")

        card = await self._get_card_by_masked_no(masked_card_no)

        if card is None or not card.is_mcp_enabled:
            return MCPErrorResponse(
                message="접근 권한이 없거나 존재하지 않는 정보입니다.",
                error_code="CARD_NOT_FOUND_OR_DISABLED"
            )

        try:
            transactions = await self._fetch_real_card_transactions(
                company_code=card.card_code,
                card=card,
                start_date=start_date,
                end_date=end_date,
            )

            # 카드 정보 구성 (Enum 기반으로 타입 안전하게)
            card_company = CardCompany.get_korean_name(card.card_code)
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


# ─────────────────────────────────────────────────────────────
# ImportSupporter 진입점
# ─────────────────────────────────────────────────────────────

def setup(mcp: FastMCP) -> None:
    """
    FastMCP 인스턴스를 주입받아 카드 관련 Tool 을 등록합니다.

    의존성 주입 패턴을 적용하여 Repository와 CodefClient 팩토리를 주입합니다.
    이를 통해 결합도를 낮추고 테스트 용이성을 향상시킵니다.

    ImportSupporter(mcp).load_modules("app.mcp") 에 의해 자동 호출됩니다.

    Args:
        mcp: app/core/mcp_middleware.py 에서 생성된 FastMCP 인스턴스
    """
    from app.core.mcp_deps import (
        get_card_account_repository,
        get_system_repository, 
        get_codef_client
    )

    # DI 컨테이너 설정: 의존성 팩토리들을 주입하여 CardTool 인스턴스 생성
    CardTool.register_mcp(
        mcp,
        card_repo_factory=get_card_account_repository,
        system_repo_factory=get_system_repository,
        codef_client_factory=get_codef_client
    )
