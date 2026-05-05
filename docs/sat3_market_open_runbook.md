# SAT3 Market Open Runbook

> 개장일 즉시 자동매매 시작 절차
> 마지막 수정: 2026-05-05

---

## 개장일 타임라인

| 시간 | 단계 | 명령 |
|------|------|------|
| 08:30 | Preflight | `sat3_preflight_check.py` |
| 08:50 | REST 사전점검 | `kis_readonly_smoke.py --real` |
| 08:55 | WebSocket 사전점검 | `kis_ws_readonly_smoke.py --real-ws` |
| 09:00 | Dashboard 확인 | `localhost:5173` |
| 09:05 | Dry-Run | Launcher step 5 |
| 09:15 | SafetyGate 확인 | Launcher step 6 |
| 09:20 | LIVE=true 수동 전환 | `.env` 직접 편집 |
| 09:20 | 자동매매 시작 | `--confirm-live-order` |

## 자동매매 시작 조건

모든 조건 충족 시에만:

- [ ] REST 사전점검 성공
- [ ] WebSocket 사전점검 성공
- [ ] Dashboard 정상
- [ ] Session = REGULAR_MARKET
- [ ] Market Regime ≠ BEAR/UNKNOWN
- [ ] Emergency Stop inactive
- [ ] LIVE_TRADING_ENABLED=true (수동)
- [ ] --confirm-live-order 명시
- [ ] SafetyGate 11-layer 통과

## 별도 1주 수동 검증 없음

실전 가능 상태가 되면 개발된 Scanner → Quant → Strategy → Risk → SafetyGate 흐름에 따라 **즉시 자동매매 시작**. 별도 1주 검증 단계 강제하지 않음.
