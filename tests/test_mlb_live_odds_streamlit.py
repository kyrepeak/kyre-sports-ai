from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import mlb_live_odds_streamlit_v1 as ui


SAMPLE_PAYLOAD = {
    "data_type": "mlb_live_odds_api_response_v1",
    "schema_version": 1,
    "source": "FanDuel",
    "transport": "anonymous_public_get_only",
    "http_methods": ["GET"],
    "collected_at_utc": "2026-08-31T04:26:29+00:00",
    "game_count": 1,
    "games": [
        {
            "official_game_id": 824473,
            "scheduled_start_utc": "2026-08-31T22:40:00Z",
            "away_team": {"id": 135, "name": "San Diego Padres"},
            "home_team": {"id": 113, "name": "Cincinnati Reds"},
            "sportsbook": "FanDuel",
            "fully_priced": True,
            "markets": {
                "moneyline": {"away_odds": -148, "home_odds": 126},
                "run_line": {
                    "away_line": -1.5,
                    "away_odds": 112,
                    "home_line": 1.5,
                    "home_odds": -134,
                },
                "total": {"line": 9.0, "over_odds": -120, "under_odds": -102},
            },
        }
    ],
}


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_fetch_live_mlb_odds_uses_certified_endpoint_contract():
    seen = {}

    def fake_get(url, **kwargs):
        seen["url"] = url
        seen.update(kwargs)
        return FakeResponse(SAMPLE_PAYLOAD)

    result = ui.fetch_live_mlb_odds(base_url="https://example.test/", request_get=fake_get)

    assert seen["url"] == "https://example.test/api/v1/mlb/odds"
    assert seen["params"] == {"max_events": 30, "fully_priced_only": "true"}
    assert seen["timeout"] == 25
    assert result["source"] == "FanDuel"


def test_fetch_live_mlb_odds_rejects_wrong_schema():
    bad = dict(SAMPLE_PAYLOAD, schema_version=2)

    with pytest.raises(ui.MLBLiveOddsUIError, match="unsupported schema"):
        ui.fetch_live_mlb_odds(
            base_url="https://example.test",
            request_get=lambda *args, **kwargs: FakeResponse(bad),
        )


def test_build_game_cards_formats_core_markets():
    cards = ui.build_game_cards(SAMPLE_PAYLOAD)

    assert len(cards) == 1
    card = cards[0]
    assert card["matchup"] == "San Diego Padres @ Cincinnati Reds"
    assert card["moneyline"] == {"away": "-148", "home": "+126"}
    assert card["run_line"]["away_line"] == "-1.5"
    assert card["run_line"]["home_line"] == "+1.5"
    assert card["total"] == {"line": "9", "over": "-120", "under": "-102"}


def test_format_helpers_keep_signs_market_appropriate():
    assert ui.format_american_odds(105) == "+105"
    assert ui.format_american_odds(-110) == "-110"
    assert ui.format_line(1.5, signed=True) == "+1.5"
    assert ui.format_line(-1.5, signed=True) == "-1.5"
    assert ui.format_line(9.0) == "9"
    assert ui.format_line(8.5) == "8.5"


def test_isolated_streamlit_page_renders_odds_cards():
    script = f'''\
import mlb_live_odds_streamlit_v1 as ui
payload = {SAMPLE_PAYLOAD!r}
ui._cached_live_mlb_odds = lambda base_url: payload
ui.render_mlb_live_odds_page()
'''
    at = AppTest.from_string(script).run(timeout=15)

    assert not at.exception
    assert len(at.metric) == 2
    assert at.metric[0].label == "Fully priced games"
    assert at.metric[0].value == "1"
    markdown_values = [element.value for element in at.markdown]
    assert any("MLB Live Odds" in value for value in markdown_values)
    assert any("San Diego Padres @ Cincinnati Reds" in value for value in markdown_values)


def test_lazy_router_waits_until_page_config_before_sidebar_ui():
    source = Path("streamlit_memory_lazy_router_v1.py").read_text(encoding="utf-8")
    render_app = source.index("def render_app()")
    page_config = source.index("st.set_page_config(", render_app)
    sidebar = source.index("st.sidebar.button", page_config)

    assert render_app < page_config < sidebar
    assert "ks_mlb_live_odds_route" in source
    assert "render_mlb_live_odds_page" in source
