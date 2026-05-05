import React, { useEffect, useState } from "react";
import { fetchDailySummary } from "../../api/dashboardApi";

export default function DailySummaryCard({ date }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    fetchDailySummary(date).then(setData).catch(() => {});
  }, [date]);

  if (!data) return <div className="card"><h3>일일 요약</h3><p>불러오는 중...</p></div>;
  const wr = data.win_rate ? (data.win_rate * 100).toFixed(1) : "0.0";
  return (
    <div className="card">
      <h3>일일 매매 요약 {data.date && `(${data.date})`}</h3>
      <p>총 거래: {data.total_trades}건</p>
      <p>승: {data.wins} / 패: {data.losses}</p>
      <p>승률: <span className={data.win_rate >= 0.5 ? "safe" : "danger"}>{wr}%</span></p>
      <p>실현손익: <span className={data.realized_pnl >= 0 ? "safe" : "danger"}>₩{data.realized_pnl?.toLocaleString()}</span></p>
      <p>수익 팩터: {data.profit_factor?.toFixed(2)}</p>
      <p>최대 낙폭: {data.max_drawdown_pct?.toFixed(1)}%</p>
    </div>
  );
}
