# SAT3 Dashboard Runbook

> 상태: CONDITIONALLY_READY
> 목적: 조회전용 상태 확인 (주문/실행 제어 없음)

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
| System Status | LIVE_TRADING_ENABLED=false(기본), Emergency Stop inactive |
| Session Status | 기본 UNKNOWN + Buy Allowed=No (소스 주입 시 변경) |
| Market Regime | 기본 UNKNOWN + New Buy Allowed=No (소스 주입 시 변경) |
| WebSocket Status | provider 미연결 시 UNKNOWN + reason 확인 |
| Data Router | Source/연결 상태 확인 |
| Data Quality | warning 존재 시 원인 확인 |
| Scanner Candidates | 종목/Scanner/Included/Reason |
| Quant Scores | PASS/WATCH/REJECT 카운트 |
| Risk Decisions | Symbol/Side/Allowed/Reason |

## 보안

- 주문 실행 버튼 없음
- LIVE 토글 버튼 없음
- Emergency Stop 제어 없음 (CLI only)
- Secret 표시 없음
