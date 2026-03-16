# app/core/mcp_deps.py

"""
MCP 에이전트 인증 의존성.

AI 에이전트가 /mcp 엔드포인트에 접근하기 전,
Authorization 헤더의 Bearer 토큰을 DB 저장 값과 대조합니다.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import AsyncSessionFactory
from app.repository.system_repository import SystemRepository

if TYPE_CHECKING:
    pass


# ─────────────────────────────────────────────────────────────
# Bearer 스킴 추출기 (auto_error=True → 헤더 누락 시 401 자동 반환)
# ─────────────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=True)


async def verify_agent_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """
    AI 에이전트 토큰 검증 의존성.

    요청 헤더에서 ``Authorization: Bearer <TOKEN>`` 을 추출하여
    DB 의 ``mcp_agent_token`` 과 비교합니다.

    Args:
        credentials: FastAPI HTTPBearer 가 파싱한 자격증명 객체

    Returns:
        str: 검증된 토큰 문자열

    Raises:
        HTTPException(401): 토큰이 일치하지 않는 경우
    """
    provided_token: str = credentials.credentials

    repo = SystemRepository()
    repo.set_factory(AsyncSessionFactory)

    async with repo:
        config = await repo.get_or_create_config()
        expected_token: str = config.mcp_agent_token

    if not provided_token or provided_token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 에이전트 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return provided_token
