# src/repository/card_account_repository.py

from __future__ import annotations
from sqlalchemy import delete, select

from app.dto.card_account_dto import CardAccountUpsertData
from app.model.card_account import CardAccount
from app.repository.base_repository import BaseRepository


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
                encrypted_card_no=data.encrypted_card_no,
                encrypted_card_password=data.encrypted_card_password,
                card_name=data.card_name,
                card_image_url=data.card_image_url,
                is_mcp_enabled=True,
            )
            self._session.add(card)
            await self._session.flush()
            await self._session.refresh(card)
            return card

        # 기존 레코드: is_mcp_enabled 상태는 절대 덮어쓰지 않는다. 암호화 필드는 갱신한다.
        existing.card_code = data.card_code
        existing.masked_card_no = data.masked_card_no
        existing.card_name = data.card_name
        existing.card_image_url = data.card_image_url
        if data.encrypted_card_no is not None:
            existing.encrypted_card_no = data.encrypted_card_no
        if data.encrypted_card_password is not None:
            existing.encrypted_card_password = data.encrypted_card_password
        await self._session.flush()
        return existing

    async def upsert_many(
        self,
        records: list[CardAccountUpsertData],
    ) -> list[CardAccount]:
        """
        복수 건 upsert.

        Args:
            records: CardAccountUpsertData 리스트

        Returns:
            list[CardAccount]: upsert 결과 ORM 객체 리스트
        """
        if not records:
            return []

        if self._session is NotImplemented or self._session is None:
            raise RuntimeError(
                "DB 세션이 초기화되지 않았습니다. "
                "async with CardAccountRepository() as repo: 또는 "
                "의존성 주입을 통해 사용하세요."
            )

        hashed_card_nos = [record.hashed_card_no for record in records]
        result = await self._session.execute(
            select(CardAccount).where(CardAccount.hashed_card_no.in_(hashed_card_nos))
        )
        existing_cards = {card.hashed_card_no: card for card in result.scalars().all()}

        results: list[CardAccount] = []
        new_cards: list[CardAccount] = []

        for record in records:
            existing_card = existing_cards.get(record.hashed_card_no)
            
            if existing_card is None:
                # 신규 카드 생성
                new_card = CardAccount(
                    card_code=record.card_code,
                    hashed_card_no=record.hashed_card_no,
                    masked_card_no=record.masked_card_no,
                    encrypted_card_no=record.encrypted_card_no,
                    encrypted_card_password=record.encrypted_card_password,
                    card_name=record.card_name,
                    card_image_url=record.card_image_url,
                    is_mcp_enabled=True,
                )
                self._session.add(new_card)
                new_cards.append(new_card)
                results.append(new_card)
            else:
                # 기존 카드 업데이트 (is_mcp_enabled 상태는 유지)
                existing_card.card_code = record.card_code
                existing_card.masked_card_no = record.masked_card_no
                existing_card.card_name = record.card_name
                existing_card.card_image_url = record.card_image_url
                if record.encrypted_card_no is not None:
                    existing_card.encrypted_card_no = record.encrypted_card_no
                if record.encrypted_card_password is not None:
                    existing_card.encrypted_card_password = record.encrypted_card_password
                results.append(existing_card)

        await self._session.flush()
        
        # 신규 생성된 카드들의 ID 갱신
        if new_cards:
            for card in new_cards:
                await self._session.refresh(card)

        return results

    async def update_mcp_enabled(
        self,
        hashed_card_no: str,
        enabled: bool,
    ) -> CardAccount:
        """
        특정 카드의 MCP 에이전트 노출 여부를 업데이트합니다.

        Args:
            hashed_card_no: 해시된 카드번호 (PK)
            enabled: True = 노출, False = 비노출

        Returns:
            CardAccount: 업데이트된 ORM 객체

        Raises:
            RuntimeError: 세션이 초기화되지 않은 경우
            ValueError: 해당 카드번호가 DB에 없는 경우
        """
        if self._session is NotImplemented or self._session is None:
            raise RuntimeError(
                "DB 세션이 초기화되지 않았습니다. "
                "async with CardAccountRepository() as repo: 형식으로 사용하세요."
            )

        result = await self._session.execute(
            select(CardAccount).where(
                CardAccount.hashed_card_no == hashed_card_no
            )
        )
        card: CardAccount | None = result.scalars().first()

        if card is None:
            raise ValueError(f"카드번호 해시 {hashed_card_no!r} 를 찾을 수 없습니다.")

        card.is_mcp_enabled = enabled
        await self._session.flush()
        return card

    async def delete_by_card_code(self, card_code: str) -> int:
        """
        특정 기관 코드(card_code)에 해당하는 모든 카드를 삭제합니다.

        Args:
            card_code: CODEF 카드사 코드 (예: "0306")

        Returns:
            삭제된 행 수
        """
        if self._session is NotImplemented or self._session is None:
            raise RuntimeError(
                "DB 세션이 초기화되지 않았습니다. "
                "async with CardAccountRepository() as repo: 형식으로 사용하세요."
            )
        result = await self._session.execute(delete(CardAccount).where(CardAccount.card_code == card_code))
        await self._session.flush()
        return result.rowcount or 0

    async def get_enabled_accounts(self) -> list[CardAccount]:
        """
        MCP 에이전트에 노출 가능한 카드 목록을 조회합니다.
        
        is_mcp_enabled가 True인 카드만 반환합니다.
        
        Returns:
            list[CardAccount]: MCP 노출 허용된 카드 목록
            
        Raises:
            RuntimeError: 세션이 초기화되지 않은 경우
        """
        if self._session is NotImplemented or self._session is None:
            raise RuntimeError(
                "DB 세션이 초기화되지 않았습니다. "
                "async with CardAccountRepository() as repo: 형식으로 사용하세요."
            )
        
        result = await self._session.execute(
            select(CardAccount).where(CardAccount.is_mcp_enabled.is_(True))
        )
        return result.scalars().all()

    async def get_by_masked_card_no(self, masked_card_no: str) -> CardAccount | None:
        """
        마스킹된 카드번호로 카드를 조회합니다.
        
        Args:
            masked_card_no: 마스킹된 카드번호 (예: 1234-****-****-5678)
            
        Returns:
            CardAccount | None: 해당하는 카드 객체 또는 None
            
        Raises:
            RuntimeError: 세션이 초기화되지 않은 경우
        """
        if self._session is NotImplemented or self._session is None:
            raise RuntimeError(
                "DB 세션이 초기화되지 않았습니다. "
                "async with CardAccountRepository() as repo: 형식으로 사용하세요."
            )
        
        result = await self._session.execute(
            select(CardAccount).where(CardAccount.masked_card_no == masked_card_no)
        )
        return result.scalars().first()
