# SAT3 Runtime Scheduler (N12)

Session-aware execution plans. Phase: N12.

| Session | Scan | Evaluate | New Buy | EOD |
|---------|------|----------|---------|-----|
| REGULAR_MARKET | ✓ | ✓ | ✓ | - |
| PRE_MARKET | Prepare | - | - | - |
| LATE_MARKET | - | - | Blocked | - |
| CLOSED_AFTER | - | - | - | ✓ |
| UNKNOWN | Block All | Block All | Block All | - |
