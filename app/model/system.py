# src/model/system.py

from __future__ import annotations
from typing import Optional
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.model.base import Base


class SystemConfig(Base):
    """
    시스템 전역 설정 테이블.

    이 테이블은 항상 단 하나의 로우(id=1)만 가집니다.
    - hash_salt          : 계좌/카드번호 단방향 해시에 사용하는 랜덤 솔트
    - mcp_agent_token    : MCP 에이전트 인증 토큰
    - codef_connected_id : Codef API 최초 기관 등록 후 발급되는 연결 식별자
    두 값 모두 최초 실행 시 secrets 모듈로 자동 생성됩니다.
    """

    __tablename__ = "system_config"
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # SHA-256 해싱에 사용되는 랜덤 솔트 (hex 64자)
    hash_salt: Mapped[str] = mapped_column(String(128), nullable=False)

    # MCP 에이전트와의 통신 인증 토큰 (hex 64자)
    mcp_agent_token: Mapped[str] = mapped_column(String(128), nullable=False)

    # Codef API connected_id (최초 기관 등록 시 발급, 이후 기관 추가·조회·삭제에 재사용)
    codef_connected_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    def __repr__(self) -> str:
        return f"<SystemConfig id={self.id}>"

def setup(*args, **kwargs) -> None:
    pass

