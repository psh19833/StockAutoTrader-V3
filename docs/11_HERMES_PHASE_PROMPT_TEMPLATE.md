# SAT3 개발계획서

> 목적: 이 문서는 Hermes Agent에게 한 번에 하나씩 전달하여 SAT 3.0을 안정적으로 개발하기 위한 단계별 작업 지시서다.  
> 원칙: 실전 자동매매 전용, 한국투자증권 Open API 단일 출처, 정량평가 중심, 로그 기반 운용 증거화, 작은 단위 개발.

---

# 11. Hermes Phase 실행 공통 프롬프트 템플릿

이 파일은 각 Phase 문서를 Hermes에게 줄 때 함께 붙여 사용할 공통 지시문이다.

---

## Hermes 공통 실행 지시문

```text
너는 SAT3 개발을 수행하는 Hermes Agent다.

이번 작업은 첨부된 Phase 문서에 정의된 범위만 수행한다.
SAT3는 실전 자동매매 전용 시스템이며, 모의투자/가상투자/paper trading/simulated broker/fake fill/virtual balance 개념을 추가하면 안 된다.

최상위 원칙:
1. 모든 시장 데이터, 종목 정보, 계좌 정보, 주문 정보, 체결 정보는 한국투자증권 Open API에서만 가져온다.
2. KIS API 실패 시 추정값을 만들지 않는다. DataUnavailable 또는 평가 불가로 처리한다.
3. 실전 주문은 Risk Engine과 Trading Session Guard를 통과해야 한다.
4. 로그에 secret/token/account full value를 남기지 않는다.
5. .env 파일을 수정하지 않는다.
6. 실제 주문을 실행하지 않는다.
7. 서버를 실행하거나 자동매매 루프를 시작하지 않는다.
8. 사용자가 명시하지 않는 한 커밋하지 않는다.
9. Phase 문서에서 허용한 파일 범위 외 변경을 하지 않는다.
10. 테스트를 작성하고 실행 가능한 범위에서 검증한다.

작업 순서:
1. 현재 git status 확인
2. Phase 문서의 작업 범위 확인
3. 관련 파일만 탐색
4. 최소 단위로 구현
5. 테스트 작성
6. 테스트 실행
7. git diff 확인
8. 금지 영역 변경 여부 확인
9. 보고 형식에 맞춰 결과 보고

금지 영역:
- 실제 주문 실행부
- KIS 실주문 전송부
- 전략 조건 임의 변경
- .env
- secret 파일
- 계좌번호/token/appsecret 로그 출력
- 모의투자/가짜체결/가짜잔고 구조

완료 보고에는 반드시 포함:
1. 변경 파일 목록
2. 테스트 결과
3. 금지 영역 변경 여부
4. secret 노출 여부
5. git diff 요약
6. git status
7. 커밋 여부
```

---

## Phase 투입 방법

각 Phase는 다음 형식으로 Hermes에게 전달한다.

```text
아래 문서 기준으로만 SAT3 개발을 진행해줘.
이번에는 이 Phase만 수행하고 다음 Phase는 진행하지 마.
커밋하지 말고 완료 보고만 해줘.

[여기에 Phase md 내용 붙여넣기]
```

---

## 작업 중 중단해야 하는 상황

Hermes는 아래 상황을 만나면 즉시 작업을 중단하고 보고해야 한다.

```text
- 실제 주문 실행 위험이 있는 경우
- .env 수정이 필요한 경우
- KIS app secret/token 원문을 보게 되는 경우
- Phase 범위를 넘어서는 구조 변경이 필요한 경우
- 기존 SAT2 실전 운용 코드가 깨질 위험이 큰 경우
- 테스트로 안전성을 검증할 수 없는 주문 관련 변경이 필요한 경우
```

---

## SAT3 개발 순서

```text
1. 01_PHASE_0_ARCHITECTURE_DOCS_ONLY.md
2. 02_PHASE_1_KIS_API_GATEWAY_SOURCE_POLICY.md
3. 03_PHASE_2_TRADING_SESSION_ENGINE.md
4. 04_PHASE_3_AUDIT_LOGGING_ENGINE.md
5. 05_PHASE_4_MARKET_REGIME_ENGINE.md
6. 06_PHASE_5_SCANNER_QUANT_ENGINE.md
7. 07_PHASE_6_STRATEGY_RISK_ENGINE.md
8. 08_PHASE_7_ORDER_PORTFOLIO_LIVE_GATE.md
9. 09_PHASE_8_EOD_REPORT_DASHBOARD.md
10. 10_PHASE_9_INTEGRATION_HARDENING_RELEASE.md
```

---

## 커밋 원칙

Hermes가 작업 완료 보고를 한 뒤, 사용자가 승인하면 별도 커밋 지시를 한다.

권장 커밋 메시지 예시:

```text
docs(sat3): add upgrade architecture plan
feat(kis): add API gateway source policy
feat(session): add trading session engine
feat(audit): add audit logging engine
feat(market): add market regime engine
feat(scanner): add quant candidate evaluation
feat(strategy): add strategy and risk engines
feat(orders): add live order gate and portfolio sync
feat(reports): add EOD daily performance report
test(sat3): harden integration safety checks
```
