import aiohttp
import asyncio
import base64
import urllib.parse
import json

from ahttp_client import Session, RequestCore
from typing import Optional

from .access_token import AccessToken
from .property import OAUTH_DOMAIN, PATH_GET_TOKEN


class CodefBaseHttp(Session):
    def __init__(
            self,
            base_url: str,
            client_id: str,
            client_secret: str,
            loop: Optional[asyncio.AbstractEventLoop] = None
    ):
        super().__init__(base_url=base_url, loop=loop, directly_response=True)

        self._client_id = client_id
        self._client_secret = client_secret

        self._oauth2_session = aiohttp.ClientSession(base_url=OAUTH_DOMAIN)
        self._access_token: Optional[AccessToken] = None

    async def fetch_access_token(self) -> AccessToken:
        params = {
            "grant_type": "client_credentials",
            "scope": "read"
        }

        _token = b"%s:%s" % (self._client_id.encode(), self._client_secret.encode())
        header = {
            "Authorization": f"Basic {base64.b64encode(_token).decode()}"
        }

        response = await self._oauth2_session.post(PATH_GET_TOKEN, params=params, headers=header)

        if response.status != 200:
            raise Exception(f"Failed to fetch access token: {response.status}")

        raw_data = await response.json()
        self._access_token = AccessToken.model_validate(raw_data)
        return self._access_token

    def update_access_token(self, access_token: AccessToken):
        self._access_token = access_token

    async def before_request(self, request: RequestCore, path: str) -> tuple[RequestCore, str]:
        if self._access_token is None or self._access_token.is_expired:
            await self.fetch_access_token()

        request.headers["Authorization"] = f"Bearer {self._access_token.access_token}"
        return request, path

    async def after_request(self, response: aiohttp.ClientResponse):
        if response.content_type.startswith("text/plain"):
            text = await response.text()
            decoded_text = urllib.parse.unquote_plus(text)
            serialization = json.loads(decoded_text)
            return serialization
        return response
