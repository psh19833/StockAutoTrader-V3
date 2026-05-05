# SAT3 Audit Live Timeline (Repository/DB 연결)

## 1) 목표
운영 중 생성되는 `AuditEvent`를 Repository/DB(SQLite)에 저장하고,
Dashboard의 Timeline 목록 / Detail 조회가 **실제 저장소 기반**으로 동작하도록 연결한다.

- Dashboard는 **조회 전용(READ-ONLY)**
- 프론트는 평가항목(checklist)을 하드코딩하지 않고, 백엔드가 내려주는 schema/result를 렌더링만 한다.

## 2) 저장소 구조
### 2.1 SQLite 파일
- 기본 경로: `<project_root>/data/sat3_audit.db`
- 환경변수로 override 가능:
  - `SAT3_AUDIT_DB_PATH=/abs/path/to/sat3_audit.db`

### 2.2 테이블: `audit_events`
저장 정책(핵심):
- `payload`는 JSON 문자열로 저장하되, **저장 전 secret sanitization 적용**
- Dashboard detail 응답은 **payload_sanitized만 반환**

주요 컬럼(개요):
- `event_id` (TEXT): Dashboard detail lookup의 primary key 역할
- `event_time` (TEXT): ISO8601 timestamp
- `event_type` (TEXT)
- `severity` (TEXT)
- `source` (TEXT)
- `symbol` (TEXT)
- `strategy_name` (TEXT)
- `status` (TEXT)
- `summary` (TEXT)
- `correlation_id` (TEXT)
- `has_checklist` (INTEGER 0/1)
- `payload` (TEXT JSON)

## 3) event_id / correlation_id 정책
### 3.1 event_id
- **필수**: Dashboard Timeline 목록에 반드시 포함
- 저장 시 누락되면 Repository가 UUID 기반으로 자동 생성
  - (레거시 저장 호출 호환 목적)

### 3.2 correlation_id
- 같은 흐름(예: scan → quant → risk → safety_gate → order/fill)을 묶는 키
- Detail API는 동일 `correlation_id`를 가진 `related_events`를 함께 반환
- `related_events`는 과도한 응답 방지를 위해 limit을 적용한다(기본 200)

## 4) Checklist 저장/조회 정책
- Checklist는 AuditEvent payload 내부의 `payload.checklist`로 저장/조회한다.
- `schema_version`은 **그대로 보존**한다(현재 `1.0`).
- checklist item의 unknown 필드는 `meta`로 보존하며, UI는 이를 안전하게 표시한다.

## 5) Sanitized payload 정책 / 금지 항목
Dashboard는 아래 원칙을 반드시 지킨다:
1. raw REST response 전체 반환 금지
2. raw WebSocket 전문 전체 반환 금지
3. 아래 secret 원문 반환 금지
   - `appkey/appsecret/app_key/app_secret`
   - `access_token`
   - `approval_key`
   - `telegram_bot_token`

Detail 응답은 **payload_sanitized**만 반환하며,
저장소의 `payload`도 저장 단계에서 1차 sanitize를 수행한다.

## 6) API
### 6.1 Timeline 목록
- `GET /api/dashboard/audit?limit=50`
- 반환 필드:
  - `event_id`
  - `event_time`
  - `event_type`
  - `severity`
  - `source`
  - `symbol`
  - `strategy_name`
  - `status`
  - `summary`
  - `correlation_id`
  - `has_checklist`

### 6.2 Detail
- `GET /api/dashboard/audit/{event_id}`
- 저장소에서 `event_id`로 조회
- 반환:
  - `payload_sanitized`만 제공
  - `checklist`: `payload.checklist`가 있으면 그대로 반환
  - `related_events`: 동일 `correlation_id` 기반 (limit 적용)

## 7) 구현 포인트
- `backend/main.py`에서 SQLite 연결/초기화 후, DashboardService singleton에 repository 주입
- `DashboardService`는 repository가 있으면 timeline/detail/related_events를 repository 기반으로 조회
- InMemory fallback은 유지(저장소 초기화 실패 시에도 대시보드 시작 가능)
