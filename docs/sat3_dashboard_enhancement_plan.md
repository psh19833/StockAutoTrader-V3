# SAT3 Dashboard Enhancement Plan

> 작성일: 2026-05-05
> 상태: 계획 단계

---

## 1. Log System (운영 로그)

### 구조
```
logs/
├── 2026-05-06/                  # 날짜별 디렉토리
│   ├── trading.log              # 매매 관련 (주문접수/체결/청산)
│   ├── scanner.log              # 스캐너 실행 기록
│   ├── quant.log                # 퀀트 평가 기록
│   ├── risk.log                 # 리스크 판단 기록
│   ├── system.log               # 시스템 상태 (시작/종료/오류)
│   ├── websocket.log            # WebSocket 연결/끊김/메시지
│   ├── telegram.log             # Telegram 메시지 발송 기록
│   └── emergency.log            # Emergency Stop 활성화/해제
```

### 라이프사이클
- **08:50 장 시작 전**: 오늘 날짜 디렉토리 생성, 모든 로그 파일 open
- **09:00~15:20 장 중**: 각 컴포넌트가 해당 로그 파일에 append
- **15:30 장 종료 후**: EOD 요약 생성, 로그 파일 close
- **다음 날**: 새 디렉토리에 새 로그 시작

### Dashboard 표시
- **좌측**: 섹션 탭 (Trading, Scanner, Quant, Risk, System, WebSocket, Telegram, Emergency)
- **상단**: 날짜 선택기 (드롭다운 또는 좌우 화살표)
- **본문**: 선택한 섹션 + 날짜의 로그 내용 (최신순, 100줄씩 페이지)

### 백엔드 API
```
GET /api/dashboard/logs/dates              → 사용 가능한 날짜 목록
GET /api/dashboard/logs/{date}/{section}   → 특정 날짜/섹션 로그
```

---

## 2. Telegram Connection Status Card

### 표시 정보
| 필드 | 값 예시 |
|------|---------|
| 연결 상태 | CONNECTED / DISCONNECTED |
| Chat ID | -1001234567890 (last 4 digits only) |
| 봇 이름 | @SAT3_ver2_bot |
| 마지막 메시지 | 2026-05-06 10:30:15 |
| 오류 | None / Timeout / Auth Failed |

### 백엔드 API
```
GET /api/dashboard/telegram-status
```

### 상태 확인 방법
- Telegram Bot API `getMe` 호출로 봇 연결 확인
- `getUpdates`로 최근 메시지 수신 확인
- 실패 시 오류 메시지 표시

### 보안
- Chat ID 전체 노출 금지 (마지막 4자리만)
- Bot Token 원문 노출 금지

---

## 3. KIS Account Info Card

### 표시 정보
| 필드 | 표시 | 비고 |
|------|------|------|
| 계좌번호 | 4441******* | 마스킹 |
| 상품코드 | 01 | |
| 예수금 | 12,345,678 | REST 잔고조회 |
| 평가금액 | 15,000,000 | |
| 총매수금액 | 10,000,000 | |
| 보유종목수 | 3 | |
| D+2 예수금 | 12,000,000 | |

### 백엔드 API
```
GET /api/dashboard/kis-account
```

### 데이터 출처
- KIS REST: `/uapi/domestic-stock/v1/trading/inquire-balance`
- 장 시작/종료 시 갱신
- Stale 판단: 60초 이상이면 "데이터 갱신 필요" 표시

### 보안
- 계좌번호 마스킹
- 실제 금액은 표시하되, Dashboard는 Read-Only

---

## 4. Daily Trading Summary

### 표시 정보
| 지표 | 설명 |
|------|------|
| 날짜 | 2026-05-06 |
| 총 매매 횟수 | 12 |
| 승리 | 7 (58.3%) |
| 패배 | 5 (41.7%) |
| 실현 손익 | +₩234,500 |
| 미실현 손익 | +₩50,000 |
| Profit Factor | 1.85 |
| 최대 낙폭 | -3.2% |
| 평균 보유시간 | 45분 |
| 수수료 합계 | ₩12,000 |

### 전략별 breakdown
| 전략 | 트레이드 | 승률 | PnL |
|------|---------|------|-----|
| RAPID_SURGE | 5 | 60% | +₩150,000 |
| PULLBACK | 4 | 50% | +₩50,000 |
| BREAKOUT | 3 | 66% | +₩34,500 |

### 백엔드 API
```
GET /api/dashboard/daily-summary/{date}
GET /api/dashboard/daily-summary/dates    → 요약 가능한 날짜 목록
```

### 데이터 출처
- `analytics/performance_analyzer.py`의 PerformanceAnalyzer
- DB의 fills, orders 테이블
- EOD Report 데이터

---

## 5. Frontend 컴포넌트 추가

### 신규 컴포넌트
```
src/components/dashboard/
├── LogViewer.jsx              # 로그 뷰어 (날짜 선택 + 섹션 탭)
├── TelegramStatusCard.jsx     # Telegram 연결 상태
├── KisAccountCard.jsx         # 계좌 정보
├── DailySummaryCard.jsx       # 일별 매매 요약
└── StrategyBreakdownTable.jsx # 전략별 성과 테이블
```

### DashboardPage.jsx 수정
- LogViewer를 하단에 추가
- TelegramStatusCard, KisAccountCard를 카드 영역에 추가
- DailySummaryCard를 우측 사이드바로 추가

---

## 6. 구현 순서

| # | 작업 | 비고 |
|---|------|------|
| 1 | LogSystem 백엔드 (logger, file manager) | tools/daily_logger.py |
| 2 | Log API endpoint | /api/dashboard/logs/* |
| 3 | LogViewer frontend | 날짜 선택 + 섹션 탭 |
| 4 | TelegramStatus API + Card | getMe/getUpdates 체크 |
| 5 | KIS Account API + Card | REST 잔고조회 연동 |
| 6 | DailySummary API + Card | PerformanceAnalyzer 연동 |
| 7 | DashboardPage 통합 | 모든 신규 컴포넌트 배치 |
| 8 | docs 문서화 | |

---

## 7. 보안 원칙

- 계좌번호: 마스킹 (끝 4자리만)
- Chat ID: 마스킹 (끝 4자리만)
- Bot Token: 절대 출력 금지
- app_key/app_secret: 절대 출력 금지
- KIS 잔고: 실제 금액 표시 가능 (Read-Only)
- Dashboard: 주문 버튼 없음, LIVE 토글 없음
