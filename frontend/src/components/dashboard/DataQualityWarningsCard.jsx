
export default function DataQualityWarningsCard({ warnings }) {
  if (!warnings || warnings.length === 0) return null;
  return (
    <div className="card warn">
      <h3>데이터 품질 경고</h3>
      <ul>{warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
    </div>
  );
}
