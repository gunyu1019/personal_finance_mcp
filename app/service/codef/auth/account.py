from __future__ import annotations
from pydantic import Field
from typing import Optional, Literal

from ..base_model import CodefBaseModel


class Account(CodefBaseModel):
    code: Optional[str] = Field(None, exclude=True)  # 결과코드
    message: Optional[str] = Field(None, exclude=True)   # 메시지
    country_code: Literal['KR'] = "KR"  # 국가코드 (한국: KR)
    client_type: Literal['P', 'B', 'A']  # 고객 구분 (개인: P, 기업/법인: B, 통합: A)
    organization: str = Field(alias='organizationCode')  # 기관코드
    business_type: Literal['BK', 'CD', 'ST', 'IS']  # 업무 구분 (은행/저축은행: BK, 카드: CD, 증권: ST, 보험: IS)
    login_type: Optional[Literal['0', '1']] = None # 로그인 방식 (0: 인증서, 1: 아이디/패스워드) / 계정 삭제 시에만 사용