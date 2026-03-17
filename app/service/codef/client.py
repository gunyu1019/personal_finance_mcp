from __future__ import annotations

import asyncio
import inspect

from functools import wraps
from typing import Optional, Callable, Awaitable, Any, TypeVar, Literal

from .access_token import AccessToken
from .auth.account import Account
from .auth.account_input import AccountModifyList, AccountList, AccountRegisterList
from .auth.account_register import AccountRegister
from .auth.account_result import AccountModifyResult, ConnectedIdListResult, AccountListResult
from .auth.http import AuthHttp
from .bank.bank_result import BankRegistrationResult, BankAccountResult
from .bank.bank_transaction import BankTransaction
from .bank.http import BankHttp
from .card.card_account import CardAccount
from .card.card_approval import CardApproval
from .card.card_result import CardRegistrationResult
from .card.http import CardHttp
from .encryption import get_encrypt
from .property import API_DOMAIN
from .result import CodefResult

T = TypeVar("T")


class CodefClient:
    @staticmethod
    def _token_validation(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(self: CodefClient, *args: Any, **kwargs: Any) -> T:
            await self.ensure_access_token()
            return await func(self, *args, **kwargs)

        return wrapper

    def __init__(
            self,
            public_key_pem: str,
            client_id: str,
            client_secret: str,
            base_url: str = API_DOMAIN,
            loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        self.__public_key_pem = public_key_pem
        self.__client_id = client_id
        self.__client_secret = client_secret

        self._auth_http = AuthHttp(base_url=base_url, client_id=client_id, client_secret=client_secret, loop=loop)
        self._bank_http = BankHttp(base_url=base_url, client_id=client_id, client_secret=client_secret, loop=loop)
        self._card_http = CardHttp(base_url=base_url, client_id=client_id, client_secret=client_secret, loop=loop)

        self._access_token: Optional[AccessToken] = None
        self._token_lock = asyncio.Lock()

    @property
    def client_id(self) -> str:
        return self.__client_id

    @property
    def client_secret(self) -> str:
        return self.__client_secret

    @property
    def public_key_pem(self) -> str:
        return self.__public_key_pem

    def update_access_token(self, access_token: AccessToken):
        self._access_token = access_token
        self._auth_http.update_access_token(access_token)
        self._bank_http.update_access_token(access_token)
        self._card_http.update_access_token(access_token)

    async def fetch_access_token(self) -> AccessToken:
        access_token = await self._auth_http.fetch_access_token()
        self.update_access_token(access_token)
        return access_token

    async def ensure_access_token(self) -> AccessToken:
        if self._access_token is not None and not self._access_token.is_expired:
            self.update_access_token(self._access_token)
            return self._access_token

        async with self._token_lock:
            if self._access_token is not None and not self._access_token.is_expired:
                self.update_access_token(self._access_token)
                return self._access_token

            return await self.fetch_access_token()

    def _encrypt_password(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return get_encrypt(value=value, public_key_pem=self.__public_key_pem)

    def _encrypt_account_register(self, account_register: AccountRegister) -> AccountRegister:
        encrypted_password = self._encrypt_password(account_register.password)
        encrypted_card_password = self._encrypt_password(account_register.card_password)

        account_register.password = encrypted_password
        account_register.card_password = encrypted_card_password
        return account_register

    @_token_validation
    async def auth_create_account(
            self,
            account: list[AccountRegister],
            authorization: Optional[str] = None
    ) -> CodefResult[AccountModifyResult]:
        encrypted_accounts = [self._encrypt_account_register(item) for item in account]
        return await self._auth_http.create_account(
            account=AccountRegisterList(account_list=encrypted_accounts),
            authorization=authorization
        )

    @_token_validation
    async def auth_add_account(
            self,
            connected_id: str,
            account: list[AccountRegister],
            authorization: Optional[str] = None
    ) -> CodefResult[AccountModifyResult]:
        encrypted_accounts = [self._encrypt_account_register(item) for item in account]
        return await self._auth_http.add_account(
            account=AccountModifyList(account_list=encrypted_accounts, connected_id=connected_id),
            authorization=authorization,
        )

    @_token_validation
    async def auth_update_account(
            self,
            connected_id: str,
            account: list[AccountRegister],
            authorization: Optional[str] = None
    ) -> CodefResult[AccountModifyResult]:
        encrypted_accounts = [self._encrypt_account_register(item) for item in account]
        return await self._auth_http.update_account(
            account=AccountModifyList(account_list=encrypted_accounts, connected_id=connected_id),
            authorization=authorization,
        )

    @_token_validation
    async def auth_delete_account(
            self,
            account: list[Account],
            connected_id: str,
            authorization: Optional[str] = None
    ) -> CodefResult[AccountModifyResult]:
        return await self._auth_http.delete_account(
            account=AccountList(account_list=account, connected_id=connected_id),
            authorization=authorization
        )

    @_token_validation
    async def auth_get_account_list(
            self,
            connected_id: str,
            authorization: Optional[str] = None
    ) -> CodefResult[AccountListResult]:
        return await self._auth_http.get_account_list(connected_id=connected_id, authorization=authorization)

    @_token_validation
    async def auth_get_cid_list(
            self,
            page_no: int,
            authorization: Optional[str] = None
    ) -> CodefResult[ConnectedIdListResult]:
        return await self._auth_http.get_cid_list(page_no=page_no, authorization=authorization)

    @_token_validation
    async def bank_registration_status(
            self,
            connected_id: str,
            organization: str,
            birth_date: Optional[str] = None,
            authorization: Optional[str] = None,
    ) -> CodefResult[BankRegistrationResult]:
        return await self._bank_http.bank_registration_status(
            connected_id=connected_id,
            organization=organization,
            birth_date=birth_date,
            authorization=authorization,
        )

    @_token_validation
    async def bank_account_list(
            self,
            organization: str,
            connected_id: str,
            birth_date: Optional[str] = None,
            withdraw_account_no: Optional[str] = None,
            withdraw_account_password: Optional[str] = None,
            authorization: Optional[str] = None,
    ) -> CodefResult[BankAccountResult]:
        encrypted_withdraw_password = self._encrypt_password(withdraw_account_password)
        return await self._bank_http.bank_account_list(
            organization=organization,
            connected_id=connected_id,
            birth_date=birth_date,
            withdraw_account_no=withdraw_account_no,
            withdraw_account_password=encrypted_withdraw_password,
            authorization=authorization,
        )

    @_token_validation
    async def bank_transaction_list(
            self,
            organization: str,
            connected_id: str,
            account: str,
            start_date: str,
            end_date: str,
            order_by: Optional[str] = '0',
            inquiry_type: Optional[str] = None,
            account_password: Optional[str] = None,
            birth_date: Optional[str] = None,
            authorization: Optional[str] = None,
    ) -> CodefResult[BankTransaction]:
        encrypted_account_password = self._encrypt_password(account_password)
        return await self._bank_http.bank_transaction_list(
            organization=organization,
            connected_id=connected_id,
            account=account,
            start_date=start_date,
            end_date=end_date,
            order_by=order_by,
            inquiry_type=inquiry_type,
            account_password=encrypted_account_password,
            birth_date=birth_date,
            authorization=authorization,
        )

    @_token_validation
    async def card_registration_status(
            self,
            connected_id: str,
            organization: str,
            inquiry_type: Literal["0", "1"] = "0",
            identity: Optional[str] = None,
            birth_date: Optional[str] = None,
            user_id: Optional[str] = None,
            card_no: Optional[str] = None,
            card_password: Optional[str] = None,
            card_valid_period: Optional[str] = None,
            authorization: Optional[str] = None,
    ) -> CodefResult[CardRegistrationResult]:
        encrypted_card_password = self._encrypt_password(card_password)
        return await self._card_http.card_registration_status(
            connected_id=connected_id,
            organization=organization,
            inquiry_type=inquiry_type,
            identity=identity,
            birth_date=birth_date,
            user_id=user_id,
            card_no=card_no,
            card_password=encrypted_card_password,
            card_valid_period=card_valid_period,
            authorization=authorization,
        )

    @_token_validation
    async def card_account_list(
            self,
            connected_id: str,
            organization: str,
            inquiry_type: Literal["0", "1"] = "0",
            birth_date: Optional[str] = None,
            card_no: Optional[str] = None,
            card_password: Optional[str] = None,
            authorization: Optional[str] = None,
    ) -> CodefResult[CardAccount | list[CardAccount]]:
        encrypted_card_password = self._encrypt_password(card_password)
        return await self._card_http.card_account_list(
            connected_id=connected_id,
            organization=organization,
            inquiry_type=inquiry_type,
            birth_date=birth_date,
            card_no=card_no,
            card_password=encrypted_card_password,
            authorization=authorization,
        )

    @_token_validation
    async def card_approval_list(
            self,
            organization: str,
            connected_id: str,
            start_date: str,
            end_date: str,
            birth_date: Optional[str] = None,
            order_by: Optional[str] = "0",
            inquiry_type: Literal["0", "1"] = "0",
            card_name: Optional[str] = None,
            duplicate_card_idx: Optional[str] = None,
            card_no: Optional[str] = None,
            card_password: Optional[str] = None,
            member_store_info_type: Literal["0", "1", "2", "3"] = "0",
            authorization: Optional[str] = None,
    ) -> CodefResult[CardApproval | list[CardApproval]]:
        encrypted_card_password = self._encrypt_password(card_password)
        return await self._card_http.card_approval_list(
            organization=organization,
            connected_id=connected_id,
            start_date=start_date,
            end_date=end_date,
            birth_date=birth_date,
            order_by=order_by,
            inquiry_type=inquiry_type,
            card_name=card_name,
            duplicate_card_idx=duplicate_card_idx,
            card_no=card_no,
            card_password=encrypted_card_password,
            member_store_info_type=member_store_info_type,
            authorization=authorization,
        )

    async def close(self):
        import asyncio
        
        await asyncio.gather(
            self._close_http_client(self._auth_http),
            self._close_http_client(self._bank_http),
            self._close_http_client(self._card_http),
            return_exceptions=True  # 하나의 close가 실패해도 나머지는 계속 진행
        )

    @staticmethod
    async def _close_http_client(http_client: Any):
        close_method = getattr(http_client, "close", None)
        if callable(close_method):
            close_result = close_method()
            if inspect.isawaitable(close_result):
                await close_result

        oauth2_session = getattr(http_client, "_oauth2_session", None)
        if oauth2_session is not None and not oauth2_session.closed:
            await oauth2_session.close()
