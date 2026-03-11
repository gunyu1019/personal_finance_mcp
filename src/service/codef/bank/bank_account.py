from typing import Optional

from ..base_model import CodefBaseModel


class BankAccount(CodefBaseModel):
    res_account: str
    res_account_display: str
    res_account_name: str
    res_account_balance: str
    res_account_nick_name: Optional[str] = None
    res_account_start_date: Optional[str] = None
    res_last_tran_date: Optional[str] = None

    """보유계좌 내의 개별 계좌 상세 정보"""
    res_account_end_date: Optional[str] = None
    res_account_deposit: Optional[str] = None
    res_account_currency: Optional[str] = None  # ISO4217 통화코드

    # 특정 계좌 종류에만 있는 필드들
    res_overdraft_acct_yn: Optional[str] = None   # 예금/신탁
    res_account_lifetime: Optional[str] = None    # 예금/신탁
    res_earnings_rate: Optional[str] = None       # 펀드
    res_account_invested_cost: Optional[str] = None # 펀드
    res_account_loan_exec_no: Optional[str] = None  # 대출
