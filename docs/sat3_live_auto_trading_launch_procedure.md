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
- risk limits(일손실/최대종목/최대주문금액/종목노출/대기주문/중복주문가드) 로드
- audit logging active

## Risk limit 운영값 제안 (보수 시작값)
아래는 운영자가 수동으로 .env에 입력할 기본 운영 후보값이다. (자동 변경 금지)

- SAT3_MAX_DAILY_LOSS_KRW=50000
  - 의미: 일일 최대 손실 한도
- SAT3_MAX_POSITION_COUNT=2
  - 의미: 최대 동시 보유 종목 수
- SAT3_MAX_ORDER_AMOUNT_KRW=50000
  - 의미: 1회 주문 최대 금액
- SAT3_MAX_AMOUNT_PER_SYMBOL_KRW=100000
  - 의미: 종목당 최대 노출 금액
- SAT3_MAX_PENDING_ORDERS=1
  - 의미: 동시에 대기 가능한 주문 수
- SAT3_DUPLICATE_ORDER_GUARD_ENABLED=true
  - 의미: 중복 주문 방지

## 운영자 수동 설정 (코드 자동변경 금지)
아래 8개 항목은 운영자가 .env에서 수동 설정해야 하며, 애플리케이션이 자동 변경하면 안 된다.

필수 live env:
1) LIVE_TRADING_ENABLED=true
2) SAT3_CONFIRM_LIVE_AUTO_TRADING=CONFIRM_LIVE_AUTO_TRADING

필수 risk env:
3) SAT3_MAX_DAILY_LOSS_KRW=50000
4) SAT3_MAX_POSITION_COUNT=2
5) SAT3_MAX_ORDER_AMOUNT_KRW=50000
6) SAT3_MAX_AMOUNT_PER_SYMBOL_KRW=100000
7) SAT3_MAX_PENDING_ORDERS=1
8) SAT3_DUPLICATE_ORDER_GUARD_ENABLED=true

주의:
- .env 원문 전체 출력 금지
- appkey/appsecret/access_token/approval_key 원문 출력 금지
- 설정 반영을 위해 backend 프로세스 재시작 필요 (.env는 프로세스 시작 시 로드)

## Precheck-only 절차 (실제 live start/주문 금지)
아래 절차는 판정 확인 전용이며, 자동매매를 시작하지 않는다.

1) 기본 준비상태 점검
- `cd /home/psh19/StockAutoTrader-V3/backend && ../.venv/bin/python scripts/sat3_preflight_check.py`

2) KIS REST/WS read-only 점검
- `cd /home/psh19/StockAutoTrader-V3/backend && ../.venv/bin/python scripts/kis_readonly_smoke.py --real`
- `cd /home/psh19/StockAutoTrader-V3/backend && ../.venv/bin/python scripts/kis_ws_readonly_smoke.py --real-ws --duration 20 --max-messages 5`

3) LIVE 게이트 판정 체크만 수행 (시작 호출 없음)
- `cd /home/psh19/StockAutoTrader-V3/backend && PYTHONPATH=. ../.venv/bin/python - <<'PY'`
- `from main import _build_live_start_checks`
- `checks, ctx = _build_live_start_checks()`
- `failed = [k for k, v in checks.items() if not v]`
- `print({'failed': failed, 'context': ctx})`
- `PY`

확인 대상 체크:
- LIVE_TRADING_ENABLED_TRUE
- CONFIRM_ENV_SET
- SESSION_REGULAR_MARKET
- MARKET_REGIME_KNOWN
- RISK_LIMITS_LOADED
- KIS_REST_AVAILABLE (REST OK)
- KIS_WS_AVAILABLE (WS OK)
- EMERGENCY_STOP_INACTIVE
- PORTFOLIO_SOURCE_KIS_REST_FRESH (Portfolio not stale)

## SESSION_REGULAR_MARKET 장중 재검증 절차
- 현재 `CLOSED_AFTER_MARKET`은 장외 시간이므로 정상 blocker
- 장중(권장 09:15~15:20 KST)에 동일 precheck를 재실행
- session_source가 `KST_TIME_WITH_PRICE_ONLY` 이상(또는 더 강한 source)에서 `REGULAR_MARKET`인지 확인
- 장외(CLOSED/UNKNOWN)면 live start 차단 유지가 정상
- session이 UNKNOWN 또는 CLOSED이면 실전 자동매매 시작 금지

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
  "max_daily_loss_krw": 50000,
  "max_position_count": 2,
  "max_order_amount_krw": 50000,
  "interval_sec": 10
}

## Rollback 절차 (즉시 차단)
1. LIVE_TRADING_ENABLED=false로 수동 복구
2. SAT3_CONFIRM_LIVE_AUTO_TRADING 해제(환경변수 unset 또는 .env 제거)
3. 필요 시 Emergency Stop activate
4. runtime precheck 재확인 후 live start 차단 상태 검증

## 금지
- GET/querystring 기반 live start 금지
- confirm 없는 live start 금지
- Dashboard 단일 토글로 live start 금지
