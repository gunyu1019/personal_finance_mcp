# src/schema/card_account.py

from pydantic import BaseModel, ConfigDict, Field


class CardAccountCreate(BaseModel):
    """
    카드 등록 요청 스키마.

    raw_card_no 는 서버에서 해시/마스킹 처리 후 폐기되며 DB에 저장되지 않습니다.
    """

    card_code: str = Field(..., description="CODEF 카드사 코드 (예: '0306' = 신한카드)")
    raw_card_no: str = Field(..., description="원본 카드번호 (서버에서 해시/마스킹 처리 후 폐기)")


class CardAccountResponse(BaseModel):
    """
    카드 응답 스키마.

    raw_card_no, hashed_card_no 는 절대 포함하지 않습니다.
    card_code, masked_card_no, is_mcp_enabled 만 클라이언트에 노출합니다.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="카드 고유 ID")
    card_code: str = Field(..., description="CODEF 카드사 코드 (예: '0306')")
    masked_card_no: str = Field(..., description="마스킹된 카드번호 (예: 1234-****-****-5678)")
    is_mcp_enabled: bool = Field(..., description="MCP 에이전트 노출 여부")
