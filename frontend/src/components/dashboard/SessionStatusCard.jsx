
export default function SessionStatusCard({ data }) {
  if (!data) return <div className="card">데이터 없음</div>;
  return (
    <div className="card">
      <h3>장 세션</h3>
      <p>상태: <span className={data.session_state === "REGULAR_MARKET" ? "safe" : "warn"}>{data.session_state}</span></p>
      <p>신규매수: <span className={data.buy_allowed ? "safe" : "warn"}>{data.buy_allowed ? "가능" : "차단"}</span></p>
      <p>거래일: {data.is_trading_day ? "예" : "아니오"}</p>
      {data.reason && <p style={{ fontSize: 12, color: "#8b949e", marginTop: 8, borderTop: "1px solid #30363d", paddingTop: 6 }}>{data.reason}</p>}
      {data.detail && <p style={{ fontSize: 11, color: "#6e7681" }}>{data.detail}</p>}
    </div>
  );
}
