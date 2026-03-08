from datetime import datetime
from pydantic import computed_field

from .base_model import CodefBaseModel


class AccessToken(CodefBaseModel):
    access_token: str
    token_type: str
    expires_in: int
    scope: str

    created_at: datetime = datetime.now()

    @computed_field
    @property
    def is_expired(self) -> bool:
        return datetime.now() > (self.created_at + datetime.fromtimestamp(self.expires_in))
