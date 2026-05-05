# SAT3 Dashboard Runbook

## 실행

```bash
# Backend (terminal 1)
cd /home/psh19/StockAutoTrader-V3
PYTHONPATH=./backend .venv/bin/python -m uvicorn dashboard.main:app --host 0.0.0.0 --port 8000

# Frontend (terminal 2)
cd frontend && npm run dev
```

Open http://localhost:5173

## 확인 카드

| 카드 | 확인 항목 |
|------|-----------|
| System Status | LIVE_TRADING_ENABLED=false, Emergency Stop inactive |
| Session Status | REGULAR_MARKET, Buy Allowed=Yes |
| Market Regime | BULL/NEUTRAL/BEAR, New Buy Allowed |
| WebSocket Status | CONNECTED, subscribed channels 표시 |
| Data Router | Source=REST/WS, WS Connected |
| Data Quality | Warning 없음 |
| Scanner Candidates | 종목/Scanner/Included/Reason |
| Quant Scores | PASS/WATCH/REJECT 카운트 |
| Risk Decisions | Symbol/Side/Allowed/Reason |

## 보안

- 주문 실행 버튼 없음
- LIVE 토글 버튼 없음
- Emergency Stop 제어 없음 (CLI only)
- Secret 표시 없음
