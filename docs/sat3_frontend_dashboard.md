# SAT3 Frontend Dashboard (N10)

**Phase:** N10
**Stack:** Vite + React
**상태:** 구현 완료

---

## Components

| Component | Description |
|-----------|-------------|
| SystemStatusCard | LIVE_TRADING_ENABLED, Emergency Stop, Modules, Tests |
| SessionStatusCard | Session state, Buy allowed, Trading day |
| MarketRegimeCard | Regime, New buy allowed, Score |
| WebSocketStatusCard | Connection state, Channels, Reconnects, Errors |
| DataRouterStatusCard | Source, WS/REST availability |
| DataQualityWarningsCard | Stale data, disconnect warnings |
| ScannerCandidatesTable | Symbol, Type, Included, Exclusion reason |
| QuantScoresTable | Decision-level summary counts |
| RiskDecisionsTable | Symbol, Side, Allowed, Reason |

## Security

- 주문 실행 버튼 없음
- LIVE 토글 없음
- Emergency Stop 제어 버튼 없음
- Secret 표시 없음
