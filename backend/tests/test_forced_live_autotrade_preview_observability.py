import json


def test_fixture_preview_contains_observability_fields():
    # Must be pure/local: fixture mode should not require network/KIS.
    from scripts.forced_live_autotrade_preview import run_preview

    report = run_preview(mode="fixture", symbol="005930")

    assert report["actual_order_submitted"] is False

    # Scanner observability
    assert "scanner" in report
    assert "debug" in report["scanner"]
    assert report["scanner"]["debug"]["stocks_built_count"] is not None

    # Universe observability
    assert "universe" in report
    for k in ("requested_top_n", "raw_row_count", "parsed_symbol_count", "used_symbol_count", "sample_count", "limit_reason"):
        assert k in report["universe"]

    # Ensure no secrets in report serialization
    s = json.dumps(report, ensure_ascii=False)
    for bad in ("app_secret", "APP_SECRET", "access_token", "Bearer "):
        assert bad not in s
