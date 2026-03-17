# app/mcp/bank_tool.py

"""
은행 계좌 및 거래내역 MCP Tool.

이 파일은 FastMCP 인스턴스를 직접 import 하지 않습니다.
파일 하단의 setup(mcp) 함수가 ImportSupporter 에 의해 호출되며,
mcp 인스턴스를 주입받아 @mcp.tool() 데코레이터로 Tool 을 등록합니다.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional
import datetime

from sqlalchemy import select
from fastmcp.tools import tool

from app.core.config import settings, BANK_MAPPING
from app.core.security import decrypt_sensitive_data
from app.core.database import AsyncSessionFactory
from app.core.mcp_component import MCPComponent
from app.model.bank_account import BankAccount
from app.repository.bank_account_repository import BankAccountRepository
from app.repository.system_repository import SystemRepository
from app.schema.mcp_responses import (
    BankAccountListResponse,
    BankTransactionListResponse,
    BankAccountInfo,
    BankTransactionRecord,
    MCPErrorResponse,
)
from app.service.codef.client import CodefClient
from app.service.codef.property import DEMO_DOMAIN, API_DOMAIN, SANDBOX_DOMAIN

if TYPE_CHECKING:
    from fastmcp import FastMCP


logger = logging.getLogger(__name__)


class BankTool(MCPComponent):
    # ─────────────────────────────────────────────────────────────
    # 내부 헬퍼: DB 에서 is_mcp_enabled == True 인 계좌만 조회
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    async def _get_enabled_accounts() -> list[BankAccount]:
        """is_mcp_enabled == True 인 계좌 목록을 반환합니다."""
        repo = BankAccountRepository()
        repo.set_factory(AsyncSessionFactory)
        async with repo:
            result = await repo._session.execute(
                select(BankAccount).where(BankAccount.is_mcp_enabled.is_(True))
            )
            return result.scalars().all()


    @staticmethod
    async def _get_account_by_masked_no(masked_account_no: str) -> BankAccount | None:
        """마스킹된 계좌번호로 단건 조회합니다."""
        repo = BankAccountRepository()
        repo.set_factory(AsyncSessionFactory)
        async with repo:
            result = await repo._session.execute(
                select(BankAccount).where(
                    BankAccount.masked_account_no == masked_account_no
                )
            )
            return result.scalars().first()


    # ─────────────────────────────────────────────────────────────
    # CODEF 거래내역 조회 (실제 연동)
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    async def _fetch_real_bank_transactions(
        company_code: str,
        account: BankAccount,
        start_date: str,
        end_date: str,
    ) -> list[BankTransactionRecord]:
        """
        CODEF API를 호출하여 실제 은행 거래내역을 조회합니다.

        - DB의 codef_connected_id를 connected_id로 사용합니다.
        - encrypted_account_no를 복호화한 원본 번호를 account 파라미터로 전달합니다.
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

        # ── 계좌번호 복호화 (in-memory only) ─────────────────────
        if not account.encrypted_account_no:
            raise ValueError("암호화된 계좌번호가 없습니다. 데이터 동기화를 다시 수행해주세요.")

        try:
            real_account_no = decrypt_sensitive_data(account.encrypted_account_no)
        except Exception as e:
            logger.error("계좌번호 복호화 실패 — bank_code=%s", company_code)
            raise ValueError("계좌번호 복호화에 실패했습니다.") from e

        client = CodefClient(
            public_key_pem=settings.CODEF_PUBLIC_KEY,
            client_id=settings.CODEF_CLIENT_ID,
            client_secret=settings.CODEF_CLIENT_SECRET,
            base_url=base_url,
        )

        try:
            res = await client.bank_transaction_list(
                organization=company_code,
                connected_id=connected_id,          # DB의 codef_connected_id 사용
                account=real_account_no,            # 복호화된 원본 계좌번호
                start_date=start_date,              # 파라미터로 전달받은 시작일
                end_date=end_date,                  # 파라미터로 전달받은 종료일
            )
            if res.result.code != "CF-00000":
                logger.error("CODEF API 오류 — code=%s message=%s", res.result.code, res.result.message)
                raise ValueError(f"CODEF API Error: {res.result.message}")

            transactions: list[BankTransactionRecord] = []
            if res.data and res.data.res_tr_history_list:
                for item in res.data.res_tr_history_list:
                    transactions.append(BankTransactionRecord(
                        date=item.res_account_tr_date,
                        time=item.res_account_tr_time,
                        withdrawal=item.res_account_out,
                        deposit=item.res_account_in,
                        balance=item.res_after_tran_balance,
                        description1=item.res_account_desc1,
                        description2=item.res_account_desc2,
                        description3=item.res_account_desc3,
                        description4=item.res_account_desc4,
                    ))
            return transactions
        except Exception as e:
            logger.error("[_fetch_real_bank_transactions] 조회 실패 — bank_code=%s", company_code)
            raise
        finally:
            await client.close()

    @tool()
    async def get_bank_transactions(
        self, 
        masked_account_no: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> BankTransactionListResponse | MCPErrorResponse:
        """
        특정 은행 계좌의 거래내역을 조회합니다.

        DB 에서 해당 계좌를 찾지 못하거나 is_mcp_enabled == False 인 경우
        에러 응답을 반환합니다.

        Args:
            masked_account_no: 마스킹된 계좌번호 (예: 110-***-***789)
            start_date: 조회 시작일 (YYYYMMDD, 기본값: 30일 전)
            end_date: 조회 종료일 (YYYYMMDD, 기본값: 오늘)

        Returns:
            BankTransactionListResponse | MCPErrorResponse: 타입 안전한 거래내역 응답 또는 에러 응답
        """
        # 날짜 파라미터 기본값 설정
        if end_date is None:
            end_date = datetime.date.today().strftime("%Y%m%d")
        if start_date is None:
            start_date_obj = datetime.date.today() - datetime.timedelta(days=30)
            start_date = start_date_obj.strftime("%Y%m%d")

        account = await self._get_account_by_masked_no(masked_account_no)

        if account is None or not account.is_mcp_enabled:
            return MCPErrorResponse(
                message="접근 권한이 없거나 존재하지 않는 정보입니다.",
                error_code="ACCOUNT_NOT_FOUND_OR_DISABLED"
            )

        try:
            transactions = await self._fetch_real_bank_transactions(
                company_code=account.bank_code,
                account=account,
                start_date=start_date,
                end_date=end_date,
            )

            # 계좌 정보 구성
            bank_name = BANK_MAPPING.get(account.bank_code, f"은행({account.bank_code})")
            account_info = BankAccountInfo(
                bank_name=bank_name,
                company_code=account.bank_code,
                masked_account_no=account.masked_account_no,
                account_name=account.account_name,
                account_type=account.account_type,
            )

            return BankTransactionListResponse(
                account_info=account_info,
                transactions=transactions,
                total_count=len(transactions)
            )

        except Exception as e:
            logger.error("거래내역 조회 실패: %s", e)
            return MCPErrorResponse(
                message=f"금융기관 통신 지연으로 내역을 불러오지 못했습니다. ({str(e)})",
                error_code="CODEF_API_ERROR"
            )

    @tool()
    async def get_enabled_bank_accounts(self) -> BankAccountListResponse:
        """
        MCP 에이전트에게 노출된 은행 계좌 목록을 반환합니다.

        is_mcp_enabled 가 True 인 계좌만 조회되며,
        민감 정보 보호를 위해 마스킹된 정보만 포함됩니다.

        Returns:
            BankAccountListResponse: 타입 안전한 은행 계좌 목록 응답
        """
        accounts = await self._get_enabled_accounts()
        account_infos = []

        for account in accounts:
            # 은행명 매핑 (코드 → 한글명)
            bank_name = BANK_MAPPING.get(account.bank_code, f"은행({account.bank_code})")

            account_infos.append(BankAccountInfo(
                bank_name=bank_name,
                company_code=account.bank_code,
                masked_account_no=account.masked_account_no,
                account_name=account.account_name,
                account_type=account.account_type,
            ))

        return BankAccountListResponse(accounts=account_infos)

    logger.info("은행 Tool 등록 완료: get_enabled_bank_accounts, get_bank_transactions")


# ─────────────────────────────────────────────────────────────
# ImportSupporter 진입점
# ─────────────────────────────────────────────────────────────

def setup(mcp: FastMCP) -> None:
    """
    FastMCP 인스턴스를 주입받아 은행 관련 Tool 을 등록합니다.

    ImportSupporter(mcp).load_modules("app.mcp") 에 의해 자동 호출됩니다.

    Args:
        mcp: app/core/mcp_middleware.py 에서 생성된 FastMCP 인스턴스
    """
    BankTool.register_mcp(mcp)
