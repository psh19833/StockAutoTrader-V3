import React, { useState, useEffect } from "react";
import { fetchDashboardSummary } from "../api/dashboardApi";
import SystemStatusCard from "../components/dashboard/SystemStatusCard";
import SessionStatusCard from "../components/dashboard/SessionStatusCard";
import MarketRegimeCard from "../components/dashboard/MarketRegimeCard";
import WebSocketStatusCard from "../components/dashboard/WebSocketStatusCard";
import DataRouterStatusCard from "../components/dashboard/DataRouterStatusCard";
import DataQualityWarningsCard from "../components/dashboard/DataQualityWarningsCard";
import ScannerCandidatesTable from "../components/dashboard/ScannerCandidatesTable";
import QuantScoresTable from "../components/dashboard/QuantScoresTable";
import RiskDecisionsTable from "../components/dashboard/RiskDecisionsTable";

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

  if (error) return <div className="error">Dashboard unavailable: {error.message}</div>;
  if (!data) return <div className="loading">Loading SAT3 Dashboard...</div>;

  return (
    <div className="dashboard">
      <h1>SAT3 Dashboard</h1>
      <div className="cards">
        <SystemStatusCard data={data.system} />
        <SessionStatusCard data={data.session} />
        <MarketRegimeCard data={data.market_regime} />
        <WebSocketStatusCard data={data.ws_status} />
        <DataRouterStatusCard data={data.data_router} />
        <DataQualityWarningsCard warnings={data.ws_status?.data_quality_warnings} />
      </div>
      <ScannerCandidatesTable candidates={data.candidates || []} />
      <QuantScoresTable scores={data.quant_summary || {}} />
      <RiskDecisionsTable decisions={data.risk_decisions || []} />
    </div>
  );
}
