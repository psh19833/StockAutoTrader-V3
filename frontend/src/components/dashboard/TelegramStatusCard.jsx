import { useEffect, useState } from "react";
import { fetchTelegramStatus } from "../../api/dashboardApi";

export default function TelegramStatusCard() {
  const [data, setData] = useState(null);
  useEffect(() => {
    fetchTelegramStatus().then(setData).catch(() => {});
    const t = setInterval(() => fetchTelegramStatus().then(setData).catch(() => {}), 10000);
    return () => clearInterval(t);
  }, []);

  if (!data) return <div className="card"><h3>텔레그램</h3><p>불러오는 중...</p></div>;
  const statusLabel = data.status_label || (data.connected ? "연결됨" : data.error === "external_probe_disabled" ? "조회 비활성화" : "끊김");
  const statusDetail = data.status_detail || (data.connected ? "Telegram 상태 확인 성공" : data.error === "external_probe_disabled" ? "대시보드용 외부 조회가 꺼져 있습니다." : "Telegram 연결에 실패했습니다.");
  const cls = data.connected ? "safe" : data.error === "external_probe_disabled" ? "warning" : "danger";
  return (
    <div className="card">
      <h3>텔레그램</h3>
      <p>상태: <span className={cls}>{statusLabel}</span></p>
      <p>{statusDetail}</p>
      {data.bot_name && <p>봇: {data.bot_name}</p>}
      {data.chat_id && <p>채팅방 ID: {data.chat_id}</p>}
      {data.last_message_at && <p>마지막 메시지: {data.last_message_at}</p>}
      {data.error && <p className="danger">오류: {data.error}</p>}
    </div>
  );
}
