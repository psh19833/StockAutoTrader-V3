const BLOCKER_LABELS = {
  SESSION_REGULAR_MARKET: "정규장 아님 또는 정규장 조건 미충족",
  OPEN_ORDER_PENDING: "미체결 주문 존재 또는 미체결 상태 확인 필요",
  KIS_REST_AVAILABLE: "KIS REST 데이터 사용 불가",
  KIS_REST_FRESH: "KIS REST 데이터 최신 아님",
  KIS_WS_AVAILABLE: "KIS WS 연결/가용성 부족",
  KIS_WS_FRESH: "KIS WS 데이터 최신 아님",
  MARKET_REGIME_KNOWN: "시장 레짐 미확인",
  OPEN_ORDER_RECONCILIATION_KNOWN: "미체결 주문 재확인 불가",
};

const REASON_LABELS = {
  SESSION_STATE_NOT_REGULAR_MARKET: "현재 세션이 정규장이 아니어서 주문 제출 차단",
  LIVE_TRADING_ENABLED: "실거래 기능 비활성",
  TOKEN_EXPIRED: "토큰 만료",
  TOKEN_CACHE_UNAVAILABLE: "토큰 캐시 없음",
  TOKEN_CACHE_ERROR: "토큰 캐시 오류",
  SELECTED_CANDIDATE_MISSING: "선정된 후보 없음",
  STRATEGY_NOT_BUY: "전략이 BUY가 아님",
  RISK_NOT_APPROVED: "리스크 승인 없음",
  BALANCE_UNAVAILABLE: "잔고 정보 없음",
  ORDERABLE_UNAVAILABLE: "주문 가능 금액 없음",
  CASH_UNAVAILABLE: "현금 주문 가능 금액 없음",
  ACCOUNT_PARTS_INVALID: "계좌 8/2 분리 오류",
  MARKET_REGIME_UNKNOWN: "시장 레짐 미확인",
  REST_SNAPSHOT_NOT_FRESH: "REST 스냅샷 최신 아님",
  WS_SNAPSHOT_NOT_FRESH: "WS 스냅샷 최신 아님",
};

function yn(value) {
  return value ? "예" : "아니오";
}

function humanReason(code) {
  return REASON_LABELS[code] || code || "-";
}

function humanBlocker(code) {
  return BLOCKER_LABELS[code] || code || "-";
}

export default function LiveReadinessCard({ summary, runtimeStatus }) {
  const livePipeline = summary?.live_pipeline_summary || {};
  const orderState = summary?.order_submit_state || {};
  const status = runtimeStatus || summary?.runtime_status || {};
  const orderChecks = status?.order_submit_checks || orderState?.checks || {};
  const blockers = status?.live_start_blockers || summary?.live_start_blockers || [];
  const selectedSymbol = livePipeline?.selected_candidate?.symbol || orderChecks?.selected_symbol || "";
  const selectedProductType = livePipeline?.selected_candidate?.product_type || orderChecks?.product_type || "";
  const restAvailable = !!summary?.data_router?.rest_available;
  const restFresh = !!summary?.data_router?.rest_snapshot_fresh;
  const wsAvailable = summary?.ws_status?.connection_state === "CONNECTED" || !!summary?.ws_status?.snapshot_fresh;
  const wsFresh = !!summary?.ws_status?.snapshot_fresh;
  const marketRegimeKnown = !!summary?.market_regime && summary.market_regime.regime !== "UNKNOWN";
  const openOrderKnown = !!orderChecks?.open_order_state_known;
  const openOrderPending = !!orderChecks?.open_order_pending;
  const openOrderSource = orderChecks?.open_order_state_source || "";
  const openOrderReason = orderChecks?.open_order_state_reason || "";
  const openOrderBlocker = orderChecks?.open_order_state_blocker || "";
  const runtimeSession = status?.session || "-";
  const marketSession = summary?.session?.session_state || "UNKNOWN";

  return (
    <div className="card">
      <h3>라이브 준비 상태</h3>
      <p>runtime running: <span className={status?.running ? "danger" : "safe"}>{yn(status?.running)}</span></p>
      <p>실행 대상 세션(runtime): {runtimeSession}</p>
      <p>현재 시장 세션(summary.session): {marketSession}</p>
      <p>mode: {status?.mode || "-"}</p>
      <p>live_auto_ready: <span className={summary?.live_auto_ready ? "safe" : "warn"}>{yn(summary?.live_auto_ready)}</span></p>
      <p>blockers:</p>
      <ul style={{ marginTop: 4, paddingLeft: 18 }}>
        {(blockers || []).length ? blockers.map((code) => (
          <li key={code}>
            {humanBlocker(code)} <span style={{ fontSize: 12, opacity: 0.7 }}>({code})</span>
          </li>
        )) : <li>없음</li>}
      </ul>
      <p>order_submit_enabled: <span className={orderState?.order_submit_enabled ? "safe" : "warn"}>{yn(orderState?.order_submit_enabled)}</span></p>
      <p>reason: {humanReason(orderState?.order_submit_enabled_reason || status?.order_submit_enabled_reason || "")}</p>
      <p style={{ fontSize: 12, opacity: 0.7 }}>원문: {orderState?.order_submit_enabled_reason || status?.order_submit_enabled_reason || "-"}</p>
      <p>next blocking: {humanReason(orderState?.next_blocking_point || "")}</p>
      <p style={{ fontSize: 12, opacity: 0.7 }}>원문: {orderState?.next_blocking_point || "-"}</p>
      <p>selected: {selectedSymbol || "-"}{selectedProductType ? ` (${selectedProductType})` : ""}</p>
      <p>REST available/fresh: {yn(restAvailable)} / {yn(restFresh)}</p>
      <p>WS available/fresh: {yn(wsAvailable)} / {yn(wsFresh)}</p>
      <p>market_regime_known: {yn(marketRegimeKnown)}</p>
      <p>open_order_recon_known: {yn(openOrderKnown)}</p>
      <p>open order pending: {yn(openOrderPending)}</p>
      <p>open order source: {openOrderSource || "-"}</p>
      <p>open order reason: {openOrderReason || "-"}</p>
      <p>open order blocker: {openOrderBlocker || "-"}</p>
      <p>risk/strategy/buy: {yn(orderChecks?.risk_allowed)} / {yn(orderChecks?.strategy_buy)} / {yn(orderChecks?.allow_new_buy)}</p>
      {orderState?.order_submit_enabled_reason && (
        <p style={{ fontSize: 12, color: "#8b949e", marginTop: 8, borderTop: "1px solid #30363d", paddingTop: 6 }}>
          {orderState.order_submit_enabled_reason}
        </p>
      )}
    </div>
  );
}
