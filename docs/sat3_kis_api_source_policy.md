# SAT3 Phase 1 — KIS API Gateway: Source Policy & Module Reference

> Document version: 1.0  
> Last updated: 2025-05-04  
> Scope: Phase 1 — KIS API Gateway

---

## 1. Phase 1 목표 요약

### 1.1 KIS API Gateway

SAT3의 모든 데이터는 한국투자증권(KIS) Open API를 통해서만 수급된다.  
Phase 1에서는 이 원칙을 강제하는 **Gateway 계층**의 기초 인프라를 구축했다.

**핵심 원칙:**
- **KIS_API 단일 출처**: 모든 데이터는 `source="KIS_API"` 메타데이터를 가져야 한다.
- **외부 데이터 출처 금지**: 크롤링, CSV 파일, 추정값, 제3자 API 등 KIS 외부 데이터는 일체 허용하지 않는다.
- **DataUnavailable 원칙**: API 조회 실패 시 추정값을 생성하거나 기본값으로 대체하지 않는다.  
  명시적으로 `DataUnavailable` 객체를 반환하거나 예외를 발생시켜야 한다.

### 1.2 아키텍처 개요

```
┌─────────────────────────────────────────┐
│            SAT3 Application              │
│  (Strategy, Scanner, Session, Engine)    │
├─────────────────────────────────────────┤
│            KisClient                     │  ← 단일 진입점
├─────────────────────────────────────────┤
│  AuthManager  │  RateLimiter  │  Policy  │
├─────────────────────────────────────────┤
│  Endpoints  │  Errors  │  Schemas       │
├─────────────────────────────────────────┤
│         KIS Open API (HTTP/WebSocket)     │
└─────────────────────────────────────────┘
```

---

## 2. 구현된 모듈 설명

### 2.1 `backend/kis/schemas.py` — 데이터 스키마

**역할:** KIS 데이터 출처 메타데이터와 실패 신호 정의

| 클래스 | 설명 |
|---|---|
| `KisSourceMeta` | 모든 KIS API 응답에 첨부되는 출처 메타데이터 (source, endpoint, fetched_at, raw_response_hash, is_stale, missing_fields, tr_id, request_id) |
| `DataUnavailable` | API 실패 시 사용하는 데이터 불가 신호. 추정값 대체 금지를 강제하기 위한 타입 |

**주요 정책:**
- `source`는 항상 `"KIS_API"`로 고정
- `is_stale=True`로 설정 가능 (상위 레이어에서 stale 데이터 식별)
- `missing_fields`로 특정 필드 누락 기록

### 2.2 `backend/kis/errors.py` — KIS 에러 분류

**역할:** KIS API 응답의 오류 코드를 분류하고 전용 예외 클래스 매핑

| 클래스 | 설명 |
|---|---|
| `KisApiError` | 모든 KIS API 오류의 기본 예외 |
| `KisAuthError` | 인증 실패 (에러 코드 401XX 계열) |
| `KisRateLimitError` | 호출 제한 위반 (에러 코드 429XX 계열) |
| `KisServerError` | 서버 오류 (에러 코드 500XX 계열) |
| `KisInvalidParamError` | 잘못된 파라미터 (에러 코드 403XX, 404XX 계열) |
| `classify_kis_error()` | 에러 코드 문자열을 받아 적절한 예외 클래스 반환 |

**에러 코드 맵:** 15개 이상의 실제 KIS 에러 코드 매핑 (OAuth, Rate Limit, 시스템, 파라미터)

### 2.3 `backend/kis/rate_limit.py` — Rate Limit 관리

**역할:** KIS API 호출 속도 제한 (Sliding Window 방식)

| 클래스 | 설명 |
|---|---|
| `KisRateLimiter` | 초당/일일 호출 제한 관리자. `collections.deque` 기반 Sliding Window |
| `RateLimitState` | 현재 호출 상태 정보 (total, remaining) |
| `RateLimitExceeded` | 제한 초과 시 예외 |

**동작:**
- 초당 20회 (KIS 기본 제한)
- 일일 10,000회 추정
- `acquire()` 호출 시 window 내 허용 범위 확인 후 카운트
- 초과 시 `RateLimitExceeded` 예외 발생

### 2.4 `backend/kis/raw_logger.py` — Secret 마스킹 로거

**역할:** 민감 정보가 로그에 노출되는 것을 방지하는 안전한 로깅 계층

**마스킹 대상:**
| 항목 | 예시 출력 |
|---|---|
| AppKey | `abc***xyz` (처음 3자 + `***` + 마지막 3자) |
| AppSecret | `abc***xyz` (처음 3자 + `***` + 마지막 3자) |
| Access Token | `eyJ***abc` (처음 3자 + `***` + 마지막 3자) |
| Refresh Token | 동일 규칙 |
| Approval Key | 동일 규칙 |
| 계좌번호 | `000***01` (처음 3자 + `***` + 마지막 2자) |
| Telegram Bot Token | `123***456` (`:` 기준 앞/뒤 일부만 남김) |
| Telegram Chat ID | `-100***789` (처음 4자 + `***` + 마지막 3자) |

**기능:**
- `KisSafeLogger`: 표준 Python 로거 포맷, 메시지 필터링 자동 적용
- HTTP 헤더 sanitize 함수 제공 (authorization, appkey, appsecret 필드 마스킹)

### 2.5 `backend/kis/endpoints.py` — KIS API Endpoint Catalog

**역할:** 모든 KIS API 엔드포인트를 한 곳에서 정의하고 관리

**8개 카테고리:**
| 카테고리 | 설명 | 예시 endpoint |
|---|---|---|
| `OAUTH` | OAuth 인증 | `oauth_token` (POST) |
| `DOMESTIC_ORDER` | 국내주식 주문/계좌 | `inquire_balance`, `order_buy`, `order_sell` |
| `DOMESTIC_QUOTE` | 국내주식 기본시세 | `inquire_price`, `inquire_ccnl` |
| `DOMESTIC_SECTOR` | 국내주식 업종/기타 | `inquire_sector_index` |
| `DOMESTIC_ITEM` | 국내주식 종목정보 | `inquire_item_info` |
| `DOMESTIC_ANALYSIS` | 국내주식 시세분석 | `inquire_investor`, `inquire_elw` |
| `DOMESTIC_RANK` | 국내주식 순위분석 | `inquire_volume_rank` |
| `DOMESTIC_REALTIME` | 국내주식 실시간시세 | `realtime_websocket` |

**Endpoint 메타데이터 구조:**
| 필드 | 설명 |
|---|---|
| `name` | 고유 식별자 |
| `category` | 위 8개 카테고리 중 하나 |
| `path` | API 경로 |
| `method` | HTTP 메서드 |
| `tr_id` | KIS TR ID (또는 None) |
| `requires_auth` | 인증 필요 여부 |
| `is_order_endpoint` | 주문 관련 endpoint 여부 |
| `data_source` | 항상 `"KIS_API"` |
| `description` | 한글 설명 |

**Resolver 함수:**
- `get_endpoint(name)`: 이름으로 endpoint 조회 (없으면 `EndpointNotFoundError`)
- `list_endpoints_by_category(category)`: 카테고리별 endpoint 목록
- `is_order_endpoint(name)`: 주문 endpoint 확인

**Phase 1 제한:**
- 주문 endpoint(`order_buy`, `order_sell`)는 **식별만 가능**하며 실제 실행 로직은 포함하지 않음
- 실제 API 호출 로직은 Phase 3+에서 구현

### 2.6 `backend/kis/auth.py` — OAuth 인증 관리

**역할:** KIS API Access Token의 생명주기 관리

| 클래스 | 설명 |
|---|---|
| `KisToken` | Access Token 데이터 클래스 (access_token, token_type, expires_in, issued_at, expires_at, is_expired) |
| `KisAuthManager` | 토큰 생명주기 관리자 |
| `TokenState` | 토큰 상태 (NONE / VALID / EXPIRED / REFRESHING) |
| `AuthConfig` | 인증 설정 (refresh margin 등) |

**토큰 생명주기:**
1. 초기 상태: `NONE`
2. `refresh_token()` → `VALID` (refresh callback 실행)
3. 시간 경과 → `EXPIRED`
4. 만료 임박(margin 이내) → `needs_refresh()` = `True`

**주요 기능:**
- `set_refresh_callback()`: 실제 OAuth 호출을 수행하는 콜백 등록 (Phase 2+에서 구현)
- `require_valid_token()`: 유효한 토큰 요구 (없으면 `InvalidTokenError`, 만료면 `TokenExpiredError`)
- `get_authorization_header()`: `authorization: Bearer <token>` + appkey/appsecret 헤더 반환

### 2.7 `backend/kis/client.py` — KIS API Client 단일 진입점

**역할:** 모든 KIS REST API 호출의 단일 진입점

**구성:**
- `base_url`: 실전 서버 URL 고정 (`https://openapi.koreainvestment.com:9443`, 모의투자 URL 없음)
- `_build_url(path)`: 전체 URL 생성
- `_prepare_headers(tr_id, requires_auth)`: HTTP 헤더 준비
- `get_endpoint_info(name)`: Endpoint Catalog 조회
- `is_order_endpoint(name)`: 주문 endpoint 확인
- `data_unavailable()`: 실패 시 DataUnavailable 생성

**Phase 1 구현 범위:**
- 구조, 헤더/URL 준비, 정책 연결까지만 구현
- 실제 HTTP 호출(`requests` / `httpx` 사용)은 이후 Phase에서 구현
- Client는 Rate Limiter, Auth Manager, Source Policy를 내부에 통합

### 2.8 `backend/kis/source_policy.py` — 출처 검증 정책

**역할:** 모든 데이터가 KIS_API 출처 정책을 준수하는지 검증

| 클래스/함수 | 설명 |
|---|---|
| `SourcePolicy` | Source Metadata 검증기 |
| `validate_source()` | 편의 검증 함수 |
| `build_source_meta()` | API 응답으로부터 KisSourceMeta 생성 |

**검증 규칙:**

| 조건 | 결과 |
|---|---|
| `meta is None` | → `MissingKisSourceError` |
| `meta.source != "KIS_API"` | → `MissingKisSourceError` |
| `meta.is_stale == True` | → `StaleDataError` |
| 실제 경과 시간 > max_stale | → `StaleDataError` |
| `meta.missing_fields` 비어있지 않음 | → `MissingFieldError` |
| `meta`가 `DataUnavailable` | → `MissingKisSourceError` |
| 모두 통과 | → `True` |

**build_source_meta 동작:**
- 원본 응답 문자열로 SHA256 해시 생성 (`raw_response_hash`)
- `expected_fields` 목록과 비교하여 누락된 필드 자동 감지
- `request_id` 미지정 시 endpoint + 타임스탬프 기반 자동 생성

---

## 3. Endpoint Catalog 정책

### 3.1 정의 위치 고정

모든 endpoint는 `backend/kis/endpoints.py`의 `ENDPOINT_CATALOG` 딕셔너리에 등록된다.  
프로젝트 내 어디에서도 하드코딩된 URL 문자열을 사용하지 않는다.

### 3.2 Order Endpoint 식별

주문 관련 endpoint는 `is_order_endpoint=True`로 표시된다.  
Phase 1에서는 이 플래그로 식별만 가능하며, 실제 주문 실행은 구현되지 않는다.

### 3.3 Endpoint 추가 절차

새로운 endpoint가 필요할 경우:
1. `_ENDPOINT_DEFS`에 8개 항목 tuple 추가
2. `ENDPOINT_CATALOG`에 자동 등록
3. `test_kis_endpoints.py`에서 최소 1개 테스트 추가

---

## 4. Source Policy 원칙

모든 데이터는 **반드시** `KisSourceMeta`를 동반해야 한다.

```
KisSourceMeta(
    source="KIS_API",          # 출처 (고정)
    endpoint="/uapi/...",      # 호출한 endpoint 경로
    fetched_at=...,            # 호출 시각 (UTC)
    raw_response_hash="...",   # 원본 응답 SHA256 해시
    request_id="...",          # 요청 식별자
    tr_id="FHKST...",          # KIS TR ID (선택)
    is_stale=False,            # stale 플래그
    missing_fields=(),         # 누락된 필드 목록
)
```

**강제 사항:**
- source가 "KIS_API"가 아니면 `MissingKisSourceError`
- endpoint 기록은 필수 (어느 API에서 왔는지 추적)
- fetched_at으로 데이터 신선도 검증
- raw_response_hash로 응답 무결성 검증
- stale data는 `StaleDataError`로 거부
- KIS 외부 데이터(`source != "KIS_API"`)는 일체 거부

---

## 5. API 실패 처리 정책

### 5.1 추정값 생성 금지

**절대 하지 않는 것:**
- API 조회 실패 시 "어제와 동일한 가격" 같은 추정 사용
- 기본값(`0`, `-1`, `{}`)으로 대체
- "시장이 열리지 않았으므로 0으로 처리" 같은 가정
- 과거 데이터로 현재 데이터 추정

### 5.2 허용되는 처리

| 상황 | 처리 |
|---|---|
| API 호출 실패 | `DataUnavailable(reason_code, reason_text)` 반환 |
| 잘못된 파라미터 | `KisInvalidParamError` 예외 |
| Rate Limit 초과 | `RateLimitExceeded` 예외 (호출 재시도 전 지연) |
| 만료된 데이터 | `StaleDataError` 예외 |
| 인증 실패 | `KisAuthError` 예외 (refresh 후 재시도) |

### 5.3 실패 사유 기록

`DataUnavailable`에는 반드시 다음 필드가 포함된다:
- `reason_code`: 오류 코드 (KIS 에러 코드 또는 내부 코드)
- `reason_text`: 사람이 읽을 수 있는 설명
- `endpoint`: 실패가 발생한 API 엔드포인트
- `fetched_at`: 실패 시각

---

## 6. Secret / 민감정보 보호 정책

### 6.1 보호 대상

| 항목 | 보호 수준 |
|---|---|
| KIS AppKey | 로그/출력에서 마스킹 필수 |
| KIS AppSecret | 로그/출력에서 마스킹 필수 |
| KIS Access Token | 로그/출력에서 마스킹 필수 |
| KIS Refresh Token | 로그/출력에서 마스킹 필수 |
| Approval Key | 로그/출력에서 마스킹 필수 |
| 계좌번호 | 전체 노출 금지 |
| Telegram Bot Token | 로그/출력에서 마스킹 필수 |
| Telegram Chat ID | 로그/출력에서 마스킹 필수 |

### 6.2 Raw Logger 마스킹 정책

`backend/kis/raw_logger.py`의 `KisSafeLogger`는 모든 로그 메시지를 자동 필터링한다.

**마스킹 규칙 (처음 N자 + `***` + 마지막 M자):**

| 대상 | 앞 | 가림 | 뒤 |
|---|---|---|---|
| AppKey | 3자 | `***` | 3자 |
| AppSecret | 3자 | `***` | 3자 |
| Access Token | 3자 | `***` | 3자 |
| 계좌번호 | 3자 | `***` | 2자 |
| Telegram Bot Token | 3자 | `***` | 3자 |
| Telegram Chat ID | 4자 | `***` | 3자 |

### 6.3 HTTP 헤더 마스킹

`sanitize_headers()` 함수는 HTTP 요청/응답 헤더에서 다음 필드를 마스킹한다:
- `authorization`
- `appkey` (대소문자 무관)
- `appsecret` (대소문자 무관)

### 6.4 저장 정책

- 모든 Secret 값은 `.env` 파일에서만 관리
- `.gitignore`에 `.env` 등록
- 테스트 코드에는 더미 패턴(`_SAMPLE_*`)만 사용
- 문서에 실제 값 절대 기재 금지

---

## 7. Rate Limit / Auth / Client 동작 개요

### 7.1 Rate Limiter

**목적:** KIS API의 초당 호출 제한(20회/s)을 위반하지 않도록 보장

**동작:**
1. `rate_limiter.acquire()` 호출 시 Sliding Window 확인
2. 현재 Window 내 허용 회수 이내면 카운트 증가 후 통과
3. 초과 시 `RateLimitExceeded` 예외 발생
4. `state()`로 현재 호출 현황 조회

**Phase 1 구현:** 메모리 내 Sliding Window  
**향후:** 분산 환경 대비 Redis 기반 확장 가능

### 7.2 Token Lifecycle

```
[초기] NONE
  │
  ├── refresh_token() → 콜백 실행 → 새 KisToken → VALID
  │
  ├── 시간 경과 or 만료 임박(margin 이내) → needs_refresh() = True
  │     └── refresh_token() → 자동 갱신
  │
  ├── 만료 → EXPIRED
  │     └── require_valid_token() → TokenExpiredError
  │
  └── clear_token() → NONE
```

**Phase 1 구현:** 토큰 상태 관리 및 refresh 콜백 인터페이스  
**Phase 2+ 구현:** 실제 OAuth Token 발급(POST `/oauth2/tokenP`) 콜백

### 7.3 Auth Header 준비

`KisAuthManager.get_authorization_header()`가 반환하는 헤더:
```
authorization: Bearer <access_token>
appkey: <app_key>
appsecret: <app_secret>
```

- `requires_auth=True`일 때만 포함
- 인증 불필요 endpoint(OAuth 등)는 auth header 없이 호출

### 7.4 Client — 단일 진입점

`KisClient`는 SAT3의 모든 KIS REST API 호출의 단일 창구다.

**Phase 1 제공:**
- `_build_url(path)` → 전체 URL
- `_prepare_headers(tr_id, requires_auth)` → HTTP 헤더
- `get_endpoint_info(name)` → Endpoint 정보
- `is_order_endpoint(name)` → 주문 endpoint 확인
- `data_unavailable(...)` → DataUnavailable 생성

**Phase 3+ 제공 예정:**
- `request(endpoint_name, params)` → 실제 HTTP 호출
- `_handle_response(response)` → SourceMeta 자동 생성
- `_handle_error(error)` → KisApiError 매핑
- Rate Limiter → Auth → Request → Source Policy 검증 파이프라인

---

## 8. 테스트 요약

### 8.1 모듈별 테스트 현황 (총 128개, GREEN ✅)

| 모듈 | 테스트 파일 | 테스트 수 | 통과 |
|---|---|---|---|
| `schemas.py` | `test_kis_schemas.py` | 11 | ✅ |
| `errors.py` | `test_kis_errors.py` | 17 | ✅ |
| `rate_limit.py` | `test_kis_rate_limit.py` | 11 | ✅ |
| `raw_logger.py` | `test_kis_raw_logger.py` | 21 | ✅ |
| `endpoints.py` | `test_kis_endpoints.py` | 25 | ✅ |
| `auth.py` | `test_kis_auth.py` | 22 | ✅ |
| `source_policy.py` | `test_kis_client_source_policy.py` | 10 | ✅ |
| `client.py` | `test_kis_client_source_policy.py` | 11 | ✅ |
| **전체** | **7개 파일** | **128** | **✅ ALL GREEN** |

### 8.2 TDD 사이클 준수

모든 모듈은 RED(테스트 먼저 작성) → GREEN(구현) → REFACTOR 순서로 개발되었다.  
기존 테스트는 수정 없이 유지되었으며, 신규 추가로 인한 회귀는 0건이다.

---

## 9. 다음 Phase 연결점

### 9.1 Phase 2 — Trading Session Engine

Phase 2에서는 KIS Gateway를 통해 **실제 장 운영 시간**을 조회하고 관리한다.

**연결 사항:**
- KIS `국내휴장일조회` endpoint는 Gateway의 `endpoints.py`를 통해 접근
- KIS `장운영정보` endpoint는 동일
- Session Engine은 `KisClient`를 DI(의존성 주입)로 받아 사용
- 로컬 시스템 시간만으로 휴장일/장시간을 판단하지 않음
- 모든 장 정보는 KIS API를 통해 실시간 조회

### 9.2 사용해야 할 Endpoint (Phase 2+)

| 기능 | endpoint name | 비고 |
|---|---|---|
| 국내휴장일조회 | `inquire_holiday_kr` | Endpoint Catalog에 추가 필요 |
| 장운영정보조회 | `inquire_market_time` | Endpoint Catalog에 추가 필요 |

### 9.3 금지 사항 (Phase 2)

- **로컬 시간 기반 휴장일 판단 금지** — 반드시 KIS API 조회
- **하드코딩된 휴장일 리스트 금지**
- **추정 휴장일/장시간 사용 금지**
- Session Engine에서도 Gateway의 Source Policy가 적용됨 — 모든 데이터는 `KisSourceMeta` 필요