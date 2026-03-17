from __future__ import annotations
from enum import StrEnum
from typing import ClassVar


class CardCompany(StrEnum):
    """
    카드사 코드 (4자리 문자열)
    
    CODEF API에서 사용되는 카드사 기관 코드를 enum으로 정의합니다.
    타입 안전성과 코드 가독성을 향상시키며, IDE의 자동완성을 지원합니다.
    """
    KB = "0301"
    HYUNDAI = "0302"
    SAMSUNG = "0303"
    NH = "0304"
    BC = "0305"
    SHINHAN = "0306"
    CITI = "0307"
    WOORI = "0309"
    LOTTE = "0311"
    HANA = "0313"
    JEONBUK = "0315"
    GWANGJU = "0316"
    SUHYUP = "0320"
    JEJU = "0321"

    @classmethod
    def _get_korean_names(cls) -> dict[str, str]:
        """한글 카드사명 매핑을 반환합니다."""
        return {
            "0301": "KB국민카드",
            "0302": "현대카드",
            "0303": "삼성카드", 
            "0304": "NH농협카드",
            "0305": "BC카드",
            "0306": "신한카드",
            "0307": "씨티카드",
            "0309": "우리카드",
            "0311": "롯데카드",
            "0313": "하나카드",
            "0315": "전북카드",
            "0316": "광주카드",
            "0320": "수협카드",
            "0321": "제주카드",
        }

    @classmethod
    def _get_password_required_codes(cls) -> set[str]:
        """비밀번호가 필요한 카드사 코드들을 반환합니다."""
        return {"0301", "0302", "0303", "0306", "0309", "0311", "0313"}

    @classmethod
    def get_korean_name(cls, code: str) -> str:
        """
        카드사 코드에 해당하는 한글 카드사명을 반환합니다.
        
        Args:
            code: 카드사 코드 (4자리 문자열)
            
        Returns:
            str: 한글 카드사명 또는 "카드사({code})" 형태의 기본값
        """
        return cls._get_korean_names().get(code, f"카드사({code})")

    @classmethod
    def get_all_mappings(cls) -> dict[str, str]:
        """
        모든 카드사 코드와 한글명의 매핑을 반환합니다.
        
        Returns:
            dict[str, str]: 카드사 코드 -> 한글명 매핑 딕셔너리
        """
        return cls._get_korean_names().copy()

    @property
    def korean_name(self) -> str:
        """현재 enum 값에 해당하는 한글 카드사명을 반환합니다."""
        return self._get_korean_names().get(self.value, f"카드사({self.value})")

    @classmethod
    def from_code(cls, code: str) -> "CardCompany | None":
        """
        카드사 코드로부터 CardCompany enum을 찾아 반환합니다.
        
        Args:
            code: 카드사 코드 (4자리 문자열)
            
        Returns:
            CardCompany | None: 해당하는 enum 또는 None
        """
        try:
            return cls(code)
        except ValueError:
            return None

    def requires_password(self) -> bool:
        """
        카드 비밀번호가 필요한 카드사인지 확인합니다.
        
        Returns:
            bool: 카드 비밀번호가 필요하면 True
        """
        return self.value in self._get_password_required_codes()

    @classmethod
    def get_password_required_codes(cls) -> set[str]:
        """
        카드 비밀번호가 필요한 모든 카드사 코드를 반환합니다.
        
        Returns:
            set[str]: 비밀번호 필수 카드사 코드들
        """
        return cls._get_password_required_codes().copy()

    def is_major_card(self) -> bool:
        """
        주요 카드사인지 확인합니다.
        
        Returns:
            bool: 주요 카드사이면 True
        """
        # 주요 카드사: KB, 현대, 삼성, 신한, 우리, 롯데, 하나
        major_cards = {
            self.KB, self.HYUNDAI, self.SAMSUNG, 
            self.SHINHAN, self.WOORI, self.LOTTE, self.HANA
        }
        return self in major_cards

    def requires_birth_date(self) -> bool:
        """생년월일이 필요한 카드사인지 확인합니다."""
        return self.value == "0311"  # 롯데카드

    def requires_card_info(self) -> bool:
        """카드번호와 비밀번호가 필요한 카드사인지 확인합니다."""
        return self.value in ("0301", "0302")  # KB, 현대카드

    @classmethod
    def get_extra_field_requirements(cls) -> dict[str, dict[str, bool]]:
        """
        각 카드사의 추가 필드 요구사항을 반환합니다.
        
        Returns:
            dict: 카드사코드 -> 필드 요구사항 매핑
        """
        return {
            "0301": {"card_info": True},    # KB카드 - 카드번호, 비밀번호 필요
            "0302": {"card_info": True},    # 현대카드 - 카드번호, 비밀번호 필요  
            "0311": {"birth_date": True},   # 롯데카드 - 생년월일 필요
        }