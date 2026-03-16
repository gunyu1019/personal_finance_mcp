# src/schema/bank_account.py

from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field


class BankAccountCreate(BaseModel):
    """
    은행 계좌 등록 요청 스키마.

    raw_account_no 는 서버에서 해시/마스킹 처리 후 폐기되며 DB에 저장되지 않습니다.
    """

    bank_code: str = Field(..., description="CODEF 기관 코드 (예: '0088' = 신한은행)")
    raw_account_no: str = Field(..., description="원본 계좌번호 (서버에서 해시/마스킹 처리 후 폐기)")


class BankAccountResponse(BaseModel):
    """
    은행 계좌 응답 스키마.

    raw_account_no, hashed_account_no 는 절대 포함하지 않습니다.
    bank_code, masked_account_no, is_mcp_enabled 만 클라이언트에 노출합니다.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="계좌 고유 ID")
    bank_code: str = Field(..., description="CODEF 기관 코드 (예: '0088')")
    masked_account_no: str = Field(..., description="마스킹된 계좌번호 (예: 110-***-***789)")
    is_mcp_enabled: bool = Field(..., description="MCP 에이전트 노출 여부")
