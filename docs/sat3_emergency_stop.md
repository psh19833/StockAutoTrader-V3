# SAT3 Emergency Stop Procedures

> SAT3 비상정지 절차
> 마지막 수정: 2026-05-04
> 적용 대상: SAT3 실전 운용 중 발생하는 모든 비상 상황

---

## 1. 비상정지 정의

비상정지(Emergency Stop)는 SAT3의 모든 신규 주문 및 자동매매 활동을 즉시 중단하는 안전장치이다.
비상정지가 활성화되면 Risk Engine과 LiveOrderGate가 모든 주문을 차단한다.

### 비상정지 시 차단되는 것

- ✅ 신규 매수 주문
- ✅ 신규 매도 주문 (청산 포함)
- ✅ Scanner 실행 (선택적)
- ✅ Strategy Signal 생성 (선택적)

### 비상정지 시에도 유지되는 것

- ✅ Audit Log 기록
- ✅ Telegram 알림 (시스템 상태)
- ✅ KIS API 조회 (Read-Only)
- ✅ 포지션/잔고 모니터링

---

## 2. 비상정지 발동 조건

다음 상황이 발생하면 즉시 비상정지를 발동한다:

### 자동 발동 (시스템 감지)

| 조건 | 감지 주체 |
|------|----------|
| 일일 손실 한도 초과 | Risk Engine (`DAILY_LOSS_LIMIT_BLOCKED`) |
| 연속 손실 3회 이상 | Risk Engine (구현 예정) |
| KIS API 연속 5회 실패 | Session Guard |
| SESSION_STATE_UNKNOWN 진입 | Session Guard |
| Market Regime UNKNOWN 진입 | Market Regime Engine |
| Audit Writer 장애 | Audit Engine |

### 수동 발동 (운용자 판단)

| 상황 | 조치 |
|------|------|
| 시장 급락/급변동 | 즉시 비상정지 |
| 예상치 못한 대량 주문 | 즉시 비상정지 |
| KIS API 장애 지속 | 비상정지 + KIS 고객센터 확인 |
| 시스템 오작동 의심 | 즉시 비상정지 |
| 체결-주문 불일치 발견 | 즉시 비상정지 + 전수 조사 |
| Telegram 알림 두절 | 비상정지 + 통신 확인 |
| 계좌 잔고 불일치 | 즉시 비상정지 + KIS 확인 |

---

## 3. 비상정지 실행 방법

### 방법 1: 환경변수 설정 (권장)

```bash
# 시스템 환경변수 설정
export SAT3_EMERGENCY_STOP=true

# 또는 .env 파일 수정 (금지: Hermes Agent가 직접 수정하지 않음)
# SAT3_EMERGENCY_STOP=true
```

### 방법 2: Runtime Context 설정 (구현 예정)

```python
from safety import set_emergency_stop
set_emergency_stop(True)
```

### 방법 3: 서버 프로세스 강제 종료 (최후 수단)

```bash
# 백엔드 프로세스 종료
fuser -k 8000/tcp
# 또는
pkill -f uvicorn
```

---

## 4. 비상정지 확인 방법

```bash
# 1. Risk Engine 상태 확인
cd /home/psh19/StockAutoTrader-V3
PYTHONPATH=./backend .venv/bin/python -c "
from safety.preflight import run_preflight
result = run_preflight(False, True, True, True, True, True)
print(result.summary)
"

# 2. LiveOrderGate 확인
# - 모든 주문이 ORDER_REJECTED_BY_GATE로 반환되어야 함

# 3. Audit Log 확인
# - RISK_REJECTED 이벤트가 EMERGENCY_STOP_BLOCKED 사유로 기록되어야 함
```

---

## 5. 비상정지 해제 절차

### 5.1 해제 전 확인사항

- [ ] 비상정지 발동 원인 파악 완료
- [ ] 발동 원인 해결 완료
- [ ] KIS API 정상 응답 확인
- [ ] Session State REGULAR_MARKET 확인
- [ ] Market Regime BULL/NEUTRAL 확인
- [ ] 계좌 잔고 정상 확인
- [ ] 미체결 주문 없음 확인
- [ ] Telegram 알림 정상 수신 확인
- [ ] Audit Log 정상 기록 확인

### 5.2 해제 명령

```bash
# 환경변수 해제
unset SAT3_EMERGENCY_STOP

# Runtime Context 해제 (구현 예정)
# set_emergency_stop(False)
```

### 5.3 해제 후 모니터링

해제 후 최소 5분간 아래 항목을 집중 모니터링한다:

1. Scanner 정상 실행 여부
2. Strategy Signal 정상 생성 여부
3. Risk Decision 정상 승인 여부
4. 주문 정상 제출 여부 (LIVE_TRADING_ENABLED=false 시 제출 안 됨)
5. 체결 정상 확인 여부
6. Telegram 알림 정상 수신 여부
7. Audit Log 정상 기록 여부

---

## 6. 비상정지 시나리오별 대응

### 시나리오 1: 시장 급락

```
1. 즉시 비상정지 발동
2. 모든 보유 포지션 확인
3. 손실 규모 파악
4. KIS 수동 청산 여부 결정
5. 시장 안정화까지 대기
6. 해제 절차에 따라 재개
```

### 시나리오 2: KIS API 장애

```
1. 비상정지 발동
2. KIS API 상태 페이지 확인
3. 5분 간격으로 재시도
4. API 복구 확인
5. Session State / Market Regime 재평가
6. 해제 절차에 따라 재개
```

### 시나리오 3: 시스템 오작동

```
1. 즉시 서버 프로세스 종료
2. Audit Log 전수 조사
3. 오작동 원인 파악
4. 코드 수정 및 테스트
5. 재배포
6. 소액 테스트 주문 1회
7. 정상 확인 후 운용 재개
```

### 시나리오 4: 체결-주문 불일치

```
1. 즉시 비상정지
2. 모든 주문/체결 내역 KIS와 대사
3. 불일치 건수 파악
4. KIS 고객센터 보고 (1588-0037)
5. 불일치 원인 조사
6. 수동 청산 여부 결정
7. 원인 해결 및 재발방지 조치 후 재개
```

---

## 7. 비상 연락망

| 역할 | 연락처 | 비고 |
|------|--------|------|
| 시스템 개발자 | (설정) | 1차 기술 대응 |
| 시스템 운용자 | (설정) | 1차 운용 대응 |
| KIS 고객센터 | 1588-0037 | API 장애 문의 |
| KIS 영업점 | (설정) | 계좌 관련 문의 |

---

## 8. 비상정지 테스트

월 1회 이상 비상정지 발동/해제 훈련을 실시한다:

1. 비상정지 발동 테스트
2. 모든 주문 차단 확인
3. Audit Log EMERGENCY_STOP_BLOCKED 기록 확인
4. Telegram 비상 알림 수신 확인
5. 비상정지 해제 테스트
6. 정상 운용 복귀 확인

---

## 9. 관련 코드

| 모듈 | 파일 | 역할 |
|------|------|------|
| Risk Engine | `backend/risk/risk_engine.py` | `check_emergency_stop()` |
| LiveOrderGate | `backend/order/live_order_gate.py` | `emergency_stop` 필드 |
| RiskContext | `backend/risk/risk_context.py` | `emergency_stop` 필드 |
| Preflight | `backend/safety/preflight.py` | `EMERGENCY_STOP` 체크 |
| Config Validator | `backend/safety/config_validator.py` | 설정 검증 |
