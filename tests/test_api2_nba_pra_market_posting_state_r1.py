from pathlib import Path
from datetime import date

from sports_api.api import nba_pra_market_provider_independence_v1 as api
import nba_pra_page1_provider_independence_v1 as page


def test_upcoming_provider_no_pra_is_market_not_posted_yet(monkeypatch):
    monkeypatch.setattr(api.prior, "_fetch_fanduel_pra_observations", lambda _: ([], "FANDUEL_NO_PRA"))
    monkeypatch.setattr(api, "_fetch_draftkings_pra_observations", lambda _: ([], "DRAFTKINGS_ACCESS_FAILURE:HTTPStatusError"))
    monkeypatch.setattr(api, "_reference_recent_participant_profiles", lambda _: ({"p1": {"player_name": "Player One", "team": "PHX", "season_baseline": {"games": 1, "pra": 20.0}}}, "RECENT_PARTICIPANTS_1"))
    payload = api.collect_nba_pra_market(date(2026, 10, 24))
    assert payload["ready"] is False
    assert payload["diagnostic_state"] == "MARKET_NOT_POSTED_YET"
    assert payload["global_market_state_reason"] == "UPCOMING_MARKET_NOT_POSTED_YET"
    assert payload["fabrication"] is False


def test_real_market_still_wins_over_posting_state(monkeypatch):
    rows = [{"sportsbook": "FanDuel", "player_name": "Player One", "side": "over", "line": 30.5, "price": -110}]
    monkeypatch.setattr(api.prior, "_fetch_fanduel_pra_observations", lambda _: (rows, "FANDUEL_OK"))
    payload = api.collect_nba_pra_market(date(2026, 10, 24))
    assert payload["ready"] is True
    assert payload["diagnostic_state"] == "OK"
    assert payload["global_market_state_reason"] == "MARKET_AVAILABLE"


def test_page_rechecks_only_when_market_not_posted():
    pending = {"market": {}, "sources": {"kyre_sports_api": {"diagnostic_state": "MARKET_NOT_POSTED_YET"}}}
    active = {"market": {"p1": {"featured_quote": {"line": 30.5}}}, "sources": {"kyre_sports_api": {"diagnostic_state": "OK"}}}
    assert page.should_auto_refresh_market(pending) is True
    assert page.should_auto_refresh_market(active) is False


def test_page_declares_60_second_market_recheck():
    source = Path("nba_pra_page1_provider_independence_v1.py").read_text()
    assert "st_autorefresh" in source
    assert "60000" in source or "60_000" in source
