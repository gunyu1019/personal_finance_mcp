# src/repository/card_account_repository.py

from sqlalchemy import select

from src.dto.card_account_dto import CardAccountUpsertData
from src.model.card_account import CardAccount
from src.repository.base_repository import BaseRepository


class CardAccountRepository(BaseRepository):
    """
    카드 계좌(CardAccount) 전용 Repository.

    BaseRepository 의 세션 관리(call / __aenter__ / __aexit__)를 그대로 사용합니다.
    """

    async def upsert(self, data: CardAccountUpsertData) -> CardAccount:
        """
        단건 upsert.

        - hashed_card_no 기준으로 DB 조회
        - 없으면 is_mcp_enabled=True 로 INSERT
        - 있으면 card_code, masked_card_no 만 UPDATE (is_mcp_enabled 유지)

        Args:
            data: 저장할 카드 데이터

        Returns:
            CardAccount: INSERT 또는 UPDATE 된 ORM 객체

        Raises:
            RuntimeError: 세션이 초기화되지 않은 경우
        """
        if self._session is NotImplemented or self._session is None:
            raise RuntimeError(
                "DB 세션이 초기화되지 않았습니다. "
                "async with CardAccountRepository() as repo: 또는 "
                "의존성 주입을 통해 사용하세요."
            )

        result = await self._session.execute(
            select(CardAccount).where(
                CardAccount.hashed_card_no == data.hashed_card_no
            )
        )
        existing: CardAccount | None = result.scalars().first()

        if existing is None:
            card = CardAccount(
                card_code=data.card_code,
                hashed_card_no=data.hashed_card_no,
                masked_card_no=data.masked_card_no,
                is_mcp_enabled=True,
            )
            self._session.add(card)
            await self._session.flush()
            await self._session.refresh(card)
            return card

        # 기존 레코드: is_mcp_enabled 상태는 절대 덮어쓰지 않는다.
        existing.card_code = data.card_code
        existing.masked_card_no = data.masked_card_no
        await self._session.flush()
        return existing

    async def upsert_many(
        self,
        records: list[CardAccountUpsertData],
    ) -> list[CardAccount]:
        """
        복수 건 upsert.

        각 레코드를 순서대로 upsert() 하여 처리합니다.
        단일 세션 내에서 실행되므로 호출 전 세션이 활성 상태여야 합니다.

        Args:
            records: CardAccountUpsertData 리스트

        Returns:
            list[CardAccount]: upsert 결과 ORM 객체 리스트
        """
        results: list[CardAccount] = []
        for record in records:
            card = await self.upsert(record)
            results.append(card)
        return results
