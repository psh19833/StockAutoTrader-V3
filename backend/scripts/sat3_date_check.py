#!/usr/bin/env python3
"""SAT3 날짜/시간 확인 — 오늘 거래일 여부와 현재 세션 상태 출력.

Usage:
  PYTHONPATH=./backend python backend/scripts/sat3_date_check.py
"""
from __future__ import annotations

import os, sys
from datetime import datetime, date, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_DIR = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_DIR, ".env"))
except ImportError:
    pass

KST = timezone(timedelta(hours=9))
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]

# 알려진 한국 공휴일 (2026년)
KNOWN_HOLIDAYS_2026 = {
    "2026-01-01",  # 신정
    "2026-02-16", "2026-02-17",  # 설날
    "2026-03-02",  # 삼일절
    "2026-05-05",  # 어린이날
    "2026-05-25",  # 석가탄신일
    "2026-06-06",  # 현충일
    "2026-08-17",  # 광복절
    "2026-09-24", "2026-09-25",  # 추석
    "2026-10-03",  # 개천절
    "2026-10-09",  # 한글날
    "2026-12-25",  # 크리스마스
}

# 장 시간표 (KST)
MARKET_SCHEDULE = [
    ("08:30", "08:50", "장 전 점검", "CLOSED_BEFORE_MARKET"),
    ("08:50", "09:00", "동시호가", "PRE_MARKET_AUCTION"),
    ("09:00", "15:20", "정규장", "REGULAR_MARKET"),
    ("15:20", "15:30", "장 마감 임박", "LATE_MARKET"),
    ("15:30", "15:40", "마감 동시호가", "CLOSING_AUCTION"),
    ("15:40", "18:00", "시간외", "AFTER_MARKET"),
]


def main():
    now_kst = datetime.now(KST)
    today_str = now_kst.strftime("%Y-%m-%d")
    weekday = now_kst.weekday()

    print("=" * 50)
    print("  SAT3 날짜/시간 확인")
    print("=" * 50)
    print(f"  한국 시간: {now_kst.strftime('%Y-%m-%d %H:%M:%S')} ({WEEKDAY_KR[weekday]}요일)")
    print(f"  UTC 시간:  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")

    # 거래일 판단
    is_weekend = weekday >= 5
    is_holiday = today_str in KNOWN_HOLIDAYS_2026
    is_trading_day = not is_weekend and not is_holiday

    print()
    if is_holiday:
        print(f"  📅 오늘은 공휴일입니다 — 주식시장 휴장")
    elif is_weekend:
        print(f"  📅 오늘은 주말입니다 — 주식시장 휴장")
    elif is_trading_day:
        print(f"  📅 오늘은 거래일입니다 — 주식시장 개장")
    else:
        print(f"  📅 거래일 여부 확인 불가")

    # 현재 세션 상태
    now_str = now_kst.strftime("%H:%M")
    current_session = None

    for start, end, label, state in MARKET_SCHEDULE:
        if start <= now_str < end:
            current_session = (label, state)
            break

    if current_session is None:
        if now_str >= "18:00" or now_str < "08:30":
            current_session = ("장 마감", "CLOSED_AFTER_MARKET")
        else:
            current_session = ("알 수 없음", "UNKNOWN")

    print(f"  ⏰ 현재 세션: {current_session[0]} ({current_session[1]})")

    # 신규매수 가능 여부
    can_buy = current_session[1] == "REGULAR_MARKET" and is_trading_day
    print(f"  💰 신규매수: {'✅ 가능' if can_buy else '❌ 불가'}")

    # 장 시간표
    print()
    print("  장 시간표:")
    for start, end, label, state in MARKET_SCHEDULE:
        marker = " ← 현재" if current_session and current_session[1] == state else ""
        print(f"    {start}~{end}  {label} ({state}){marker}")

    print()
    print("=" * 50)

    # 운영 스케줄 추천
    if is_trading_day and current_session[1] == "CLOSED_BEFORE_MARKET":
        print("  다음 단계: Preflight → REST smoke → WS smoke")
    elif is_trading_day and current_session[1] == "REGULAR_MARKET":
        print("  다음 단계: Dry-run → SafetyGate → LIVE=true → 자동매매")
    elif not is_trading_day:
        print("  휴장일 — 개발/점검 작업만 수행")
    else:
        print(f"  현재 세션({current_session[0]})에서는 신규매매 불가")
    print("=" * 50)


if __name__ == "__main__":
    main()
