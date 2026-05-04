"""MarketRegimeResult — 시장 평가 최종 결과"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from market_regime.regime_state import MarketRegime
from market_regime.regime_score import MarketRegimeScore


@dataclass(frozen=True)
class MarketRegimeResult:
    """Market Regime 평가 결과

    단일 평가 사이클의 모든 판단 정보를 담는다.
    """
    regime: MarketRegime
    score: MarketRegimeScore
    total_score: float                     # 0~100 정규화 점수
    candidate_score_adjustment: float      # 후보 점수 보정값
    allow_new_buy: bool                    # 신규매수 허용 여부
    min_candidate_score_required: float    # 최소 후보 점수 요구값
    reasons: tuple[str, ...] = ()
    source_endpoints: tuple[str, ...] = ()
    data_quality_warnings: tuple[str, ...] = ()
    evaluated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )