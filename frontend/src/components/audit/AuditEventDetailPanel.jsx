import { useEffect, useState } from "react";
import { fetchAuditEventDetail } from "../../api/dashboardApi";
import EvidenceChecklistCard from "./EvidenceChecklistCard";
import SanitizedJsonCollapse from "./SanitizedJsonCollapse";

export default function AuditEventDetailPanel({ eventId }) {
  const [result, setResult] = useState({ eventId: null, detail: null, error: null });

  useEffect(() => {
    let cancelled = false;

    if (eventId) {
      fetchAuditEventDetail(eventId)
        .then((detail) => {
          if (!cancelled) {
            setResult({ eventId, detail, error: null });
          }
        })
        .catch((error) => {
          if (!cancelled) {
            setResult({ eventId, detail: null, error });
          }
        });
    }

    return () => {
      cancelled = true;
    };
  }, [eventId]);

  const isCurrentResult = result.eventId === eventId;
  const detail = isCurrentResult ? result.detail : null;
  const error = isCurrentResult ? result.error : null;

  if (!eventId) {
    return (
      <div className="card" style={{ marginTop: 16 }}>
        <h3>Event Detail</h3>
        <div style={{ fontSize: 12, opacity: 0.8 }}>
          Timeline에서 이벤트를 선택하면 상세 + Evidence Checklist가 표시됩니다.
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card" style={{ marginTop: 16 }}>
        <h3>Event Detail</h3>
        <div className="error">불러오기 실패: {error.message}</div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="card" style={{ marginTop: 16 }}>
        <h3>Event Detail</h3>
        <div className="loading">불러오는 중...</div>
      </div>
    );
  }

  return (
    <div style={{ marginTop: 16 }}>
      <div className="card">
        <h3>Event Detail</h3>

        <div style={{ fontSize: 12, opacity: 0.9 }}>
          <div>
            event_id: <span style={{ fontFamily: "monospace" }}>{detail.event_id || ""}</span>
          </div>
          <div>
            correlation_id: <span style={{ fontFamily: "monospace" }}>{detail.correlation_id || ""}</span>
          </div>
          <div>
            event_type: <span style={{ fontFamily: "monospace" }}>{detail.event_type || ""}</span>
          </div>
          <div>
            severity: <span style={{ fontFamily: "monospace" }}>{detail.severity || "INFO"}</span>
          </div>
          <div>
            timestamp: <span style={{ fontFamily: "monospace" }}>{detail.timestamp || ""}</span>
          </div>
          <div>
            symbol: <span style={{ fontFamily: "monospace" }}>{detail.symbol || ""}</span>
          </div>
          {detail.strategy_name ? (
            <div>
              strategy_name: <span style={{ fontFamily: "monospace" }}>{detail.strategy_name}</span>
            </div>
          ) : null}
          {detail.status ? (
            <div>
              status: <span style={{ fontFamily: "monospace" }}>{detail.status}</span>
            </div>
          ) : null}
          {detail.summary ? <div>summary: {detail.summary}</div> : null}
        </div>

        <EvidenceChecklistCard checklist={detail.checklist} />

        <div className="card" style={{ marginTop: 12 }}>
          <h3>Related Events (correlation_id)</h3>
          <div style={{ overflowX: "auto" }}>
            <table className="table" style={{ width: "100%", minWidth: 800 }}>
              <thead>
                <tr>
                  <th>time</th>
                  <th>severity</th>
                  <th>event_type</th>
                  <th>symbol</th>
                  <th>summary</th>
                  <th>event_id</th>
                </tr>
              </thead>
              <tbody>
                {(detail.related_events || []).map((e, idx) => (
                  <tr key={e.event_id || idx}>
                    <td>{e.timestamp || ""}</td>
                    <td>{e.severity || ""}</td>
                    <td>{e.event_type || ""}</td>
                    <td>{e.symbol || ""}</td>
                    <td style={{ maxWidth: 260, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {e.summary || ""}
                    </td>
                    <td style={{ fontFamily: "monospace" }}>{e.event_id || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <SanitizedJsonCollapse data={detail.payload_sanitized} />
      </div>
    </div>
  );
}
