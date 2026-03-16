# src/api/crypto.py

"""
RSA 공개키 제공 API (CBV 형태).
"""

from typing import TYPE_CHECKING

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from fastapi_restful.cbv import cbv

from app.core.crypto import get_public_key_pem

router = APIRouter(prefix="/api/crypto", tags=["crypto"])


@cbv(router)
class CryptoAPI:
    @router.get(
        "/public-key",
        summary="RSA 공개키 조회",
        description=(
            "서버의 RSA-2048 공개키를 PEM 형식으로 반환합니다. "
            "클라이언트는 이 공개키를 사용하여 비밀번호 등 민감한 데이터를 암호화한 뒤 전송해야 합니다."
        ),
    )
    async def get_public_key(self) -> JSONResponse:
        """
        RSA 공개키 조회 엔드포인트.
        """
        return JSONResponse(content={"public_key": get_public_key_pem()})


def setup(fastapi_app: FastAPI) -> None:
    fastapi_app.include_router(router)

