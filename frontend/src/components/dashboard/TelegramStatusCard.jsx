import React, { useEffect, useState } from "react";
import { fetchTelegramStatus } from "../../api/dashboardApi";

export default function TelegramStatusCard() {
  const [data, setData] = useState(null);
  useEffect(() => {
    fetchTelegramStatus().then(setData).catch(() => {});
    const t = setInterval(() => fetchTelegramStatus().then(setData).catch(() => {}), 10000);
    return () => clearInterval(t);
  }, []);

  if (!data) return <div className="card"><h3>텔레그램</h3><p>불러오는 중...</p></div>;
  const cls = data.connected ? "safe" : "danger";
  return (
    <div className="card">
      <h3>텔레그램</h3>
      <p>상태: <span className={cls}>{data.connected ? "연결됨" : "끊김"}</span></p>
      {data.bot_name && <p>봇: {data.bot_name}</p>}
      {data.chat_id && <p>채팅방 ID: {data.chat_id}</p>}
      {data.last_message_at && <p>마지막 메시지: {data.last_message_at}</p>}
      {data.error && <p className="danger">오류: {data.error}</p>}
    </div>
  );
}
