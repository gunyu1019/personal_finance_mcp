from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from typing import Self


class BaseRepository:
    def __init__(self):
        self.factory: async_sessionmaker | None = NotImplemented
        self._session: AsyncSession | None = NotImplemented

    def set_factory(self, factory: async_sessionmaker):
        self.factory = factory

    async def call(self) -> Self:
        if self.factory is None:
            raise Exception("Factory is not set")

        try:
            self._session = self.factory()
            yield self
        except Exception as e:
            await self._session.rollback()
            raise e
        else:
            await self._session.commit()
        finally:
            await self._session.close()
            self._session = NotImplemented

    async def __aenter__(self):
        self._session = self.factory()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._session.close()
