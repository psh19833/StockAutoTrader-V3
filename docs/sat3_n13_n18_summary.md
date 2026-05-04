# SAT3 N13-N18 Documentation Summary

## N13 — Safety Gate
Multi-layer order blocking: LIVE_TRADING_ENABLED, Emergency Stop, Session, Regime, Stale data, Max loss/position, Duplicate, WS disconnect.

## N14 — Order API
Guarded KIS cash order submission. TR_ID: TTTC0012U (buy), TTTC0011U (sell). SafetyGate required.

## N15 — Fill Reconciliation
Three-way: WS fill notice (provisional) + REST fills + REST balance → confirmed.

## N16 — Exit Strategy
Stop loss (-3%), Take profit (+5%), Trailing stop. SafetyGate required.

## N17 — Small Order Validation
1-share test with --confirm-live-order flag. Dry-run default.

## N18 — Performance Analytics
Win rate, profit factor, drawdown, strategy/regime grouping.
