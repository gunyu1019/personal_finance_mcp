from __future__ import annotations
from enum import StrEnum


class Company(StrEnum):
    """은행 코드 (4자리 문자열)"""
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
