from typing import Generic, TypeVar
from .base_model import CodefBaseModel

T = TypeVar("T")


class CodefResultInfo(CodefBaseModel):
    code: str
    message: str
    extra_message: str
    transaction_id: str


class CodefResult(CodefBaseModel, Generic[T]):
    code: CodefResultInfo  # 결과코드
    data: T  # 결과 데이터
