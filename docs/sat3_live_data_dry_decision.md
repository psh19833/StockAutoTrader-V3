# SAT3 Live Data Dry Decision Pipeline (N11)

**Phase:** N11
**상태:** 구현 완료

## Pipeline

Scanner → Quant → Strategy → Risk → OrderIntent (blocked)

- LIVE_TRADING_ENABLED=false 시 주문 제출 차단
- Fake fill 없음
- KOSPI/KOSDAQ 보통주만
- ETF/ETN/ELW/우선주/UNKNOWN 제외
