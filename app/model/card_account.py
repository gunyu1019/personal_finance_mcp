# src/model/card_account.py

from __future__ import annotations
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import Base


class CardAccount(Base):
    """카드 정보 모델."""

    __tablename__ = "card_accounts"
    __table_args__ = {'extend_existing': True}

    # CODEF 카드사 코드 (예: "0306" = 신한카드)
    card_code: Mapped[str] = mapped_column(String(10), nullable=False)

    # SHA-256 해시된 카드번호 (중복 등록 방지용 Unique)
    hashed_card_no: Mapped[str] = mapped_column(String(64), nullable=False, primary_key=True)

    # 마스킹된 카드번호 (예: 1234-****-****-5678)
    masked_card_no: Mapped[str] = mapped_column(String(25), nullable=False)

    # AES-256 암호화된 원본 카드번호 (Codef API 호출용)
    encrypted_card_no: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # AES-256 암호화된 카드 비밀번호 앞자리 (Codef API 호출용)
    encrypted_card_password: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 카드 상품명 (예: "taptap O 카드")
    card_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 카드 이미지 URL (CODEF res_image_link)
    card_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # MCP 에이전트 노출 여부 (기본 True)
    is_mcp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return (
            f"<CardAccount id={self.hashed_card_no} code={self.card_code!r} "
            f"masked={self.masked_card_no!r} mcp={self.is_mcp_enabled}>"
        )

def setup(*args, **kwargs) -> None:
    pass

