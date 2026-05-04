# SAT3 KIS WebSocket Foundation (N8)

**작성일:** 2026-05-05
**Phase:** N8
**상태:** 구현 완료

---

## 1. REST와 WebSocket 역할 분리

| 영역 | 담당 | 프로토콜 |
|------|------|----------|
| 종목 기본 정보 | KIS REST API (`/uapi/domestic-stock/v1/quotations/*`) | REST |
| 시장 스케줄 | KIS REST API (`/uapi/domestic-stock/v1/quotations/*`) | REST |
| 계좌 정보 | KIS REST API (`/uapi/domestic-stock/v1/trading/inquire-*`) | REST |
| 실시간 체결가 | KIS WebSocket (`H0STCNT0`) | WebSocket |
| 실시간 호가 | KIS WebSocket (`H0STASP0`) | WebSocket |
| 실시간 체결통보 | KIS WebSocket (`H0STCNI0`) | WebSocket |
| 장운영정보 | KIS WebSocket (`H0STMKO0`) | WebSocket |
| 예상체결 | KIS WebSocket (`H0STANC0`) | WebSocket |

**원칙:** REST API로 가능한 정보는 REST API를 우선 사용. 실시간성이 필요한 데이터만 WebSocket으로 수신.

---

## 2. WebSocket 담당 기능

- **실시간 체결가 수신 (H0STCNT0):** 매매 판단 보조, not 자동 주문
- **실시간 호가 수신 (H0STASP0):** 시장 깊이 모니터링
- **실시간 체결통보 수신 (H0STCNI0):** 체결 확정 용도 (REST 체결조회와 병행)
- **장운영정보 수신 (H0STMKO0):** 개장/폐장/서킷브레이커 감지
- **실시간 예상체결 수신 (H0STANC0):** 장 시작 전 가격 예측
- **연결 상태 모니터링:** Dashboard에 WebSocketStatusView 표시

---

## 3. approval_key 발급 흐름

```
1. KisCredentials에서 app_key, app_secret 추출
2. POST /oauth2/Approval 요청 (KisTransport)
   body: { grant_type: "client_credentials", appkey: ..., secretkey: ... }
3. 응답 output.approval_key 추출
4. WsApprovalKey 객체 내부 저장
5. 외부 노출 시 MASKED_APPROVAL_KEY ("****-****-****")로 마스킹
6. 실패 시 ApprovalKeyError 발생
```

**보안:**
- `__repr__`, `__str__`, `get_masked()` 는 항상 MASKED_APPROVAL_KEY 반환
- `get_approval_key()` 로만 실제 키 접근 (내부 WebSocket 연결 시만 사용)
- app_key, app_secret, account_no는 repr/log에 노출 금지

---

## 4. 실시간 데이터 채널

| TR_ID | 채널명 | 채널 타입 | 시장 |
|-------|--------|-----------|------|
| H0STCNT0 | 실시간 체결가 | realtime | KRX |
| H0STASP0 | 실시간 호가 | realtime | KRX |
| H0STCNI0 | 실시간 체결통보 | notification | 통합 |
| H0STMKO0 | 장운영정보 | realtime | 통합 |
| H0STANC0 | 실시간 예상체결 | realtime | KRX |

모든 endpoint는 `source="KIS_API_WS"` 메타데이터 포함.

---

## 5. source="KIS_API_WS" 정책

- 모든 WebSocket 메시지 모델(`WebSocketMessageBase`)은 `source="KIS_API_WS"` 고정
- `WebSocketConnectionStatus.source`도 `"KIS_API_WS"` 고정
- `WebSocketStatusView.source`도 `"KIS_API_WS"` 고정
- REST API는 `source="KIS_API"`, WebSocket은 `source="KIS_API_WS"`로 구분

---

## 6. raw message logging 정책

- **raw 전문 전체 로그 금지**
- 대신 `raw_hash`(SHA-256)만 기록하여 데이터 무결성 검증
- `WsMessageParser`는 raw message를 파싱 후 hash만 보존
- `AuditEvent` payload에도 raw message 미포함

---

## 7. reconnect/backoff 정책

- `ReconnectConfig` 모델로 제어
- 기본값: max_retries=5, base_delay=1.0s, max_delay=60s, backoff_multiplier=2.0
- 지수 backoff: delay = base_delay × (multiplier^attempt), capped at max_delay
- reconnect 발생 시 `WS_RECONNECTING` AuditEvent 생성 (severity=WARNING)
- `StubWebSocketClient._simulate_reconnect()`로 테스트 가능

---

## 8. 체결 확정 정책

- **WebSocket 체결통보(H0STCNI0) + REST 체결조회**로 확인
- `RealtimeFillNotice` 모델이 체결 정보 수신
- **주문 성공 ≠ 체결 성공** — 혼동 금지
- 체결 확정 전까지 포지션 미반영

---

## 9. Dashboard 표시 정책

```
WebSocketStatusView:
  - connection_state: DISCONNECTED | CONNECTING | CONNECTED | RECONNECTING | ERROR
  - subscribed_channels: 구독 중인 TR_ID 목록
  - last_message_at: 마지막 메시지 수신 시각 (UTC)
  - reconnect_count: 재연결 횟수
  - last_error_type: 마지막 오류 유형
  - data_quality_warnings: 데이터 품질 경고 목록
  - source: "KIS_API_WS"
```

`DashboardSummary.ws_status`는 Optional (기존 코드와 호환 유지).

---

## 10. 주문 구현 금지사항

- 실제 주문 구현 금지 (LIVE_TRADING_ENABLED=false)
- 매수/매도/정정/취소 주문 endpoint 호출 금지
- WebSocket 데이터를 통한 자동 주문 실행 금지
- Dashboard에 주문 버튼 추가 금지
- Dashboard WebSocketStatusView에 주문 관련 필드 금지
- `AuditEvent`에서 WebSocket 이벤트로 ORDER_SUBMITTED 등 생성 금지

---

## 11. 모듈 구조

```
backend/kis/
├── ws_models.py          # WebSocket 데이터 모델 (6개 모델 + base)
├── ws_endpoints.py       # WebSocket endpoint catalog (5개 endpoint)
├── ws_approval.py        # approval_key 발급·관리
├── ws_parser.py          # raw message → typed model 파서
├── ws_client.py          # WebSocketClient, StubWSClient, GuardedRealWSClient
└── ws_event_bridge.py    # WebSocket message → AuditEvent 변환

backend/dashboard/
└── dashboard_models.py   # WebSocketStatusView + DashboardSummary.ws_status

backend/audit_logging/
└── audit_event.py        # AuditEventType에 WS_* 8종 추가
```

---

## 12. 테스트

- 모든 테스트는 StubTransport / StubWebSocketClient 기반
- 실제 KIS WebSocket 서버 접속 없음
- GuardedRealWebSocketClient.connect()는 NotImplementedError 발생
- 기존 926개 테스트 유지 확인
