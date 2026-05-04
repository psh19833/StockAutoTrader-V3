import React from "react";

export default function QuantScoresTable({ scores }) {
  const keys = Object.keys(scores);
  if (!keys.length) return <div className="card"><h3>Quant Scores</h3><p>None</p></div>;
  return (
    <div className="card">
      <h3>Quant Summary</h3>
      <table><thead><tr><th>Decision</th><th>Count</th></tr></thead>
      <tbody>{keys.map(k => <tr key={k}><td>{k}</td><td>{scores[k]}</td></tr>)}</tbody></table>
    </div>
  );
}
