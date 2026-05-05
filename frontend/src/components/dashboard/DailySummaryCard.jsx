import React, { useEffect, useState } from "react";
import { fetchDailySummary } from "../../api/dashboardApi";

export default function DailySummaryCard({ date }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    fetchDailySummary(date).then(setData).catch(() => {});
  }, [date]);

  if (!data) return <div className="card"><h3>Daily Summary</h3><p>Loading...</p></div>;
  const wr = data.win_rate ? (data.win_rate * 100).toFixed(1) : "0.0";
  return (
    <div className="card">
      <h3>Daily Summary {data.date && `(${data.date})`}</h3>
      <p>Trades: {data.total_trades}</p>
      <p>Wins: {data.wins} / Losses: {data.losses}</p>
      <p>Win Rate: <span className={data.win_rate >= 0.5 ? "safe" : "danger"}>{wr}%</span></p>
      <p>Realized PnL: <span className={data.realized_pnl >= 0 ? "safe" : "danger"}>₩{data.realized_pnl?.toLocaleString()}</span></p>
      <p>Profit Factor: {data.profit_factor?.toFixed(2)}</p>
      <p>Max Drawdown: {data.max_drawdown_pct?.toFixed(1)}%</p>
    </div>
  );
}
