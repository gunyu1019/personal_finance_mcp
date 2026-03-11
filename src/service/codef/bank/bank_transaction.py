from typing import Optional
from ..base_model import CodefBaseModel


class TransactionHistory(CodefBaseModel):
    res_account_tr_date: str
    res_account_tr_time: str
    res_account_out: str
    res_account_in: str
    res_after_tran_balance: str
    res_account_desc1: Optional[str] = None
    res_account_desc2: Optional[str] = None
    res_account_desc3: Optional[str] = None
    res_account_desc4: Optional[str] = None


class BankTransaction(CodefBaseModel):
    res_account: str
    res_account_display: str
    res_account_name: str
    res_account_balance: str
    res_account_nick_name: Optional[str] = None
    res_account_start_date: Optional[str] = None
    res_last_tran_date: Optional[str] = None

    res_withdrawal_amt: Optional[str] = None
    res_loan_limit_amt: Optional[str] = None
    res_account_holder: Optional[str] = None
    res_management_branch: Optional[str] = None
    res_interest_rate: Optional[str] = None
    res_loan_end_date: Optional[str] = None
    res_account_status: Optional[str] = None
    comm_start_date: Optional[str] = None
    comm_end_date: Optional[str] = None

    # 거래내역 리스트
    res_tr_history_list: Optional[list[TransactionHistory]] = []