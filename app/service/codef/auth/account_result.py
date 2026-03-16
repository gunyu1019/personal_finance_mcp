from __future__ import annotations
from .account import Account
from ..base_model import CodefBaseModel


class AccountModifyResult(CodefBaseModel):
    connected_id: str  # 커넥티드 아이디
    success_list: list[Account]
    error_list: list[Account]


class AccountListResult(CodefBaseModel):
    connected_id: str  # 커넥티드 아이디
    account_list: list[Account]


class ConnectedIdListResult(CodefBaseModel):
    page_no: int
    has_next: bool
    connected_id_list: list[str]
    next_page_no: int
