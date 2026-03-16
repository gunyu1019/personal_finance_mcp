from __future__ import annotations
from typing import Generic, TypeVar, Optional
from .base_model import CodefBaseModel

T = TypeVar("T")


class CodefResultInfo(CodefBaseModel):
    code: str
    message: str
    extra_message: str
    transaction_id: Optional[str] = None


class CodefResult(CodefBaseModel, Generic[T]):
    result: CodefResultInfo  # 결과코드
    data: T  # 결과 데이터
