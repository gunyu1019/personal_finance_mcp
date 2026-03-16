# src/core/config.py

from __future__ import annotations
import configparser
import os

from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 환경 변수 설정."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 관리자 페이지 로그인 비밀번호
    ROOT_PASSWORD: str = "changeme"

    # 비동기 SQLite 연결 URL
    DATABASE_URL: str = "sqlite+aiosqlite:///./mydata.db"

    # CODEF Personal Finance MCP API 인증 정보
    CODEF_CLIENT_ID: str = ""
    CODEF_CLIENT_SECRET: str = ""
    CODEF_PUBLIC_KEY: str = ""

    CODEF_MODE: Literal["live", "demo", "sandbox"] = "demo"

    # 서버 설정
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    # 상수 설정
    ADMIN_COOKIE_NAME: str = "admin_session"
    TOKEN_EXPIRE_HOURS: int = 12
    JWT_ALGORITHM: str = "HS256"
    JWT_SUBJECT: str = "admin"
    SSE_RETRY_TIMEOUT: int = 15000

    # AES-256 대칭키 암호화 설정
    ENCRYPTION_SECRET_KEY: str = ""

# ───────────────────────────────────────────
# 금융사 매핑 (mapping.ini → 딕셔너리)
# ───────────────────────────────────────────

def _load_mapping() -> tuple[dict[str, str], dict[str, str]]:
    """
    루트 디렉토리의 mapping.ini 파일을 읽어
    (BANK_MAPPING, CARD_MAPPING) 딕셔너리 튜플을 반환합니다.
    파일이 없으면 빈 딕셔너리를 반환합니다.
    """
    # 이 파일 기준으로 프로젝트 루트를 탐색
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    mapping_path = os.path.join(base_dir, "mapping.ini")

    parser = configparser.ConfigParser()
    parser.read(mapping_path, encoding="utf-8")

    bank_mapping: dict[str, str] = dict(parser["BANK"]) if "BANK" in parser else {}
    card_mapping: dict[str, str] = dict(parser["CARD"]) if "CARD" in parser else {}
    return bank_mapping, card_mapping


# 전역 설정 인스턴스
settings = Settings()

# 프로젝트 절대 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATE_DIR = os.path.join(BASE_DIR, "app", "template")

# 금융사 매핑 딕셔너리 (모듈 로드 시 1회 파싱)
BANK_MAPPING, CARD_MAPPING = _load_mapping()

# 카드 비밀번호가 필수적으로 요구되는 카드사 코드 목록
# 승인내역 조회 등 API 통신에서 비밀번호가 반드시 필요한 기관들
CARD_PASSWORD_REQUIRED_CODES = {
    "0302",  # 현대카드
    "0301",  # KB국민카드
    # 필요시 추가 카드사 코드를 여기에 추가
}
