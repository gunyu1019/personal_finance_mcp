import asyncio

from ahttp_client import BodyJson, request, Header, Body
from ahttp_client.extension import pydantic_response_model, pydantic_request_model
from typing import Annotated, Optional

from ..base_http import CodefBaseHttp
from ..result import CodefResult

from .account_input import AccountList, AccountModifyList, AccountRegisterList
from .account_result import AccountModifyResult, ConnectedIdListResult, AccountListResult
from .property import *


class AuthHttp(CodefBaseHttp):
    def __init__(self, base_url: str, client_id: str, client_secret: str,
                 loop: Optional[asyncio.AbstractEventLoop] = None):
        super().__init__(base_url, client_id, client_secret, loop)

    @pydantic_request_model()
    @pydantic_response_model()
    @request("POST", PATH_CREATE_ACCOUNT, directly_response=True)
    async def create_account(
            self,
            account: Annotated[AccountRegisterList, Body],
            authorization: Annotated[Optional[str], Header.to_camel()] = None
    ) -> CodefResult[AccountModifyResult]:
        pass

    @pydantic_request_model()
    @pydantic_response_model()
    @request("POST", PATH_ADD_ACCOUNT, directly_response=True)
    async def add_account(
            self,
            account: Annotated[AccountModifyList, Body],
            authorization: Annotated[Optional[str], Header.to_camel()] = None
    ) -> CodefResult[AccountModifyResult]:
        pass

    @pydantic_request_model()
    @pydantic_response_model()
    @request("POST", PATH_UPDATE_ACCOUNT, directly_response=True)
    async def update_account(
            self,
            account: Annotated[AccountModifyList, Body],
            authorization: Annotated[Optional[str], Header.to_camel()] = None
    ) -> CodefResult[AccountModifyResult]:
        pass

    @pydantic_request_model()
    @pydantic_response_model()
    @request("POST", PATH_DELETE_ACCOUNT, directly_response=True)
    async def delete_account(
            self,
            account: Annotated[AccountList, Body],
            authorization: Annotated[Optional[str], Header.to_camel()] = None
    ) -> CodefResult[AccountModifyResult]:
        pass

    @pydantic_request_model()
    @pydantic_response_model()
    @request("POST", PATH_GET_ACCOUNT_LIST, directly_response=True)
    async def get_account_list(
            self,
            connected_id: Annotated[str, BodyJson.to_camel()],
            authorization: Annotated[Optional[str], Header.to_camel()] = None
    ) -> CodefResult[AccountListResult]:
        pass

    @pydantic_request_model()
    @pydantic_response_model()
    @request("POST", PATH_GET_CID_LIST, directly_response=True)
    async def get_cid_list(
            self,
            page_no: Annotated[int, BodyJson.to_camel()],
            authorization: Annotated[Optional[str], Header.to_camel()] = None
    ) -> CodefResult[ConnectedIdListResult]:
        pass
