# src/repository/system_repository.py

import secrets

from sqlalchemy import select

from src.model.system import SystemConfig
from src.repository.base_repository import BaseRepository

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
