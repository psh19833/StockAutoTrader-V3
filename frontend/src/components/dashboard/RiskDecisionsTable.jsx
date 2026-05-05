import React from "react";

export default function RiskDecisionsTable({ decisions }) {
  if (!decisions.length) return <div className="card"><h3>리스크 판정</h3><p>없음</p></div>;
  return (
    <div className="card">
      <h3>리스크 판정 ({decisions.length}건)</h3>
      <table><thead><tr><th>종목</th><th>방향</th><th>허용</th><th>사유</th></tr></thead>
      <tbody>{decisions.map((d, i) => (
        <tr key={i} className={d.allowed ? "safe" : "danger"}><td>{d.symbol}</td><td>{d.side === "BUY" ? "매수" : "매도"}</td><td>{d.allowed ? "예" : "아니오"}</td><td>{d.reason_code}: {d.reason_text}</td></tr>
      ))}</tbody></table>
    </div>
  );
}
