from __future__ import annotations
from typing import Literal, Optional

from ..base_model import CodefBaseModel


class CardRegistrationStatusList(CodefBaseModel):
    res_registration_status: Literal['0', '1', '2', '3', '4']
    res_result_desc: Optional[str] = None


class CardRegistrationResult(CodefBaseModel):
    res_registration_status: Literal['0', '1']
    res_result_desc: Optional[str] = None
    res_reg_status_list: list[CardRegistrationStatusList] = []
