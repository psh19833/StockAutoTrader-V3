"""MarketRegimeInputs — KIS API 응답에서 추출한 시장 평가 입력값

모든 입력은 KIS_API source에서만 온다는 전제.
missing field 검증으로 데이터 부족을 감지한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IndexData:
    """지수 데이터"""
    kospi_current: float | None = None
    kospi_change_pct: float | None = None
    kospi_ma5_pct: float | None = None       # 5일선 대비 현재가 비율(%)
    kospi_ma20_pct: float | None = None      # 20일선 대비
    kospi_ma60_pct: float | None = None      # 60일선 대비
    kosdaq_current: float | None = None
    kosdaq_change_pct: float | None = None
    kosdaq_ma5_pct: float | None = None
    kosdaq_ma20_pct: float | None = None
    kosdaq_ma60_pct: float | None = None
    intraday_stability: float | None = None  # 0~1, 높을수록 안정적

    @property
    def missing_fields(self) -> list[str]:
        """누락된 필드 목록"""
        missing: list[str] = []
        for f_name in ("kospi_current", "kospi_change_pct", "kosdaq_current", "kosdaq_change_pct"):
            if getattr(self, f_name) is None:
                missing.append(f_name)
        return missing


@dataclass(frozen=True)
class BreadthData:
    """시장 폭 데이터"""
    advance_count: int | None = None         # 상승 종목 수
    decline_count: int | None = None         # 하락 종목 수
    unchanged_count: int | None = None       # 보합 종목 수
    advance_sector_count: int | None = None  # 상승 업종 수
    total_sector_count: int | None = None    # 전체 업종 수

    @property
    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        if self.advance_count is None:
            missing.append("advance_count")
        if self.decline_count is None:
            missing.append("decline_count")
        return missing


@dataclass(frozen=True)
class MomentumData:
    """모멘텀 데이터"""
    kospi_1d_momentum: float | None = None     # 당일 모멘텀
    kospi_5d_momentum: float | None = None     # 5일 모멘텀 (%)
    kospi_20d_momentum: float | None = None    # 20일 모멘텀 (%)
    high_volume_ratio: float | None = None      # 거래량 증가 종목 비율 (0~1)
    high_price_near_ratio: float | None = None  # 신고가 근접 종목 비율 (0~1)

    @property
    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        if self.kospi_1d_momentum is None:
            missing.append("kospi_1d_momentum")
        return missing


@dataclass(frozen=True)
class VolatilityData:
    """변동성 데이터"""
    intraday_range_pct: float | None = None     # 장중 변동폭 (%)
    vi_triggered_count: int | None = None        # VI 발동 종목 수
    extreme_updown_mixed: bool | None = None     # 급등락 혼재
    trend_consistency: float | None = None       # 장중 추세 일관성 (0~1)

    @property
    def missing_fields(self) -> list[str]:
        return []  # volatility는 부재 시 중립값 사용 가능


@dataclass(frozen=True)
class TradingValueData:
    """거래대금 데이터"""
    kospi_volume: float | None = None            # KOSPI 거래대금
    kosdaq_volume: float | None = None           # KOSDAQ 거래대금
    volume_change_pct: float | None = None       # 전일 대비 거래대금 증감 (%)
    top_volume_concentration: float | None = None  # 상위 종목 집중도 (0~1)

    @property
    def missing_fields(self) -> list[str]:
        return []


@dataclass(frozen=True)
class SectorStrengthData:
    """업종 강도 데이터"""
    up_sector_ratio: float | None = None       # 상승 업종 비율 (0~1)
    leading_sector_strength: float | None = None  # 주도 업종 강도 (0~1)
    sector_trend_continuity: float | None = None  # 업종 추세 지속성 (0~1)
    overheat_sector_ratio: float | None = None    # 과열 업종 비율 (0~1)

    @property
    def missing_fields(self) -> list[str]:
        return []


@dataclass(frozen=True)
class ForeignFlowData:
    """외국인/기관 수급 데이터"""
    foreign_net_buy: float | None = None         # 외국인 순매수 금액
    institution_net_buy: float | None = None     # 기관 순매수 금액
    kosdaq_foreign_flow: float | None = None     # 코스닥 외국인 수급

    @property
    def missing_fields(self) -> list[str]:
        return []


@dataclass(frozen=True)
class MarketRegimeInputs:
    """시장 평가 전체 입력값

    KIS API 응답을 통해 채워진다.
    source는 반드시 "KIS_API"여야 함.
    """
    source: str = ""
    index: IndexData = field(default_factory=IndexData)
    breadth: BreadthData = field(default_factory=BreadthData)
    momentum: MomentumData = field(default_factory=MomentumData)
    volatility: VolatilityData = field(default_factory=VolatilityData)
    trading_value: TradingValueData = field(default_factory=TradingValueData)
    sector_strength: SectorStrengthData = field(default_factory=SectorStrengthData)
    foreign_flow: ForeignFlowData = field(default_factory=ForeignFlowData)
    source_endpoints: tuple[str, ...] = ()

    def validate(self) -> list[str]:
        """입력값 검증

        Returns:
            검증 경고/에러 메시지 목록. 비어있으면 유효.
        """
        warnings: list[str] = []

        if self.source.upper() != "KIS_API":
            warnings.append(f"source=KIS_API expected, got '{self.source}'")

        # 각 하위 데이터 missing 확인
        for data_obj, name in [
            (self.index, "index"),
            (self.breadth, "breadth"),
            (self.momentum, "momentum"),
        ]:
            missing = data_obj.missing_fields
            if missing:
                warnings.append(f"{name} missing fields: {missing}")

        return warnings