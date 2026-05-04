# SAT3 개발계획서

> 목적: 이 문서는 Hermes Agent에게 한 번에 하나씩 전달하여 SAT 3.0을 안정적으로 개발하기 위한 단계별 작업 지시서다.  
> 원칙: 실전 자동매매 전용, 한국투자증권 Open API 단일 출처, 정량평가 중심, 로그 기반 운용 증거화, 작은 단위 개발.

---

# 02. Phase 1 - KIS API Gateway + Source Policy

## 1. Phase 목적

이 Phase의 목표는 SAT3의 모든 외부 데이터 진입점을 **한국투자증권 Open API Gateway**로 통일하는 것이다.

```text
목표:
- KIS API 호출을 한 계층으로 집중
- API 응답에 source metadata 부여
- KIS 외부 데이터 사용을 방지하는 Source Policy 설계
- API 실패 시 추정값 생성 금지
- secret/token/account 정보 로그 노출 방지
```

주의: 이 Phase에서는 실제 주문 기능을 구현하지 않는다.  
주문 endpoint wrapper는 스키마/인터페이스 수준까지 가능하지만, 실제 주문 실행 연결은 이후 Phase에서 진행한다.

## 2. 작업 범위

허용 파일 범위 예시:

```text
backend/kis/
backend/tests/test_kis_*.py
docs/sat3_kis_api_source_policy.md
```

생성 권장 구조:

```text
backend/kis/
├─ __init__.py
├─ client.py
├─ auth.py
├─ endpoints.py
├─ rate_limit.py
├─ errors.py
├─ schemas.py
├─ raw_logger.py
└─ source_policy.py
```

## 3. 금지 사항

```text
금지:
- 실제 주문 전송 구현
- 전략 로직 수정
- 스캐너 로직 수정
- 리스크 엔진 수정
- .env 수정
- 서버 실행
- 자동매매 실행
- KIS 외부 API 추가
- 크롤링 추가
- 모의투자 broker 추가
- fake response를 운영 코드 fallback으로 사용
```

테스트 fixture는 허용한다.  
단, 운영 코드에서 fixture를 fallback data로 사용하면 안 된다.

## 4. 핵심 설계

### 4.1 KIS API Client

`backend/kis/client.py`는 모든 KIS REST 호출의 단일 진입점이다.

필수 기능:

```text
- base_url 관리
- headers 생성
- access token 주입
- TR ID 주입
- request_id 생성
- timeout 설정
- retry policy 적용
- latency 측정
- response parsing
- KIS error code mapping
- raw_response_hash 생성
- sanitized log 전달
```

### 4.2 Source Policy

모든 API 응답에서 생성된 데이터는 source metadata를 가져야 한다.

예시 모델:

```python
@dataclass(frozen=True)
class KisSourceMeta:
    source: Literal["KIS_API"]
    endpoint: str
    tr_id: str | None
    fetched_at: datetime
    raw_response_hash: str
    request_id: str
    is_stale: bool = False
    missing_fields: tuple[str, ...] = ()
```

### 4.3 DataUnavailable

API 실패나 필수 필드 누락 시 추정값을 만들지 않는다.

```python
@dataclass(frozen=True)
class DataUnavailable:
    reason_code: str
    reason_text: str
    endpoint: str
    fetched_at: datetime
    request_id: str | None = None
```

규칙:

```text
API 실패 → DataUnavailable
필수 필드 누락 → DataUnavailable
stale data → 평가 불가 또는 Risk Engine 거절
임의 기본값 대체 금지
```

## 5. Endpoint 분류 문서화

`backend/kis/endpoints.py` 또는 문서에 KIS API 영역을 분류한다.

```text
인증:
- OAuth token
- approval key / websocket key

국내주식 주문/계좌:
- 주문
- 정정취소
- 주문체결조회
- 잔고조회
- 매수가능조회
- 실현손익
- 기간별 손익

국내주식 기본시세:
- 현재가
- 호가/예상체결
- 기간별시세
- 당일분봉
- 일별분봉
- 시간대별체결

국내주식 업종/기타:
- 업종 현재지수
- 업종 일자별지수
- 업종 시간별지수
- 국내휴장일조회
- 변동성완화장치 현황

국내주식 종목정보:
- 상품기본조회
- 주식기본조회
- 재무비율
- 수익성비율
- 안정성비율
- 성장성비율

시세분석/순위분석:
- 거래량순위
- 등락률순위
- 체결강도상위
- 호가잔량순위
- 신고/신저근접
- 투자자매매동향
- 공매도/신용잔고

실시간시세:
- 실시간체결가
- 실시간호가
- 실시간체결통보
- 장운영정보
```

## 6. Secret Sanitizer

로그에 다음 값이 절대 노출되면 안 된다.

```text
- app key
- app secret
- access token
- refresh token
- approval key
- 계좌번호 전체
- 텔레그램 bot token
- 텔레그램 chat_id 전체
- API header 원문
- .env 전체 내용
```

`log_sanitizer`가 아직 없다면 Phase 1에서는 최소한 `backend/kis/raw_logger.py` 안에서 마스킹 함수를 분리한다.  
전용 Logging Engine은 Phase 3에서 확장한다.

마스킹 예시:

```text
12345678-01 → 1234****-**
abcdef1234567890 → abcd********7890
```

## 7. 테스트 요구사항

테스트 파일 예시:

```text
backend/tests/test_kis_source_policy.py
backend/tests/test_kis_client_sanitizer.py
backend/tests/test_kis_data_unavailable.py
```

필수 테스트:

```text
1. KisSourceMeta 생성 시 source가 KIS_API로 고정되는지
2. API 실패 시 DataUnavailable을 반환하는지
3. 필수 필드 누락 시 추정값을 만들지 않는지
4. raw_response_hash가 생성되는지
5. secret/token/account 값이 로그 문자열에 노출되지 않는지
6. KIS 외부 source가 들어오면 거부되는지
7. stale data를 표시할 수 있는지
```

## 8. 문서 산출물

```text
docs/sat3_kis_api_source_policy.md
```

문서 포함 내용:

```text
- KIS API 단일 출처 원칙
- 금지 데이터 출처
- DataUnavailable 처리 정책
- Source Metadata 구조
- Secret Masking 정책
- Endpoint 영역 분류
- 이후 Phase와의 연결 방식
```

## 9. 검증 명령

```bash
pytest backend/tests/test_kis_source_policy.py backend/tests/test_kis_client_sanitizer.py backend/tests/test_kis_data_unavailable.py
git diff -- backend/kis backend/tests docs/sat3_kis_api_source_policy.md
git status --short
```

## 10. Hermes 보고 형식

```text
Phase 1 완료 보고

1. 생성/수정 파일:
2. KIS API Gateway 구조:
3. Source Policy 구조:
4. DataUnavailable 처리 방식:
5. Secret Masking 테스트 결과:
6. KIS 외부 데이터 차단 방식:
7. 테스트 결과:
8. 금지 영역 변경 여부:
9. git diff 요약:
10. git status:
11. 커밋 여부: 미수행
```
