# main.py

"""
FastAPI 애플리케이션 진입점.

서버 구동 시 DB 테이블을 초기화하고, 모든 라우터를 등록합니다.
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP
from fastmcp.utilities.lifespan import combine_lifespans
from starlette.types import ASGIApp

from app.core.config import settings
from app.core.database import init_db
from app.core.import_supporter import ImportSupporter
from app.core.mcp_middleware import AgentTokenASGIMiddleware

if TYPE_CHECKING:
    pass

# ─────────────────────────────────────────────────────────────
# 상수 설정
# ─────────────────────────────────────────────────────────────

directory = os.path.join(
    *(os.path.split(os.path.dirname(os.path.abspath(__file__))))[:-1]
)

# ─────────────────────────────────────────────────────────────
# 로깅 설정
# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 앱 생명주기 (Lifespan) 관리
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def fastapi_lifespan(fastapi_app: FastAPI):
    # 0. RSA 키 쌍 생성 트리거 (Lazy loading 방지)
    import app.core.crypto  # noqa: F401

    logger.info("ImportSupporter를 통한 API 및 Model 동적 로딩 시작")

    # 1. API 모듈 동적 등록 (각 모듈의 setup(app)이 호출됨)
    api_supporter = ImportSupporter(fastapi_app, is_debug=True)
    api_supporter.load_modules(package="app.api", directory=directory)

    # 2. Model 모듈 동적 등록 (단순 import를 통해 SQLAlchemy Base metadata에 등록)
    model_supporter = ImportSupporter()
    model_supporter.load_modules(package="app.model", directory=directory)

    await init_db()

    logger.info("애플리케이션 시작 완료 — 모듈 동적 로드 및 DB 초기화, RSA 키 생성, MCP 서버 구동 완료")

    yield


# ─────────────────────────────────────────────────────────────
# FastMCP 앱 생성
# ─────────────────────────────────────────────────────────────

mcp = FastMCP(name="Personal Finance MCP")
logger.info("FastMCP 인스턴스 생성 완료: 'Personal Finance MCP'")

mcp_asgi: ASGIApp = mcp.http_app(path="/sse", transport="streamable-http")
protected_mcp_asgi = AgentTokenASGIMiddleware(mcp_asgi)

tool_loader = ImportSupporter(mcp, is_debug=True)
tool_loader.load_modules(package="app.mcp", directory=directory)

logger.info("app/mcp/ Tool 파일 동적 로드 완료")

# ─────────────────────────────────────────────────────────────
# FastAPI 앱 생성
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="마이데이터 MCP 관리 서버",
    description=(
        "은행·카드 마이데이터를 AI 에이전트(MCP)에게 안전하게 제공하는 관리 서버입니다. "
        "RSA E2EE 암호화와 JWT 인증을 적용합니다."
    ),
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=combine_lifespans(fastapi_lifespan, mcp_asgi.lifespan),
)

# CORS 미들웨어 (필요 시 origins 제한)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/mcp", protected_mcp_asgi)

# ─────────────────────────────────────────────────────────────
# 직접 실행 진입점
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=False,
        log_level="info",
    )
