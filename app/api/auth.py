# src/api/auth.py
import logging
import jwt
from datetime import datetime, timedelta, timezone
from typing import Annotated, TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status, FastAPI, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi_restful.cbv import cbv
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.schema.auth import LoginRequest, TokenResponse

logger = logging.getLogger(__name__)

# HTTP Bearer scheme (auto_error=False → 직접 401 처리)
_bearer_scheme = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ─────────────────────────────────────────────────────────────
# 의존성 함수
# ─────────────────────────────────────────────────────────────

async def get_current_admin(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ] = None,
) -> str:
    """
    FastAPI 의존성 함수 — 인증된 관리자인지 검증합니다.
    (Bearer 토큰 또는 access_token 쿠키 모두 지원합니다)
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="유효하지 않거나 만료된 인증 토큰입니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = None
    if credentials:
        token = credentials.credentials
    if not token:
        token = request.cookies.get(settings.ADMIN_COOKIE_NAME)

    if not token:
        raise unauthorized

    try:
        payload = jwt.decode(token, settings.ROOT_PASSWORD, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        logger.warning("관리자 토큰 만료")
        raise unauthorized
    except jwt.InvalidTokenError as exc:
        logger.warning("관리자 토큰 유효하지 않음: %s", exc)
        raise unauthorized

    sub: str | None = payload.get("sub")
    if sub != settings.JWT_SUBJECT:
        raise unauthorized

    return sub


# ─────────────────────────────────────────────────────────────
# 엔드포인트 (CBV)
# ─────────────────────────────────────────────────────────────

@cbv(router)
class AuthAPI:
    # 멤버 변수: DB 세션 의존성 (요구사항에 맞춤)
    session: AsyncSession = Depends(get_session)

    def _create_access_token(self) -> tuple[str, int]:
        """JWT 토큰을 생성합니다."""
        expire = datetime.now(tz=timezone.utc) + timedelta(hours=settings.TOKEN_EXPIRE_HOURS)
        payload = {
            "sub": settings.JWT_SUBJECT,
            "exp": expire,
            "iat": datetime.now(tz=timezone.utc),
        }
        token = jwt.encode(payload, settings.ROOT_PASSWORD, algorithm=settings.JWT_ALGORITHM)
        expires_in = int(timedelta(hours=settings.TOKEN_EXPIRE_HOURS).total_seconds())
        return token, expires_in

    def _create_auth_cookie(self, response: Response, token: str, expires_in: int) -> None:
        """인증 쿠키를 응답에 설정합니다."""
        response.set_cookie(
            key=settings.ADMIN_COOKIE_NAME,
            value=token,
            httponly=True,
            max_age=expires_in,
            samesite="lax",
            secure=False,
        )

    @router.post(
        "/login",
        response_model=TokenResponse,
        summary="관리자 로그인",
        description=(
            "비밀번호가 올바르면 Bearer JWT 토큰을 발급하고 인증 쿠키를 설정합니다."
        ),
    )
    async def post_login(self, body: LoginRequest, response: Response) -> TokenResponse:
        """
        관리자 로그인 엔드포인트.
        """
        if body.password != settings.ROOT_PASSWORD:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="비밀번호가 올바르지 않습니다.",
            )

        token, expires_in = self._create_access_token()
        self._create_auth_cookie(response, token, expires_in)

        logger.info("관리자 로그인 성공 — 토큰 및 쿠키 발급 완료")
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=expires_in,
        )

    @router.post(
        "/logout",
        summary="관리자 로그아웃",
        description="관리자 세션 및 인증 쿠키를 파기하여 로그아웃합니다.",
    )
    async def post_logout(self, response: Response) -> dict[str, str]:
        """
        관리자 로그아웃 엔드포인트.
        """
        response.delete_cookie(
            key=settings.ADMIN_COOKIE_NAME,
            httponly=True,
            samesite="lax",
            secure=False,
        )
        response.delete_cookie(key="admin_token")
        response.delete_cookie(key="access_token")

        logger.info("관리자 로그아웃 성공 — 인증 쿠키 파기 완료")
        return {"message": "로그아웃 성공"}


def setup(fastapi_app: FastAPI) -> None:
    fastapi_app.include_router(router)

