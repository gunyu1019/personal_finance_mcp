from enum import IntEnum


class Company(IntEnum):
    """은행 코드"""
    KDB = 2  # 산업은행
    IBK = 3  # 기업은행
    KB = 4  # 국민은행
    SUHYUP = 7  # 수협은행
    NH = 11  # 농협은행
    WOORI = 20  # 우리은행
    SC = 23  # SC은행
    CITI = 27  # 씨티은행
    DAEGU = 31  # 대구은행
    BUSAN = 32  # 부산은행
    GWANGJU = 34  # 광주은행
    JEJU = 35  # 제주은행
    JEONBUK = 37  # 전북은행
    GYEONGNAM = 39  # 경남은행
    SAEMAEUL = 45  # 새마을금고
    CU = 48  # 신협은행
    POST = 71  # 우체국
    KEB_HANA = 81  # KEB하나은행
    SHINHAN = 88  # 신한은행
    K_BANK = 89  # K뱅크
