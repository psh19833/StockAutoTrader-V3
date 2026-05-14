
function fmtValue(v) {
  if (v === null || v === undefined) return "";
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

function statusColor(status) {
  switch (status) {
    case "PASS":
      return "#22c55e";
    case "FAIL":
      return "#ef4444";
    case "WARN":
      return "#f59e0b";
    case "INFO":
    default:
      return "#60a5fa";
  }
}

export default function EvidenceChecklistCard({ checklist }) {
  const hasChecklist = !!checklist && typeof checklist === "object";
  const schemaVersion = checklist?.schema_version || "";
  const stage = checklist?.stage || "";
  const items = Array.isArray(checklist?.items) ? checklist.items : [];

  return (
    <div className="card" style={{ marginTop: 12 }}>
      <h3>Evidence Checklist</h3>
      {!hasChecklist ? (
        <div style={{ fontSize: 12, opacity: 0.8 }}>
          checklist 없음 (event payload에 checklist가 포함되지 않았거나, 저장소에 아직 반영되지 않았습니다)
        </div>
      ) : null}
      <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 8 }}>
        schema_version: <span style={{ fontFamily: "monospace" }}>{schemaVersion || "(none)"}</span>
        {stage ? (
          <>
            {" "} | stage: <span style={{ fontFamily: "monospace" }}>{stage}</span>
          </>
        ) : null}
      </div>

      {items.length === 0 ? (
        <div style={{ fontSize: 12, opacity: 0.8 }}>
          checklist items (0)
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="table" style={{ width: "100%", minWidth: 900 }}>
            <thead>
              <tr>
                <th>status</th>
                <th>label</th>
                <th>key</th>
                <th>value</th>
                <th>threshold</th>
                <th>reason</th>
                <th>source</th>
                <th>evaluated_at</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it, idx) => (
                <tr key={it.key || idx}>
                  <td style={{ fontWeight: 700, color: statusColor(it.status) }}>{it.status || ""}</td>
                  <td>{it.label || ""}</td>
                  <td style={{ fontFamily: "monospace" }}>{it.key || ""}</td>
                  <td style={{ maxWidth: 220, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {fmtValue(it.value)}
                  </td>
                  <td style={{ maxWidth: 160, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {fmtValue(it.threshold)}
                  </td>
                  <td style={{ maxWidth: 260, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {it.reason || ""}
                  </td>
                  <td>{it.source || ""}</td>
                  <td style={{ fontFamily: "monospace" }}>{it.evaluated_at || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Unknown checklist items safety: show raw item JSON if meta exists */}
      {items.some((it) => it && it.meta) ? (
        <div style={{ marginTop: 8, fontSize: 12, opacity: 0.8 }}>
          * unknown fields are preserved under <span style={{ fontFamily: "monospace" }}>meta</span>
        </div>
      ) : null}
    </div>
  );
}
