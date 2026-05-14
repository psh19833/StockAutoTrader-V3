
export default function DataRouterStatusCard({ data }) {
  if (!data) return <div className="card"><h3>데이터 라우터</h3><p>데이터 없음</p></div>;
  return (
    <div className="card">
      <h3>데이터 라우터</h3>
      <p>출처: {data.source || "KIS_API_REST"}</p>
      <p>실시간: <span className={data.ws_connected ? "safe" : "warn"}>{data.ws_connected ? "연결됨" : "끊김"}</span></p>
      <p>REST: <span className={data.rest_available ? "safe" : "danger"}>{data.rest_available ? "가능" : "불가"}</span></p>
    </div>
  );
}
