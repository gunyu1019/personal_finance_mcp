# src/dto/bank_account_dto.py

from pydantic import BaseModel, Field


class BankAccountUpsertData(BaseModel):
    """upsert() 메서드에 전달할 계좌 데이터 DTO."""

    bank_code: str = Field(..., description="CODEF 기관 코드")
    hashed_account_no: str = Field(..., description="해시된 계좌 번호 (PK)")
    masked_account_no: str = Field(..., description="마스킹된 계좌 번호")
