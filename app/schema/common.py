# src/schema/common.py

from __future__ import annotations
from pydantic import BaseModel, Field


class ToggleMCPRequest(BaseModel):
    """MCP 에이전트 노출 여부 토글 요청 스키마."""

    is_mcp_enabled: bool = Field(..., description="true = MCP 에 노출, false = 비노출")
