# SAT3 LIVE AUTO TRADING Launch Procedure (Guarded)

## 목적
실전 자동매매는 반복 주문이 가능하지만, 아래 게이트를 통과하기 전에는 시작되지 않는다.

## 필수 게이트
- LIVE_TRADING_ENABLED=true
- SAT3_CONFIRM_LIVE_AUTO_TRADING=CONFIRM_LIVE_AUTO_TRADING
- Emergency Stop 비활성
- REST/WS 상태 정상 (REST available, WS connected or readonly verified)
- session=REGULAR_MARKET
- market_regime!=UNKNOWN
- risk limits(일손실/최대종목/최대주문금액) 로드
- audit logging active

## 시작 방법 (CLI)
python backend/scripts/sat3_live_auto_trading_start.py \
  --confirm-live-auto-trading CONFIRM_LIVE_AUTO_TRADING \
  --confirm-account <ACCOUNT_NO> \
  --max-daily-loss-krw <KRW> \
  --max-position-count <N> \
  --max-order-amount-krw <KRW> \
  --interval-sec <SEC>=5 이상

## 시작 방법 (API)
POST /api/runtime/start-live
{
  "confirm": "CONFIRM_LIVE_AUTO_TRADING",
  "max_daily_loss_krw": 100000,
  "max_position_count": 5,
  "max_order_amount_krw": 300000,
  "interval_sec": 10
}

## 금지
- GET/querystring 기반 live start 금지
- confirm 없는 live start 금지
- Dashboard 단일 토글로 live start 금지
