from __future__ import annotations
from typing import Literal, Optional
from pydantic import Field

from ..base_model import CodefBaseModel


class CardApproval(CodefBaseModel):# 필수 필드 (O)
    res_used_date: str
    res_used_amount: str
    res_payment_type: Literal['1', '2', '3']
    res_account_currency: str
    res_home_foreign_type: Literal['1', '2']

    res_cancel_yn: Literal['0', '1', '2', '3'] = Field(alias="resCancelYN")

    # 선택 필드 (△)
    res_used_time: Optional[str] = None
    res_card_no: Optional[str] = None
    res_card_no1: Optional[str] = None
    res_card_name: Optional[str] = None
    res_member_store_name: Optional[str] = None
    res_installment_month: Optional[str] = None
    res_approval_no: Optional[str] = None
    res_payment_due_date: Optional[str] = None

    # 가맹점 부가 정보 (reqMemberStoreInfoYN 조건 등)
    res_member_store_corp_no: Optional[str] = None
    res_member_store_type: Optional[str] = None
    res_member_store_tel_no: Optional[str] = None
    res_member_store_addr: Optional[str] = None
    res_member_store_no: Optional[str] = None
    res_cancel_amount: Optional[str] = None
    res_cash_back: Optional[str] = None

    comm_start_date: str
    comm_end_date: str

    # 약어 등 대문자 연속으로 인해 수동 alias가 필요한 선택 필드
    res_vat: Optional[str] = Field(default=None, alias="resVAT")
    res_krw_amt: Optional[str] = Field(default=None, alias="resKRWAmt")
