import React from "react";

export default function MarketRegimeCard({ data }) {
  if (!data) return <div className="card">데이터 없음</div>;
  const regimeMap = { BULL: "강세", NEUTRAL: "중립", BEAR: "약세", UNKNOWN: "알 수 없음" };
  return (
    <div className="card">
      <h3>시장 국면</h3>
      <p>국면: <span className={data.allow_new_buy ? "safe" : "warn"}>{regimeMap[data.regime] || data.regime}</span></p>
      <p>신규매수: {data.allow_new_buy ? "허용" : "차단"}</p>
      <p>점수: {data.total_score?.toFixed(1)}</p>
      {data.reason && <p style={{ fontSize: 12, color: "#8b949e", marginTop: 8, borderTop: "1px solid #30363d", paddingTop: 6 }}>{data.reason}</p>}
      {data.factors && <p style={{ fontSize: 11, color: "#6e7681" }}>{data.factors}</p>}
    </div>
  );
}
