import React, { useEffect, useState } from "react";
import { fetchTelegramStatus } from "../../api/dashboardApi";

export default function TelegramStatusCard() {
  const [data, setData] = useState(null);
  useEffect(() => {
    fetchTelegramStatus().then(setData).catch(() => {});
    const t = setInterval(() => fetchTelegramStatus().then(setData).catch(() => {}), 10000);
    return () => clearInterval(t);
  }, []);

  if (!data) return <div className="card"><h3>Telegram</h3><p>Loading...</p></div>;
  const cls = data.connected ? "safe" : "danger";
  return (
    <div className="card">
      <h3>Telegram</h3>
      <p>Status: <span className={cls}>{data.connected ? "CONNECTED" : "DISCONNECTED"}</span></p>
      {data.bot_name && <p>Bot: {data.bot_name}</p>}
      {data.chat_id && <p>Chat ID: {data.chat_id}</p>}
      {data.last_message_at && <p>Last: {data.last_message_at}</p>}
      {data.error && <p className="danger">{data.error}</p>}
    </div>
  );
}
