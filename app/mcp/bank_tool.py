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

from fastmcp.tools import tool

from app.core.config import settings, BANK_MAPPING
from app.service.codef.bank.company import BankCompany
from app.core.security import decrypt_sensitive_data
from app.core.mcp_component import MCPComponent
from app.model.bank_account import BankAccount
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
    """
    은행 관련 MCP Tool.
    
    의존성 주입 패턴을 적용하여 Repository와 외부 서비스 클라이언트를 주입받아 사용합니다.
    이를 통해 결합도를 낮추고 테스트 용이성을 향상시킵니다.
    """

    def __init__(self, bank_repo_factory=None, system_repo_factory=None, codef_client_factory=None):
        """
        의존성 주입을 위한 생성자.
        
        Args:
            bank_repo_factory: BankAccountRepository 생성 팩토리
            system_repo_factory: SystemRepository 생성 팩토리  
            codef_client_factory: CodefClient 생성 팩토리
        """
        # DI 컨테이너에서 의존성을 주입받음 (기본값은 런타임에서 설정)
        self._bank_repo_factory = bank_repo_factory
        self._system_repo_factory = system_repo_factory
        self._codef_client_factory = codef_client_factory

    async def _get_enabled_accounts(self) -> list[BankAccount]:
        """
        MCP에 노출 허용된 계좌 목록을 반환합니다.
        
        DI 적용: 주입받은 Repository 팩토리를 사용하여 결합도 감소
        """
        if self._bank_repo_factory:
            async with self._bank_repo_factory() as repo:
                return await repo.get_enabled_accounts()
        
        # 기본 구현 (하위 호환성)
        from app.core.database import AsyncSessionFactory
        from app.repository.bank_account_repository import BankAccountRepository
        
        repo = BankAccountRepository()
        repo.set_factory(AsyncSessionFactory)
        async with repo:
            return await repo.get_enabled_accounts()

    async def _get_account_by_masked_no(self, masked_account_no: str) -> BankAccount | None:
        """
        마스킹된 계좌번호로 단건 조회합니다.
        
        DI 적용: 주입받은 Repository 팩토리를 사용하여 결합도 감소
        """
        if self._bank_repo_factory:
            async with self._bank_repo_factory() as repo:
                return await repo.get_by_masked_account_no(masked_account_no)
        
        # 기본 구현 (하위 호환성)
        from app.core.database import AsyncSessionFactory
        from app.repository.bank_account_repository import BankAccountRepository
        
        repo = BankAccountRepository()
        repo.set_factory(AsyncSessionFactory)
        async with repo:
            return await repo.get_by_masked_account_no(masked_account_no)


    # ─────────────────────────────────────────────────────────────
    # CODEF 거래내역 조회 (실제 연동)
    # ─────────────────────────────────────────────────────────────
    async def _fetch_real_bank_transactions(
        self,
        company_code: str,
        account: BankAccount,
        start_date: str,
        end_date: str,
    ) -> list[BankTransactionRecord]:
        """
        CODEF API를 호출하여 실제 은행 거래내역을 조회합니다.

        DI 적용: 주입받은 SystemRepository와 CodefClient 팩토리를 사용하여 
        외부 의존성과의 결합도를 낮춤으로써 테스트 용이성 및 유지보수성 향상

        - DB의 codef_connected_id를 connected_id로 사용합니다.
        - encrypted_account_no를 복호화한 원본 번호를 account 파라미터로 전달합니다.
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

        # ── 계좌번호 복호화 (in-memory only) ─────────────────────
        if not account.encrypted_account_no:
            raise ValueError("암호화된 계좌번호가 없습니다. 데이터 동기화를 다시 수행해주세요.")

        try:
            real_account_no = decrypt_sensitive_data(account.encrypted_account_no)
        except Exception as e:
            logger.error("계좌번호 복호화 실패 — bank_code=%s", company_code)
            raise ValueError("계좌번호 복호화에 실패했습니다.") from e

        # ── CODEF API 호출 (DI 적용) ────────────────────────────────────
        if self._codef_client_factory:
            async with self._codef_client_factory() as client:
                return await self._execute_bank_api_call(
                    client, company_code, connected_id, real_account_no, start_date, end_date
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
                return await self._execute_bank_api_call(
                    client, company_code, connected_id, real_account_no, start_date, end_date
                )
            finally:
                await client.close()

    async def _execute_bank_api_call(
        self,
        client: CodefClient,
        company_code: str,
        connected_id: str,
        real_account_no: str,
        start_date: str,
        end_date: str,
    ) -> list[BankTransactionRecord]:
        """
        실제 CODEF API 호출 로직을 분리하여 중복 제거 및 테스트 용이성 향상
        """
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
                transactions = [
                    BankTransactionRecord(
                        date=item.res_account_tr_date,
                        time=item.res_account_tr_time,
                        withdrawal=item.res_account_out,
                        deposit=item.res_account_in,
                        balance=item.res_after_tran_balance,
                        description1=item.res_account_desc1,
                        description2=item.res_account_desc2,
                        description3=item.res_account_desc3,
                        description4=item.res_account_desc4,
                    )
                    for item in res.data.res_tr_history_list
                ]
            return transactions
        except Exception as e:
            logger.error("[_fetch_real_bank_transactions] 조회 실패 — bank_code=%s", company_code)
            raise

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

            # 계좌 정보 구성 (Enum 기반으로 타입 안전하게)
            bank_name = BankCompany.get_korean_name(account.bank_code)
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
            # 은행명 매핑 (Enum 기반으로 타입 안전하게)
            bank_name = BankCompany.get_korean_name(account.bank_code)

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

    의존성 주입 패턴을 적용하여 Repository와 CodefClient 팩토리를 주입합니다.
    이를 통해 결합도를 낮추고 테스트 용이성을 향상시킵니다.

    ImportSupporter(mcp).load_modules("app.mcp") 에 의해 자동 호출됩니다.

    Args:
        mcp: app/core/mcp_middleware.py 에서 생성된 FastMCP 인스턴스
    """
    from app.core.mcp_deps import (
        get_bank_account_repository,
        get_system_repository, 
        get_codef_client
    )

    # DI 컨테이너 설정: 의존성 팩토리들을 주입하여 BankTool 인스턴스 생성
    BankTool.register_mcp(
        mcp,
        bank_repo_factory=get_bank_account_repository,
        system_repo_factory=get_system_repository,
        codef_client_factory=get_codef_client
    )
