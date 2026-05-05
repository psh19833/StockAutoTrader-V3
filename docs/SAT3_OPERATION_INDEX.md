# SAT3 Operation Index

> 전체 운영 문서 목록 및 상황별 참조
> 상태: CONDITIONALLY_READY
> 테스트 기준: `cd backend && ../.venv/bin/python -m pytest -q` (현재 1273 passed)

## 운영 문서 목록

| 문서 | 내용 |
|------|------|
| [sat3_operational_runbook.md](sat3_operational_runbook.md) | 시스템 개요, 파이프라인, 9단계 운용 절차 |
| [sat3_market_open_runbook.md](sat3_market_open_runbook.md) | 개장일 타임라인, 조건부 실전 전환 조건/증적 템플릿 |
| [sat3_ops_prep.md](sat3_ops_prep.md) | 개장일 간략 체크리스트 |
| [sat3_dashboard_runbook.md](sat3_dashboard_runbook.md) | Dashboard 실행/확인 방법 |
| [sat3_emergency_stop.md](sat3_emergency_stop.md) | 비상정지 절차 |
| [sat3_kis_readonly_smoke_test.md](sat3_kis_readonly_smoke_test.md) | REST read-only smoke |
| [sat3_ops2_ws_real_smoke.md](sat3_ops2_ws_real_smoke.md) | WebSocket read-only smoke |
| [sat3_release_checklist.md](sat3_release_checklist.md) | 릴리스 체크리스트 |

## 상황별 참조

| 상황 | 문서 |
|------|------|
| 개장일 시작 | sat3_market_open_runbook.md |
| 장애 발생 | sat3_emergency_stop.md |
| Dashboard 문제 | sat3_dashboard_runbook.md |
| REST API 문제 | sat3_kis_readonly_smoke_test.md |
| WebSocket 문제 | sat3_ops2_ws_real_smoke.md |

## CLI 명령어

```bash
# Preflight
PYTHONPATH=./backend .venv/bin/python backend/scripts/sat3_preflight_check.py

# Emergency Stop
PYTHONPATH=./backend .venv/bin/python backend/scripts/sat3_emergency_stop_cli.py status
PYTHONPATH=./backend .venv/bin/python backend/scripts/sat3_emergency_stop_cli.py activate --reason "..."

# Dashboard health
PYTHONPATH=./backend .venv/bin/python backend/scripts/sat3_dashboard_health_check.py

# Market open launcher
PYTHONPATH=./backend .venv/bin/python backend/scripts/sat3_market_open_launcher.py [1-9]

# REST smoke
PYTHONPATH=./backend .venv/bin/python backend/scripts/kis_readonly_smoke.py --real

# WebSocket smoke
PYTHONPATH=./backend .venv/bin/python backend/scripts/kis_ws_readonly_smoke.py --real-ws
```
