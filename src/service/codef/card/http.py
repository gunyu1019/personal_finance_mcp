import asyncio

from ahttp_client import BodyJson, Header, request
from ahttp_client.extension import pydantic_response_model, pydantic_request_model
from typing import Annotated, Optional, Literal

from ..base_http import CodefBaseHttp
from ..result import CodefResult
from .card_approval import CardApproval
from .card_account import CardAccount
from .card_result import CardRegistrationResult

from .property import *



class CardHttp(CodefBaseHttp):
    def __init__(self, base_url: str, client_id: str, client_secret: str,
                 loop: Optional[asyncio.AbstractEventLoop] = None):
        super().__init__(base_url, client_id, client_secret, loop)

    @pydantic_request_model()
    @pydantic_response_model()
    @request("POST", PATH_CARD_REGISTRATION_STATUS)
    async def card_registration_status(
            self,
            connected_id: Annotated[str, BodyJson.to_camel()],
            organization: Annotated[str, BodyJson.to_camel()],
            inquiry_type: Annotated[Literal['0', '1'], BodyJson.to_camel()] = '0',
            identity: Annotated[Optional[str], BodyJson.to_camel()] = None,
            birth_date: Annotated[Optional[str], BodyJson.to_camel()] = None,
            user_id: Annotated[Optional[str], BodyJson.to_camel()] = None,
            card_no: Annotated[Optional[str], BodyJson.to_camel()] = None,
            card_password: Annotated[Optional[str], BodyJson.to_camel()] = None,
            card_valid_period: Annotated[Optional[str], BodyJson.to_camel()] = None,
            authorization: Annotated[Optional[str], Header.to_camel()] = None,
    ) -> CodefResult[CardRegistrationResult]:
        pass

    @pydantic_request_model()
    @pydantic_response_model()
    @request("POST", PATH_CARD_ACCOUNT_LIST)
    async def card_account_list(
            self,
            connected_id: Annotated[str, BodyJson.to_camel()],
            organization: Annotated[str, BodyJson.to_camel()],
            inquiry_type: Annotated[Literal['0', '1'], BodyJson.to_camel()] = '0',
            user_id: Annotated[Optional[str], BodyJson.to_camel()] = None,
            card_no: Annotated[Optional[str], BodyJson.to_camel()] = None,
            card_password: Annotated[Optional[str], BodyJson.to_camel()] = None,
            authorization: Annotated[Optional[str], Header.to_camel()] = None,
    ) -> CodefResult[CardAccount]:
        pass

    @pydantic_request_model()
    @pydantic_response_model()
    @request("POST", PATH_CARD_APPROVAL_LIST)
    async def card_approval_list(
            self,
            organization: Annotated[str, BodyJson.to_camel()],
            connected_id: Annotated[str, BodyJson.to_camel()],
            start_date: Annotated[str, BodyJson.to_camel()],
            end_date: Annotated[str, BodyJson.to_camel()],
            birth_date: Annotated[Optional[str], BodyJson.to_camel()] = None,
            order_by: Annotated[Optional[Literal['0', '1']], BodyJson.to_camel()] = "0",
            inquiry_type: Annotated[Optional[Literal['0', '1']], BodyJson.to_camel()] = None,
            card_name: Annotated[Optional[str], BodyJson.to_camel()] = None,
            duplicate_card_idx: Annotated[Optional[str], BodyJson.to_camel()] = None,
            card_no: Annotated[Optional[str], BodyJson.to_camel()] = None,
            card_password: Annotated[Optional[str], BodyJson.to_camel()] = None,
            member_store_info_type: Annotated[Literal['0', '1', '2', '3'], BodyJson.to_camel()] = '0',
            authorization: Annotated[Optional[str], Header.to_camel()] = None,
    ) -> CodefResult[list[CardApproval]]:
        pass
