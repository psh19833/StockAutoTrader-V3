
const stateMap = { CONNECTED: "safe", CONNECTING: "warn", DISCONNECTED: "danger", ERROR: "danger", RECONNECTING: "warn" };
const labelMap = { CONNECTED: "연결됨", CONNECTING: "연결 중", DISCONNECTED: "끊김", ERROR: "오류", RECONNECTING: "재연결 중" };

export default function WebSocketStatusCard({ data }) {
  if (!data) return <div className="card"><h3>실시간 시세</h3><p>데이터 없음</p></div>;
  return (
    <div className="card">
      <h3>실시간 시세 (WS)</h3>
      <p>상태: <span className={stateMap[data.connection_state] || "warn"}>{labelMap[data.connection_state] || data.connection_state}</span></p>
      <p>채널: {data.subscribed_channels?.join(", ") || "없음"}</p>
      <p>재연결: {data.reconnect_count}회</p>
      {data.last_error_type && <p className="danger">오류: {data.last_error_type}</p>}
    </div>
  );
}
