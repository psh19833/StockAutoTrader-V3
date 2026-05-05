# SAT3 Telegram Notification System — 구현 계획서

> 작성일: 2026-05-05
> 상태: 계획 단계
> Bot: @SAT_ver2_bot | Chat ID: 2118976841

---

## 1. 개요

SAT3 운용 중 발생하는 모든 중요 이벤트를 Telegram으로 실시간 발송한다.
Dashboard의 TelegramStatusCard(연결 확인)에 더해 실제 메시지 발송 기능을 추가한다.

---

## 2. 파일 구조

```
backend/
├── notifications/
│   ├── __init__.py
│   ├── telegram_sender.py      # Telegram 메시지 발송 코어
│   ├── notification_service.py  # 이벤트 → 메시지 변환 + 발송
│   └── throttle.py              # 중복 발송 방지 (초당/분당 제한)
├── tools/
│   └── daily_logger.py          # 기존: telegram.log 카테고리 추가됨
└── main.py                      # 신규 endpoint: /api/telegram/test
```

---

## 3. telegram_sender.py

**역할:** Telegram Bot API 호출 (sendMessage)

**주요 기능:**
- `send_message(text)` — 기본 텍스트 발송
- `send_markdown(text)` — 마크다운 형식 발송
- `get_me()` — 봇 연결 확인
- `.env`에서 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 읽기
- 실패 시 로그 기록, 예외 미전파

**보안:**
- Bot Token 원문 로그 출력 금지
- Chat ID는 로그에 표시 허용 (운영 확인용)

---

## 4. notification_service.py

**역할:** 이벤트 → 한글 메시지 변환

**지원 이벤트 18종:**

| # | 이벤트 | 한글 메시지 예시 |
|---|--------|-----------------|
| 1 | 장 시작 | 🟢 장 시작 — REGULAR_MARKET 진입 |
| 2 | 스캔 완료 | 🔍 스캔 완료: 12종목 발견 |
| 3 | 후보 발견 | 📊 신규 후보: 005930 삼성전자 (RAPID_SURGE) |
| 4 | 후보 제외 | ❌ 000660 SK하이닉스 제외: ETF |
| 5 | 퀀트 평가 | 📈 005930 PASS (0.85) / 035720 REJECT (0.32) |
| 6 | 전략 신호 | 🎯 매수신호: 005930 RAPID_SURGE 신뢰도 0.82 |
| 7 | 리스크 승인 | ✅ 리스크 승인: 005930 매수 |
| 8 | 리스크 거절 | ⛔ 리스크 거절: 005930 — 일일손실한도 |
| 9 | 주문 접수 | 📝 주문접수: 005930 매수 10주 72,000원 ORD-001 |
| 10 | 주문 실패 | 🚫 주문실패: 005930 매수 — 잔고부족 |
| 11 | 체결 확인 | 💰 체결확인: 005930 매수 10주 72,000원 |
| 12 | 손절 실행 | 🔴 손절: 005930 -3.2% 69,800원 |
| 13 | 익절 실행 | 🟢 익절: 005930 +5.1% 75,600원 |
| 14 | 비상정지 | 🛑 비상정지 활성화! 모든 주문 차단 |
| 15 | 비상정지 해제 | ⚠️ 비상정지 해제 — SafetyGate 재확인 필요 |
| 16 | WS 끊김 | ⚡ WebSocket 끊김 — 실시간 데이터 중단 |
| 17 | WS 재연결 | 🔌 WebSocket 재연결 성공 |
| 18 | 장 종료 | 🏁 장 종료 — 승률 60% / PnL +234,500 / 12건 |

---

## 5. throttle.py

**역할:** 과도한 메시지 발송 방지

**규칙:**
- 초당 최대 3건
- 분당 최대 20건
- 동일 종목+이벤트 5초 내 중복 차단
- Emergency Stop, WS disconnect는 throttle 무시 (즉시 발송)

---

## 6. main.py 추가 endpoint

```
GET /api/telegram/test  →  "SAT3 Telegram 알림 테스트" 메시지 발송
```

---

## 7. Dashboard 연동

- TelegramStatusCard: 기존 그대로 (getMe로 연결 확인)
- notification_service가 발송할 때마다 `tools/daily_logger`의 `telegram.log`에 기록

---

## 8. 테스트 계획

| # | 테스트 |
|---|--------|
| 1 | telegram_sender가 실제 발송 없이 mock으로 동작하는지 |
| 2 | notification_service 18종 메시지 포맷 확인 |
| 3 | throttle 중복 차단 확인 |
| 4 | Emergency Stop이 throttle 무시하는지 |
| 5 | secret(token) 미노출 확인 |
| 6 | 실제 Telegram API 호출 없음 (테스트) |
| 7 | 기존 1183개 테스트 유지 |

---

## 9. 변경 파일 (예상 7개)

| 파일 | 구분 |
|------|------|
| backend/notifications/__init__.py | 신규 |
| backend/notifications/telegram_sender.py | 신규 |
| backend/notifications/notification_service.py | 신규 |
| backend/notifications/throttle.py | 신규 |
| backend/main.py | 수정 (test endpoint) |
| backend/tests/test_telegram_notification.py | 신규 |
| docs/sat3_telegram_notification.md | 신규 |

---

## 10. 보안

- Bot Token: `.env`에서만 로드, 코드/로그에 미노출
- Chat ID: 로그/메시지에 포함 허용 (운영 확인용)
- 실제 발송: 테스트에서는 금지 (mock만 사용)
- Throttle: 무분별 발송 방지

---

계획 승인 시 즉시 구현 시작합니다.
