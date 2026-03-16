# src/api/finance.py
# 마이데이터 금융 정보 API

import json
import logging
from typing import Any, AsyncGenerator, ClassVar, Literal, TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status, FastAPI
from fastapi.responses import StreamingResponse
from fastapi_restful.cbv import cbv

from app.api.auth import get_current_admin
from app.core.crypto import decrypt_data, encrypt_sensitive_data
from app.core.config import settings, CARD_PASSWORD_REQUIRED_CODES
from app.core.database import AsyncSessionFactory
from app.core.security import hash_data, mask_account_no, mask_card_no
from app.dto.bank_account_dto import BankAccountUpsertData
from app.dto.card_account_dto import CardAccountUpsertData
from app.repository.bank_account_repository import BankAccountRepository
from app.repository.card_account_repository import CardAccountRepository
from app.repository.system_repository import SystemRepository
from app.schema.finance import (
    FormField,
    FormResponse,
    SyncRequest,
    ToggleRequest,
    ToggleResponse,
)
from app.service.codef.client import CodefClient
from app.service.codef.auth.account_register import AccountRegister
from app.service.codef.property import API_DOMAIN, DEMO_DOMAIN, SANDBOX_DOMAIN

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/finance", tags=["finance"])

# ─────────────────────────────────────────────────────────────
# 동기화 관련 헬퍼 클래스 (모의 데이터 구조 유지)
# ─────────────────────────────────────────────────────────────
class _MockBankRawAccount:
    def __init__(
        self,
        raw_account_no: str,
        account_name: str | None = None,
        account_type: str | None = None,
    ) -> None:
        self.raw_account_no = raw_account_no
        self.account_name = account_name
        self.account_type = account_type

class _MockCardRawAccount:
    def __init__(
        self,
        raw_card_no: str,
        card_name: str | None = None,
        card_image_url: str | None = None,
    ) -> None:
        self.raw_card_no = raw_card_no
        self.card_name = card_name
        self.card_image_url = card_image_url

# ─────────────────────────────────────────────────────────────
# 엔드포인트 통합 리팩토링 (CBV)
# ─────────────────────────────────────────────────────────────

@cbv(router)
class FinanceAPI:
    # 멤버 변수: 관리자 인증 검증 (하위 모든 라우터에 자동 적용됨)
    admin_sub: str = Depends(get_current_admin)

    # ─────────────────────────────────────────────────────────────
    # 클래스 기저 설정 (폼 필드 및 민감 필드 등 상수)
    # ─────────────────────────────────────────────────────────────
    _BASE_FIELDS: ClassVar[list[FormField]] = [
        FormField(name="id",       label="아이디",   type="text"),
        FormField(name="password", label="비밀번호", type="password"),
    ]

    _FIELD_BIRTH_DATE: ClassVar[FormField] = FormField(name="birthDate", label="생년월일 (YYYYMMDD)", type="text")
    _FIELD_WITHDRAW_ACCOUNT_NO: ClassVar[FormField] = FormField(name="withdrawAccountNo", label="출금계좌번호", type="text")
    _FIELD_WITHDRAW_ACCOUNT_PASSWORD: ClassVar[FormField] = FormField(name="withdrawAccountPassword", label="출금계좌비밀번호", type="password")
    _FIELD_CARD_NO: ClassVar[FormField] = FormField(name="cardNo", label="카드번호", type="text")
    _FIELD_CARD_PASSWORD: ClassVar[FormField] = FormField(name="cardPassword", label="카드비밀번호", type="password")

    _BANK_EXTRA_FIELDS: ClassVar[dict[str, list[FormField]]] = {
        "0023": [_FIELD_BIRTH_DATE],
        "0027": [_FIELD_BIRTH_DATE],
        "0031": [_FIELD_BIRTH_DATE, _FIELD_WITHDRAW_ACCOUNT_NO, _FIELD_WITHDRAW_ACCOUNT_PASSWORD],
        "0088": [_FIELD_BIRTH_DATE],
        "0089": [_FIELD_BIRTH_DATE],
    }

    _CARD_EXTRA_FIELDS: ClassVar[dict[str, list[FormField]]] = {
        "0301": [_FIELD_CARD_NO, _FIELD_CARD_PASSWORD],
        "0302": [_FIELD_CARD_NO, _FIELD_CARD_PASSWORD],
        "0311": [_FIELD_BIRTH_DATE],
    }

    _SENSITIVE_FIELDS: ClassVar[tuple[str, ...]] = ("password", "cardPassword", "withdrawAccountPassword")

    # ─────────────────────────────────────────────────────────────
    # 내부 프라이빗 유틸리티 메서드
    # ─────────────────────────────────────────────────────────────

    def _generate_form_fields(self, org_type: str, company_code: str) -> list[FormField]:
        """조기분기 룰에 따라 동적 폼 필드를 생성합니다."""
        if org_type == "bank":
            extra = self._BANK_EXTRA_FIELDS.get(company_code, [])
        elif org_type == "card":
            extra = self._CARD_EXTRA_FIELDS.get(company_code, [])
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"지원하지 않는 org_type: {org_type!r}. 'bank' 또는 'card' 만 허용합니다.",
            )
        return self._BASE_FIELDS + extra

    def _yield_sse_status(self, data: dict) -> str:
        """SSE 통신용 메시지 청크를 포맷팅합니다."""
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    def _decrypt_login_data(self, login_data: dict) -> dict:
        """암호화된 사용자의 로그인 정보를 RSA 복호화합니다."""
        decrypted = dict(login_data)
        for field in self._SENSITIVE_FIELDS:
            if field in decrypted and decrypted[field]:
                try:
                    decrypted[field] = decrypt_data(decrypted[field])
                except ValueError as exc:
                    logger.error("RSA 복호화 실패 — field=%s error=%s", field, exc)
                    raise ValueError(field) from exc
        return decrypted

    async def _get_hash_salt(self) -> str:
        """DB에 저장된 해시용 소금값을 가져옵니다."""
        system_repo = SystemRepository()
        system_repo.set_factory(AsyncSessionFactory)
        async with system_repo as repo:
            config = await repo.get_or_create_config()
            await repo._session.commit()
            return config.hash_salt

    async def _fetch_bank_accounts(self, company_code: str, login_data: dict[str, Any]) -> list[_MockBankRawAccount]:
        """실제 CODEF API를 통해 은행 계좌를 조회합니다."""
        base_url = API_DOMAIN if settings.CODEF_MODE == "live" else (SANDBOX_DOMAIN if settings.CODEF_MODE == "sandbox" else DEMO_DOMAIN)
        client = CodefClient(
            public_key_pem=settings.CODEF_PUBLIC_KEY,
            client_id=settings.CODEF_CLIENT_ID,
            client_secret=settings.CODEF_CLIENT_SECRET,
            base_url=base_url
        )
        try:
            account_register = AccountRegister(
                business_type="BK",
                client_type="P",
                organization=company_code,
                login_type="1",
                id=login_data.get("id", ""),
                password=login_data.get("password", ""),
                birth_date=login_data.get("birthDate"),
            )
            auth_res = await client.auth_create_account([account_register])
            if auth_res.result.code not in ("CF-00000", "CF-11200"):
                raise ValueError(f"계정 등록 실패: {auth_res.result.message}")
            
            # 응답에서 connected_id 확보 (만약 존재하지 않으면 폼 데이터를 임시 사용)
            connected_id = auth_res.data.connected_id if auth_res.data else login_data.get("id", "")
            
            res = await client.bank_account_list(
                organization=company_code,
                connected_id=connected_id,
                birth_date=login_data.get("birthDate"),
                withdraw_account_no=login_data.get("withdrawAccountNo"),
                withdraw_account_password=login_data.get("withdrawAccountPassword")
            )
            
            if res.result.code != "CF-00000":
                raise ValueError(f"은행 계좌 조회 실패: {res.result.message}")
                
            _ACCOUNT_TYPE_MAP = {
                "res_deposit_trust": "예금",
                "res_foreign_currency": "외화",
                "res_fund": "펀드",
                "res_loan": "대출",
                "res_insurance": "보험",
            }
            out = []
            if res.data:
                for attr, acct_type in _ACCOUNT_TYPE_MAP.items():
                    val = getattr(res.data, attr, None)
                    if not val:
                        continue
                    items = val if isinstance(val, list) else [val]
                    for item in items:
                        if hasattr(item, "res_account") and item.res_account:
                            out.append(_MockBankRawAccount(
                                raw_account_no=item.res_account,
                                account_name=getattr(item, "res_account_name", None) or None,
                                account_type=acct_type,
                            ))
            return out
        finally:
            await client.close()

    async def _fetch_card_accounts(self, company_code: str, login_data: dict[str, Any]) -> list[_MockCardRawAccount]:
        """실제 CODEF API를 통해 카드 목록을 조회합니다."""
        base_url = API_DOMAIN if settings.CODEF_MODE == "live" else (SANDBOX_DOMAIN if settings.CODEF_MODE == "sandbox" else DEMO_DOMAIN)
        client = CodefClient(
            public_key_pem=settings.CODEF_PUBLIC_KEY,
            client_id=settings.CODEF_CLIENT_ID,
            client_secret=settings.CODEF_CLIENT_SECRET,
            base_url=base_url
        )
        try:
            account_register = AccountRegister(
                business_type="CD",
                client_type="P",
                organization=company_code,
                login_type="1",
                id=login_data.get("id", ""),
                password=login_data.get("password", ""),
                birth_date=login_data.get("birthDate"),
                card_no=login_data.get("cardNo"),
                card_password=login_data.get("cardPassword"),
            )
            auth_res = await client.auth_create_account([account_register])
            if auth_res.result.code not in ("CF-00000", "CF-11200"):
                raise ValueError(f"계정 등록 실패: {auth_res.result.message}")
            
            connected_id = auth_res.data.connected_id if auth_res.data else login_data.get("id", "")
            
            res = await client.card_account_list(
                organization=company_code,
                connected_id=connected_id,
                birth_date=login_data.get("birthDate"),
                card_no=login_data.get("cardNo"),
                card_password=login_data.get("cardPassword")
            )
            
            if res.result.code != "CF-00000":
                raise ValueError(f"카드 목록 조회 실패: {res.result.message}")
                
            out = []
            if res.data:
                items = res.data if isinstance(res.data, list) else [res.data]
                for item in items:
                    if hasattr(item, "res_card_no") and item.res_card_no:
                        out.append(_MockCardRawAccount(
                            raw_card_no=item.res_card_no,
                            card_name=getattr(item, "res_card_name", None) or None,
                            card_image_url=getattr(item, "res_image_link", None) or None,
                        ))
            return out
        finally:
            await client.close()

    async def _save_items(self, org_type: str, company_code: str, raw_items: list[_MockBankRawAccount] | list[_MockCardRawAccount], login_data: dict[str, Any] | None = None) -> int:
        """가져온 금융 데이터를 해싱 및 마스킹 처리하여 DB에 저장합니다."""
        if not raw_items:
            return 0
        salt = await self._get_hash_salt()

        if org_type == "bank":
            upsert_records: list[BankAccountUpsertData] = []
            for raw in raw_items:
                raw_no: str = raw.raw_account_no  # type: ignore[union-attr]
                upsert_records.append(
                    BankAccountUpsertData(
                        bank_code=company_code,
                        hashed_account_no=hash_data(raw_no, salt),
                        masked_account_no=mask_account_no(raw_no),
                        encrypted_account_no=encrypt_sensitive_data(raw_no),  # 원본 계좌번호 암호화
                        account_name=getattr(raw, "account_name", None),
                        account_type=getattr(raw, "account_type", None),
                    )
                )

            bank_repo = BankAccountRepository()
            bank_repo.set_factory(AsyncSessionFactory)
            async with bank_repo as repo:
                results = await repo.upsert_many(upsert_records)
                await repo._session.commit()
            return len(results)

        else:
            upsert_records_card: list[CardAccountUpsertData] = []
            # 카드 비밀번호는 특정 카드사에서만 저장 (데이터 최소화 원칙)
            card_password = login_data.get("cardPassword", "") if login_data else ""
            
            for raw in raw_items:
                raw_no_c: str = raw.raw_card_no  # type: ignore[union-attr]
                
                # 비밀번호가 필수인 카드사인지 확인
                encrypted_password = None
                if company_code in CARD_PASSWORD_REQUIRED_CODES and card_password:
                    encrypted_password = encrypt_sensitive_data(card_password)
                    logger.info(f"카드사 {company_code}: 비밀번호 저장 (API 통신 필수)")
                else:
                    logger.info(f"카드사 {company_code}: 비밀번호 미저장 (데이터 최소화)")
                
                upsert_records_card.append(
                    CardAccountUpsertData(
                        card_code=company_code,
                        hashed_card_no=hash_data(raw_no_c, salt),
                        masked_card_no=mask_card_no(raw_no_c),
                        encrypted_card_no=encrypt_sensitive_data(raw_no_c),  # 원본 카드번호 암호화
                        encrypted_card_password=encrypted_password,  # 조건부 비밀번호 암호화
                        card_name=getattr(raw, "card_name", None),
                        card_image_url=getattr(raw, "card_image_url", None),
                    )
                )

            card_repo = CardAccountRepository()
            card_repo.set_factory(AsyncSessionFactory)
            async with card_repo as repo:
                results = await repo.upsert_many(upsert_records_card)
                await repo._session.commit()
            return len(results)

    # ─────────────────────────────────────────────────────────────
    # 라우터 엔드포인트
    # ─────────────────────────────────────────────────────────────

    @router.patch(
        "/toggle/{org_type}/{item_id}",
        response_model=ToggleResponse,
        status_code=status.HTTP_200_OK,
        summary="MCP 권한 토글",
        description=(
            "은행 계좌 또는 카드의 MCP 에이전트 노출 여부를 업데이트합니다. "
            "관리자 인증(Bearer JWT)이 필요합니다."
        ),
    )
    async def toggle_mcp_status(
        self,
        org_type: Literal["bank", "card"],
        item_id: str,
        body: ToggleRequest,
    ) -> ToggleResponse:
        """MCP 권한 토글 API."""
        try:
            if org_type == "bank":
                bank_repo = BankAccountRepository()
                bank_repo.set_factory(AsyncSessionFactory)
                async with bank_repo as repo:
                    account = await repo.update_mcp_enabled(item_id, body.is_mcp_enabled)
                    await repo._session.commit()
            elif org_type == "card":
                card_repo = CardAccountRepository()
                card_repo.set_factory(AsyncSessionFactory)
                async with card_repo as repo:
                    account = await repo.update_mcp_enabled(item_id, body.is_mcp_enabled)
                    await repo._session.commit()
            else:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"지원하지 않는 org_type: {org_type!r}",
                )

            logger.info("%s MCP 권한 변경 — item_id=%s enabled=%s", org_type, item_id, body.is_mcp_enabled)

        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc

        return ToggleResponse(
            org_type=org_type,
            item_id=item_id,
            is_mcp_enabled=body.is_mcp_enabled,
        )

    @router.get(
        "/form/{org_type}/{company_code}",
        response_model=FormResponse,
        summary="동적 로그인 폼 조회",
        description="마이데이터 연동에 필요한 입력 필드 목록을 반환합니다.",
    )
    async def get_dynamic_form(
        self,
        org_type: Literal["bank", "card"],
        company_code: str,
    ) -> FormResponse:
        """기관별 동적 로그인 폼 반환 API."""
        fields = self._generate_form_fields(org_type, company_code)
        return FormResponse(fields=fields)

    @router.post(
        "/sync",
        status_code=status.HTTP_200_OK,
        summary="마이데이터 동기화 (SSE 스트리밍)",
        response_class=StreamingResponse,
        response_model=None,
    )
    async def sync_finance_data(self, body: SyncRequest) -> StreamingResponse:
        """마이데이터 동기화 API (SSE). (RSA 복호화 로직 포함 및 진행상황 스트리밍 반환)"""
        async def _stream() -> AsyncGenerator[str, None]:
            # ── Step 1: RSA 복호화 ──────────────────────────────
            yield self._yield_sse_status({"step": "decrypting", "message": "비밀번호 복호화 중..."})

            try:
                decrypted_login_data = self._decrypt_login_data(dict(body.login_data))
            except ValueError as exc:
                yield self._yield_sse_status({
                    "step": "error",
                    "message": f"복호화 오류: {exc.args[0]} 필드 처리 실패",
                })
                return

            # ── Step 2: 금융기관 데이터 조회 ─────────────────────
            yield self._yield_sse_status({"step": "fetching", "message": "금융기관 데이터 조회 중..."})

            try:
                if body.org_type == "bank":
                    raw_items = await self._fetch_bank_accounts(body.company_code, decrypted_login_data)
                else:
                    raw_items = await self._fetch_card_accounts(body.company_code, decrypted_login_data)
            except Exception as exc:
                logger.error("데이터 조회 실패: %s", exc)
                yield self._yield_sse_status({"step": "error", "message": f"데이터 조회 실패: {exc}"})
                return

            yield self._yield_sse_status({
                "step": "fetched",
                "message": f"{len(raw_items)}건 조회 완료",
                "count": len(raw_items),
            })

            # ── Step 3: DB 저장 ───────────────────────────────────
            yield self._yield_sse_status({"step": "saving", "message": "데이터 저장 중..."})

            try:
                synced_count = await self._save_items(body.org_type, body.company_code, raw_items, decrypted_login_data)
            except Exception as exc:
                logger.error("데이터 저장 실패: %s", exc)
                yield self._yield_sse_status({"step": "error", "message": f"저장 실패: {exc}"})
                return

            # ── Step 4: 완료 ──────────────────────────────────────
            yield self._yield_sse_status({
                "step": "done",
                "message": "동기화 완료",
                "synced_count": synced_count,
                "org_type": body.org_type,
                "company_code": body.company_code,
            })

        return StreamingResponse(
            _stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )


def setup(fastapi_app: FastAPI) -> None:
    fastapi_app.include_router(router)

