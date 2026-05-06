# SAT3 D-Day Auto Trading Runbook (2026-05-07)

## 목적
SAT3를 내일 장중 자동매매 가능 상태로 만들기 위한 사전 정리/검증/배포 절차를 완료한다.

## 단계
1. 작업트리 분리 커밋
   - 1차: Dashboard/runtime status(read-only) 묶음
   - 2차: 실주문 실행경로 묶음
2. 테스트 게이트
   - KIS auth 관련 테스트
   - runtime/dashboard 관련 테스트
   - backend 전체 pytest
   - frontend build
3. 원격 반영
   - 각 커밋 push
4. 장전 운영 체크
   - runtime API dry-run 점검
   - live 모드 차단/허용 조건 점검
   - Go/No-Go 기록

## Go 조건
- backend pytest green
- frontend build green
- runtime start/status/stop 정상
- live enable 제어 조건 문서화 완료

## No-Go 조건
- 테스트 실패
- runtime 상태 불안정
- 주문 경로 우회 가능성 미해소

## 비고
- 민감정보 출력 금지
- 실제 주문 API/실체결 호출 없음(코드 레벨/테스트 레벨 점검만 수행)

## 2026-05-06 운영 증적/장전 Go-No-Go 상태 반영
- 상태: SAFE_RECOVERED
- 준비도: CONDITIONALLY_READY
- KIS tokenP 403 이슈: 해결 완료(내부 과호출 경로 제거 및 런타임 live 차단 반영)
- 실주문 실행경로: 닫힘 유지
- runtime API: dry-run 전용 유지
- mode=live 요청: RUNTIME_LIVE_MODE_DISABLED로 차단

### 실전 전 필수 잔여 조건(읽기전용 검증)
1. readonly REST smoke 증적 확보(토큰/현재가/잔고 조회 결과)
2. readonly WS smoke 증적 확보(approval_key/연결/구독 결과)
3. Dashboard 핵심 상태 정상 표시 확인(data_router/session/regime/ws/runtime/stale)
4. Emergency Stop 상태 확인(INACTIVE/ACTIVE 명시)
5. 실주문 경로는 별도 승인 전까지 닫힘 유지(재개방 금지)
