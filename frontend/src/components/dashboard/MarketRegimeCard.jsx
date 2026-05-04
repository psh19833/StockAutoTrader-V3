import React from "react";

export default function MarketRegimeCard({ data }) {
  if (!data) return <div className="card">No regime data</div>;
  return (
    <div className="card">
      <h3>Market Regime</h3>
      <p>Regime: <span className={data.allow_new_buy ? "safe" : "warn"}>{data.regime}</span></p>
      <p>New Buy: {data.allow_new_buy ? "Allowed" : "Blocked"}</p>
      <p>Score: {data.total_score?.toFixed(2)}</p>
    </div>
  );
}
