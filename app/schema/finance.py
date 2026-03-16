# src/schema/finance.py

from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field


class FormField(BaseModel):
    """폼 입력 필드 단건 스키마."""

    name: str = Field(..., description="필드 키 이름 (HTML name 속성)")
    label: str = Field(..., description="화면에 표시할 한글 레이블")
    type: str = Field(..., description="HTML input type (text, password, …)")


class FormResponse(BaseModel):
    """GET /api/finance/form/{org_type}/{company_code} 응답 스키마."""

    fields: list[FormField] = Field(..., description="표시할 폼 필드 목록")


class SyncRequest(BaseModel):
    """마이데이터 동기화 요청 스키마."""

    org_type: Literal["bank", "card"] = Field(
        ..., description="기관 유형 ('bank' 또는 'card')"
    )
    company_code: str = Field(
        ..., description="4자리 CODEF 기관 코드 (예: '0088')"
    )
    login_data: dict[str, Any] = Field(
        ...,
        description=(
            "폼에서 입력받은 로그인 데이터 딕셔너리. "
            "키: 폼 필드 name (예: id, password, birthDate 등)"
        ),
    )


class SyncResponse(BaseModel):
    """마이데이터 동기화 응답 스키마."""

    org_type: str = Field(..., description="동기화된 기관 유형")
    company_code: str = Field(..., description="동기화된 기관 코드")
    synced_count: int = Field(..., description="DB에 upsert 된 계좌/카드 건수")


class ToggleRequest(BaseModel):
    """PATCH /api/finance/toggle/{org_type}/{item_id} 요청 스키마."""

    is_mcp_enabled: bool = Field(..., description="MCP 에이전트 노출 여부")


class ToggleResponse(BaseModel):
    """PATCH /api/finance/toggle/{org_type}/{item_id} 응답 스키마."""

    org_type: Literal["bank", "card"] = Field(..., description="기관 유형")
    item_id: str = Field(..., description="hashed_account_no 또는 hashed_card_no")
    is_mcp_enabled: bool = Field(..., description="업데이트된 MCP 에이전트 노출 여부")
