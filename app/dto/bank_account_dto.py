# src/dto/bank_account_dto.py

from __future__ import annotations
from pydantic import BaseModel, Field


class BankAccountUpsertData(BaseModel):
    """upsert() 메서드에 전달할 계좌 데이터 DTO."""

    bank_code: str = Field(..., description="CODEF 기관 코드")
    hashed_account_no: str = Field(..., description="해시된 계좌 번호 (PK)")
    masked_account_no: str = Field(..., description="마스킹된 계좌 번호")
    encrypted_account_no: str | None = Field(None, description="AES-256 암호화된 원본 계좌번호")
    account_name: str | None = Field(None, description="계좌 상품명")
    account_type: str | None = Field(None, description="계좌 유형 (예금/외화/펀드/대출/보험)")
