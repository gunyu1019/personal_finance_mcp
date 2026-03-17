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
# 금융사 매핑 (Enum 기반 + mapping.ini 보완)
# ───────────────────────────────────────────

def _load_mapping() -> tuple[dict[str, str], dict[str, str]]:
    """
    Enum 기반 매핑을 우선 사용하고, mapping.ini 파일로 보완합니다.
    
    1. BankCompany, CardCompany enum에서 기본 매핑을 가져옴
    2. mapping.ini 파일이 있으면 추가/덮어쓰기로 보완
    3. 타입 안전성과 확장성을 모두 제공
    
    Returns:
        tuple[dict[str, str], dict[str, str]]: (BANK_MAPPING, CARD_MAPPING) 딕셔너리
    """
    try:
        # Enum 기반 기본 매핑 로드
        from app.service.codef.bank.company import BankCompany
        from app.service.codef.card.company import CardCompany
        
        bank_mapping = BankCompany.get_all_mappings()
        card_mapping = CardCompany.get_all_mappings()
    except ImportError:
        # Enum을 가져올 수 없는 경우 빈 딕셔너리로 시작
        bank_mapping: dict[str, str] = {}
        card_mapping: dict[str, str] = {}

    # mapping.ini 파일로 보완 (있는 경우)
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        mapping_path = os.path.join(base_dir, "mapping.ini")

        parser = configparser.ConfigParser()
        parser.read(mapping_path, encoding="utf-8")

        # ini 파일의 내용으로 기존 매핑을 업데이트 (덮어쓰기 허용)
        if "BANK" in parser:
            bank_mapping.update(dict(parser["BANK"]))
        if "CARD" in parser:
            card_mapping.update(dict(parser["CARD"]))
    except (FileNotFoundError, configparser.Error):
        # mapping.ini 파일이 없거나 파싱 실패해도 enum 매핑은 유지
        pass

    return bank_mapping, card_mapping


def _get_card_password_required_codes() -> set[str]:
    """
    카드 비밀번호가 필수인 카드사 코드들을 Enum에서 가져옵니다.
    
    Returns:
        set[str]: 비밀번호 필수 카드사 코드 집합
    """
    try:
        from app.service.codef.card.company import CardCompany
        return CardCompany.get_password_required_codes()
    except ImportError:
        # Enum을 가져올 수 없는 경우 하드코딩된 기본값 사용
        return {
            "0301",  # KB국민카드
            "0302",  # 현대카드
            "0303",  # 삼성카드
            "0306",  # 신한카드
            "0309",  # 우리카드
            "0311",  # 롯데카드
            "0313",  # 하나카드
        }


# 전역 설정 인스턴스
settings = Settings()

# 프로젝트 절대 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATE_DIR = os.path.join(BASE_DIR, "app", "template")

# 금융사 매핑 딕셔너리 (모듈 로드 시 1회 파싱, Enum 기반)
BANK_MAPPING, CARD_MAPPING = _load_mapping()

# 카드 비밀번호가 필수적으로 요구되는 카드사 코드 목록 (Enum 기반)
# 승인내역 조회 등 API 통신에서 비밀번호가 반드시 필요한 기관들
CARD_PASSWORD_REQUIRED_CODES = _get_card_password_required_codes()
