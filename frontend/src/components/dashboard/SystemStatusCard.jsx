
export default function SystemStatusCard({ data }) {
  if (!data) return <div className="card">데이터 없음</div>;
  return (
    <div className="card">
      <h3>시스템 상태</h3>
      <p>실전매매: <span className={data.live_trading_enabled ? "danger" : "safe"}>{data.live_trading_enabled ? "활성" : "비활성"}</span></p>
      <p>비상정지: <span className={data.emergency_stop ? "danger" : "safe"}>{data.emergency_stop ? "작동 중" : "해제"}</span></p>
      <p>모듈: {data.modules_loaded ? "정상" : "오류"}</p>
      <p>테스트: {data.total_tests}건</p>
    </div>
  );
}
