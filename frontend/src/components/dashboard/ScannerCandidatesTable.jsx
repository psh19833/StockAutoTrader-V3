import React from "react";

export default function ScannerCandidatesTable({ candidates }) {
  if (!candidates.length) return <div className="card"><h3>스캐너 후보</h3><p>없음</p></div>;
  return (
    <div className="card">
      <h3>스캐너 후보 ({candidates.length}건)</h3>
      <table><thead><tr><th>종목</th><th>유형</th><th>포함</th><th>사유</th></tr></thead>
      <tbody>{candidates.map((c, i) => (
        <tr key={i}><td>{c.symbol}</td><td>{c.scanner_type}</td><td>{c.included ? "예" : "아니오"}</td><td>{c.excluded_reason || "-"}</td></tr>
      ))}</tbody></table>
    </div>
  );
}
