# SAT3 Operational Runbook

> SAT3 실전 운용 매뉴얼
> 마지막 수정: 2026-05-06
> 상태: CONDITIONALLY_READY (실전매매 전환 대기)

---

## 1. 시스템 개요

### 테스트 기준 (Canonical)
- backend 테스트 기준 명령:
  - `cd backend && ../.venv/bin/python -m pytest -q`
- 현재 기준 결과: `1273 passed`
- root pytest 직접 실행 결과는 운영 판정 기준으로 사용하지 않는다.

SAT3(StockAutoTrader V3)는 한국투자증권(KIS) Open API 기반 실전 자동매매 시스템이다.

### 핵심 원칙

1. **실전 계좌 전용** — 모의투자, paper trading 일체 금지
2. **KIS API 단일 출처** — 외부 크롤링, 임의 종목 리스트 금지
3. **KOSPI/KOSDAQ 보통주만** — ETF/ETN/ELW/REIT/SPAC/우선주 등 제외
4. **LIVE_TRADING_ENABLED=false 기본값** — 명시적 활성화 전까지 주문 차단
5. **주문 성공 ≠ 체결 성공** — 체결은 WS 체결통보 + REST 체결조회 + REST 잔고조회 reconcile
6. **모든 결정은 Audit Log로 증명** — SCAN → QUANT → STRATEGY → RISK → ORDER → FILL 추적
7. **SafetyGate 필수 통과** — 11-layer 검증 없이 주문 불가
8. **Emergency Stop 우선** — active 시 모든 주문 차단
9. **LIVE_TRADING_ENABLED 수동 전환만** — 자동 true 전환 금지

### 파이프라인

```
KIS REST + WebSocket → DataRouter → Scanner → Quant → Strategy
                       ↘ MarketCache         ↘ RiskDecision
                              ↓                    ↓
                         Market Regime        SafetyGate (11-layer)
                              ↓                    ↓
                         Session Guard        Order API
                              ↓                    ↓
                         Runtime Scheduler    Fill Reconciliation
```

---

## 2. 개장일 운용 플로우 (9단계)

### Step 1: Preflight
```bash
cd /home/psh19/StockAutoTrader-V3
PYTHONPATH=./backend .venv/bin/python -c "
from safety.preflight import run_preflight
result = run_preflight()
print(result.summary)
"
```
- LIVE_TRADING_ENABLED: false 상태 확인
- Emergency Stop: inactive 확인
- 모듈 로드 확인

### Step 2: REST Read-Only 사전 점검
```bash
PYTHONPATH=./backend .venv/bin/python backend/scripts/kis_readonly_smoke.py --real
```
- Token 발급 성공 확인
- 현재가/종목정보/잔고조회 정상 확인
- secret masking 확인

### Step 3: WebSocket 사전 점검
```bash
PYTHONPATH=./backend .venv/bin/python backend/scripts/kis_ws_readonly_smoke.py --real-ws
```
- approval_key 발급 성공 확인
- WS 연결 성공 확인
- 4개 채널(trade_tick, order_book, market_status, expected_execution) 수신 확인
- parsed summary만 출력, raw 전문 없음

### Step 4: Dashboard 확인
```bash
cd frontend && npm run dev
# 브라우저에서 http://localhost:5173 접속
```
- System Status: LIVE_TRADING_ENABLED=false, Emergency Stop inactive
- WebSocket Status: CONNECTED, subscribed channels 확인
- Data Router: REST available, WS connected
- Market Regime: BULL/NEUTRAL/BEAR/UNKNOWN 확인
- 모든 카드/테이블 정상 렌더링 확인

### Step 5: Dry-Run (LIVE_TRADING_ENABLED=false)
```bash
PYTHONPATH=./backend .venv/bin/python -c "
from runtime.orchestrator import Orchestrator
from runtime.scheduler import SessionState
orch = Orchestrator()
result = orch.tick(SessionState.REGULAR_MARKET)
print(result)
"
```
- Scanner/Quant/Strategy/Risk pipeline 정상 실행 확인
- OrderIntent 생성되지만 submitted=false 확인
- AuditEvent 생성 확인

### Step 6: SafetyGate 최종 확인
```bash
PYTHONPATH=./backend .venv/bin/python -c "
from safety.live_order_safety_gate import LiveOrderSafetyGate
gate = LiveOrderSafetyGate()
result = gate.check(
    live_trading_enabled=False,  # 아직 false
    session='REGULAR_MARKET',
    market_regime='NORMAL',
    risk_approved=True,
    quote_stale=False,
    orderbook_stale=False,
)
print(f'SafetyGate: {result.passed}')
print(f'Block reasons: {result.block_reasons}')
"
```
- LIVE_TRADING_ENABLED=false → BLOCKED (정상)
- 다른 조건은 모두 통과 확인
- 11-layer 모두 확인

### Step 7: LIVE_TRADING_ENABLED=true 수동 전환
```bash
# .env 파일 직접 편집 (사용자가 수동으로)
# LIVE_TRADING_ENABLED=true 로 변경
nano .env
```
- **자동 전환 금지**
- 변경 후 SafetyGate 재확인

### Step 8: Confirm 옵션 명시
```bash
PYTHONPATH=./backend .venv/bin/python backend/scripts/sat3_live_order_smoke.py --confirm-live-order --dry-run
# dry-run 먼저 실행하여 모든 조건 확인
# 이상 없으면 --dry-run 제거하고 실제 실행
```
- --confirm-live-order 필수
- --dry-run 기본 → 모든 조건 통과 확인
- SafetyGate APPROVED 확인

### Step 9: 자동매매 시작
```bash
PYTHONPATH=./backend .venv/bin/python -c "
from runtime.orchestrator import Orchestrator
from runtime.scheduler import SessionState
orch = Orchestrator()
# REGULAR_MARKET tick → Scanner → Quant → Strategy → Risk → SafetyGate → Order
result = orch.tick(SessionState.REGULAR_MARKET)
"
```
- Scanner → Quant → Strategy → RiskDecision → SafetyGate 통과한 주문만 즉시 제출
- 첫 운용에서도 SafetyGate 필수 통과
- 주문 접수 ≠ 체결 성공
- 체결 확정: WS 체결통보 + REST 체결조회 + REST 잔고조회 reconcile

---

## 3. 장 중 운용

```
감시 항목:
- Dashboard: System/WS/Session/Regime 상태
- Telegram: SCAN_STARTED, QUANT_EVALUATED, RISK_REJECTED, ORDER_SUBMITTED 등
- Audit Log: 모든 이벤트 기록

금지:
- Emergency Stop active 시 모든 주문 차단
- REGULAR_MARKET 외 주문 금지
- BEAR/UNKNOWN Regime 신규매수 금지
- stale quote/orderbook 주문 금지
- LATE_MARKET(15:20~) 신규매수 금지
```

---

## 4. 장 종료 후

```bash
# EOD Report 자동 생성 (Runtime Scheduler)
# Telegram EOD 요약 수신
# Audit Log 확인
```

---

## 5. Market Regime별 운용 정책

| Regime | 신규매수 | RAPID_SURGE | BREAKOUT | LIQUIDITY | PULLBACK |
|--------|---------|-------------|----------|-----------|----------|
| BULL | 허용 | 적극 | 적극 | 허용 | 허용 |
| NEUTRAL | 허용 | 고득점만 | 제한적 | 중심 | 중심 |
| BEAR | **차단** | 비활성 | 비활성 | 비활성 | 비활성 |
| UNKNOWN | **차단** | 비활성 | 비활성 | 비활성 | 비활성 |

---

## 6. SafetyGate 11-Layer

| Layer | 조건 | 실패 시 |
|-------|------|---------|
| 1 | LIVE_TRADING_ENABLED=true | 주문 차단 |
| 2 | Emergency Stop inactive | 주문 차단 |
| 3 | Session=REGULAR_MARKET | 주문 차단 |
| 4 | Regime ≠ BEAR/UNKNOWN | 신규매수 차단 |
| 5 | RiskDecision APPROVED | 주문 차단 |
| 6 | Quote fresh (60s) | 주문 보류 |
| 7 | Orderbook fresh (60s) | 주문 보류 |
| 8 | Max daily loss 미초과 | 주문 차단 |
| 9 | Max position 미초과 | 주문 차단 |
| 10 | No duplicate order | 주문 차단 |
| 11 | WS connected | 리스크 경고 |

---

## 7. 비상 연락

- KIS API 고객센터: 1588-0037
- 시스템 담당자: (설정 필요)
