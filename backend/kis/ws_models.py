"""KIS WebSocket data models — real-time market data message containers.

All WebSocket messages carry source metadata, raw message integrity hash,
and parsed-status flags. No raw message bodies are retained — only
raw_hash for reproducibility checks.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class WebSocketMessageBase:
    """Common base for all KIS WebSocket real-time messages.

    Core contract:
      - source: always "KIS_API_WS"
      - tr_id: KIS transaction ID (H0STCNT0, H0STASP0, etc.)
      - symbol: stock code (e.g., "005930")
      - received_at: UTC timestamp when the message was received
      - raw_hash: SHA-256 or similar hash of the raw message (for audit)
      - parsed_ok: True if parsing succeeded, False if unknown/error
      - data_quality_warnings: list of warnings (stale, missing fields, etc.)
    """

    source: str = "KIS_API_WS"
    tr_id: str = ""
    symbol: str = ""
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_hash: Optional[str] = None
    parsed_ok: bool = True
    data_quality_warnings: list[str] = field(default_factory=list)


@dataclass
class RealtimeTradeTick(WebSocketMessageBase):
    """KIS real-time trade tick (체결가) — TR_ID: H0STCNT0.

    실시간 체결가 정보. 매수/매도 판단의 보조 지표로 사용.
    """

    trade_price: Optional[int] = None
    trade_volume: Optional[int] = None
    trade_time: Optional[str] = None
    change_sign: Optional[str] = None   # "1": 상승, "2": 하락, "3": 보합 등
    change_price: Optional[int] = None
    ask_price: Optional[int] = None
    bid_price: Optional[int] = None
    trade_type: Optional[str] = None     # "1": 매수, "2": 매도

    def __post_init__(self):
        self.tr_id = "H0STCNT0"


@dataclass
class RealtimeOrderBook(WebSocketMessageBase):
    """KIS real-time order book (호가) — TR_ID: H0STASP0.

    실시간 호가창 정보.
    """

    ask_prices: list[int] = field(default_factory=list)
    ask_volumes: list[int] = field(default_factory=list)
    bid_prices: list[int] = field(default_factory=list)
    bid_volumes: list[int] = field(default_factory=list)
    total_ask_volume: Optional[int] = None
    total_bid_volume: Optional[int] = None

    def __post_init__(self):
        self.tr_id = "H0STASP0"


@dataclass
class RealtimeFillNotice(WebSocketMessageBase):
    """KIS real-time fill notice (체결통보) — TR_ID: H0STCNI0.

    체결 확정은 이 메시지 또는 REST 체결조회로만 확인한다.
    주문 성공 ≠ 체결 성공.
    """

    order_number: Optional[str] = None
    fill_price: Optional[int] = None
    fill_volume: Optional[int] = None
    fill_time: Optional[str] = None
    order_type: Optional[str] = None    # "01": 매수, "02": 매도

    def __post_init__(self):
        self.tr_id = "H0STCNI0"


@dataclass
class RealtimeMarketStatus(WebSocketMessageBase):
    """KIS real-time market status (장운영정보) — TR_ID: H0STMKO0.

    시장 개장/폐장/서킷브레이커 등 장 운영 상태.
    """

    market_status: Optional[str] = None  # "OPEN", "CLOSE", "BREAK", etc.
    market_session: Optional[str] = None  # "REGULAR", "AFTER_HOURS", etc.

    def __post_init__(self):
        self.tr_id = "H0STMKO0"


@dataclass
class RealtimeExpectedExecution(WebSocketMessageBase):
    """KIS real-time expected execution (예상체결) — TR_ID: H0STANC0.

    장 시작 전 예상 체결가 정보.
    """

    expected_price: Optional[int] = None
    expected_volume: Optional[int] = None
    expected_change: Optional[str] = None

    def __post_init__(self):
        self.tr_id = "H0STANC0"


@dataclass
class WebSocketConnectionStatus:
    """WebSocket connection health and subscription state.

    Dashboard에서 WebSocket 상태를 표시하기 위한 모델.
    """

    source: str = "KIS_API_WS"
    connection_state: str = "DISCONNECTED"
    subscribed_channels: list[str] = field(default_factory=list)
    last_message_at: Optional[datetime] = None
    reconnect_count: int = 0
    last_error_type: Optional[str] = None
    data_quality_warnings: list[str] = field(default_factory=list)

    # Contract marker: this client does not run an automatic receive loop.
    receiver_loop_running: bool = False
    receive_loop_status: str = "manual_recv_only"
