import React, { useEffect, useState } from "react";
import { fetchStrategyBreakdown } from "../../api/dashboardApi";

export default function StrategyBreakdownTable({ date }) {
  const [data, setData] = useState([]);
  useEffect(() => {
    fetchStrategyBreakdown(date).then(setData).catch(() => setData([]));
  }, [date]);

  if (!data.length) return <div className="card"><h3>전략별 성과</h3><p>데이터 없음</p></div>;
  return (
    <div className="card">
      <h3>전략별 성과</h3>
      <table><thead><tr><th>전략</th><th>거래</th><th>승률</th><th>손익</th><th>평균손익</th></tr></thead>
      <tbody>{data.map((s, i) => (
        <tr key={i}>
          <td>{s.strategy}</td><td>{s.trades}건</td>
          <td className={s.win_rate >= 0.5 ? "safe" : "danger"}>{(s.win_rate * 100).toFixed(1)}%</td>
          <td className={s.total_pnl >= 0 ? "safe" : "danger"}>₩{s.total_pnl?.toLocaleString()}</td>
          <td>₩{s.avg_pnl?.toLocaleString()}</td>
        </tr>
      ))}</tbody></table>
    </div>
  );
}
