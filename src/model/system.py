# src/model/system.py

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class SystemConfig(Base):
    """
    시스템 전역 설정 테이블.

    이 테이블은 항상 단 하나의 로우(id=1)만 가집니다.
    - hash_salt      : 계좌/카드번호 단방향 해시에 사용하는 랜덤 솔트
    - mcp_agent_token: MCP 에이전트 인증 토큰
    두 값 모두 최초 실행 시 secrets 모듈로 자동 생성됩니다.
    """

    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # SHA-256 해싱에 사용되는 랜덤 솔트 (hex 64자)
    hash_salt: Mapped[str] = mapped_column(String(128), nullable=False)

    # MCP 에이전트와의 통신 인증 토큰 (hex 64자)
    mcp_agent_token: Mapped[str] = mapped_column(String(128), nullable=False)

    def __repr__(self) -> str:
        return f"<SystemConfig id={self.id}>"
