# src/api/page.py
# HTML 페이지 렌더링 라우터

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi_restful.cbv import cbv

from app.api.auth import get_current_admin
from app.core.config import BANK_MAPPING, CARD_MAPPING, TEMPLATE_DIR, settings
from app.core.database import AsyncSessionFactory
from app.repository.bank_account_repository import BankAccountRepository
from app.repository.card_account_repository import CardAccountRepository
from app.repository.system_repository import SystemRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["page"])

_templates_instance = Jinja2Templates(directory=TEMPLATE_DIR)


# 내부 유틸리티
async def _get_system_token() -> str:
    repo = SystemRepository()
    repo.set_factory(AsyncSessionFactory)
    async with repo as r:
        config = await r.get_or_create_config()
        await r._session.commit()
        return config.mcp_agent_token


@cbv(router)
class PageAPI:
    # 멤버 변수: Jinja2Templates 인스턴스 (FastAPI가 의존성으로 해석하지 않도록 타입 힌트 생략)
    templates = _templates_instance

    @router.get("/login", response_class=HTMLResponse, include_in_schema=False, response_model=None)
    async def get_login(self, request: Request) -> HTMLResponse | RedirectResponse:
        """
        관리자 로그인 페이지.
        만약 쿠키에 이미 액세스 토큰이 존재해 인증이 가능하다면 바로 대시보드로 리다이렉트 처리합니다.
        (get_current_admin 의존성을 강제하면 미인증 시 401 에러가 발생하므로 여기서는 의존성을 쓰지 않고 예외 처리로 우회)
        """
        # 간단히 쿠키만 체크해서 리다이렉트
        try:
            import jwt
            token = request.cookies.get(settings.ADMIN_COOKIE_NAME)
            if token and jwt.decode(token, settings.ROOT_PASSWORD, algorithms=[settings.JWT_ALGORITHM]).get("sub") == settings.JWT_SUBJECT:
                return RedirectResponse(url="/", status_code=302)
        except Exception:
            pass

        return self.templates.TemplateResponse("login.html", {"request": request})

    @router.get("/", response_class=HTMLResponse, include_in_schema=False, response_model=None)
    async def get_dashboard(
        self,
        request: Request,
    ) -> HTMLResponse | RedirectResponse:
        """
        금융 대시보드 페이지.
        """
        try:
            admin_sub = await get_current_admin(request=request)
        except Exception:
            return RedirectResponse(url="/login", status_code=303)

        bank_accounts = []
        try:
            bank_repo = BankAccountRepository()
            bank_repo.set_factory(AsyncSessionFactory)
            async with bank_repo as repo:
                from sqlalchemy import select
                from app.model.bank_account import BankAccount
                result = await repo._session.execute(select(BankAccount))
                bank_accounts = result.scalars().all()
        except Exception as exc:
            logger.warning("은행 계좌 조회 실패: %s", exc)

        card_accounts = []
        try:
            card_repo = CardAccountRepository()
            card_repo.set_factory(AsyncSessionFactory)
            async with card_repo as repo:
                from sqlalchemy import select
                from app.model.card_account import CardAccount
                result = await repo._session.execute(select(CardAccount))
                card_accounts = result.scalars().all()
        except Exception as exc:
            logger.warning("카드 조회 실패: %s", exc)

        try:
            mcp_token = await _get_system_token()
        except Exception as exc:
            logger.warning("mcp_agent_token 조회 실패: %s", exc)
            mcp_token = ""

        return self.templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "bank_accounts": bank_accounts,
                "card_accounts": card_accounts,
                "bank_mapping": BANK_MAPPING,
                "card_mapping": CARD_MAPPING,
                "mcp_agent_token": mcp_token,
            },
        )

    @router.get("/settings", response_class=HTMLResponse, include_in_schema=False, response_model=None)
    async def get_settings(
        self,
        request: Request,
    ) -> HTMLResponse | RedirectResponse:
        """
        설정 및 기관 연동 페이지.
        """
        try:
            admin_sub = await get_current_admin(request=request)
        except Exception:
            return RedirectResponse(url="/login", status_code=303)

        try:
            mcp_token = await _get_system_token()
        except Exception as exc:
            logger.warning("mcp_agent_token 조회 실패: %s", exc)
            mcp_token = ""

        return self.templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "mcp_agent_token": mcp_token,
                "bank_mapping": BANK_MAPPING,
                "card_mapping": CARD_MAPPING,
            },
        )


def setup(fastapi_app: FastAPI) -> None:
    fastapi_app.include_router(router)

