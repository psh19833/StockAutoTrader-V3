# SAT3 Dashboard Enhancement (OPS-3)

> 마지막 수정: 2026-05-05

## 신규 컴포넌트

| 컴포넌트 | 내용 |
|----------|------|
| TelegramStatusCard | 봇 연결 상태, bot name, chat_id 전체 표시 |
| KisAccountCard | 계좌번호, 예수금, 평가금액, 보유종목 |
| DailySummaryCard | 승률, Profit Factor, 실현손익, 최대낙폭 |
| StrategyBreakdownTable | 전략별 거래수/승률/PnL |
| LogViewer | 날짜 선택 + 섹션 탭 + 로그 tail |

## 로그 구조

```
logs/YYYY-MM-DD/
├── trading.log
├── scanner.log
├── quant.log
├── risk.log
├── system.log
├── websocket.log
├── telegram.log
└── emergency.log
```

## 보안

- appkey/appsecret/access_token/approval_key: Dashboard 표시 금지
- 계좌번호: 전체 표시 (로컬 대시보드)
- Chat ID: 전체 표시 (로컬 대시보드)
- 주문 버튼: 없음
- LIVE 토글: 없음

## .env 설정

```
TELEGRAM_BOT_TOKEN=<bot_token_from_env>
TELEGRAM_CHAT_ID=<verified_chat_id_from_env>
```
