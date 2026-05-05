import React from "react";

export default function QuantScoresTable({ scores }) {
  const keys = Object.keys(scores);
  if (!keys.length) return <div className="card"><h3>퀀트 평가</h3><p>없음</p></div>;
  return (
    <div className="card">
      <h3>퀀트 평가 요약</h3>
      <table><thead><tr><th>판정</th><th>건수</th></tr></thead>
      <tbody>{keys.map(k => <tr key={k}><td>{k}</td><td>{scores[k]}</td></tr>)}</tbody></table>
    </div>
  );
}
