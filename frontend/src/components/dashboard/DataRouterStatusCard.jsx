import React from "react";

export default function DataRouterStatusCard({ data }) {
  if (!data) return <div className="card"><h3>Data Router</h3><p>No data</p></div>;
  return (
    <div className="card">
      <h3>Data Router</h3>
      <p>Source: {data.source || "KIS_API_REST"}</p>
      <p>WS: <span className={data.ws_connected ? "safe" : "warn"}>{data.ws_connected ? "Connected" : "Disconnected"}</span></p>
      <p>REST: <span className={data.rest_available ? "safe" : "danger"}>{data.rest_available ? "Available" : "Unavailable"}</span></p>
    </div>
  );
}
