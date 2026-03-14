# src/model/bank_account.py

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class BankAccount(Base):
    """은행 계좌 정보 모델."""

    __tablename__ = "bank_accounts"

    # CODEF 기관 코드 (예: "0088" = 신한은행)
    bank_code: Mapped[str] = mapped_column(String(10), nullable=False)

    # SHA-256 해시된 계좌번호 (중복 등록 방지용 Unique)
    hashed_account_no: Mapped[str] = mapped_column(String(64), nullable=False, primary_key=True)

    # 마스킹된 계좌번호 (예: 110-***-***789)
    masked_account_no: Mapped[str] = mapped_column(String(50), nullable=False)

    # MCP 에이전트 노출 여부 (기본 True)
    is_mcp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return (
            f"<BankAccount id={self.hashed_account_no} code={self.bank_code!r} "
            f"masked={self.masked_account_no!r} mcp={self.is_mcp_enabled}>"
        )
