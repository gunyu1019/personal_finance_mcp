from __future__ import annotations
from enum import StrEnum
from typing import ClassVar


class BankCompany(StrEnum):
    """
    은행 코드 (4자리 문자열)
    
    CODEF API에서 사용되는 은행 기관 코드를 enum으로 정의합니다.
    타입 안전성과 코드 가독성을 향상시키며, IDE의 자동완성을 지원합니다.
    """
    KDB = "0002"  # 산업은행
    IBK = "0003"  # 기업은행
    KB = "0004"  # 국민은행
    SUHYUP = "0007"  # 수협은행
    NH = "0011"  # 농협은행
    WOORI = "0020"  # 우리은행
    SC = "0023"  # SC은행
    CITI = "0027"  # 씨티은행
    DAEGU = "0031"  # 대구은행
    BUSAN = "0032"  # 부산은행
    GWANGJU = "0034"  # 광주은행
    JEJU = "0035"  # 제주은행
    JEONBUK = "0037"  # 전북은행
    GYEONGNAM = "0039"  # 경남은행
    SAEMAEUL = "0045"  # 새마을금고
    CU = "0048"  # 신협은행
    POST = "0071"  # 우체국
    KEB_HANA = "0081"  # KEB하나은행
    SHINHAN = "0088"  # 신한은행
    K_BANK = "0089"  # K뱅크

    @classmethod
    def _get_korean_names(cls) -> dict[str, str]:
        """한글 은행명 매핑을 반환합니다."""
        return {
            "0002": "산업은행",
            "0003": "기업은행", 
            "0004": "국민은행",
            "0007": "수협은행",
            "0011": "농협은행",
            "0020": "우리은행",
            "0023": "SC은행",
            "0027": "씨티은행",
            "0031": "대구은행",
            "0032": "부산은행",
            "0034": "광주은행",
            "0035": "제주은행",
            "0037": "전북은행",
            "0039": "경남은행",
            "0045": "새마을금고",
            "0048": "신협은행",
            "0071": "우체국",
            "0081": "KEB하나은행",
            "0088": "신한은행",
            "0089": "K뱅크",
        }

    @classmethod
    def get_korean_name(cls, code: str) -> str:
        """
        은행 코드에 해당하는 한글 은행명을 반환합니다.
        
        Args:
            code: 은행 코드 (4자리 문자열)
            
        Returns:
            str: 한글 은행명 또는 "은행({code})" 형태의 기본값
        """
        return cls._get_korean_names().get(code, f"은행({code})")

    @classmethod
    def get_all_mappings(cls) -> dict[str, str]:
        """
        모든 은행 코드와 한글명의 매핑을 반환합니다.
        
        Returns:
            dict[str, str]: 은행 코드 -> 한글명 매핑 딕셔너리
        """
        return cls._get_korean_names().copy()

    @property
    def korean_name(self) -> str:
        """현재 enum 값에 해당하는 한글 은행명을 반환합니다."""
        return self._get_korean_names().get(self.value, f"은행({self.value})")

    @classmethod
    def from_code(cls, code: str) -> "BankCompany | None":
        """
        은행 코드로부터 BankCompany enum을 찾아 반환합니다.
        
        Args:
            code: 은행 코드 (4자리 문자열)
            
        Returns:
            BankCompany | None: 해당하는 enum 또는 None
        """
        try:
            return cls(code)
        except ValueError:
            return None

    def is_special_bank(self) -> bool:
        """
        특별 취급이 필요한 은행인지 확인합니다.
        (생년월일, 출금계좌 등 추가 정보가 필요한 은행들)
        
        Returns:
            bool: 특별 취급이 필요한 은행이면 True
        """
        return self.value in ("0023", "0027", "0031", "0088", "0089")

    def requires_birth_date(self) -> bool:
        """생년월일이 필요한 은행인지 확인합니다."""
        return self.value in ("0023", "0027", "0031", "0088", "0089")

    def requires_withdraw_account(self) -> bool:
        """출금계좌 정보가 필요한 은행인지 확인합니다."""
        return self.value == "0031"  # 대구은행

    @classmethod
    def get_extra_field_requirements(cls) -> dict[str, dict[str, bool]]:
        """
        각 은행의 추가 필드 요구사항을 반환합니다.
        
        Returns:
            dict: 은행코드 -> 필드 요구사항 매핑
        """
        return {
            "0023": {"birth_date": True},  # SC은행
            "0027": {"birth_date": True},  # 씨티은행
            "0031": {"birth_date": True, "withdraw_account": True},  # 대구은행
            "0088": {"birth_date": True},  # 신한은행
            "0089": {"birth_date": True},  # K뱅크
        }