"""SAT3 Backend FastAPI Application.

Entry point for uvicorn: uvicorn main:app --host 127.0.0.1 --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="SAT3 Dashboard API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/dashboard/summary")
async def dashboard_summary():
    from dashboard.dashboard_routes import handle_get_summary
    return handle_get_summary()


@app.get("/api/dashboard/system")
async def dashboard_system():
    from dashboard.dashboard_routes import handle_get_system
    return handle_get_system()


@app.get("/api/dashboard/session")
async def dashboard_session():
    from dashboard.dashboard_routes import handle_get_session
    return handle_get_session()


@app.get("/api/dashboard/market-regime")
async def dashboard_market_regime():
    from dashboard.dashboard_routes import handle_get_market_regime
    return handle_get_market_regime()


@app.get("/api/dashboard/ws-status")
async def dashboard_ws_status():
    from dashboard.dashboard_routes import handle_get_system
    return {"connection_state": "DISCONNECTED", "subscribed_channels": []}


@app.get("/api/dashboard/candidates")
async def dashboard_candidates():
    from dashboard.dashboard_routes import handle_get_candidates
    return handle_get_candidates()


@app.get("/api/dashboard/quant-scores")
async def dashboard_quant_scores():
    from dashboard.dashboard_routes import handle_get_quant_scores
    return handle_get_quant_scores()


@app.get("/api/dashboard/risk-decisions")
async def dashboard_risk_decisions():
    from dashboard.dashboard_routes import handle_get_risk_decisions
    return handle_get_risk_decisions()


@app.get("/api/dashboard/orders")
async def dashboard_orders():
    from dashboard.dashboard_routes import handle_get_orders
    return handle_get_orders()


@app.get("/api/dashboard/fills")
async def dashboard_fills():
    from dashboard.dashboard_routes import handle_get_fills
    return handle_get_fills()


@app.get("/api/dashboard/portfolio")
async def dashboard_portfolio():
    from dashboard.dashboard_routes import handle_get_portfolio
    return handle_get_portfolio()


@app.get("/api/dashboard/eod")
async def dashboard_eod():
    from dashboard.dashboard_routes import handle_get_eod_latest
    return handle_get_eod_latest()


@app.get("/api/dashboard/audit")
async def dashboard_audit(limit: int = 50):
    from dashboard.dashboard_routes import handle_get_audit_timeline
    return handle_get_audit_timeline(limit)


@app.get("/health")
async def health():
    return {"status": "ok"}
