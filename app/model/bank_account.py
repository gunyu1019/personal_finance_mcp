# src/model/bank_account.py

from __future__ import annotations
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import Base


class BankAccount(Base):
    """은행 계좌 정보 모델."""

    __tablename__ = "bank_accounts"
    __table_args__ = {'extend_existing': True}

    # CODEF 기관 코드 (예: "0088" = 신한은행)
    bank_code: Mapped[str] = mapped_column(String(10), nullable=False)

    # SHA-256 해시된 계좌번호 (중복 등록 방지용 Unique)
    hashed_account_no: Mapped[str] = mapped_column(String(64), nullable=False, primary_key=True)

    # 마스킹된 계좌번호 (예: 110-***-***789)
    masked_account_no: Mapped[str] = mapped_column(String(50), nullable=False)

    # AES-256 암호화된 원본 계좌번호 (Codef API 호출용)
    encrypted_account_no: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 계좌 상품명 (예: "직장인 우대 통장")
    account_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 계좌 유형 (예: "예금", "외화", "펀드", "대출", "보험")
    account_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # MCP 에이전트 노출 여부 (기본 True)
    is_mcp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return (
            f"<BankAccount id={self.hashed_account_no} code={self.bank_code!r} "
            f"masked={self.masked_account_no!r} mcp={self.is_mcp_enabled}>"
        )

def setup(*args, **kwargs) -> None:
    pass

