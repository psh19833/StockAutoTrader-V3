# SAT3 KIS Data Connection Policy

> SAT3 KIS API 연결 정책 — REST + WebSocket 하이브리드
> 마지막 수정: 2026-05-05

---

## 1. 핵심 원칙

SAT3의 데이터 연결은 **REST API 우선**을 기본으로 하되,
REST로 제공되지 않거나 실시간성이 필요한 기능은 **KIS WebSocket**을 사용한다.

```
REST API → 스냅샷, 조회, 계좌, 잔고, 체결내역, 종목정보, 순위, 시세분석
WebSocket → 실시간 체결가, 호가, 체결통보, 장운영정보, 예상체결
```

---

## 2. REST API 담당 기능

| 기능 | Endpoint | TR_ID | 주기/방식 |
|------|----------|-------|----------|
| Token 발급 | POST /oauth2/tokenP | - | 1일 1회 + 갱신 |
| 현재가 시세 | GET /uapi/.../inquire-price | FHKST01010100 | 요청 시 |
| 호가/예상체결가 | GET /uapi/.../inquire-asking-price-exp-ccn | FHKST01010200 | 요청 시 |
| 기간별 시세(일봉) | GET /uapi/.../inquire-daily-itemchartprice | FHKST03010100 | EOD/필요 시 |
| 시간대별 체결가 | GET /uapi/.../inquire-time-ccnl | FHKST01010300 | 요청 시 |
| 주식 기본 조회 | GET /uapi/.../inquire-stock-basic-info | FHKST01010600 | 스캔 시 |
| 휴장일 조회 | GET /uapi/.../inquire-holiday | FHKST01010900 | 장 시작 전 |
| 잔고 조회 | GET /uapi/.../trading/inquire-balance | TTTC8434R | EOD/요청 시 |
| 체결내역 조회 | GET /uapi/.../trading/inquire-ccnl | TTTC8001R | EOD/확인 시 |
| 매수가능 조회 | GET /uapi/.../trading/inquire-psbl-order | TTTC8908R | 주문 전 |
| 실현손익 조회 | GET /uapi/.../trading/inquire-profit | TTTC8504R | EOD |
| 등락률 순위 | GET /uapi/.../ranking/fluctuation | FHPST01800000 | 스캔 보조 |
| 거래량 순위 | GET /uapi/.../inquire-volume-top | FHPST01710000 | 스캔 보조 |

---

## 3. WebSocket 담당 기능

| 기능 | WebSocket TR | 필요 이유 |
|------|-------------|----------|
| 실시간 체결가 | H0STCNT0 | 급등주 포착, 체결강도 실시간 계산 |
| 실시간 호가 | H0STASP0 | 스프레드, 매수/매도벽 실시간 감지 |
| 실시간 체결통보 | H0STCNI0 | 체결 확정 — REST 체결조회 대체/보완 |
| 실시간 장운영정보 | - | 장 상태 변화 즉시 감지 |
| 실시간 예상체결 | - | 동시호가 시간대 가격 발견 |

### 급등주 단타에서 WebSocket이 필요한 이유

- **REST 호가 조회는 시차 있음** — 1~3초 전 데이터일 수 있음
- **급등 포착은 초 단위** — REST polling으로는 초기 급등을 놓침
- **체결 확인** — WebSocket 체결통보가 REST 체결조회보다 수 초 빠름
- **스프레드/매도벽 감시** — 실시간 호가로 청산 타이밍 포착

---

## 4. 체결 확정 정책

```
주문 제출 ≠ 주문 성공 ≠ 체결 성공

체결 확정 방법 (우선순위):
1. WebSocket 실시간 체결통보 (H0STCNI0) — 가장 빠름
2. REST 체결내역 조회 (GET /uapi/.../trading/inquire-ccnl) — 확인/보완
3. REST 잔고 조회 (GET /uapi/.../trading/inquire-balance) — 최종 대사
```

절대 금지:
- 주문 제출 성공을 체결로 간주하지 않는다
- REST 응답 "체결" 상태를 실시간 체결로 가정하지 않는다
- WebSocket 연결 끊김 시 REST polling으로 대체 가능하나 명시적 경고 표시

---

## 5. Data Source Metadata

모든 데이터는 출처를 명시한다:

```python
source: Literal["KIS_API_REST", "KIS_API_WS"]
source_endpoints: tuple[str, ...]  # 호출한 endpoint/TR 목록
fetched_at: datetime               # 데이터 수신 시각 (UTC)
data_quality_warnings: tuple[str, ...] # 누락/지연/오류 경고
```

- REST 데이터: `source="KIS_API_REST"`
- WebSocket 데이터: `source="KIS_API_WS"`
- WebSocket 연결 끊김 후 REST 대체: `source="KIS_API_REST"` + warning
- API 실패: `DataUnavailable`, 추정값 생성 금지

---

## 6. WebSocket 연결/장애/재연결 정책

### 연결
- 장 시작 전(08:50) WebSocket 연결 수립
- 실시간 체결가, 호가, 체결통보 구독
- 연결 성공 시 `source_endpoints` 기록

### 장애 감지
- heartbeat/ping 미응답 5초 → 연결 끊김 감지
- 3회 연속 재연결 실패 → REST polling fallback
- 모든 데이터에 `data_quality_warnings=("ws_disconnected",)` 추가

### 재연결
- 1차: 즉시 재연결
- 2차: 3초 후 재연결
- 3차: 10초 후 재연결
- 3회 초과: REST fallback + Telegram 경고 + Dashboard Warning
- 장 종료 시 정상 종료

### Dashboard 표시
- WebSocket 상태: CONNECTED / DISCONNECTED / FALLBACK_REST
- 마지막 메시지 수신 시각
- 재연결 횟수
- 현재 데이터 소스 표시 (REST / WS)

---

## 7. 주문 구현 전 금지사항

| 항목 | 상태 |
|------|------|
| REST 주문 API 호출 | ❌ 금지 |
| WebSocket 주문 전송 | ❌ 금지 |
| LIVE_TRADING_ENABLED=true | ❌ 금지 |
| .env secret 원문 출력 | ❌ 금지 |
| WebSocket approval_key 원문 출력 | ❌ 금지 |
| 가짜 체결/호가 데이터 생성 | ❌ 금지 |
| WebSocket 실패 시 추정값 대체 | ❌ 금지 |

---

## 8. WebSocket 개발 Phase (N8)

다음 Phase에서 구현할 WebSocket Foundation:

1. `backend/kis/ws_client.py` — WebSocket 연결 관리
2. `backend/kis/ws_handlers.py` — 메시지 파싱 (체결가, 호가, 체결통보)
3. `backend/kis/ws_data_models.py` — WebSocket 데이터 모델
4. `backend/kis/ws_reconnect.py` — 재연결 정책
5. 기존 Scanner/Quant와 WebSocket 데이터 연동 adapter
6. Dashboard WebSocket 상태 표시

---

## 9. REST API 우선 원칙 요약

1. REST로 가능한 모든 기능은 REST를 우선 사용한다
2. 실시간성이 필요한 기능만 WebSocket을 사용한다
3. WebSocket 장애 시 REST로 fallback 가능
4. 데이터 출처(source)를 항상 명시한다
5. 어떤 연결 방식이든 실패 시 추정값 생성 금지
