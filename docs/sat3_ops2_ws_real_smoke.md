# SAT3 KIS WebSocket Real Smoke Test (OPS-2)

**Phase:** OPS-2
**상태:** 구현 완료

---

## 실제 WebSocket 연결

GuardedRealWebSocketClient가 `websocket-client` 라이브러리를 사용하여 KIS 실시간 서버에 연결한다.

### 의존성
```
pip install websocket-client
```

### 연결 흐름
1. `.env`에서 `KIS_WEBSOCKET_URL` 로드
2. `--real-ws` 옵션 확인
3. approval_key 발급 (REST /oauth2/Approval)
4. `websocket.create_connection(url, timeout=10)` 호출
5. 구독 payload 전송 (JSON)
6. 메시지 수신 → parser → summary 출력
7. 연결 종료

---

## 실행 방법

```bash
# Stub 모드 (실제 연결 없음)
PYTHONPATH=./backend python backend/scripts/kis_ws_readonly_smoke.py

# 실제 WS 모드
PYTHONPATH=./backend python backend/scripts/kis_ws_readonly_smoke.py --real-ws --duration 30 --max-messages 10
```

## 기본값

- --symbol: 005930
- --duration: 30초
- --max-messages: 10개
- --channels: trade_tick, order_book, market_status, expected_execution
- --include-fill-notice: off (기본 제외)

---

## 보안

- approval_key: 모든 출력에서 `****-****-****`
- subscribe payload: 마스킹 버전만 출력
- raw 전문: 출력 금지, raw_hash만 저장
- WebSocket URL: repr/log 미노출
