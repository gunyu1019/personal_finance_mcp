# src/api/auth.py

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from src.core.config import settings
from src.schema.auth import LoginRequest, TokenResponse

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# 상수 및 설정
# ─────────────────────────────────────────────────────────────

_ALGORITHM = "HS256"
_TOKEN_EXPIRE_HOURS = 12
_SUBJECT = "admin"

# HTTP Bearer scheme (auto_error=False → 직접 401 처리)
_bearer_scheme = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ─────────────────────────────────────────────────────────────
# 내부 유틸리티
# ─────────────────────────────────────────────────────────────

def _create_access_token() -> tuple[str, int]:
    """
    관리자용 JWT 액세스 토큰을 생성합니다.

    서명 키로 settings.ROOT_PASSWORD 를 사용하며 HS256 알고리즘으로 서명합니다.

    Returns:
        (토큰 문자열, 만료까지 남은 초)
    """
    expire = datetime.now(tz=timezone.utc) + timedelta(hours=_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": _SUBJECT,
        "exp": expire,
        "iat": datetime.now(tz=timezone.utc),
    }
    token = jwt.encode(payload, settings.ROOT_PASSWORD, algorithm=_ALGORITHM)
    expires_in = int(timedelta(hours=_TOKEN_EXPIRE_HOURS).total_seconds())
    return token, expires_in


def _decode_token(token: str) -> dict:
    """
    JWT 토큰을 검증하고 페이로드를 반환합니다.

    Args:
        token: Bearer 토큰 문자열

    Returns:
        디코드된 페이로드 딕셔너리

    Raises:
        jwt.ExpiredSignatureError: 토큰 만료
        jwt.InvalidTokenError: 토큰 무효
    """
    return jwt.decode(token, settings.ROOT_PASSWORD, algorithms=[_ALGORITHM])


# ─────────────────────────────────────────────────────────────
# 의존성 함수
# ─────────────────────────────────────────────────────────────

async def get_current_admin(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> str:
    """
    FastAPI 의존성 함수 — 인증된 관리자인지 검증합니다.

    Authorization: Bearer <token> 헤더에서 JWT 를 꺼내 검증합니다.
    검증 실패 시 HTTP 401 을 반환합니다.

    Returns:
        str: JWT payload 의 "sub" 클레임 값 (= "admin")

    Raises:
        HTTPException(401): 토큰 없음 또는 유효하지 않은 토큰
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="유효하지 않거나 만료된 인증 토큰입니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = _decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        logger.warning("관리자 토큰 만료")
        raise unauthorized
    except jwt.InvalidTokenError as exc:
        logger.warning("관리자 토큰 유효하지 않음: %s", exc)
        raise unauthorized

    sub: str | None = payload.get("sub")
    if sub != _SUBJECT:
        raise unauthorized

    return sub


# ─────────────────────────────────────────────────────────────
# 엔드포인트
# ─────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="관리자 로그인",
    description=(
        "비밀번호가 올바르면 Bearer JWT 토큰을 발급합니다. "
        f"토큰 유효 기간은 {_TOKEN_EXPIRE_HOURS}시간입니다."
    ),
)
async def login(body: LoginRequest) -> TokenResponse:
    """
    관리자 로그인 엔드포인트.

    클라이언트가 전달한 비밀번호를 `settings.ROOT_PASSWORD` 와 비교하고,
    일치하면 JWT 액세스 토큰을 발급합니다.
    """
    if body.password != settings.ROOT_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비밀번호가 올바르지 않습니다.",
        )

    token, expires_in = _create_access_token()

    logger.info("관리자 로그인 성공 — 토큰 발급 완료")
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
    )
