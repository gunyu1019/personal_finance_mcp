# src/model/card_account.py

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class CardAccount(Base):
    """카드 정보 모델."""

    __tablename__ = "card_accounts"

    # CODEF 카드사 코드 (예: "0306" = 신한카드)
    card_code: Mapped[str] = mapped_column(String(10), nullable=False)

    # SHA-256 해시된 카드번호 (중복 등록 방지용 Unique)
    hashed_card_no: Mapped[str] = mapped_column(String(64), nullable=False, primary_key=True)

    # 마스킹된 카드번호 (예: 1234-****-****-5678)
    masked_card_no: Mapped[str] = mapped_column(String(25), nullable=False)

    # MCP 에이전트 노출 여부 (기본 True)
    is_mcp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return (
            f"<CardAccount id={self.hashed_card_no} code={self.card_code!r} "
            f"masked={self.masked_card_no!r} mcp={self.is_mcp_enabled}>"
        )
