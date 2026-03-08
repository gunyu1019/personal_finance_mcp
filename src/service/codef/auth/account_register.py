from typing import Literal, Optional
from ..base_model import CodefBaseModel


class AccountRegister(CodefBaseModel):
    country_code: Literal['KR'] = "KR"  # 국가코드 (한국: KR)
    business_type: Literal['BK', 'CD', 'ST', 'IS']  # 업무 구분 (은행/저축은행: BK, 카드: CD, 증권: ST, 보험: IS)
    organization: str  # TODO
    client_type: Literal['P', 'B', 'A']  # 고객 구분 (개인: P, 기업/법인: B, 통합: A)
    login_type: Literal['0', '1']  # 로그인 방식 (0: 인증서, 1: 아이디/패스워드)

    password: str  # 패스워드 (인증서 방식: 인증서 패스워드, 아이디 방식: 아이디 패스워드)
    cert_type: Literal['1', 'pfx'] = '1'  # 인증서 구분 (기본인증서: '1', pfx: 'pfx', Default: '1')

    # 인증서 관련 (조건부 필수)
    der_file: Optional[str] = None  # BASE64 Encoding된 인증서 der 파일 문자열 (기본인증서 필수)
    key_file: Optional[str] = None  # BASE64 Encoding된 인증서 key 파일 문자열 (기본인증서 필수)
    cert_file: Optional[str] = None  # BASE64 Encoding된 인증서 pfx 문자열 (인증서pfx 필수)

    # 아이디/패스워드 방식 관련 (조건부 필수)
    id: Optional[str] = None  # 아이디 (아이디 방식일 경우 필수, 키움 복수 계정 보유 고객의 경우 사용)

    # 선택 필드
    add_password: Optional[str] = None  # 복수계정 패스워드 (키움 복수 계정 보유 고객의 경우 사용)
    birth_date: Optional[str] = None  # 생년월일
    identity: Optional[str] = None  # 사용자 주민번호/사업자번호 (보험사 - 필수 입력여부 확인)
    user_name: Optional[str] = None  # 사용자이름 (보험사 - 필수 입력여부 확인)
    login_type_level: Optional[Literal['0', '1', '2']] = None  # 로그인구분 (신한/롯데 법인카드 - 0: 이용자, 1: 사업장/부서관리자, 2: 총괄관리자, default: "2")
    client_type_level: Optional[Literal['0', '1', '2', '3']] = None  # 의뢰인구분 (신한 법인카드 - 0: 신용카드회원, 1: 체크카드회원, 2: 연구비신용카드회원, 3: 프리플러스회원)
    card_no: Optional[str] = None  # 카드번호 (현대카드 아이디로그인 필수, KB 카드소지확인 인증이 필요한 경우)
    card_password: Optional[str] = None  # RSA 암호화된 카드 비밀번호 (현대카드 아이디로그인 필수: 4자리, KB 카드소지확인: 앞 2자리)

    @classmethod
    def with_cert(
            cls,
            business_type: Literal['BK', 'CD', 'ST', 'IS'],
            organization: str,
            client_type: Literal['P', 'B', 'A'],
            der_file: str,
            key_file: str,
            cert_file: str,
            password: str,
            **kwargs  # Additional Field
    ):
        return cls(
            business_type=business_type,
            organization=organization,
            client_type=client_type,
            login_type='0',
            cert_type='pfx',
            der_file=der_file,
            key_file=key_file,
            cert_file=cert_file,
            password=password,
            **kwargs
        )

    @classmethod
    def with_id(
            cls,
            business_type: Literal['BK', 'CD', 'ST', 'IS'],
            organization: str,
            client_type: Literal['P', 'B', 'A'],
            account_id: str,
            password: str,
            **kwargs  # Additional Field
    ):
        return cls(
            business_type=business_type,
            organization=organization,
            client_type=client_type,
            login_type='1',
            id=account_id,
            password=password,
            **kwargs
        )
