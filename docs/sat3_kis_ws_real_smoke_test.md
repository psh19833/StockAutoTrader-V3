# SAT3 KIS WebSocket Real Smoke Test (N8-C)

**작성일:** 2026-05-05
**Phase:** N8-C
**상태:** 구현 완료

---

## 1. 개요

N8-B에서 준비한 smoke 스크립트를 실제 KIS WebSocket 연결 검증을 위해 보강한다.
GuardedRealWebSocketClient의 연결/하트비트/재연결 구조를 준비하고,
pipe-delimited 메시지 형식에 대비한 parser를 추가한다.

**핵심:** 실제 연결은 `--real-ws` 옵션에서만 시도하며, 기본값은 StubWebSocketClient.

---

## 2. GuardedRealWebSocketClient 보강

### 2.1 heartbeat
- `_heartbeat()`: CONNECTED 상태에서만 `last_message_at` 갱신
- DISCONNECTED 상태에서는 무시
- keep-alive 추적용

### 2.2 connection_state
- `ConnectionState` enum: DISCONNECTED / CONNECTING / CONNECTED / RECONNECTING / ERROR
- `connect()` → 현재 NotImplementedError (skeleton)
- `disconnect()` → DISCONNECTED 전환, subscribed 초기화

### 2.3 reconnect/backoff
- `ReconnectConfig`: max_retries=5, base_delay=1.0s, max_delay=60s, backoff_multiplier=2.0
- `compute_delay(attempt)` → 지수 backoff (capped)

### 2.4 subscribe payload
- `build_subscribe_payload(tr_id, symbol, approval_key)` → wire-level payload
- `build_unsubscribe_payload(tr_id, symbol, approval_key)` → unregister payload
- `get_subscribe_payload_masked()` → 마스킹 버전 (display/log 용)

---

## 3. Pipe-delimited parser

KIS WebSocket은 pipe(`|`)로 구분된 형식으로 메시지를 전송할 수 있다:

```
0|H0STCNT0|005930|72000|100|093015
```

`_parse_pipe_delimited()` 함수가 이 형식을 dict로 변환한다.
TR_ID별 필드 매핑이 `_PIPE_TR_FIELDS`에 정의되어 있다.

| TR_ID | 필드 |
|-------|------|
| H0STCNT0 | tr_type, tr_id, MKSC_SHRN_ISCD, STCK_PRPR, CNTG_VOL, STCK_CNTG_HOUR, change_sign, change_price |
| H0STASP0 | tr_type, tr_id, MKSC_SHRN_ISCD, ASKP1~10, BIDP1~10 |
| H0STCNI0 | tr_type, tr_id, MKSC_SHRN_ISCD, ODNO, FTNG_ORD_PRC, FTNG_ORD_QTY |
| H0STMKO0 | tr_type, tr_id, MKSC_SHRN_ISCD, MKSC_STATUS, MKSC_SESSION |
| H0STANC0 | tr_type, tr_id, MKSC_SHRN_ISCD, STCK_ANT_CNTG_PRC, ANT_CNTG_QTY, ANT_CNTG_VS |

- JSON 형식이 우선 시도됨
- JSON 파싱 실패 시 pipe-delimited 시도
- 둘 다 실패 시 `parsed_ok=False`
- unknown TR_ID → `parsed_ok=False`

---

## 4. Smoke script 보강

### 신규 옵션
| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--duration` | 0 | 최대 수신 시간 (초, 0=무제한) |
| `--max-messages` | 0 | 최대 수신 메시지 수 (0=무제한) |
| `--real-ws` | false | GuardedRealWebSocketClient 사용 |

### 실행 예
```bash
# Stub 모드, 30초, 최대 10메시지
PYTHONPATH=./backend python backend/scripts/kis_ws_readonly_smoke.py --duration 30 --max-messages 10

# Real WS 모드 (connect는 NotImplementedError)
PYTHONPATH=./backend python backend/scripts/kis_ws_readonly_smoke.py --real-ws
```

---

## 5. 보안

- approval_key: 모든 출력에서 `****-****-****`로 마스킹
- raw 메시지: 전체 출력 금지, `raw_hash`만 저장
- app_key/app_secret: credentials 로드 시 자동 마스킹
- pipe-delimited 원문: dict로 변환만, 원문 저장 안 함
