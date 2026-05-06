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

## 운영자 수동 설정 (코드 자동변경 금지)
아래 값은 운영자가 .env에서 수동으로 설정해야 하며, 애플리케이션이 자동 변경하면 안 된다.

1) LIVE_TRADING_ENABLED=true 수동 설정
- .env에서 `LIVE_TRADING_ENABLED=true`로 직접 수정
- 자동 토글 금지

2) SAT3_CONFIRM_LIVE_AUTO_TRADING 수동 설정
- 동일 쉘 세션에서만 임시 사용 권장:
  - `export SAT3_CONFIRM_LIVE_AUTO_TRADING=CONFIRM_LIVE_AUTO_TRADING`
- 영구 저장이 필요하면 .env에 수동 추가 (자동 쓰기 금지)

3) Risk limit 필수 키(수동)
- SAT3_MAX_DAILY_LOSS_KRW=100000
- SAT3_MAX_POSITION_COUNT=3
- SAT3_MAX_ORDER_AMOUNT_KRW=50000
- SAT3_MAX_AMOUNT_PER_SYMBOL_KRW=100000
- SAT3_MAX_PENDING_ORDERS=1
- SAT3_DUPLICATE_ORDER_GUARD_ENABLED=true
- 모든 숫자값은 양의 정수여야 함(0/음수/문자열 금지)

4) 설정 반영 확인 (secret 원문 출력 금지)
- 값 원문 대신 true/false 또는 set/unset만 확인
- 예시:
  - `python - <<'PY'`
  - `import os`
  - `keys=["LIVE_TRADING_ENABLED","SAT3_CONFIRM_LIVE_AUTO_TRADING","SAT3_MAX_DAILY_LOSS_KRW","SAT3_MAX_DAILY_LOSS_PCT","SAT3_MAX_POSITION_COUNT","SAT3_MAX_ORDER_AMOUNT_KRW","SAT3_MAX_AMOUNT_PER_SYMBOL_KRW","SAT3_MAX_PENDING_ORDERS","SAT3_DUPLICATE_ORDER_GUARD_ENABLED"]`
  - `print({k:("set" if os.getenv(k) else "unset") for k in keys})`
  - `PY`

5) 서버 재시작
- .env를 수정한 경우 서버 재시작 필요
- export로만 설정한 경우 해당 프로세스 재기동 필요

## Rollback 절차 (즉시 차단)
1. `LIVE_TRADING_ENABLED=false`로 수동 복구
2. `unset SAT3_CONFIRM_LIVE_AUTO_TRADING` (또는 .env에서 제거)
3. 필요 시 Emergency Stop activate
4. runtime precheck 재확인 후 live start 차단 상태 검증

## 금지
- GET/querystring 기반 live start 금지
- confirm 없는 live start 금지
- Dashboard 단일 토글로 live start 금지
