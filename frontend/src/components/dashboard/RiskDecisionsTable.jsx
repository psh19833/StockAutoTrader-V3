import React from "react";

export default function RiskDecisionsTable({ decisions }) {
  if (!decisions.length) return <div className="card"><h3>Risk Decisions</h3><p>None</p></div>;
  return (
    <div className="card">
      <h3>Risk Decisions ({decisions.length})</h3>
      <table><thead><tr><th>Symbol</th><th>Side</th><th>Allowed</th><th>Reason</th></tr></thead>
      <tbody>{decisions.map((d, i) => (
        <tr key={i} className={d.allowed ? "safe" : "danger"}><td>{d.symbol}</td><td>{d.side}</td><td>{d.allowed ? "Yes" : "No"}</td><td>{d.reason_code}: {d.reason_text}</td></tr>
      ))}</tbody></table>
    </div>
  );
}
