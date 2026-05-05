import React, { useEffect, useState } from "react";
import { fetchAuditTimeline } from "../../api/dashboardApi";

function rowKey(e, idx) {
  const t = e.event_time || e.timestamp || "";
  return e.event_id || `${e.correlation_id || ""}-${t}-${idx}`;
}

export default function AuditTimelineList({ onSelectEvent, selectedEventId }) {
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let mounted = true;
    const load = () => {
      setLoading(true);
      return fetchAuditTimeline(50)
        .then((rows) => {
          if (!mounted) return;
          setEvents(rows || []);
          setError(null);
        })
        .catch((e) => {
          if (!mounted) return;
          setError(e);
        })
        .finally(() => {
          if (!mounted) return;
          setLoading(false);
        });
    };

    load();
    const interval = setInterval(load, 5000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  if (error) {
    return (
      <div className="card">
        <h3>Audit Timeline</h3>
        <div className="error">불러오기 실패: {error.message}</div>
      </div>
    );
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3>Audit Timeline</h3>
      <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 8 }}>
        클릭하면 상세 패널 + Evidence Checklist 표시
      </div>
      {loading ? (
        <div className="loading" style={{ fontSize: 12, opacity: 0.8 }}>불러오는 중...</div>
      ) : null}

      {(events || []).length === 0 && !loading ? (
        <div style={{ fontSize: 12, opacity: 0.8 }}>이벤트가 없습니다.</div>
      ) : null}

      <div style={{ overflowX: "auto" }}>
        <table className="table" style={{ width: "100%", minWidth: 900 }}>
          <thead>
            <tr>
              <th>time</th>
              <th>severity</th>
              <th>event_type</th>
              <th>symbol</th>
              <th>strategy_name</th>
              <th>status</th>
              <th>summary</th>
              <th>correlation_id</th>
            </tr>
          </thead>
          <tbody>
            {(events || []).map((e, idx) => {
              const key = rowKey(e, idx);
              const selected = selectedEventId && e.event_id === selectedEventId;
              return (
                <tr
                  key={key}
                  style={{ cursor: e.event_id ? "pointer" : "default", opacity: e.event_id ? 1 : 0.6, background: selected ? "#1f2937" : "transparent" }}
                  onClick={() => {
                    if (!e.event_id) return;
                    onSelectEvent && onSelectEvent(e.event_id);
                  }}
                >
                  <td>{e.event_time || e.timestamp || ""}</td>
                  <td>{e.severity || "INFO"}</td>
                  <td>{e.event_type || ""}</td>
                  <td>{e.symbol || ""}</td>
                  <td>{e.strategy_name || ""}</td>
                  <td>{e.status || ""}</td>
                  <td style={{ maxWidth: 260, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {e.summary || ""}
                  </td>
                  <td style={{ fontFamily: "monospace" }}>{e.correlation_id || ""}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div style={{ fontSize: 12, opacity: 0.7, marginTop: 8 }}>
        주의: event_id 없는 항목은 상세 조회 불가 (백엔드 저장소 미연결 시 발생)
      </div>
    </div>
  );
}
