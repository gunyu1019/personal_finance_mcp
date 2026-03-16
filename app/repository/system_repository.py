# src/repository/system_repository.py

from __future__ import annotations
import secrets
from typing import Optional

from sqlalchemy import select

from app.model.system import SystemConfig
from app.repository.base_repository import BaseRepository

# 자동 생성되는 토큰 바이트 길이 (hex 문자열로 변환 시 2배 → 64자)
_TOKEN_BYTES = 32


class SystemRepository(BaseRepository):
    """
    시스템 설정(SystemConfig) 전용 Repository.
    """

    async def get_or_create_config(self) -> SystemConfig:
        """
        DB 에 SystemConfig 레코드가 존재하면 반환하고,
        없으면 hash_salt 와 mcp_agent_token 을 secrets 모듈로 자동 생성하여 저장 후 반환합니다.

        항상 단 하나의 로우(id=1)만 유지됩니다.

        Returns:
            SystemConfig: 현재 시스템 설정 레코드

        Raises:
            RuntimeError: 세션이 초기화되지 않은 경우
        """
        if self._session is NotImplemented or self._session is None:
            raise RuntimeError(
                "DB 세션이 초기화되지 않았습니다. "
                "async with SystemRepository() as repo: 또는 "
                "의존성 주입을 통해 사용하세요."
            )

        # 기존 레코드 조회
        result = await self._session.execute(select(SystemConfig))
        config = result.scalars().first()

        if config is not None:
            return config

        # 최초 실행: 난수 생성 후 저장
        new_config = SystemConfig(
            hash_salt=secrets.token_hex(_TOKEN_BYTES),           # 64자 hex
            mcp_agent_token=secrets.token_hex(_TOKEN_BYTES),     # 64자 hex
        )
        self._session.add(new_config)
        await self._session.flush()   # id 할당을 위해 flush (commit 은 호출자 책임)
        await self._session.refresh(new_config)
        return new_config

    async def regenerate_mcp_token(self) -> str:
        """
        MCP 에이전트 토큰을 재발급합니다.
        
        Returns:
            str: 새로 생성된 MCP 에이전트 토큰
        """
        if self._session is NotImplemented or self._session is None:
            raise RuntimeError(
                "DB 세션이 초기화되지 않았습니다. "
                "async with SystemRepository() as repo: 형식으로 사용하세요."
            )

        config = await self.get_or_create_config()
        new_token = secrets.token_hex(_TOKEN_BYTES)  # 64자 hex
        config.mcp_agent_token = new_token
        await self._session.flush()
        return new_token

    async def get_connected_id(self) -> Optional[str]:
        """
        DB에 저장된 Codef connected_id를 반환합니다.

        Returns:
            Optional[str]: connected_id 문자열 또는 None (미등록 시)
        """
        config = await self.get_or_create_config()
        return config.codef_connected_id

    async def save_connected_id(self, connected_id: str) -> None:
        """
        Codef connected_id를 DB에 저장합니다. (최초 발급 또는 갱신)

        Args:
            connected_id: Codef API로부터 발급받은 connected_id 문자열
        """
        if self._session is NotImplemented or self._session is None:
            raise RuntimeError(
                "DB 세션이 초기화되지 않았습니다. "
                "async with SystemRepository() as repo: 형식으로 사용하세요."
            )
        config = await self.get_or_create_config()
        config.codef_connected_id = connected_id
        await self._session.flush()
