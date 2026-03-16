# src/dto/card_account_dto.py

from __future__ import annotations
from pydantic import BaseModel, Field


class CardAccountUpsertData(BaseModel):
    """upsert() 메서드에 전달할 카드 데이터 DTO."""

    card_code: str = Field(..., description="CODEF 카드사 코드")
    hashed_card_no: str = Field(..., description="해시된 카드 번호 (PK)")
    masked_card_no: str = Field(..., description="마스킹된 카드 번호")
    encrypted_card_no: str | None = Field(None, description="AES-256 암호화된 원본 카드번호")
    encrypted_card_password: str | None = Field(None, description="AES-256 암호화된 카드 비밀번호")
    card_name: str | None = Field(None, description="카드 상품명")
    card_image_url: str | None = Field(None, description="카드 이미지 URL")
