# SAT3 KIS WebSocket Read-Only Smoke Test (N8-B)

**작성일:** 2026-05-05
**Phase:** N8-B
**상태:** 구현 완료

---

## 1. 목적

KIS WebSocket Foundation(N8)의 실제 연결을 검증하기 전, read-only smoke 테스트를 준비한다.

기본값은 StubWebSocketClient를 사용하여 실제 네트워크 연결 없이 검증하며,
`--real-ws` 옵션을 통해서만 GuardedRealWebSocketClient를 사용한다.

---

## 2. .env 작성 주의

`.env` 파일은 `.gitignore`에 등록되어 있으며, 직접 편집이 필요하다.

```
KIS_APP_KEY=your_app_key
KIS_APP_SECRET=your_app_secret
KIS_BASE_URL=https://openapi.koreainvestment.com:9443
KIS_ACCOUNT_NO=44413716-01
KIS_ACCOUNT_PRODUCT_CODE=01
LIVE_TRADING_ENABLED=false    # 반드시 false
```

**주의:** `LIVE_TRADING_ENABLED=true`일 경우 smoke 스크립트는 즉시 중단된다.

---

## 3. approval_key 마스킹

- 모든 출력에서 approval_key는 `****-****-****`로 표시
- subscribe payload 출력 시에도 `header.approval_key`는 마스킹
- app_key/app_secret은 credentials 로드 시 자동 마스킹
- `get_subscribe_payload_masked()`로 마스킹 버전 획득 가능

---

## 4. 실행 명령

### Stub 모드 (기본 — 권장)
```bash
PYTHONPATH=./backend python backend/scripts/kis_ws_readonly_smoke.py
```

### Stub 모드 + 특정 종목
```bash
PYTHONPATH=./backend python backend/scripts/kis_ws_readonly_smoke.py --symbol 005930
```

### Stub 모드 + 특정 채널
```bash
PYTHONPATH=./backend python backend/scripts/kis_ws_readonly_smoke.py --channels trade_tick,order_book
```

### Stub 모드 + 체결통보 포함
```bash
PYTHONPATH=./backend python backend/scripts/kis_ws_readonly_smoke.py --include-fill-notice
```

---

## 5. Stub 모드

- `StubWebSocketClient` 사용
- 실제 WebSocket 연결 없음
- `connect()` / `subscribe()` / `disconnect()` 모두 상태 관리만
- 메시지 시뮬레이션: 더미 JSON → `dispatch_message()` → parsed summary 출력
- approval_key는 stub용 가짜 키 사용 (`stub-approval-key-00000000`)

**Stub 모드 출력:**
- [INFO] Using StubWebSocketClient (stub mode)
- [INFO] Credentials loaded: {...} (masked)
- [INFO] Stub approval_key: ****-****-****
- Subscribe payload (masked): {...}
- Parsed summary (summary only, no raw)

---

## 6. --real-ws 모드

- `GuardedRealWebSocketClient` 사용
- `connect()`는 아직 `NotImplementedError` (현재 skeleton)
- `approval_key`를 실제 KIS `/oauth2/Approval` endpoint로 발급 시도
- 발급 실패 시 `ApprovalKeyError` 발생
- 발급 성공 시 masked approval_key만 출력

**주의:**
- `--real-ws`는 실제 KIS API 호출이 포함됨 (approval_key 발급)
- 아직 실제 WebSocket 연결은 구현되지 않음 (NotImplementedError)
- 향후 N8-C에서 활성화 예정

---

## 7. 채널별 설명

| 채널명 | TR_ID | 설명 |
|--------|-------|------|
| trade_tick | H0STCNT0 | 실시간 체결가 |
| order_book | H0STASP0 | 실시간 호가 |
| market_status | H0STMKO0 | 장운영정보 |
| expected_execution | H0STANC0 | 실시간 예상체결 |
| fill_notice | H0STCNI0 | 실시간 체결통보 (기본 제외) |

---

## 8. fill_notice 기본 제외 정책

- `fill_notice`(체결통보)는 **기본 채널에서 제외**
- `--include-fill-notice` 플래그로만 포함 가능
- 체결통보는 **관찰/파싱 대상일 뿐**, 포지션 확정이나 주문 성공 처리로 연결하지 않음
- Dashboard/포지션 반영은 이루어지지 않음

---

## 9. 주문 구현 금지

- smoke 스크립트는 어떤 형태의 주문도 실행하지 않음
- 매수/매도/정정/취소 endpoint 호출 없음
- `LIVE_TRADING_ENABLED=true` 시 스크립트 즉시 중단
- 채널 목록에 주문 관련 TR_ID 없음
- 모든 채널은 read-only 시장 데이터

---

## 10. 체결통보는 포지션 확정이 아님

- `fill_notice` 채널은 WebSocket 체결통보 수신을 테스트하기 위한 것
- 수신된 체결통보로 자동 포지션 업데이트/확정을 하지 않음
- **주문 성공 ≠ 체결 성공** 원칙 유지
- 체결 확정은 향후 별도 Phase에서 구현

---

## 11. raw 전문 출력 금지

- `dispatch_message()`는 raw 전문을 저장/출력하지 않음
- `raw_hash`(SHA-256)만 기록
- smoke 스크립트 출력은 `_print_parsed_summary()`를 통한 typed summary만
- subscribe payload도 마스킹 버전만 출력

---

## 12. 실패 시 점검 항목

| 증상 | 점검 항목 |
|------|-----------|
| `LIVE_TRADING_ENABLED=true` 중단 | `.env` 파일 확인, `false`로 변경 |
| approval_key 발급 실패 | `app_key`/`app_secret` 확인, IP 화이트리스트 확인 |
| subscribe 실패 | TR_ID 유효성, symbol 형식 확인 |
| parse 실패 (parsed_ok=False) | TR_ID 오타, KIS API 응답 형식 변경 확인 |
| 연결 실패 (NotImplementedError) | `--real-ws` 연결 구현 예정, 현재는 skeleton |
