import React from "react";

export default function ScannerCandidatesTable({ candidates }) {
  if (!candidates.length) return <div className="card"><h3>Scanner Candidates</h3><p>None</p></div>;
  return (
    <div className="card">
      <h3>Scanner Candidates ({candidates.length})</h3>
      <table><thead><tr><th>Symbol</th><th>Type</th><th>Included</th><th>Reason</th></tr></thead>
      <tbody>{candidates.map((c, i) => (
        <tr key={i}><td>{c.symbol}</td><td>{c.scanner_type}</td><td>{c.included ? "Yes" : "No"}</td><td>{c.excluded_reason || "-"}</td></tr>
      ))}</tbody></table>
    </div>
  );
}
