# app/core/mcp_middleware.py

"""
FastMCP 서버 인프라.

ImportSupporter 의 동적 모듈 로딩 패턴을 활용하여
app/mcp/ 하위의 모든 Tool 파일에 FastMCP 인스턴스를 주입합니다.

────────────────────────────────────────────────────────────
# 호출 흐름
────────────────────────────────────────────────────────────
  app/main.py lifespan
    └─ ImportSupporter(fastapi_app).load_module("app.core.mcp_server")
           └─ setup(fastapi_app) 호출
                  ├─ FastMCP 인스턴스 생성
                  ├─ http_app(transport="sse") 로 Starlette ASGI 앱 생성
                  ├─ AgentTokenASGIMiddleware 를 씌워 토큰 인증 적용
                  ├─ FastAPI 에 /mcp 경로로 ASGI 서브앱 마운트
                  └─ ImportSupporter(mcp) 로 app/mcp/ Tool 파일 동적 로드
                         └─ 각 Tool 파일의 setup(mcp) → @mcp.tool() 등록
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastmcp import FastMCP
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.import_supporter import ImportSupporter

if TYPE_CHECKING:
    from fastapi import FastAPI


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 순수 ASGI 토큰 인증 미들웨어 (SSE 스트리밍 친화적)
# ─────────────────────────────────────────────────────────────

class AgentTokenASGIMiddleware:
    """
    /mcp ASGI 서브앱에 적용되는 Bearer 토큰 인증 순수 ASGI 미들웨어.

    - ``Authorization: Bearer <TOKEN>`` 헤더를 검사하여
      DB 의 ``mcp_agent_token`` 과 일치하지 않으면 즉시 401 을 반환합니다.
    - ``BaseHTTPMiddleware`` 가 아닌 순수 ASGI 미들웨어이므로
      SSE 스트리밍 응답을 전혀 버퍼링하지 않아 연결이 끊기지 않습니다.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # WebSocket, lifespan 등 http 타입이 아닌 scope 는 그냥 통과
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        # ── Bearer 토큰 추출 ──────────────────────────────────────
        headers: dict[bytes, bytes] = dict(scope.get("headers", []))
        auth_bytes: bytes | None = headers.get(b"authorization")

        if not auth_bytes:
            await self._send_401(send, "Authorization 헤더가 누락되었습니다.")
            return

        auth_str = auth_bytes.decode("utf-8", errors="replace")
        if not auth_str.lower().startswith("bearer "):
            await self._send_401(send, "Bearer 토큰 형식이 올바르지 않습니다.")
            return

        provided_token = auth_str[len("Bearer "):]

        # ── DB 에서 기대 토큰 조회 ────────────────────────────────
        try:
            from app.core.database import AsyncSessionFactory
            from app.repository.system_repository import SystemRepository

            repo = SystemRepository()
            repo.set_factory(AsyncSessionFactory)
            async with repo:
                config = await repo.get_or_create_config()
                expected_token: str = config.mcp_agent_token
        except Exception as exc:
            logger.error("AgentTokenASGIMiddleware: DB 조회 중 오류 — %s", exc)
            await self._send_500(send)
            return

        if not provided_token or provided_token != expected_token:
            await self._send_401(send, "유효하지 않은 에이전트 토큰입니다.")
            return

        # ── 인증 통과 → 실제 ASGI 앱으로 위임 ───────────────────
        await self._app(scope, receive, send)

    # ── 헬퍼: 401 / 500 응답 전송 ────────────────────────────────

    @staticmethod
    async def _send_json_response(
        send: Send,
        status: int,
        body: bytes,
    ) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"www-authenticate", b"Bearer"],
                    [b"content-length", str(len(body)).encode()],
                ],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})

    async def _send_401(self, send: Send, message: str) -> None:
        import json
        body = json.dumps({"detail": message}, ensure_ascii=False).encode()
        await self._send_json_response(send, 401, body)

    async def _send_500(self, send: Send) -> None:
        import json
        body = json.dumps(
            {"detail": "서버 내부 오류로 인증을 처리할 수 없습니다."},
            ensure_ascii=False,
        ).encode()
        await self._send_json_response(send, 500, body)
