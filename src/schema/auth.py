# src/schema/auth.py

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """관리자 로그인 요청 스키마."""

    password: str = Field(..., description="관리자 비밀번호 (ROOT_PASSWORD)")


class TokenResponse(BaseModel):
    """JWT 액세스 토큰 응답 스키마."""

    access_token: str = Field(..., description="Bearer 토큰")
    token_type: str = Field(default="bearer", description="토큰 타입")
    expires_in: int = Field(..., description="만료까지 남은 초(seconds)")
