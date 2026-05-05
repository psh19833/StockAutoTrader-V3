import React, { useEffect, useState } from "react";
import { fetchKisAccount } from "../../api/dashboardApi";

function fmt(n) { return n ? n.toLocaleString() : "0"; }

export default function KisAccountCard() {
  const [data, setData] = useState(null);
  useEffect(() => { fetchKisAccount().then(setData).catch(() => {}); }, []);

  if (!data) return <div className="card"><h3>계좌 정보</h3><p>불러오는 중...</p></div>;
  return (
    <div className="card">
      <h3>계좌 정보</h3>
      <p>계좌번호: {data.account_no}</p>
      <p>상품코드: {data.product_code}</p>
      <p>예수금: ₩{fmt(data.deposit)}</p>
      <p>평가금액: ₩{fmt(data.total_value)}</p>
      <p>매수금액: ₩{fmt(data.total_buy_amount)}</p>
      <p>보유종목: {data.holding_count}개</p>
      <p>D+2: ₩{fmt(data.d2_deposit)}</p>
      {data.stale && data.deposit === -1 && <p className="danger">KIS API 연결 실패 (휴장일 또는 네트워크 오류)</p>}
      {data.stale && data.deposit !== -1 && <p className="warn">데이터 갱신 필요</p>}
    </div>
  );
}
