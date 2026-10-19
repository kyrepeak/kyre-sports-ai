from datetime import date

import cfb_moneyline_clean_page_v5 as page


def test_v5_render_uses_v1_runtime_base_without_attribute_error(monkeypatch):
    """Regression for the live Streamlit crash in V5 render bootstrap."""
    v1 = page.prior.prior.prior.prior

    monkeypatch.setattr(page.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(page.st, "date_input", lambda *args, **kwargs: date(2026, 10, 18))
    monkeypatch.setattr(page.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(v1.schedule_v3, "load_with_diagnostics", lambda selected_day: ([], {}))

    page.render_moneyline_hub()
