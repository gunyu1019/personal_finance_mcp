# src/dto/card_account_dto.py

from pydantic import BaseModel, Field


class CardAccountUpsertData(BaseModel):
    """upsert() 메서드에 전달할 카드 데이터 DTO."""

    card_code: str = Field(..., description="CODEF 카드사 코드")
    hashed_card_no: str = Field(..., description="해시된 카드 번호 (PK)")
    masked_card_no: str = Field(..., description="마스킹된 카드 번호")
