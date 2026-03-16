# src/api/finance.py
# 마이데이터 금융 정보 API

import json
import logging
from typing import Any, AsyncGenerator, ClassVar, Literal, Optional, TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status, FastAPI
from fastapi.responses import StreamingResponse
from fastapi_restful.cbv import cbv
from sqlalchemy import func, select

from app.api.auth import get_current_admin
from app.core.crypto import decrypt_data, encrypt_sensitive_data, decrypt_sensitive_data
from app.core.config import settings, BANK_MAPPING, CARD_MAPPING, CARD_PASSWORD_REQUIRED_CODES
from app.core.database import AsyncSessionFactory
from app.core.security import hash_data, mask_account_no, mask_card_no
from app.dto.bank_account_dto import BankAccountUpsertData
from app.dto.card_account_dto import CardAccountUpsertData
from app.model.bank_account import BankAccount
from app.model.card_account import CardAccount
from app.repository.bank_account_repository import BankAccountRepository
from app.repository.card_account_repository import CardAccountRepository
from app.repository.system_repository import SystemRepository
from app.schema.finance import (
    DisconnectResponse,
    FormField,
    FormResponse,
    InstitutionItem,
    InstitutionsResponse,
    ResyncRequest,
    SyncRequest,
    SyncResponse,
    ToggleRequest,
    ToggleResponse,
)
from app.service.codef.client import CodefClient
from app.service.codef.auth.account import Account
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

    def _create_codef_client(self) -> CodefClient:
        """설정 기반 CodefClient 인스턴스를 생성합니다."""
        base_url = (
            API_DOMAIN if settings.CODEF_MODE == "live"
            else (SANDBOX_DOMAIN if settings.CODEF_MODE == "sandbox" else DEMO_DOMAIN)
        )
        return CodefClient(
            public_key_pem=settings.CODEF_PUBLIC_KEY,
            client_id=settings.CODEF_CLIENT_ID,
            client_secret=settings.CODEF_CLIENT_SECRET,
            base_url=base_url,
        )

    async def _get_connected_id(self) -> Optional[str]:
        """DB에서 codef_connected_id를 조회합니다."""
        system_repo = SystemRepository()
        system_repo.set_factory(AsyncSessionFactory)
        async with system_repo as repo:
            return await repo.get_connected_id()

    async def _persist_connected_id(self, connected_id: str) -> None:
        """codef_connected_id를 DB에 저장(또는 갱신)합니다."""
        system_repo = SystemRepository()
        system_repo.set_factory(AsyncSessionFactory)
        async with system_repo as repo:
            await repo.save_connected_id(connected_id)
            await repo._session.commit()

    async def _fetch_bank_accounts(
        self,
        company_code: str,
        login_data: dict[str, Any],
        existing_connected_id: Optional[str] = None,
    ) -> tuple[list[_MockBankRawAccount], str]:
        """
        Codef API로 은행 계좌를 조회합니다.

        - existing_connected_id가 없으면 auth_create_account로 신규 등록 후 connected_id 발급.
        - 있으면 auth_add_account로 기존 connected_id에 기관만 추가.
        - 발급/유지된 connected_id와 계좌 목록을 함께 반환합니다.
        """
        client = self._create_codef_client()
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

            if existing_connected_id:
                auth_res = await client.auth_add_account(existing_connected_id, [account_register])
            else:
                auth_res = await client.auth_create_account([account_register])

            if auth_res.result.code not in ("CF-00000", "CF-11200"):
                raise ValueError(f"계정 등록 실패: {auth_res.result.message}")

            connected_id: str = (
                auth_res.data.connected_id
                if auth_res.data and auth_res.data.connected_id
                else existing_connected_id or login_data.get("id", "")
            )

            res = await client.bank_account_list(
                organization=company_code,
                connected_id=connected_id,
                birth_date=login_data.get("birthDate"),
                withdraw_account_no=login_data.get("withdrawAccountNo"),
                withdraw_account_password=login_data.get("withdrawAccountPassword"),
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
            out: list[_MockBankRawAccount] = []
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
            return out, connected_id
        finally:
            await client.close()

    async def _fetch_card_accounts(
        self,
        company_code: str,
        login_data: dict[str, Any],
        existing_connected_id: Optional[str] = None,
    ) -> tuple[list[_MockCardRawAccount], str]:
        """
        Codef API로 카드 목록을 조회합니다.

        - existing_connected_id가 없으면 auth_create_account로 신규 등록.
        - 있으면 auth_add_account로 기관 추가.
        - 발급/유지된 connected_id와 카드 목록을 함께 반환합니다.
        """
        client = self._create_codef_client()
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

            if existing_connected_id:
                auth_res = await client.auth_add_account(existing_connected_id, [account_register])
            else:
                auth_res = await client.auth_create_account([account_register])

            if auth_res.result.code not in ("CF-00000", "CF-11200"):
                raise ValueError(f"계정 등록 실패: {auth_res.result.message}")

            connected_id: str = (
                auth_res.data.connected_id
                if auth_res.data and auth_res.data.connected_id
                else existing_connected_id or login_data.get("id", "")
            )

            res = await client.card_account_list(
                organization=company_code,
                connected_id=connected_id,
                birth_date=login_data.get("birthDate"),
                card_no=login_data.get("cardNo"),
                card_password=login_data.get("cardPassword"),
            )

            if res.result.code != "CF-00000":
                raise ValueError(f"카드 목록 조회 실패: {res.result.message}")

            out: list[_MockCardRawAccount] = []
            if res.data:
                items = res.data if isinstance(res.data, list) else [res.data]
                for item in items:
                    if hasattr(item, "res_card_no") and item.res_card_no:
                        out.append(_MockCardRawAccount(
                            raw_card_no=item.res_card_no,
                            card_name=getattr(item, "res_card_name", None) or None,
                            card_image_url=getattr(item, "res_image_link", None) or None,
                        ))
            return out, connected_id
        finally:
            await client.close()

    async def _save_items(
        self,
        org_type: str,
        company_code: str,
        raw_items: list[_MockBankRawAccount] | list[_MockCardRawAccount],
        login_data: dict[str, Any] | None = None,
    ) -> int:
        """가져온 금융 데이터를 해싱·마스킹·암호화하여 DB에 저장합니다."""
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
                        encrypted_account_no=encrypt_sensitive_data(raw_no),
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
            card_password = login_data.get("cardPassword", "") if login_data else ""

            for raw in raw_items:
                raw_no_c: str = raw.raw_card_no  # type: ignore[union-attr]

                encrypted_password = None
                if company_code in CARD_PASSWORD_REQUIRED_CODES and card_password:
                    encrypted_password = encrypt_sensitive_data(card_password)
                    logger.info("카드사 %s: 비밀번호 저장 (API 통신 필수)", company_code)
                else:
                    logger.info("카드사 %s: 비밀번호 미저장 (데이터 최소화)", company_code)

                upsert_records_card.append(
                    CardAccountUpsertData(
                        card_code=company_code,
                        hashed_card_no=hash_data(raw_no_c, salt),
                        masked_card_no=mask_card_no(raw_no_c),
                        encrypted_card_no=encrypt_sensitive_data(raw_no_c),
                        encrypted_card_password=encrypted_password,
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

    @router.get(
        "/institutions",
        response_model=InstitutionsResponse,
        summary="연결된 기관 목록 조회",
        description="DB에 데이터가 있는 은행/카드사 코드별 목록과 계좌·카드 수를 반환합니다.",
    )
    async def get_connected_institutions(self) -> InstitutionsResponse:
        """연결된 기관 목록 API."""
        bank_repo = BankAccountRepository()
        bank_repo.set_factory(AsyncSessionFactory)
        card_repo = CardAccountRepository()
        card_repo.set_factory(AsyncSessionFactory)

        banks: list[InstitutionItem] = []
        cards: list[InstitutionItem] = []

        async with bank_repo as repo:
            result = await repo._session.execute(
                select(BankAccount.bank_code, func.count(BankAccount.hashed_account_no))
                .group_by(BankAccount.bank_code)
            )
            for row in result.all():
                code = row[0]
                banks.append(InstitutionItem(
                    code=code,
                    name=BANK_MAPPING.get(code, f"은행({code})"),
                    account_count=row[1],
                ))

        async with card_repo as repo:
            result = await repo._session.execute(
                select(CardAccount.card_code, func.count(CardAccount.hashed_card_no))
                .group_by(CardAccount.card_code)
            )
            for row in result.all():
                code = row[0]
                cards.append(InstitutionItem(
                    code=code,
                    name=CARD_MAPPING.get(code, f"카드사({code})"),
                    account_count=row[1],
                ))

        return InstitutionsResponse(banks=banks, cards=cards)

    @router.delete(
        "/institution/{institution_code}",
        response_model=DisconnectResponse,
        status_code=status.HTTP_200_OK,
        summary="기관 연결 해제",
        description=(
            "Codef 서버의 연동을 먼저 해제(auth_delete_account)한 후, "
            "로컬 DB의 계좌·카드 레코드를 삭제합니다."
        ),
    )
    async def disconnect_institution(self, institution_code: str) -> DisconnectResponse:
        """기관 연결 해제 API — Codef Unlink 후 로컬 DB 삭제."""
        # 기관 유형 판별
        if institution_code in BANK_MAPPING:
            business_type: Literal["BK", "CD"] = "BK"
        elif institution_code in CARD_MAPPING:
            business_type = "CD"
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"알 수 없는 기관 코드입니다: {institution_code}",
            )

        # connected_id 조회 — 있으면 Codef API로 먼저 연동 해제
        connected_id = await self._get_connected_id()
        if connected_id:
            client = self._create_codef_client()
            try:
                account_obj = Account(
                    client_type="P",
                    organization=institution_code,
                    business_type=business_type,
                )
                unlink_res = await client.auth_delete_account([account_obj])
                # CF-00000: 성공 / CF-12004: 이미 삭제됨 (둘 다 허용)
                if unlink_res.result.code not in ("CF-00000", "CF-12004"):
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Codef 연동 해제 실패: {unlink_res.result.message}",
                    )
                logger.info("Codef 연동 해제 성공 — code=%s connected_id=%s", institution_code, connected_id)
            except HTTPException:
                raise
            except Exception as exc:
                logger.error("Codef 연동 해제 중 오류 — code=%s error=%s", institution_code, exc)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Codef API 통신 오류: {exc}",
                ) from exc
            finally:
                await client.close()

        # Codef 통신 성공(또는 connected_id 없음) 후 로컬 DB 삭제
        bank_repo = BankAccountRepository()
        bank_repo.set_factory(AsyncSessionFactory)
        card_repo = CardAccountRepository()
        card_repo.set_factory(AsyncSessionFactory)

        deleted_banks = 0
        deleted_cards = 0

        async with bank_repo as repo:
            deleted_banks = await repo.delete_by_bank_code(institution_code)
            await repo._session.commit()

        async with card_repo as repo:
            deleted_cards = await repo.delete_by_card_code(institution_code)
            await repo._session.commit()

        logger.info("기관 연결 해제 완료: code=%s banks=%s cards=%s", institution_code, deleted_banks, deleted_cards)
        return DisconnectResponse(
            message=f"연결이 해제되었습니다. (은행 {deleted_banks}건, 카드 {deleted_cards}건 삭제)",
            deleted_bank_accounts=deleted_banks,
            deleted_card_accounts=deleted_cards,
        )

    @router.post(
        "/sync/{institution_code}",
        response_model=SyncResponse,
        status_code=status.HTTP_200_OK,
        summary="기관 재동기화",
        description=(
            "DB의 connected_id를 사용해 Codef API를 호출하여 최신 계좌/카드 정보를 Upsert합니다. "
            "추가 입력(생년월일 등)이 필요한 기관에 login_data 없이 호출하면 428로 응답합니다."
        ),
    )
    async def resync_institution(
        self,
        institution_code: str,
        body: ResyncRequest,
    ) -> SyncResponse:
        """기관 재동기화 API — connected_id 기반 데이터 갱신."""
        # 기관 유형 판별
        org_type: Literal["bank", "card"] | None = None
        if institution_code in BANK_MAPPING:
            org_type = "bank"
        elif institution_code in CARD_MAPPING:
            org_type = "card"

        if org_type is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"알 수 없는 기관 코드입니다: {institution_code}",
            )

        # connected_id 필수 확인
        connected_id = await self._get_connected_id()
        if not connected_id:
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail="아직 등록된 Codef 계정이 없습니다. 먼저 기관을 연결해 주세요.",
            )

        # 추가 입력 필드 필요 여부 검사
        if org_type == "bank":
            extra_fields = self._BANK_EXTRA_FIELDS.get(institution_code, [])
        else:
            # CARD_PASSWORD_REQUIRED_CODES는 DB에 저장된 자격증명으로 자동 처리
            extra_fields = (
                []
                if institution_code in CARD_PASSWORD_REQUIRED_CODES
                else self._CARD_EXTRA_FIELDS.get(institution_code, [])
            )

        if extra_fields and not body.login_data:
            raise HTTPException(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                detail={
                    "requires_input": True,
                    "fields": [f.model_dump() for f in extra_fields],
                    "message": "추가 정보 입력이 필요합니다.",
                },
            )

        # login_data가 제공된 경우 RSA 복호화
        decrypted_login_data: dict[str, Any] = {}
        if body.login_data:
            try:
                decrypted_login_data = self._decrypt_login_data(dict(body.login_data))
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"복호화 오류: {exc.args[0]} 필드 처리 실패",
                ) from exc

        # 카드 비밀번호 필수 카드사는 DB에서 저장된 자격증명 복원
        if org_type == "card" and institution_code in CARD_PASSWORD_REQUIRED_CODES:
            if not decrypted_login_data.get("cardNo") or not decrypted_login_data.get("cardPassword"):
                card_repo = CardAccountRepository()
                card_repo.set_factory(AsyncSessionFactory)
                async with card_repo as repo:
                    result = await repo._session.execute(
                        select(CardAccount)
                        .where(CardAccount.card_code == institution_code)
                        .limit(1)
                    )
                    stored_card: CardAccount | None = result.scalars().first()

                if stored_card and stored_card.encrypted_card_no:
                    decrypted_login_data["cardNo"] = decrypt_sensitive_data(stored_card.encrypted_card_no)
                if stored_card and stored_card.encrypted_card_password:
                    decrypted_login_data["cardPassword"] = decrypt_sensitive_data(stored_card.encrypted_card_password)

        # Codef API 호출 (connected_id 사용, 인증 재등록 없음)
        try:
            client = self._create_codef_client()
            try:
                if org_type == "bank":
                    res = await client.bank_account_list(
                        organization=institution_code,
                        connected_id=connected_id,
                        birth_date=decrypted_login_data.get("birthDate"),
                        withdraw_account_no=decrypted_login_data.get("withdrawAccountNo"),
                        withdraw_account_password=decrypted_login_data.get("withdrawAccountPassword"),
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
                    raw_items: list[Any] = []
                    if res.data:
                        for attr, acct_type in _ACCOUNT_TYPE_MAP.items():
                            val = getattr(res.data, attr, None)
                            if not val:
                                continue
                            items = val if isinstance(val, list) else [val]
                            for item in items:
                                if hasattr(item, "res_account") and item.res_account:
                                    raw_items.append(_MockBankRawAccount(
                                        raw_account_no=item.res_account,
                                        account_name=getattr(item, "res_account_name", None) or None,
                                        account_type=acct_type,
                                    ))
                else:
                    res = await client.card_account_list(
                        organization=institution_code,
                        connected_id=connected_id,
                        birth_date=decrypted_login_data.get("birthDate"),
                        card_no=decrypted_login_data.get("cardNo"),
                        card_password=decrypted_login_data.get("cardPassword"),
                    )
                    if res.result.code != "CF-00000":
                        raise ValueError(f"카드 목록 조회 실패: {res.result.message}")

                    raw_items = []
                    if res.data:
                        items_c = res.data if isinstance(res.data, list) else [res.data]
                        for item in items_c:
                            if hasattr(item, "res_card_no") and item.res_card_no:
                                raw_items.append(_MockCardRawAccount(
                                    raw_card_no=item.res_card_no,
                                    card_name=getattr(item, "res_card_name", None) or None,
                                    card_image_url=getattr(item, "res_image_link", None) or None,
                                ))
            finally:
                await client.close()

        except Exception as exc:
            logger.error("재동기화 데이터 조회 실패 — code=%s error=%s", institution_code, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"금융기관 데이터 조회 실패: {exc}",
            ) from exc

        try:
            synced_count = await self._save_items(
                org_type, institution_code, raw_items, decrypted_login_data
            )
        except Exception as exc:
            logger.error("재동기화 저장 실패 — code=%s error=%s", institution_code, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"저장 실패: {exc}",
            ) from exc

        logger.info("재동기화 완료 — code=%s org_type=%s synced=%s", institution_code, org_type, synced_count)
        return SyncResponse(
            org_type=org_type,
            company_code=institution_code,
            synced_count=synced_count,
        )

    @router.post(
        "/sync",
        status_code=status.HTTP_200_OK,
        summary="마이데이터 동기화 (SSE 스트리밍)",
        response_class=StreamingResponse,
        response_model=None,
    )
    async def sync_finance_data(self, body: SyncRequest) -> StreamingResponse:
        """마이데이터 동기화 API (SSE). connected_id 라이프사이클 포함."""
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

            # DB에서 기존 connected_id 조회 (있으면 Add, 없으면 Create)
            existing_connected_id = await self._get_connected_id()

            try:
                if body.org_type == "bank":
                    raw_items, new_connected_id = await self._fetch_bank_accounts(
                        body.company_code, decrypted_login_data, existing_connected_id
                    )
                else:
                    raw_items, new_connected_id = await self._fetch_card_accounts(
                        body.company_code, decrypted_login_data, existing_connected_id
                    )
            except Exception as exc:
                logger.error("데이터 조회 실패: %s", exc)
                yield self._yield_sse_status({"step": "error", "message": f"데이터 조회 실패: {exc}"})
                return

            yield self._yield_sse_status({
                "step": "fetched",
                "message": f"{len(raw_items)}건 조회 완료",
                "count": len(raw_items),
            })

            # ── Step 3: DB 저장 (connected_id 포함) ──────────────
            yield self._yield_sse_status({"step": "saving", "message": "데이터 저장 중..."})

            try:
                synced_count = await self._save_items(body.org_type, body.company_code, raw_items, decrypted_login_data)

                # connected_id가 변경됐거나 새로 발급된 경우 DB 저장
                if new_connected_id and new_connected_id != existing_connected_id:
                    await self._persist_connected_id(new_connected_id)
                    logger.info("connected_id 저장 완료: %s", new_connected_id)

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
