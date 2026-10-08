from __future__ import annotations

import importlib.util
from pathlib import Path
from urllib.parse import parse_qs, urlparse

MODULE_PATH = Path("devsystem/nfl_rb_wr_render_repair_step4_mobile_route_v1.py")


def _load_module():
    assert MODULE_PATH.exists(), "Step 4 mobile-route cert module is missing"
    spec = importlib.util.spec_from_file_location("step4_mobile_route", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step4_contract_is_public_mobile_verification_only():
    mod = _load_module()
    assert mod.MISSION_STEP == "4/5"
    assert mod.WORKSTREAM == "nfl-rb-wr-render-repair-v1"
    assert mod.EXPECTED_PUBLIC_BASE_URL == "https://pickvault.streamlit.app"
    assert mod.VIEWPORTS == ((390, 844), (768, 1024), (1440, 1000))
    assert mod.MOBILE_VIEWPORT == (390, 844)
    assert mod.AUTO_MUTATE is False
    assert mod.MAY_MODIFY_PRODUCT_RUNTIME is False
    assert mod.GITHUB_ACTIONS_FALLBACK is False


def test_step4_routes_pin_rb_and_wr_styled_dom_contracts():
    mod = _load_module()
    assert set(mod.ROUTES) == {"Rushing Yards", "Receiving Yards"}
    rushing = mod.ROUTES["Rushing Yards"]
    receiving = mod.ROUTES["Receiving Yards"]
    assert rushing["card_selector"] == ".krush4-card"
    assert rushing["grid_selector"] == ".krush4-grid"
    assert "Projected Rush Yards" in rushing["labels"]
    assert "FanDuel Line" in rushing["labels"]
    assert receiving["card_selector"] == ".krecv13-card"
    assert receiving["grid_selector"] == ".krecv13-grid"
    assert "Projected Rec Yds" in receiving["labels"]
    assert "FanDuel Rec Yds" in receiving["labels"]


def test_route_url_uses_exact_nfl_jump_contract():
    mod = _load_module()
    url = mod.route_url("https://pickvault.streamlit.app", "Receiving Yards")
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "pickvault.streamlit.app"
    assert parse_qs(parsed.query) == {
        "ks_jump_sport": ["NFL"],
        "ks_jump_market": ["Receiving Yards"],
    }


def test_raw_text_fallback_detection_catches_the_regression_signature():
    mod = _load_module()
    assert mod.raw_text_fallback_detected("62.5Projected Rush Yards") is True
    assert mod.raw_text_fallback_detected("40.6Projected Rec Yds") is True
    assert mod.raw_text_fallback_detected("62.5\nProjected Rush Yards") is False
    assert mod.raw_text_fallback_detected("40.6 Projected Rec Yds") is False


def test_computed_card_style_contract_rejects_unstyled_and_accepts_cards():
    mod = _load_module()
    styled = {
        "count": 2,
        "border_style": "solid",
        "border_width": "1px",
        "border_radius": "17px",
        "background_image": "linear-gradient(rgb(11, 23, 18) 0%, rgb(10, 20, 17) 70%, rgb(13, 26, 20) 100%)",
        "background_color": "rgba(0, 0, 0, 0)",
    }
    assert mod.card_style_is_styled(styled) is True
    assert mod.card_style_is_styled({
        "count": 1,
        "border_style": "none",
        "border_width": "0px",
        "border_radius": "0px",
        "background_image": "none",
        "background_color": "rgba(0, 0, 0, 0)",
    }) is False
