# src/core/database.py

from __future__ import annotations
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings
from app.model.base import Base


# 비동기 엔진 생성
# connect_args={"check_same_thread": False} 는 aiosqlite 에서는 필요 없지만
# SQLite 파일 잠금 이슈 방지를 위해 명시합니다.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,           # 프로덕션에서는 False, 디버깅 시 True 로 변경
    future=True,
)

# 세션 팩토리
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    """
    애플리케이션 시작 시 모든 테이블을 생성합니다.
    (이미 존재하는 테이블은 건드리지 않습니다.)
    """
    # 모든 모델이 Base 에 등록되도록 임포트

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 의존성 주입용 세션 제공자.

    Example::

        @router.get("/")
        async def endpoint(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
