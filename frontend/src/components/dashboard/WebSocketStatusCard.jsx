import React from "react";

const statusClass = (s) => ({ CONNECTED: "safe", CONNECTING: "warn", DISCONNECTED: "danger", ERROR: "danger", RECONNECTING: "warn" }[s] || "warn");

export default function WebSocketStatusCard({ data }) {
  if (!data) return <div className="card"><h3>WebSocket</h3><p>No data</p></div>;
  return (
    <div className="card">
      <h3>WebSocket</h3>
      <p>State: <span className={statusClass(data.connection_state)}>{data.connection_state}</span></p>
      <p>Channels: {data.subscribed_channels?.join(", ") || "none"}</p>
      <p>Reconnects: {data.reconnect_count}</p>
      {data.last_error_type && <p className="danger">Error: {data.last_error_type}</p>}
    </div>
  );
}
