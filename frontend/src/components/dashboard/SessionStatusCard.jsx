import React from "react";

export default function SessionStatusCard({ data }) {
  if (!data) return <div className="card">No session data</div>;
  return (
    <div className="card">
      <h3>Session</h3>
      <p>State: {data.session_state}</p>
      <p>Buy Allowed: <span className={data.buy_allowed ? "safe" : "warn"}>{data.buy_allowed ? "Yes" : "No"}</span></p>
      <p>Trading Day: {data.is_trading_day ? "Yes" : "No"}</p>
    </div>
  );
}
