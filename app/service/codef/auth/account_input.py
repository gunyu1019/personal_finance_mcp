from __future__ import annotations
from pydantic import Field

from .account import Account
from .account_register import AccountRegister
from ..base_model import CodefBaseModel


class AccountRegisterList(CodefBaseModel):
    account_list: list[AccountRegister] = Field(default_factory=list)


class AccountModifyList(CodefBaseModel):
    account_list: list[AccountRegister] = Field(default_factory=list)
    connected_id: str


class AccountList(CodefBaseModel):
    account_list: list[Account] = Field(default_factory=list)
    connected_id: str
