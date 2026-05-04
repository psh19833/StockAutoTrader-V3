# SAT3 KIS Read-Only Smoke Test

> KIS 조회 전용 수동 검증 가이드
> 마지막 수정: 2026-05-04

---

## 1. 목적

SAT3의 KIS 조회 API가 정상 동작하는지 수동으로 확인하기 위한 절차입니다.
주문 API는 절대 호출하지 않습니다.

---

## 2. .env 작성 방법

```bash
# 1. 예제 파일을 복사
cp .env.example .env

# 2. .env 파일을 편집기에 열고 실제 값 입력
# ⚠️ KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO 값을 채팅/로그에 붙여넣지 마세요
```

---

## 3. Secret 노출 경고

- secret 값을 채팅창에 입력하지 마세요
- secret 값을 로그 파일에 기록하지 마세요
- .env 파일은 .gitignore로 보호됩니다
- smoke script는 masked_dict()만 출력합니다

---

## 4. 실행 명령

```bash
cd /home/psh19/StockAutoTrader-V3

# 기본 종목 (005930 삼성전자)
PYTHONPATH=./backend .venv/bin/python backend/scripts/kis_readonly_smoke.py

# 특정 종목
PYTHONPATH=./backend .venv/bin/python backend/scripts/kis_readonly_smoke.py --symbol 000660
```

---

## 5. 확인 항목

| 항목 | 정상 출력 예시 |
|------|--------------|
| LIVE_TRADING_ENABLED | false |
| Token 발급 | OK |
| 휴장일조회 | OK (N days) |
| 장운영정보 | OPEN / CLOSE |
| 현재가 | OK (75000 won) |
| 종목정보 | KOSPI/COMMON_STOCK |

---

## 6. 성공 기준

- 모든 조회 항목이 OK
- token 발급 성공
- 현재가 조회 성공 (DataUnavailable이 아닌 실제 값)
- 종목정보가 KOSPI/KOSDAQ + COMMON_STOCK

---

## 7. 실패 시 점검 항목

1. .env에 KIS_APP_KEY, KIS_APP_SECRET 값이 입력되었는지 확인
2. KIS API 키가 유효한지 KIS 개발자센터에서 확인
3. 네트워크 연결 확인
4. KIS API 서버 상태 확인
5. 종목코드가 올바른지 확인

---

## 8. 주문 Endpoint 미호출 원칙

이 smoke test는 다음 경로를 절대 호출하지 않습니다:
- /uapi/domestic-stock/v1/trading/order-cash
- /uapi/domestic-stock/v1/trading/order-credit
- /uapi/domestic-stock/v1/trading/order-rvsecncl

주문이 필요하면 SAT3-N7(실전 주문) 단계를 별도로 진행하세요.

---

## 9. LIVE_TRADING_ENABLED=false 유지 원칙

smoke test는 LIVE_TRADING_ENABLED=false일 때만 실행됩니다.
true로 변경된 경우 테스트가 중단됩니다.

---

## 10. 테스트 실행 방법 (실제 호출 없음)

```bash
cd /home/psh19/StockAutoTrader-V3
PYTHONPATH=./backend .venv/bin/python -m pytest backend/tests/test_smoke_manual.py -v
```
