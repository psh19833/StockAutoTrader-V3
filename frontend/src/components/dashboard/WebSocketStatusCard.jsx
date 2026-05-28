
const stateMap = { CONNECTED: "safe", CONNECTING: "warn", DISCONNECTED: "danger", ERROR: "danger", RECONNECTING: "warn", UNKNOWN: "warn" };
const labelMap = { CONNECTED: "연결됨", CONNECTING: "연결 중", DISCONNECTED: "끊김", ERROR: "오류", RECONNECTING: "재연결 중", UNKNOWN: "알 수 없음" };

export default function WebSocketStatusCard({ data }) {
  if (!data) return <div className="card"><h3>실시간 시세</h3><p>데이터 없음</p></div>;
  const reconnectCount = Number.isFinite(data.reconnect_count) ? data.reconnect_count : 0;
  const statusReason = data.status_reason || data.last_error_type || data.data_source || "";
  return (
    <div className="card">
      <h3>실시간 시세 (WS)</h3>
      <p>상태: <span className={stateMap[data.connection_state] || "warn"}>{labelMap[data.connection_state] || data.connection_state || "UNKNOWN"}</span></p>
      <p>채널: {data.subscribed_channels?.join(", ") || "없음"}</p>
      <p>재연결: {reconnectCount}회</p>
      <p>fresh: {data.snapshot_fresh ? "예" : "아니오"}</p>
      <p>source: {data.data_source || "-"}</p>
      {statusReason ? <p className={data.connection_state === "DISCONNECTED" || data.connection_state === "ERROR" ? "danger" : "warn"}>사유: {statusReason}</p> : null}
    </div>
  );
}
