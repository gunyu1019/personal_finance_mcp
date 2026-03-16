# src/model/__init__.py

from __future__ import annotations
from app.model.bank_account import BankAccount
from app.model.card_account import CardAccount
from app.model.system import SystemConfig

__all__ = [
    "BankAccount",
    "CardAccount",
    "SystemConfig",
]

def setup(*args, **kwargs) -> None:
    pass

