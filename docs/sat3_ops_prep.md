# SAT3 OPS-PREP — 개장일 운용 준비

> 간략 체크리스트. 상세는 sat3_operational_runbook.md 참조.

## 개장일 9단계 (순서 엄수)

| # | 단계 | 명령 | 확인 |
|---|------|------|------|
| 1 | Preflight | `preflight` | LIVE=false, EmergencyStop=off |
| 2 | REST Smoke | `kis_readonly_smoke.py --real` | Token OK, 가격/잔고 조회 OK |
| 3 | WS Smoke | `kis_ws_readonly_smoke.py --real-ws` | WS 연결 OK, 4채널 수신 OK |
| 4 | Dashboard | `npm run dev` → localhost:5173 | 모든 카드 정상 |
| 5 | Dry-Run | Orchestrator.tick(REGULAR) | Pipeline OK, OrderIntent blocked |
| 6 | SafetyGate | gate.check(...) | LIVE_TRADING=false → BLOCKED (정상) |
| 7 | LIVE=true | `.env` 수동 편집 | **사용자 직접** |
| 8 | Confirm | `--confirm-live-order --dry-run` | SafetyGate APPROVED |
| 9 | Auto | Orchestrator.tick(REGULAR) | **즉시 자동매매 시작** |

## 첫 운용에서도

- 별도 1주 수동 검증 단계 없음
- SafetyGate 11-layer 필수 통과
- Session REGULAR_MARKET, Regime ≠ BEAR/UNKNOWN
- Emergency Stop inactive
- Stale data 주문 보류

## 금지

- LIVE_TRADING_ENABLED 자동 전환
- Emergency Stop 무시
- REGULAR_MARKET 외 주문
- BEAR/UNKNOWN 신규매수
- 주문 접수 = 체결 성공 혼동
- raw 전문/secret 출력
