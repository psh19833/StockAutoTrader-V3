"""MarketRegimeScore — 시장 점수 계산 결과"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketRegimeScore:
    """Market Regime 세부 점수

    각 항목은 0~권장최대점수 범위로 정규화된다.
    total_score는 Market Risk Penalty 차감 후 0~100 정규화.
    """
    index_trend_score: float = 0.0
    market_breadth_score: float = 0.0
    market_momentum_score: float = 0.0
    volatility_risk_score: float = 0.0
    trading_value_score: float = 0.0
    sector_strength_score: float = 0.0
    foreign_institution_flow_score: float = 0.0
    market_risk_penalty: float = 0.0

    def __post_init__(self):
        """생성 후 값 검증 (범위 확인)"""
        score_attrs = [
            "index_trend_score", "market_breadth_score",
            "market_momentum_score", "volatility_risk_score",
            "trading_value_score", "sector_strength_score",
            "foreign_institution_flow_score",
        ]
        max_scores = {
            "index_trend_score": 25.0,
            "market_breadth_score": 20.0,
            "market_momentum_score": 15.0,
            "volatility_risk_score": 15.0,
            "trading_value_score": 10.0,
            "sector_strength_score": 10.0,
            "foreign_institution_flow_score": 5.0,
        }
        for attr_name in score_attrs:
            val = getattr(self, attr_name)
            max_val = max_scores.get(attr_name, 100.0)
            if val < 0 or val > max_val:
                raise ValueError(
                    f"{attr_name}={val} is out of allowed range [0, {max_val}]"
                )
        if self.market_risk_penalty < 0 or self.market_risk_penalty > 40:
            raise ValueError(
                f"market_risk_penalty={self.market_risk_penalty} is out of range [0, 40]"
            )

    @property
    def raw_total(self) -> float:
        """Risk Penalty 차감 전 합계"""
        return (
            self.index_trend_score
            + self.market_breadth_score
            + self.market_momentum_score
            + self.volatility_risk_score
            + self.trading_value_score
            + self.sector_strength_score
            + self.foreign_institution_flow_score
        )

    @property
    def total_score(self) -> float:
        """최종 점수 (0~100, Market Risk Penalty 차감 후)"""
        raw = self.raw_total - self.market_risk_penalty
        return max(0.0, min(100.0, raw))