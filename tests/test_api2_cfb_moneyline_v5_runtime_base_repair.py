from datetime import date
from pathlib import Path

import cfb_moneyline_clean_page_v5 as v5
import cfb_moneyline_clean_page_v6 as page


def test_v6_render_uses_v1_runtime_base_without_attribute_error(monkeypatch):
    """Regression for the live Streamlit AttributeError in V5 render bootstrap."""
    v1 = page.prior.prior.prior.prior.prior

    monkeypatch.setattr(page.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(page.st, "date_input", lambda *args, **kwargs: date(2026, 10, 18))
    monkeypatch.setattr(page.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(v1.schedule_v3, "load_with_diagnostics", lambda selected_day: ([], {}))

    page.render_moneyline_hub()


def test_v6_preserves_frozen_v5_model_contract():
    assert page.FROZEN_MONEYLINE_OWNER == v5.FROZEN_MONEYLINE_OWNER
    assert page.FROZEN_RAW_MODEL == v5.FROZEN_RAW_MODEL
    assert page.FROZEN_FINAL_MODEL == v5.FROZEN_FINAL_MODEL
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False


def test_live_loader_routes_cfb_moneyline_to_v6_runtime_repair():
    source = Path("universal_runtime_v5_loader_v17.py").read_text()
    assert 'page = importlib.import_module("cfb_moneyline_clean_page_v6")' in source
    assert 'route.sport_id == "cfb" and route.market_id == "moneyline"' in source
