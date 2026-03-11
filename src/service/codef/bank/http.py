import asyncio

from ahttp_client import BodyJson, request
from ahttp_client.extension import pydantic_response_model, pydantic_request_model
from typing import Annotated, Optional, Literal

from ..base_http import CodefBaseHttp
from ..result import CodefResult

from .bank_result import BankAccountResult, BankRegistrationResult
from .bank_transaction import BankTransaction
from .property import *



class BankHttp(CodefBaseHttp):
    def __init__(self, base_url: str, client_id: str, client_secret: str,
                 loop: Optional[asyncio.AbstractEventLoop] = None):
        super().__init__(base_url, client_id, client_secret, loop)

    @pydantic_request_model()
    @pydantic_response_model()
    @request("POST", PATH_BANK_REGISTRATION_STATUS)
    async def bank_registration_status(
            self,
            connected_id: Annotated[str, BodyJson.to_camel()],
            organization: Annotated[str, BodyJson.to_camel()],
            birth_date: Annotated[Optional[str], BodyJson.to_camel()] = None,
    ) -> CodefResult[BankRegistrationResult]:
        pass

    @pydantic_request_model()
    @pydantic_response_model()
    @request("POST", PATH_BANK_ACCOUNT_LIST)
    async def bank_account_list(
            self,
            organization: Annotated[str, BodyJson.to_camel()],
            connected_id: Annotated[str, BodyJson.to_camel()],
            birth_date: Annotated[Optional[str], BodyJson.to_camel()] = None,
            withdraw_account_no: Annotated[Optional[str], BodyJson.to_camel()] = None,
            withdraw_account_password: Annotated[Optional[str], BodyJson.to_camel()] = None,
    ) -> CodefResult[BankAccountResult]:
        pass

    @pydantic_request_model()
    @pydantic_response_model()
    @request("POST", PATH_BANK_TRANSACTION_LIST)
    async def bank_transaction_list(
            self,
            organization: Annotated[str, BodyJson.to_camel()],
            connected_id: Annotated[str, BodyJson.to_camel()],
            account: Annotated[str, BodyJson.to_camel()],  # 숫자만 입력
            start_date: Annotated[str, BodyJson.to_camel()],
            end_date: Annotated[str, BodyJson.to_camel()],
            order_by: Annotated[Optional[Literal['0', '1']], BodyJson.to_camel()] = None,
            inquiry_type: Annotated[Optional[Literal['0', '1']], BodyJson.to_camel()] = None,
            account_password: Annotated[Optional[str], BodyJson.to_camel()] = None,
            birth_date: Annotated[Optional[str], BodyJson.to_camel()] = None,
    ) -> CodefResult[BankTransaction]:
        pass
