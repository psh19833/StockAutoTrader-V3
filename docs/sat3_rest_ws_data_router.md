# SAT3 REST + WebSocket Data Router (N9)

**Phase:** N9
**상태:** 구현 완료

---

## 개요

REST snapshot과 WebSocket stream을 하나의 Runtime Data Layer로 통합.
MarketCache에 최신 데이터를 저장하고, MarketDataRouter를 통해 통합 접근.

---

## 아키텍처

```
REST API (snapshot) ──→ MarketCache ──→ MarketDataRouter ──→ Consumers
WebSocket (stream)  ──→              │                       (Scanner, Quant, etc.)
                                     │
                              DataQualityCheck
                              DataRouterStatusView (Dashboard)
```

---

## 모듈

| 모듈 | 역할 |
|------|------|
| rest_ws_policy.py | REST/WS 선택 정책, fallback 규칙 |
| market_cache.py | symbol별 latest quote/orderbook/tick/status 저장소 |
| data_quality.py | stale 감지, missing field, source 검증 |
| data_router.py | 통합 접근 레이어, WS → cache update |

---

## 정책

- 초기값: REST snapshot
- 실시간 갱신: WebSocket stream
- WS 장애: REST fallback
- 추정값 금지
