# SAT3 Release Checklist

> 상태: CONDITIONALLY_READY (실전 전환 증적 수집 전)

## 테스트 실행 기준 (Canonical)
- backend canonical command:
  - `cd backend && ../.venv/bin/python -m pytest -q`
- 현재 기준: `1273 passed`
- root 경로에서 pytest를 직접 실행하는 방식은 기준값으로 사용하지 않는다.

## Pre-flight
- [x] LIVE_TRADING_ENABLED=false (기본값)
- [x] Emergency Stop inactive
- [x] 모든 모듈 import 가능
- [x] Audit writer 동작 확인
- [x] Telegram notifier 동작 확인
- [x] EOD report builder 동작 확인

## Security
- [x] secret masking 정상 (app_key, api_key, token, account_no, chat_id)
- [x] .env 원문 미출력
- [x] Audit payload에 secret 미포함

## Code Integrity
- [x] requests/httpx 직접 호출 없음
- [x] KIS Gateway 우회 없음
- [x] fake fill/fake balance 없음
- [x] Order submitter는 stub only
- [x] SafetyGateResult 체인 미연결 시 주문 차단 (SAFETY_GATE_CHAIN_REQUIRED)
- [x] Fill 3-way confirm (WS + REST fill + REST balance) 확인
- [x] Portfolio source_of_truth=KIS_REST 강제 / stale+mismatch 기록
- [x] Dashboard 조회전용(주문 버튼/LIVE 토글 없음)
- [x] Telegram ORDER_SUBMITTED(접수) / FILL_CONFIRMED(체결) 의미 분리
- [x] Audit/Logging sanitize 적용 (secret/token/account/chat_id)

## 운영 증적 템플릿 (실전 전 필수)
- [ ] readonly REST smoke 결과 첨부 (명령/시각/결과 요약)
- [ ] readonly WS smoke 결과 첨부 (연결/채널/수신 요약)
- [ ] SafetyGate PASS/BLOCKED 증적 첨부 (block_reasons 포함)
- [ ] Fill 3-way confirm 증적 첨부 (ws/rest/balance 각 단계)
- [ ] Emergency Stop activate/release 증적 첨부

## Testing
- [x] 전체 테스트 1273 passed (backend canonical command 기준)
- [x] Phase별 테스트 분리 완료
- [x] 금지 import 검증 통과
- [x] secret grep 통과
