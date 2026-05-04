import React from "react";

export default function SystemStatusCard({ data }) {
  if (!data) return <div className="card">No system data</div>;
  return (
    <div className="card">
      <h3>System Status</h3>
      <p>Live Trading: <span className={data.live_trading_enabled ? "danger" : "safe"}>{data.live_trading_enabled ? "ENABLED" : "DISABLED"}</span></p>
      <p>Emergency Stop: <span className={data.emergency_stop ? "danger" : "safe"}>{data.emergency_stop ? "ACTIVE" : "INACTIVE"}</span></p>
      <p>Modules: {data.modules_loaded ? "Loaded" : "Error"}</p>
      <p>Tests: {data.total_tests}</p>
    </div>
  );
}
