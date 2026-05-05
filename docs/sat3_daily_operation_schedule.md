# SAT3 개장일 운영 스케줄 및 절차

> 마지막 수정: 2026-05-05
> 상태: N18 완료, 운영 대기

---

## 1. 내일 장 개장 전 1회성 최종 점검

### 1-1. Git / 코드 상태 확인

```bash
cd /home/psh19/StockAutoTrader-V3
git status --short
git log --oneline -10
PYTHONPATH=./backend .venv/bin/python -m pytest backend/tests -q
```

확인 기준:
- [ ] git status clean (Zone.Identifier 외)
- [ ] 최신 커밋 반영 확인
- [ ] 전체 테스트 GREEN
- [ ] .env 미포함
- [ ] LIVE_TRADING_ENABLED=false 기본값
- [ ] SafetyGate 기본 BLOCKED

### 1-2. .env 최종 확인

```bash
PYTHONPATH=./backend .venv/bin/python -c "
import os
from dotenv import load_dotenv; load_dotenv('.env')
keys = ['KIS_APP_KEY','KIS_APP_SECRET','KIS_ACCOUNT_NO','KIS_ACCOUNT_PRODUCT_CODE',
        'KIS_BASE_URL','KIS_WEBSOCKET_URL','LIVE_TRADING_ENABLED',
        'TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID','SAT3_DB_PATH']
for k in keys:
    v = os.getenv(k,'')
    print(f'  {\"✓\" if v else \"✗\"} {k}: {\"SET\" if v else \"MISSING\"}')
"
```

필수 key:
- [ ] KIS_APP_KEY
- [ ] KIS_APP_SECRET
- [ ] KIS_ACCOUNT_NO
- [ ] KIS_ACCOUNT_PRODUCT_CODE
- [ ] KIS_BASE_URL=https://openapi.koreainvestment.com:9443
- [ ] KIS_WEBSOCKET_URL
- [ ] LIVE_TRADING_ENABLED=false
- [ ] TELEGRAM_BOT_TOKEN (새로 발급된 토큰)
- [ ] TELEGRAM_CHAT_ID
- [ ] SAT3_DB_PATH

### 1-3. KIS 개발자센터 설정 확인

https://apiportal.koreainvestment.com 접속 → 내 앱

- [ ] 실전투자용 appkey/appsecret
- [ ] 실전 base URL
- [ ] IP 화이트리스트에 현재 IP 등록
- [ ] 국내주식 기본시세 권한
- [ ] 국내주식 주문/계좌 권한
- [ ] WebSocket 사용 가능
- [ ] 계좌 연결 (44413716-01)

### 1-4. Telegram 테스트

```bash
curl -X POST http://127.0.0.1:8000/api/telegram/test \
  -H "Content-Type: application/json" \
  -d '{"confirm":"SEND_TEST_TELEGRAM"}'
```

- [ ] 텔레그램 메시지 수신
- [ ] confirm 없으면 발송 안 됨

### 1-5. Dashboard 실행 확인

```bash
cd frontend && npm run build && npm run dev
# http://localhost:5173 접속
```

확인 카드:
- [ ] 시스템 상태
- [ ] 장 세션
- [ ] 시장 국면
- [ ] 실시간 시세 (WS)
- [ ] 데이터 라우터
- [ ] 텔레그램
- [ ] 계좌 정보
- [ ] 일일 매매 요약
- [ ] 전략별 성과
- [ ] 스캐너 후보
- [ ] 퀀트 평가
- [ ] 리스크 판정
- [ ] 운영 로그

금지 확인:
- [ ] 주문 실행 버튼 없음
- [ ] LIVE 토글 없음
- [ ] appkey/appsecret/token 표시 없음

### 1-6. Preflight

```bash
PYTHONPATH=./backend .venv/bin/python backend/scripts/sat3_preflight_check.py
```

- [ ] PASS 또는 WARN (FAIL 없음)
- [ ] secret 출력 없음

---

## 2. 매일 계속 수행할 운영 항목

### 2-1. 장 시작 전 (매일)

- [ ] Preflight 체크
- [ ] REST read-only 사전점검
- [ ] WebSocket 사전점검
- [ ] Dashboard 상태 확인
- [ ] Telegram 연결 확인
- [ ] Emergency Stop inactive 확인
- [ ] LIVE_TRADING_ENABLED=false 상태로 시작

### 2-2. 장중 감시 (매일)

- [ ] WebSocket 연결 상태
- [ ] REST 데이터 freshness (60초 이내)
- [ ] Scanner 후보 종목
- [ ] Quant 점수 분포
- [ ] RiskDecision 거절 사유
- [ ] SafetyGate 차단 사유
- [ ] 주문접수 / 체결확인 분리 확인
- [ ] 손절 / 익절 이벤트
- [ ] Telegram 알림 수신
- [ ] 운영 로그

### 2-3. 장마감 후 (매일)

- [ ] EOD 리포트 생성
- [ ] 일일 승률 확인
- [ ] 실현손익 확인
- [ ] 미실현손익 확인
- [ ] Profit Factor
- [ ] 전략별 성과
- [ ] 오류 로그 확인
- [ ] 내일 수정 필요 사항 기록

### 2-4. 주기적 수행 (주 1회)

- [ ] 전략별 성과 분석
- [ ] Scanner Type별 성과 분석
- [ ] Market Regime별 성과 분석
- [ ] 손절/익절 사유 분석
- [ ] Risk 거절 사유 분석
- [ ] 슬리피지 분석
- [ ] 로그 백업
- [ ] DB 백업

---

## 3. 장 시간대별 SAT3 운영 스케줄

### 08:30 — Preflight

```bash
PYTHONPATH=./backend .venv/bin/python backend/scripts/sat3_preflight_check.py
```

통과 조건:
- .env 존재, 필수 key 존재
- LIVE_TRADING_ENABLED=false
- SafetyGate BLOCKED
- Emergency Stop false
- secret 출력 없음

❌ 실패 → 자동매매 금지

### 08:50 — REST read-only 사전점검

```bash
PYTHONPATH=./backend .venv/bin/python backend/scripts/kis_readonly_smoke.py --real
```

확인:
- OAuth token 발급
- 현재가 조회
- 종목정보 조회
- 잔고조회
- 주문 endpoint 미호출

❌ 실패 → KIS 설정 / IP / 권한 확인

### 08:55 — WebSocket 사전점검

```bash
PYTHONPATH=./backend .venv/bin/python backend/scripts/kis_ws_readonly_smoke.py \
  --real-ws --symbol 005930 --duration 30 --max-messages 10
```

확인:
- approval_key 발급
- WebSocket 연결
- 체결가/호가/장운영정보 수신
- raw 전문 미출력, secret 미출력

❌ 실패 → 자동매매 금지

### 09:00 — Dashboard 확인

http://localhost:5173 접속

확인:
- 장 세션: REGULAR_MARKET
- 시장 국면: 강세/중립/약세
- KIS REST 정상
- WebSocket 연결됨
- 텔레그램 연결됨
- 계좌 정보 표시
- 비상정지 비활성

❌ 비정상 → 자동매매 보류

### 09:05 — Dry-run (LIVE_TRADING_ENABLED=false)

```bash
PYTHONPATH=./backend .venv/bin/python backend/scripts/sat3_market_open_launcher.py 5
```

흐름: Scanner → Quant → Strategy → RiskDecision → OrderIntent (차단됨)

확인:
- 후보 발굴, ETF/ETN/ELW 제외
- Quant PASS/WATCH/REJECT
- 전략 신호 생성
- RiskDecision
- 주문 제출 차단 (LIVE=false)

### 09:15 — SafetyGate 최종 확인

```bash
PYTHONPATH=./backend .venv/bin/python backend/scripts/sat3_market_open_launcher.py 6
```

통과 조건:
- Session = REGULAR_MARKET
- Regime ≠ BEAR/UNKNOWN
- Emergency Stop = false
- REST / WS / quote / orderbook fresh
- RiskDecision APPROVED

❌ 실패 → LIVE=true 전환 금지

### 09:20 — LIVE=true 수동 전환

**사용자가 직접 .env 편집:**
```bash
nano .env
# LIVE_TRADING_ENABLED=true 로 변경
```

⚠️ 자동 전환 금지, 반드시 수동

### 09:20 이후 — 자동매매 시작

```bash
PYTHONPATH=./backend .venv/bin/python backend/scripts/sat3_market_open_launcher.py 9 --confirm-live-order
```

흐름:
```
Scanner → Quant → Strategy → RiskDecision → SafetyGate
    → Order Submit → Fill Reconciliation → Portfolio Sync
    → Exit Strategy → EOD / Analytics
```

시작 조건:
- LIVE_TRADING_ENABLED=true
- --confirm-live-order 명시
- Emergency Stop false
- Session REGULAR_MARKET
- Regime ≠ BEAR/UNKNOWN
- SafetyGate approved

### 15:20 — 신규매수 차단 (LATE_MARKET)

- 신규매수 차단
- 기존 포지션 모니터링 유지
- 청산: SafetyGate + Exit Policy 기준

### 15:30 이후 — EOD / Analytics

- EOD 리포트 생성
- Telegram EOD 알림
- 승률, 손익, Profit Factor, 최대낙폭
- 전략별/Scanner별 성과
- 오류 로그 확인
- 내일 수정 사항 기록

---

## 4. 운용 중 Telegram 감시

### 정상 흐름

| 알림 | 의미 |
|------|------|
| 🚀 서버 시작 | 백엔드 기동 |
| 🔄 장 세션 변경 | REGULAR_MARKET 진입 |
| 📊 시장 국면 | BULL/NEUTRAL/BEAR |
| 🔍 스캔 완료 | 후보 N개 발견 |
| 🎯 후보 발견 | 신규 종목 |
| 📈 매수신호 | 전략 신호 |
| ✅ 리스크 승인 | 매수 승인 |
| 📤 주문접수 | KIS 주문 전송 |
| ✅ 체결확인 | 체결 완료 |
| 🟢 익절 | 수익 실현 |
| 📊 EOD | 장 마감 요약 |

### 위험 흐름 — 즉시 확인

| 알림 | 조치 |
|------|------|
| 🛑 비상정지 | 모든 주문 차단 확인 |
| ⚡ WS 끊김 | 연결 복구 대기 |
| 🚫 주문실패 | 사유 확인 |
| 🔴 손절 | 손실 규모 확인 |
| ❌ 리스크 거절 반복 | 전략 점검 |

---

## 5. 운용 중 Dashboard 감시 항목

| 영역 | 카드 | 확인 사항 |
|------|------|-----------|
| 상단 | 시스템 상태 | 실전매매=활성, 비상정지=해제 |
| 상단 | 장 세션 | REGULAR_MARKET |
| 상단 | 시장 국면 | BULL/NEUTRAL/BEAR |
| 중단 | 실시간 시세 | 연결됨, 채널 활성 |
| 중단 | 데이터 라우터 | 출처=WS, REST 가능 |
| 중단 | 텔레그램 | 연결됨 |
| 중단 | 계좌 정보 | 예수금/평가금액/보유종목 |
| 매매 | 스캐너 후보 | 종목/유형/포함여부 |
| 매매 | 퀀트 평가 | PASS/WATCH/REJECT |
| 매매 | 리스크 판정 | 허용/사유 |
| 성과 | 일일 매매 요약 | 승률/PnL/Profit Factor |
| 성과 | 전략별 성과 | 전략별 손익 |
| 운영 | 운영 로그 | 섹션별 tail |

---

## 6. 즉시 중단 조건

아래 중 하나라도 발생 시 자동매매 중단:

- [ ] WebSocket 끊김 지속 (30초 이상)
- [ ] REST 조회 실패 지속
- [ ] KIS 403 반복
- [ ] 주문 실패 반복 (3회 이상)
- [ ] 체결조회/잔고조회 불일치
- [ ] 포트폴리오 수량 불일치
- [ ] Emergency Stop active
- [ ] 장 세션 UNKNOWN
- [ ] Market Regime BEAR
- [ ] 일일 손실 한도 도달 (예수금 5%)
- [ ] Dashboard 상태 확인 불가

### 중단 명령

```bash
PYTHONPATH=./backend .venv/bin/python backend/scripts/sat3_emergency_stop_cli.py activate --reason "manual safety stop"
```

### 해제 명령

```bash
PYTHONPATH=./backend .venv/bin/python backend/scripts/sat3_emergency_stop_cli.py release --reason "manual release after check"
```

⚠️ 해제 ≠ 주문 허용. SafetyGate 재통과 필요.

---

## 7. 실행 명령 모음

| 작업 | 명령 |
|------|------|
| Preflight | `python backend/scripts/sat3_preflight_check.py` |
| REST smoke | `python backend/scripts/kis_readonly_smoke.py --real` |
| WS smoke | `python backend/scripts/kis_ws_readonly_smoke.py --real-ws --symbol 005930 --duration 30 --max-messages 10` |
| Dry-run | `python backend/scripts/sat3_market_open_launcher.py 5` |
| SafetyGate | `python backend/scripts/sat3_market_open_launcher.py 6` |
| 자동매매 시작 | `python backend/scripts/sat3_market_open_launcher.py 9 --confirm-live-order` |
| Emergency Stop | `python backend/scripts/sat3_emergency_stop_cli.py activate --reason "..."` |
| Stop 해제 | `python backend/scripts/sat3_emergency_stop_cli.py release --reason "..."` |
| Telegram test | `curl -X POST http://127.0.0.1:8000/api/telegram/test -H "Content-Type: application/json" -d '{"confirm":"SEND_TEST_TELEGRAM"}'` |
| Dashboard | `cd frontend && npm run build && npm run dev` |
