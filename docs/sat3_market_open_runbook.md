# SAT3 Market Open Runbook

> 개장일 실전 전환 점검 절차
> 마지막 수정: 2026-05-06
> 상태: CONDITIONALLY_READY (증적 충족 시 실전 전환)

---

## 개장일 타임라인

| 시간 | 단계 | 명령 |
|------|------|------|
| 08:30 | Preflight | `sat3_preflight_check.py` |
| 08:50 | REST 사전점검(읽기전용) | `kis_readonly_smoke.py --real` |
| 08:55 | WebSocket 사전점검(읽기전용) | `kis_ws_readonly_smoke.py --real-ws` |
| 09:00 | Dashboard 확인(조회전용) | `localhost:5173` |
| 09:05 | Dry-Run | Launcher step 5 |
| 09:15 | SafetyGate 확인 | Launcher step 6 |
| 09:20 | 증적 점검 | 본 문서 "운영 증적 템플릿" |
| 09:25+ | 조건부 실전 전환 검토 | 승인자 수동 판단 |

## 자동매매 시작 조건

모든 조건 충족 시에만(하나라도 미충족이면 전환 금지):

- [ ] REST 사전점검 성공 (읽기전용)
- [ ] WebSocket 사전점검 성공 (읽기전용)
- [ ] Dashboard 조회전용 확인 (주문 버튼/LIVE 토글 없음)
- [ ] Session = REGULAR_MARKET
- [ ] Market Regime 정책 충족
- [ ] Emergency Stop inactive
- [ ] LIVE_TRADING_ENABLED=true (수동)
- [ ] --confirm-live-order 명시
- [ ] SafetyGate 11-layer 통과
- [ ] SafetyGateResult 체인 연결 확인
- [ ] Fill 3-way confirm 동작 확인
- [ ] Portfolio source_of_truth=KIS_REST 확인
- [ ] Telegram ORDER_SUBMITTED/FILL_CONFIRMED 의미 분리 확인
- [ ] Audit/Logging sanitize 확인

## 운영 증적 템플릿 (실전 전 필수)

- readonly REST smoke
  - 실행 시각:
  - 명령:
  - 결과 요약:
- readonly WS smoke
  - 실행 시각:
  - 명령:
  - 결과 요약(채널/수신):
- SafetyGate PASS/BLOCKED
  - 입력 조건:
  - passed:
  - block_reasons:
- Fill 3-way confirm
  - WS provisional:
  - REST fill:
  - REST balance:
  - 최종 status:
- Emergency Stop
  - activate 증적:
  - release 증적:
