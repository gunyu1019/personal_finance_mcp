# src/repository/bank_account_repository.py

from __future__ import annotations
from sqlalchemy import select

from app.dto.bank_account_dto import BankAccountUpsertData
from app.model.bank_account import BankAccount
from app.repository.base_repository import BaseRepository


class BankAccountRepository(BaseRepository):
    """
    은행 계좌(BankAccount) 전용 Repository.

    BaseRepository 의 세션 관리(call / __aenter__ / __aexit__)를 그대로 사용합니다.
    """

    async def upsert(self, data: BankAccountUpsertData) -> BankAccount:
        """
        단건 upsert.

        - hashed_account_no 기준으로 DB 조회
        - 없으면 is_mcp_enabled=True 로 INSERT
        - 있으면 bank_code, masked_account_no 만 UPDATE (is_mcp_enabled 유지)

        Args:
            data: 저장할 계좌 데이터

        Returns:
            BankAccount: INSERT 또는 UPDATE 된 ORM 객체

        Raises:
            RuntimeError: 세션이 초기화되지 않은 경우
        """
        if self._session is NotImplemented or self._session is None:
            raise RuntimeError(
                "DB 세션이 초기화되지 않았습니다. "
                "async with BankAccountRepository() as repo: 또는 "
                "의존성 주입을 통해 사용하세요."
            )

        result = await self._session.execute(
            select(BankAccount).where(
                BankAccount.hashed_account_no == data.hashed_account_no
            )
        )
        existing: BankAccount | None = result.scalars().first()

        if existing is None:
            account = BankAccount(
                bank_code=data.bank_code,
                hashed_account_no=data.hashed_account_no,
                masked_account_no=data.masked_account_no,
                account_name=data.account_name,
                account_type=data.account_type,
                is_mcp_enabled=True,
            )
            self._session.add(account)
            await self._session.flush()
            await self._session.refresh(account)
            return account

        # 기존 레코드: is_mcp_enabled 상태는 절대 덮어쓰지 않는다.
        existing.bank_code = data.bank_code
        existing.masked_account_no = data.masked_account_no
        existing.account_name = data.account_name
        existing.account_type = data.account_type
        await self._session.flush()
        return existing

    async def upsert_many(
        self,
        records: list[BankAccountUpsertData],
    ) -> list[BankAccount]:
        """
        복수 건 upsert.

        각 레코드를 순서대로 upsert() 하여 처리합니다.
        단일 세션 내에서 실행되므로 호출 전 세션이 활성 상태여야 합니다.

        Args:
            records: BankAccountUpsertData 리스트

        Returns:
            list[BankAccount]: upsert 결과 ORM 객체 리스트
        """
        results: list[BankAccount] = []
        for record in records:
            account = await self.upsert(record)
            results.append(account)
        return results

    async def update_mcp_enabled(
        self,
        hashed_account_no: str,
        enabled: bool,
    ) -> BankAccount:
        """
        특정 계좌의 MCP 에이전트 노출 여부를 업데이트합니다.

        Args:
            hashed_account_no: 해시된 계좌번호 (PK)
            enabled: True = 노출, False = 비노출

        Returns:
            BankAccount: 업데이트된 ORM 객체

        Raises:
            RuntimeError: 세션이 초기화되지 않은 경우
            ValueError: 해당 계좌번호가 DB에 없는 경우
        """
        if self._session is NotImplemented or self._session is None:
            raise RuntimeError(
                "DB 세션이 초기화되지 않았습니다. "
                "async with BankAccountRepository() as repo: 형식으로 사용하세요."
            )

        result = await self._session.execute(
            select(BankAccount).where(
                BankAccount.hashed_account_no == hashed_account_no
            )
        )
        account: BankAccount | None = result.scalars().first()

        if account is None:
            raise ValueError(f"계좌번호 해시 {hashed_account_no!r} 를 찾을 수 없습니다.")

        account.is_mcp_enabled = enabled
        await self._session.flush()
        return account
