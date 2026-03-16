# src/model/base.py
# 하위 호환성을 위해 Base 를 src.core.database 에서 re-export 합니다.
# Base 의 실제 정의는 circular import 방지를 위해 src/core/database.py 에 있습니다.
from __future__ import annotations
from sqlalchemy.orm import DeclarativeBase


__all__ = ["Base"]

class Base(DeclarativeBase):
    """모든 SQLAlchemy 모델의 공통 베이스 클래스."""

def setup(*args, **kwargs) -> None:
    pass

