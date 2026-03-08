from typing import Optional, Literal
from ..base_model import CodefBaseModel


class Account(CodefBaseModel):
    code: Optional[str] = None  # 결과코드
    message: Optional[str] = None  # 메시지
    country_code: Literal['KR']  # 국가코드 (한국: KR)
    client_type: Literal['P', 'B', 'A']  # 고객 구분 (개인: P, 기업/법인: B, 통합: A)
    organization: str  # 기관코드
    business_type: Literal['BK', 'CD', 'ST', 'IS']  # 업무 구분 (은행/저축은행: BK, 카드: CD, 증권: ST, 보험: IS)



class AccountResult(CodefBaseModel):
    connected_id: str  # 커넥티드 아이디
    success_list: list[Account]
    error_list: list[Account]
