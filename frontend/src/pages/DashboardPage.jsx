import React, { useState, useEffect } from "react";
import { fetchDashboardSummary } from "../api/dashboardApi";
import SystemStatusCard from "../components/dashboard/SystemStatusCard";
import SessionStatusCard from "../components/dashboard/SessionStatusCard";
import MarketRegimeCard from "../components/dashboard/MarketRegimeCard";
import WebSocketStatusCard from "../components/dashboard/WebSocketStatusCard";
import DataRouterStatusCard from "../components/dashboard/DataRouterStatusCard";
import DataQualityWarningsCard from "../components/dashboard/DataQualityWarningsCard";
import TelegramStatusCard from "../components/dashboard/TelegramStatusCard";
import KisAccountCard from "../components/dashboard/KisAccountCard";
import DailySummaryCard from "../components/dashboard/DailySummaryCard";
import StrategyBreakdownTable from "../components/dashboard/StrategyBreakdownTable";
import ScannerCandidatesTable from "../components/dashboard/ScannerCandidatesTable";
import QuantScoresTable from "../components/dashboard/QuantScoresTable";
import RiskDecisionsTable from "../components/dashboard/RiskDecisionsTable";
import LogViewer from "../components/dashboard/LogViewer";

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDashboardSummary()
      .then(setData)
      .catch(setError);
    const interval = setInterval(() => {
      fetchDashboardSummary().then(setData).catch(setError);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  if (error) return <div className="error">대시보드 연결 안 됨: {error.message}</div>;
  if (!data) return <div className="loading">SAT3 대시보드 불러오는 중...</div>;

  return (
    <div className="dashboard">
      <h1>SAT3 Dashboard</h1>

      {/* Row 1: Status Cards */}
      <div className="cards">
        <SystemStatusCard data={data.system} />
        <SessionStatusCard data={data.session} />
        <MarketRegimeCard data={data.market_regime} />
        <WebSocketStatusCard data={data.ws_status} />
        <DataRouterStatusCard data={data.data_router} />
        <TelegramStatusCard />
        <KisAccountCard />
        <DataQualityWarningsCard warnings={data.ws_status?.data_quality_warnings} />
      </div>

      {/* Row 2: Daily Summary + Strategy */}
      <div className="cards" style={{ marginTop: 16 }}>
        <DailySummaryCard />
        <StrategyBreakdownTable />
      </div>

      {/* Row 3: Scanner / Quant / Risk */}
      <div style={{ marginTop: 16 }}>
        <ScannerCandidatesTable candidates={data.candidates || []} />
        <QuantScoresTable scores={data.quant_summary || {}} />
        <RiskDecisionsTable decisions={data.risk_decisions || []} />
      </div>

      {/* Row 4: Log Viewer */}
      <div style={{ marginTop: 16 }}>
        <LogViewer />
      </div>
    </div>
  );
}
