from collections import deque
from collections.abc import Sequence
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import select, exists
from sqlalchemy.sql.base import NO_ARG

from .base_repository import BaseRepository


class AuthRepository(BaseRepository):
    pass