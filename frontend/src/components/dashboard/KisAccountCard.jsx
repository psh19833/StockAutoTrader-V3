import React, { useEffect, useState } from "react";
import { fetchKisAccount } from "../../api/dashboardApi";

function fmt(n) { return n ? n.toLocaleString() : "0"; }

export default function KisAccountCard() {
  const [data, setData] = useState(null);
  useEffect(() => { fetchKisAccount().then(setData).catch(() => {}); }, []);

  if (!data) return <div className="card"><h3>KIS Account</h3><p>Loading...</p></div>;
  return (
    <div className="card">
      <h3>KIS Account</h3>
      <p>Account: {data.account_no}</p>
      <p>Product: {data.product_code}</p>
      <p>Deposit: ₩{fmt(data.deposit)}</p>
      <p>Total Value: ₩{fmt(data.total_value)}</p>
      <p>Buy Amount: ₩{fmt(data.total_buy_amount)}</p>
      <p>Holdings: {data.holding_count}</p>
      <p>D+2: ₩{fmt(data.d2_deposit)}</p>
      {data.stale && <p className="warn">Data may be stale</p>}
    </div>
  );
}
