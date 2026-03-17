# app/schema/mcp_responses.py

"""
FastMCP Tool 응답용 Pydantic 스키마 정의.

MCP Tool에서 반환하는 데이터의 타입 안정성을 보장하고,
AI 에이전트가 정확한 JSON Schema를 받을 수 있도록 합니다.

⚠️ 보안 주의사항: 
- 마스킹된 정보(masked_*)만 포함
- 암호화된 원본 데이터(encrypted_*)는 절대 포함하지 않음
"""
from __future__ import annotations

from datetime import date
from typing import Literal
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────
# 은행 계좌 관련 응답 스키마
# ─────────────────────────────────────────────────────────────

class BankAccountInfo(BaseModel):
    """MCP Tool에서 반환하는 은행 계좌 정보."""
    
    bank_name: str = Field(..., description="은행명 (예: 신한은행)")
    company_code: str = Field(..., description="CODEF 기관 코드 (예: 0088)")
    masked_account_no: str = Field(..., description="마스킹된 계좌번호 (예: 110-***-***789)")
    account_name: str | None = Field(None, description="계좌 상품명")
    account_type: str | None = Field(None, description="계좌 유형 (예금/외화/펀드/대출/보험)")


class BankTransactionRecord(BaseModel):
    """은행 거래내역 개별 레코드."""
    
    date: str = Field(..., description="거래일자 (YYYYMMDD)")
    time: str | None = Field(None, description="거래시간 (HHMMSS)")
    withdrawal: str | None = Field(None, description="출금액 (원)")
    deposit: str | None = Field(None, description="입금액 (원)")
    balance: str | None = Field(None, description="거래 후 잔액 (원)")
    resAccountDesc1: str | None = Field(None, description="거래내역 비고1 [보낸분/받는분]")
    resAccountDesc2: str | None = Field(None, description="거래내역 비고2 [거래구분/메모]")
    resAccountDesc3: str | None = Field(None, description="거래내역 비고3 [적요]")
    resAccountDesc4: str | None = Field(None, description="거래내역 비고4 [거래점]")


class BankAccountListResponse(BaseModel):
    """은행 계좌 목록 조회 응답."""
    
    accounts: list[BankAccountInfo] = Field(..., description="MCP 노출 가능한 은행 계좌 목록")


class BankTransactionListResponse(BaseModel):
    """은행 거래내역 조회 응답."""
    
    account_info: BankAccountInfo = Field(..., description="조회 대상 계좌 정보")
    transactions: list[BankTransactionRecord] = Field(..., description="거래내역 목록 (최근 30일)")
    total_count: int = Field(..., description="총 거래 건수")


# ─────────────────────────────────────────────────────────────
# 카드 관련 응답 스키마
# ─────────────────────────────────────────────────────────────

class CardAccountInfo(BaseModel):
    """MCP Tool에서 반환하는 카드 정보."""
    
    card_company: str = Field(..., description="카드사명 (예: 신한카드)")
    company_code: str = Field(..., description="CODEF 카드사 코드 (예: 0306)")
    masked_card_no: str = Field(..., description="마스킹된 카드번호 (예: 1234-****-****-5678)")
    card_name: str | None = Field(None, description="카드 상품명")
    card_image_url: str | None = Field(None, description="카드 이미지 URL")


class CardTransactionRecord(BaseModel):
    """카드 승인내역 개별 레코드."""
    
    date: str = Field(..., description="사용일자 (YYYYMMDD)")
    time: str | None = Field(None, description="사용시간 (HHMMSS)")
    merchant: str = Field(..., description="가맹점명")
    amount: str = Field(..., description="사용금액 (원)")
    currency: str | None = Field(None, description="통화코드 (KRW 등)")
    status: Literal["승인", "취소"] = Field(..., description="승인 상태")
    installment: str = Field(..., description="할부개월 (일시불/3개월 등)")


class CardAccountListResponse(BaseModel):
    """카드 목록 조회 응답."""
    
    cards: list[CardAccountInfo] = Field(..., description="MCP 노출 가능한 카드 목록")


class CardTransactionListResponse(BaseModel):
    """카드 승인내역 조회 응답."""
    
    card_info: CardAccountInfo = Field(..., description="조회 대상 카드 정보")
    transactions: list[CardTransactionRecord] = Field(..., description="승인내역 목록 (최근 30일)")
    total_count: int = Field(..., description="총 승인 건수")


# ─────────────────────────────────────────────────────────────
# 에러 응답 스키마
# ─────────────────────────────────────────────────────────────

class MCPErrorResponse(BaseModel):
    """MCP Tool 에러 응답."""
    
    error: bool = Field(True, description="에러 발생 여부")
    message: str = Field(..., description="에러 메시지")
    error_code: str | None = Field(None, description="에러 코드 (선택사항)")