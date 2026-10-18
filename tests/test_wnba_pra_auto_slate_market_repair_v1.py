from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pra_hub_uses_automatic_verified_slate_without_manual_date_picker():
    source = (ROOT / "wnba_pra_hub_v3616.py").read_text(encoding="utf-8")
    assert 'st.date_input("WNBA slate date"' not in source
    assert "resolve_active_slate_date" in source


def test_market_bridge_does_not_expire_same_slate_offers_after_ten_minutes():
    source = (ROOT / "wnba_pra_api_market_bridge_v1.py").read_text(encoding="utf-8")
    assert "SNAPSHOT_MAX_AGE_SECONDS = 600.0" not in source
    assert "same-slate" in source.lower()
