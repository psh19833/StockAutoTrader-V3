import React from "react";

export default function SessionStatusCard({ data }) {
  if (!data) return <div className="card">데이터 없음</div>;
  return (
    <div className="card">
      <h3>장 세션</h3>
      <p>상태: {data.session_state}</p>
      <p>신규매수: <span className={data.buy_allowed ? "safe" : "warn"}>{data.buy_allowed ? "가능" : "차단"}</span></p>
      <p>거래일: {data.is_trading_day ? "예" : "아니오"}</p>
    </div>
  );
}
