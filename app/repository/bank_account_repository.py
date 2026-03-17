# src/repository/bank_account_repository.py

from __future__ import annotations
from sqlalchemy import delete, select

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
                encrypted_account_no=data.encrypted_account_no,
                account_name=data.account_name,
                account_type=data.account_type,
                is_mcp_enabled=True,
            )
            self._session.add(account)
            await self._session.flush()
            await self._session.refresh(account)
            return account

        # 기존 레코드: is_mcp_enabled 상태는 절대 덮어쓰지 않는다. 암호화 필드는 갱신한다.
        existing.bank_code = data.bank_code
        existing.masked_account_no = data.masked_account_no
        existing.account_name = data.account_name
        existing.account_type = data.account_type
        if data.encrypted_account_no is not None:
            existing.encrypted_account_no = data.encrypted_account_no
        await self._session.flush()
        return existing

    async def upsert_many(
        self,
        records: list[BankAccountUpsertData],
    ) -> list[BankAccount]:
        """
        복수 건 upsert.

        Args:
            records: BankAccountUpsertData 리스트

        Returns:
            list[BankAccount]: upsert 결과 ORM 객체 리스트
        """
        if not records:
            return []

        if self._session is NotImplemented or self._session is None:
            raise RuntimeError(
                "DB 세션이 초기화되지 않았습니다. "
                "async with BankAccountRepository() as repo: 또는 "
                "의존성 주입을 통해 사용하세요."
            )

        hashed_account_nos = [record.hashed_account_no for record in records]
        result = await self._session.execute(
            select(BankAccount).where(BankAccount.hashed_account_no.in_(hashed_account_nos))
        )
        existing_accounts = {account.hashed_account_no: account for account in result.scalars().all()}

        results: list[BankAccount] = []
        new_accounts: list[BankAccount] = []

        for record in records:
            existing_account = existing_accounts.get(record.hashed_account_no)
            
            if existing_account is None:
                # 신규 계좌 생성
                new_account = BankAccount(
                    bank_code=record.bank_code,
                    hashed_account_no=record.hashed_account_no,
                    masked_account_no=record.masked_account_no,
                    encrypted_account_no=record.encrypted_account_no,
                    account_name=record.account_name,
                    account_type=record.account_type,
                    is_mcp_enabled=True,
                )
                self._session.add(new_account)
                new_accounts.append(new_account)
                results.append(new_account)
            else:
                # 기존 계좌 업데이트 (is_mcp_enabled 상태는 유지)
                existing_account.bank_code = record.bank_code
                existing_account.masked_account_no = record.masked_account_no
                existing_account.account_name = record.account_name
                existing_account.account_type = record.account_type
                if record.encrypted_account_no is not None:
                    existing_account.encrypted_account_no = record.encrypted_account_no
                results.append(existing_account)

        await self._session.flush()
        
        # 신규 생성된 계좌들의 ID 갱신
        if new_accounts:
            for account in new_accounts:
                await self._session.refresh(account)

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

    async def delete_by_bank_code(self, bank_code: str) -> int:
        """
        특정 기관 코드(bank_code)에 해당하는 모든 계좌를 삭제합니다.

        Args:
            bank_code: CODEF 기관 코드 (예: "0088")

        Returns:
            삭제된 행 수
        """
        if self._session is NotImplemented or self._session is None:
            raise RuntimeError(
                "DB 세션이 초기화되지 않았습니다. "
                "async with BankAccountRepository() as repo: 형식으로 사용하세요."
            )
        result = await self._session.execute(delete(BankAccount).where(BankAccount.bank_code == bank_code))
        await self._session.flush()
        return result.rowcount or 0

    async def get_enabled_accounts(self) -> list[BankAccount]:
        """
        MCP 에이전트에 노출 가능한 계좌 목록을 조회합니다.
        
        is_mcp_enabled가 True인 계좌만 반환합니다.
        
        Returns:
            list[BankAccount]: MCP 노출 허용된 계좌 목록
            
        Raises:
            RuntimeError: 세션이 초기화되지 않은 경우
        """
        if self._session is NotImplemented or self._session is None:
            raise RuntimeError(
                "DB 세션이 초기화되지 않았습니다. "
                "async with BankAccountRepository() as repo: 형식으로 사용하세요."
            )
        
        result = await self._session.execute(
            select(BankAccount).where(BankAccount.is_mcp_enabled.is_(True))
        )
        return result.scalars().all()

    async def get_by_masked_account_no(self, masked_account_no: str) -> BankAccount | None:
        """
        마스킹된 계좌번호로 계좌를 조회합니다.
        
        Args:
            masked_account_no: 마스킹된 계좌번호 (예: 110-***-***789)
            
        Returns:
            BankAccount | None: 해당하는 계좌 객체 또는 None
            
        Raises:
            RuntimeError: 세션이 초기화되지 않은 경우
        """
        if self._session is NotImplemented or self._session is None:
            raise RuntimeError(
                "DB 세션이 초기화되지 않았습니다. "
                "async with BankAccountRepository() as repo: 형식으로 사용하세요."
            )
        
        result = await self._session.execute(
            select(BankAccount).where(BankAccount.masked_account_no == masked_account_no)
        )
        return result.scalars().first()
