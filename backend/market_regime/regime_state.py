"""MarketRegime — 시장 상태 모델

BULL / NEUTRAL / BEAR / UNKNOWN 네 가지 상태를 정의한다.
"""
from __future__ import annotations

from enum import Enum


class MarketRegime(str, Enum):
    """시장 상태 분류"""
    BULL = "BULL"
    NEUTRAL = "NEUTRAL"
    BEAR = "BEAR"
    UNKNOWN = "UNKNOWN"


# 분류 기준 점수 임계값
BULL_THRESHOLD = 70.0       # 70점 이상 → BULL
NEUTRAL_LOWER = 40.0        # 40~69점 → NEUTRAL
# 39점 이하 → BEAR
# API 실패 / source 검증 실패 / 핵심 데이터 부족 → UNKNOWN