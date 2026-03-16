from __future__ import annotations
from typing import Literal, Optional

from ..base_model import CodefBaseModel


class CardAccount(CodefBaseModel):
    res_card_no: str
    res_sleep_yn: Optional[Literal['Y', 'N']] = None
    res_card_name: str
    res_card_type: Optional[str] = None
    res_traffic_yn: Optional[Literal['Y', 'N']] = None
    res_image_link: Optional[str] = None
    res_issue_date: Optional[str] = None
    res_valid_period: Optional[str] = None
    res_status: Optional[str] = None
