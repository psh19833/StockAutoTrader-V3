import React, { useEffect, useState } from "react";
import { fetchStrategyBreakdown } from "../../api/dashboardApi";

export default function StrategyBreakdownTable({ date }) {
  const [data, setData] = useState([]);
  useEffect(() => {
    fetchStrategyBreakdown(date).then(setData).catch(() => setData([]));
  }, [date]);

  if (!data.length) return <div className="card"><h3>Strategy Breakdown</h3><p>No data</p></div>;
  return (
    <div className="card">
      <h3>Strategy Breakdown</h3>
      <table><thead><tr><th>Strategy</th><th>Trades</th><th>Win Rate</th><th>PnL</th><th>Avg PnL</th></tr></thead>
      <tbody>{data.map((s, i) => (
        <tr key={i}>
          <td>{s.strategy}</td><td>{s.trades}</td>
          <td className={s.win_rate >= 0.5 ? "safe" : "danger"}>{(s.win_rate * 100).toFixed(1)}%</td>
          <td className={s.total_pnl >= 0 ? "safe" : "danger"}>₩{s.total_pnl?.toLocaleString()}</td>
          <td>₩{s.avg_pnl?.toLocaleString()}</td>
        </tr>
      ))}</tbody></table>
    </div>
  );
}
