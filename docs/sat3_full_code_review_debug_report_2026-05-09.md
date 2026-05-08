# SAT3 전체 코드 리뷰 및 디버그 보고서

작성시각: 2026-05-09 06:23:09 KST
대상 저장소: `/home/psh19/StockAutoTrader-V3`
검토 방식: 정적 코드 리뷰 + 읽기 전용 테스트/빌드 + 보안/시크릿 스캔
주의: 실제 KIS API 호출, 실제 Telegram 전송, live 서버 기동, 주문 실행은 수행하지 않았습니다.

---

## 1. 검증 요약

| 항목 | 결과 | 증빙 |
|---|---:|---|
| Git 브랜치 | `master` | `git branch --show-current` |
| Git remote | `https://github.com/psh19833/StockAutoTrader-V3` | `git remote -v` |
| 최근 커밋 | `5779554 fix(live): harden readiness and stabilize session tests` | `git log --oneline -5` |
| Backend 전체 테스트 | PASS | `1309 passed in 6.24s` |
| Frontend build | PASS | `vite build` 성공 |
| Targeted backend 테스트 | PASS | `48 passed in 0.13s` |
| 작업트리 | 기존 untracked `data/` 존재 | `git status --short` |
| 파일 수정 | 보고서 파일 1개 생성 | `docs/sat3_full_code_review_debug_report_2026-05-09.md` |

실행한 주요 명령:

```bash
cd /home/psh19/StockAutoTrader-V3/backend
/home/psh19/StockAutoTrader-V3/.venv/bin/python -m pytest -q
# 1309 passed in 6.24s

cd /home/psh19/StockAutoTrader-V3/frontend
npm run build
# ✓ built in 230ms
```

---

## 2. 코드베이스 규모

의존성/빌드/로그/데이터 산출물 제외 기준: `.git,node_modules,.venv,venv,__pycache__,dist,logs,data,.pytest_cache`

| 언어/종류 | 파일 수 | 라인 수 |
|---|---:|---:|
| 전체 | 331 | 106,467 |
| Python | 243 | 30,833 |
| Markdown | 47 | 9,289 |
| JSON | 2 | 2,455 |
| JSX | 22 | 805 |
| CSS | 2 | 200 |
| JavaScript | 3 | 87 |
| HTML | 1 | 13 |
| 기타 | 11 | 62,785 |

참고: `기타`에는 lock/config류 대형 텍스트 파일이 포함된 것으로 보이며, 리뷰상 핵심 소스는 Python/JSX 중심입니다.

---

## 3. 종합 판정

SAT3는 현재 테스트 수와 방어 계층 면에서 상당히 진전되어 있습니다. Scanner → Quant → Strategy → Risk → SafetyGate → Order → Fill Reconciliation 흐름이 분리되어 있고, 주문 실행 전 다중 gate를 두려는 설계 의도가 분명합니다.

다만 실전투자 시스템 기준으로는 아직 “실거래 투입 가능” 판정은 어렵습니다. 이유는 다음과 같습니다.

1. live/readiness 경로 일부가 실제 현재 상태가 아닌 하드코딩 또는 과거 smoke snapshot에 의존할 수 있습니다.
2. dashboard 조회 경로가 KIS/Telegram 외부 호출을 유발할 수 있어 read-only evidence dashboard 원칙이 약합니다.
3. 실행성 POST API가 같은 FastAPI surface에 인증 없이 노출되어 있습니다.
4. Risk/Order 최종 방어막에 SELL 보유 여부, 0원 주문, strict validation 기본값 등 실전 안전 공백이 있습니다.
5. KIS 문자열 숫자 응답 처리에서 Scanner 통과 후 Quant TypeError가 발생할 수 있습니다.
6. 로컬 `.env`는 ignore되어 있지만 LIVE_TRADING_ENABLED=true 및 실제 운영 credential 존재가 확인되어 운영 보안상 즉시 관리가 필요합니다.

권장 판정:

- 개발/검증 지속: 가능
- read-only smoke 및 dashboard 개선: 가능
- live 자동매매 시작: 보류
- 우선순위: Critical/High 항목 수정 후 전체 테스트 + live precheck dry verification 재수행

---

## 4. 긍정적으로 확인된 사항

### 4.1 Backend 테스트 기반이 강함

- 전체 backend pytest: `1309 passed`
- Scanner/Quant/Strategy/Risk/Order/Runtime/KIS/Dashboard/Audit 관련 테스트가 폭넓게 존재합니다.

### 4.2 Scanner excluded 후보가 Quant PASS로 부활하지 않음

증거:
- `backend/quant/scoring_calculator.py:281-294`
- `candidate.included == False`이면 `QuantDecision.REJECT`, `final_score=0.0` 처리

### 4.3 데이터 품질 경고가 여러 계층에서 방어됨

증거:
- Quant: `backend/quant/scoring_calculator.py:296-318`
- Strategy: `backend/strategy/strategy_evaluator.py:85-88`
- Risk: `backend/risk/risk_engine.py:113-127`, `backend/risk/risk_engine.py:205`

### 4.4 Order API 기본 차단 구조 존재

증거:
- `backend/kis/order_api.py:108-116`
- `live_trading_enabled=False` 차단
- `SafetyGateResult` 필수
- `submitter` 미설정 시 차단

### 4.5 체결 확정은 3-way reconciliation 구조

증거:
- `backend/order/fill_reconciliation.py:94-103`
- WS 체결 통지 + REST 체결 조회 + REST 잔고 반영이 모두 맞아야 `CONFIRMED`

### 4.6 Frontend 직접 주문 버튼은 확인되지 않음

- 현재 프론트엔드에서 buy/sell/order 실행 버튼 또는 live toggle UI는 확인되지 않았습니다.
- 단, backend POST API는 별도 이슈로 남아 있습니다.

---

## 5. Critical 이슈

### C-1. Orchestrator live mode가 readiness를 실제 검증하지 않고 `ready=True`를 하드코딩

증거:
- `backend/runtime/orchestrator.py:81-84`
  - live mode에서 `self._live_runner.run_tick(session=session.value, ready=True)` 호출
- `backend/runtime/live_trading_runner.py:60-86`
  - `configured`, `session`, `ready`만 확인
- `backend/runtime/orchestrator.py:22-23`
  - `SAT3_ENABLE_LIVE_RUNNER=true`이면 configured=True

위험:
- `SAT3_ENABLE_LIVE_RUNNER=true`이고 장중 세션이면, 실제 preflight/account/ws/rest/token readiness 검증 없이 live tick 실행 상태가 나올 수 있습니다.
- 현재 실제 주문까지 연결된 것으로 단정되지는 않지만, 실전 시스템에서는 live tick 자체가 운영 오해를 유발합니다.

권고:
- Orchestrator live tick은 `_build_live_start_checks()` 또는 별도 `LiveReadinessProvider` 결과를 주입받아야 합니다.
- `ready=True` 하드코딩 제거.
- 테스트 추가: `SAT3_ENABLE_LIVE_RUNNER=true`여도 readiness 실패 시 live tick 차단.

### C-2. Dashboard “조회” 경로가 실제 KIS/Telegram 네트워크 호출을 수행

증거:
- `backend/dashboard/dashboard_service.py:111-163`
  - `_probe_kis_price()`가 KIS 토큰 발급 및 현재가 조회 수행
- `backend/dashboard/dashboard_service.py:165-236`
  - `_probe_kis_holiday_status()`가 KIS 휴장일 API 호출
- `backend/dashboard/dashboard_routes.py:236-258`
  - Telegram `getMe` API 호출
- `frontend/src/pages/DashboardPage.jsx:26-33`
  - summary 5초 polling

위험:
- 대시보드 조회만으로 실전 KIS/Telegram API 호출이 반복될 수 있습니다.
- KIS rate limit, 토큰 발급 실패, IP whitelist 실패, Telegram 장애가 조회 화면에 의해 증폭될 수 있습니다.

권고:
- dashboard summary는 cache-only/evidence-only 기본값으로 전환.
- 실제 KIS/Telegram probe는 별도 명시 endpoint + 인증 + TTL cache로 분리.
- 5초 polling이 외부 API를 직접 때리지 않도록 서버 내부 sampler 도입.

### C-3. live auto trading start CLI의 `--confirm-account`가 실제 검증되지 않음

증거:
- `backend/scripts/sat3_live_auto_trading_start.py:10-11`
  - `--confirm-account` required 인자 수신
- `backend/scripts/sat3_live_auto_trading_start.py:29-36`
  - payload에 confirm_account 미포함
- `backend/main.py:435-447`
  - runtime_start_live()에서도 계좌 확인값 검사 없음

위험:
- 운영자가 입력한 계좌와 실제 `.env` 계좌가 일치하는지 확인하지 못합니다.
- 실전 계좌 오입력/다른 계좌 env 로딩 사고를 방어하지 못합니다.

권고:
- `--confirm-account` 값을 API payload에 포함.
- 서버에서 `KIS_ACCOUNT_NO`와 정확히 비교.
- 불일치 시 live start hard fail.

---

## 6. High 이슈

### H-1. KIS 문자열 숫자 응답에서 Scanner 통과 후 Quant TypeError 가능

증거:
- Scanner는 `_get_float()`로 문자열 숫자 필터 통과 가능:
  - `backend/scanner/scanner_engine.py:82-85`
- 그러나 metrics는 원본 raw 값 저장:
  - `backend/scanner/scanner_engine.py:138`
- Quant는 raw metric을 숫자로 가정하고 비교:
  - `backend/quant/scoring_calculator.py:55-116`

재현 결과:
- 문자열 숫자 stock으로 Scanner BREAKOUT은 included=True가 되었으나 Quant 평가에서 TypeError 발생:
  - `TypeError: '>=' not supported between instances of 'str' and 'int'`

권고:
- ScannerCandidate 생성 시 normalized numeric metrics를 저장하거나 Quant 입력부에서 안전 변환.
- 문자열 숫자 end-to-end 테스트 추가.

### H-2. `check_liquidity_momentum()`이 malformed rank에서 예외 발생

증거:
- `backend/scanner/filters.py:237-239`
  - `rank = metrics.get("trading_value_rank")` 후 `float(rank)` 직접 호출

재현 결과:
- `trading_value_rank="N/A"` 입력 시 `ValueError`

권고:
- 기존 `_safe_float()` 패턴 적용.
- malformed rank 테스트 추가.

### H-3. Risk Engine이 SELL 신호에 대해 보유 포지션 존재 여부를 확인하지 않음

증거:
- `backend/risk/risk_engine.py:94-101`
  - `side == "SELL"`이면 duplicate_position 검사를 무조건 통과

재현 결과:
- `current_positions=frozenset()` 상태에서 SELL 신호가 APPROVED 가능.

권고:
- SELL은 “중복 포지션 차단”이 아니라 “보유 포지션 존재 확인”으로 분리.
- `SELL_BLOCKED_NO_POSITION` 류 reject 추가.

### H-4. Risk Engine이 requested_amount=0, confidence=0 BUY도 승인 가능

증거:
- `backend/risk/risk_engine.py:132-144`
  - requested_amount가 0이면 limit 초과 검사 통과
- `backend/risk/risk_config.py:17`
  - `min_candidate_score_for_buy` 정의되어 있으나 Risk Engine에서 미사용
- `backend/risk/risk_engine.py:196-213`
  - confidence/source_quant_id 검증 항목 없음

재현 결과:
- `confidence=0.0`, `requested_amount=0` BUY 신호가 APPROVED 가능.

권고:
- requested_amount는 live 주문 전 `> 0` 필수.
- confidence/source_quant_id/candidate score 검증 추가.
- malformed/manual signal에 대한 final defense 테스트 추가.

### H-5. Order strict_validation 기본값이 False

증거:
- `backend/kis/order_api.py:84-98`
  - `strict_validation: bool = False`
- `backend/kis/order_api.py:117-124`
  - risk_decision_approved/account/correlation_id 검증은 strict_validation=True일 때만 수행

위험:
- `SafetyGateResult.passed=True`와 submitter가 있으면 strict_validation=False 상태에서 계좌/correlation/risk 승인 검증이 선택 사항이 됩니다.

권고:
- 실거래 주문 함수는 기본 `strict_validation=True`.
- `live_trading_enabled=True`이면 strict validation 강제.
- account/correlation/risk approval 테스트 추가.

### H-6. 실행성 POST API에 인증/권한 확인 없음

증거:
- `backend/main.py:403-447`
  - `/api/runtime/start`, `/api/runtime/start-live`
- `backend/main.py:480-507`
  - `/api/telegram/test`
- `backend/main.py:211-215`
  - CORS만 설정, 관리자 인증/CSRF 없음

위험:
- 로컬 브라우저/로컬 프로세스/프록시/터널 노출 시 confirm 문자열만으로 runtime start 또는 Telegram 전송 가능.

권고:
- 관리자 토큰, CSRF, local bind 검증, one-time live enable gate 추가.
- confirm 문자열은 인증 수단이 아니라 안전 문구로만 취급.

### H-7. WS/REST readiness가 과거 smoke snapshot에 의해 통과 가능

증거:
- WS:
  - `backend/dashboard/dashboard_service.py:321-329`
  - `backend/main.py:177-179`
  - `ws_readonly_smoke_verified`이면 live readiness에서 KIS_WS_AVAILABLE 통과 가능
- REST:
  - `backend/dashboard/dashboard_service.py:238-250`
  - smoke snapshot freshness 검사 없이 data_router rest_available로 사용 가능

위험:
- 현재 연결/현재 REST 가능성이 아니라 과거 evidence로 live readiness가 통과할 수 있습니다.

권고:
- live readiness에서는 현재 연결/최근 N초 이내 evidence만 인정.
- smoke snapshot에는 timestamp freshness hard check 적용.
- UI에는 snapshot 기반 상태와 current provider 상태를 명확히 분리.

### H-8. 로컬 `.env`에 실제 운영 credential 및 LIVE_TRADING_ENABLED=true 존재

증거:
- `.env`는 `.gitignore`로 ignore되어 Git에는 올라가지 않음.
- 보안 리뷰에서 다음 존재 확인:
  - KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, KIS_WS_APPROVAL_KEY
  - `LIVE_TRADING_ENABLED=true`

주의:
- 실제 값은 보고서에 기록하지 않았습니다.

권고:
- 개발/리뷰 기본 상태는 `LIVE_TRADING_ENABLED=false` 유지.
- 필요한 경우 키 회전 검토.
- `.env` 권한 및 백업/동기화 제외 확인.

---

## 7. Medium/Low 이슈

### M-1. `data/` smoke snapshot JSON이 untracked이고 .gitignore 커버리지 미흡

증거:
- `git status --short`: `?? data/`
- `data/kis_readonly_smoke_snapshot.json`
- `data/kis_ws_readonly_smoke_snapshot.json`
- `.gitignore`에는 `data/`, `data/*.json`, `*_snapshot.json` 없음

권고:
- `.gitignore`에 runtime evidence 산출물 패턴 추가.
- 커밋 전 secret scan hook 추가.

### M-2. 테스트에 전역 네트워크 차단 fixture가 없음

증거:
- `backend/tests/conftest.py`는 PYTHONPATH 설정 중심
- 일부 테스트는 개별 monkeypatch로 urlopen 차단하나 전역 차단은 없음

위험:
- 신규 테스트에서 monkeypatch 누락 시 실제 KIS/Telegram 호출 가능.

권고:
- `conftest.py`에 autouse network block fixture 추가.
- real smoke는 pytest marker + explicit env opt-in으로 분리.

### M-3. Frontend polling 중첩 및 AbortController 부재

증거:
- `frontend/src/pages/DashboardPage.jsx:26-33`: summary 5초 polling
- `frontend/src/components/audit/AuditTimelineList.jsx:34-39`: audit 5초 polling
- `frontend/src/components/dashboard/TelegramStatusCard.jsx:6-9`: telegram 10초 polling

권고:
- 이전 요청 완료 전 중복 요청 방지.
- AbortController 도입.
- server-side cached status 사용.

### M-4. Frontend error handling이 단순하고 일시 오류 후 복구 표시가 약함

증거:
- `frontend/src/api/dashboardApi.js`: HTTP status만 throw, body detail 미보존
- `frontend/src/pages/DashboardPage.jsx:26-36`: 성공 시 `setError(null)` 없음
- 일부 카드 `.catch(() => {})`로 오류를 숨김

권고:
- error detail/correlation_id 표시.
- 성공 시 error clear.
- “데이터 없음”과 “API 장애”를 UI에서 구분.

### M-5. runtime status/live blockers가 summary payload에는 있으나 UI 표시 없음

증거:
- backend payload:
  - `backend/dashboard/dashboard_routes.py:125-150`
- frontend 미표시:
  - `frontend/src/pages/DashboardPage.jsx:44-81`

권고:
- “자동매매 실행 상태/차단 사유” 한국어 evidence card 추가.
- read-only banner와 함께 표시.

### M-6. FillReconciler가 부분체결/복수체결 누적 모델이 부족

증거:
- `backend/order/fill_reconciliation.py:28-41`
  - order_number별 FillRecord 1개 저장, 동일 order_number WS notice 덮어쓰기
- `backend/order/fill_reconciliation.py:73-76`
  - REST volume과 WS volume이 정확히 같지 않으면 mismatch

권고:
- partial fill 누적, 평균단가, 잔량, 정정/취소 케이스 모델링.
- 관련 테스트 추가.

### M-7. 계좌번호/chat_id 전체 노출

증거:
- `backend/dashboard/dashboard_routes.py:250-254`
- `backend/dashboard/dashboard_routes.py:344-346`
- `frontend/src/components/dashboard/KisAccountCard.jsx:14`
- `frontend/src/components/dashboard/TelegramStatusCard.jsx:19`

권고:
- 운영 UI/API 기본 마스킹.
- 필요 시 “로컬 상세보기” 별도 명시.

### L-1. 위험한 shell=True/eval/os.system은 확인되지 않음

확인 결과:
- `shell=True`, `eval(`, `exec(`, `os.system` 직접 위험 패턴은 발견되지 않았습니다.
- subprocess는 대부분 list arg 형태로 사용되어 shell injection 위험은 낮습니다.

---

## 8. 우선순위별 조치 계획

### 즉시 조치 P0

1. `.env`에서 `LIVE_TRADING_ENABLED=false` 복구.
2. `data/`, `data/*.json`, `*_snapshot.json` .gitignore 추가 검토.
3. 실행성 POST API 인증/권한/CSRF/관리자 토큰 설계.
4. live start `--confirm-account` 서버 검증 추가.
5. Orchestrator `ready=True` 하드코딩 제거.

### 단기 조치 P1

1. KIS 문자열 숫자 normalization 적용.
2. scanner malformed rank 안전 처리.
3. Risk SELL 보유 여부/0원 주문/confidence/source_quant_id 검증.
4. Order strict_validation 기본 True 또는 live mode 강제.
5. WS/REST smoke snapshot freshness hard check.
6. Dashboard summary 외부 API 직접 호출 제거 또는 TTL cache 적용.

### 중기 조치 P2

1. Frontend polling AbortController 및 dedupe.
2. runtime status/live blockers UI card 추가.
3. fallback/source/status_reason/stale_warnings UI 표시.
4. 전역 network-block pytest fixture 추가.
5. Fill reconciliation partial fill 모델 보강.
6. 계좌/chat_id 마스킹 정책 정리.

---

## 9. 권장 테스트 추가 목록

1. `SAT3_ENABLE_LIVE_RUNNER=true` + readiness false → live tick 차단.
2. KIS 문자열 숫자 end-to-end: Scanner 통과 → Quant 예외 없음.
3. `trading_value_rank="N/A"` → Scanner 예외 없이 reject.
4. SELL without position → Risk reject.
5. BUY requested_amount=0/confidence=0/source_quant_id missing → Risk reject.
6. strict_validation false라도 live mode에서는 account/correlation/risk approval 필수.
7. smoke snapshot timestamp stale → live readiness fail.
8. Dashboard summary 호출이 외부 KIS/Telegram API를 직접 호출하지 않는지 monkeypatch 검증.
9. pytest 전역 network block fixture 검증.
10. FillReconciler partial fill 누적/잔량/정정/취소 케이스.

---

## 10. 결론

SAT3는 현재 “테스트 기반과 방어 계층 설계”는 우수합니다. 특히 주문 전 safety gate, audit/sanitizer, KIS transport 차단, 체결 reconciliation 등 실전 시스템에 필요한 핵심 구조가 이미 들어가 있습니다.

그러나 실전 자동매매 관점에서는 아직 다음 3개 축이 미완성입니다.

1. 현재성 보장: live readiness가 현재 REST/WS/계좌/토큰 상태를 직접 검증해야 함.
2. 실행면 격리: dashboard/read-only API와 runtime/execution control API를 분리하거나 강하게 인증해야 함.
3. 최종 방어막 강화: Risk/Order가 malformed/manual signal, SELL 미보유, 0원 주문, strict validation 공백을 자체적으로 차단해야 함.

따라서 다음 단계는 신규 기능 추가보다 Critical/High 항목 안정화 Phase로 잡는 것을 권장드립니다.
