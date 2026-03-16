from __future__ import annotations
from typing import Literal, Optional

from .bank_account import BankAccount
from ..base_model import CodefBaseModel


class BankRegistrationResult(CodefBaseModel):
    res_registration_status: Literal['0', '1']
    res_result_desc: str


class BankAccountResult(CodefBaseModel):
    res_deposit_trust: Optional[list[BankAccount] | BankAccount] = []
    res_foreign_currency: Optional[list[BankAccount] | BankAccount] = []
    res_fund: Optional[list[BankAccount] | BankAccount] = []
    res_loan: Optional[list[BankAccount] | BankAccount] = []
    res_insurance: Optional[list[BankAccount] | BankAccount] = []
