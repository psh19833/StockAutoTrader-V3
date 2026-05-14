import { useEffect, useState } from "react";

const WEEKDAY = ["일", "월", "화", "수", "목", "금", "토"];
const HOLIDAYS = ["2026-01-01","2026-02-16","2026-02-17","2026-03-02","2026-05-05","2026-05-25","2026-06-06","2026-08-17","2026-09-24","2026-09-25","2026-10-03","2026-10-09","2026-12-25"];
const SCHEDULE = [
  ["08:30","08:50","장 전 점검","CLOSED_BEFORE_MARKET"],
  ["08:50","09:00","동시호가","PRE_MARKET_AUCTION"],
  ["09:00","15:20","정규장","REGULAR_MARKET"],
  ["15:20","15:30","장 마감 임박","LATE_MARKET"],
  ["15:30","15:40","마감 동시호가","CLOSING_AUCTION"],
  ["15:40","18:00","시간외","AFTER_MARKET"],
];

export default function DateTimeCard() {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const kst = new Date(now.getTime() + 9 * 3600000);
  const dateStr = kst.toISOString().slice(0, 10);
  const timeStr = kst.toISOString().slice(11, 16);
  const weekday = WEEKDAY[(kst.getUTCDay() + (kst.getUTCHours() >= 15 ? 1 : 0)) % 7];
  const isHoliday = HOLIDAYS.includes(dateStr);
  const isWeekend = [0, 6].includes(new Date(dateStr).getDay()); // 일=0, 토=6
  const isTradingDay = !isHoliday && !isWeekend;

  let session = ["장 마감", "CLOSED_AFTER_MARKET"];
  for (const [s, e, label, state] of SCHEDULE) {
    if (s <= timeStr && timeStr < e) { session = [label, state]; break; }
  }

  const canBuy = session[1] === "REGULAR_MARKET" && isTradingDay;
  const statusColor = isTradingDay ? (canBuy ? "#3fb950" : "#d29922") : "#f85149";

  return (
    <div className="card" style={{ borderLeft: `3px solid ${statusColor}` }}>
      <h3>📅 날짜 / 시간</h3>
      <p style={{ fontSize: 18, fontWeight: "bold" }}>
        {dateStr} ({weekday}) {timeStr}
      </p>
      <p>거래일: <span className={isTradingDay ? "safe" : "danger"}>
        {isTradingDay ? "예" : isHoliday ? "공휴일" : "주말"}
      </span></p>
      <p>세션: {session[0]}</p>
      <p>신규매수: <span className={canBuy ? "safe" : "danger"}>
        {canBuy ? "✅ 가능" : "❌ 불가"}
      </span></p>
    </div>
  );
}
