from __future__ import annotations

import copy
import inspect

import mlb_moneyline_hub_v166 as step1
import streamlit_memory_lazy_router_v4 as router


def _official_row():
    return {
        "game_pk": 123456,
        "game_date": "2026-09-03",
        "verified": True,
        "schedule_source": "MLB Stats API V3.2",
        "away_team_id": 110,
        "away_team": "Baltimore Orioles",
        "home_team_id": 147,
        "home_team": "New York Yankees",
        "away_pitcher_id": 11,
        "away_pitcher": "Away Starter",
        "home_pitcher_id": 22,
        "home_pitcher": "Home Starter",
        "first_pitch_et": "7:15 PM",
        "venue_name": "Yankee Stadium",
        "status": "Scheduled",
    }


def _result():
    return {
        "game_pk": 123456,
        "game_date": "2026-09-03",
        "away_team_id": 110,
        "home_team_id": 147,
        "away_name": "Baltimore Orioles",
        "home_name": "New York Yankees",
        "away_pitcher": "Away Starter",
        "home_pitcher": "Home Starter",
        "first_pitch": "7:15 PM",
        "venue": "Yankee Stadium",
        "status": "Scheduled",
        "win_prob": 0.61,
    }


def test_phoenix_time_handles_dst_and_standard_time():
    assert step1._phoenix_time("2026-09-03", "7:15 PM") == "4:15 PM MST"
    assert step1._phoenix_time("2026-01-03", "7:15 PM") == "5:15 PM MST"
    assert step1._phoenix_time("2026-09-03", "TBD") == "TBD"


def test_official_game_identity_verifies_without_mutating_result():
    result = _result()
    before = copy.deepcopy(result)
    rows = {123456: _official_row()}
    lineups = {123456: {"away": 9, "home": 9}}

    ctx = step1._identity_context(result, rows, lineups)

    assert result == before
    assert ctx["grade"] == "VERIFIED"
    assert ctx["teams_match"] is True
    assert ctx["starter_text"] == "BOTH STARTERS POSTED"
    assert ctx["lineup_text"] == "BOTH LINEUPS CONFIRMED"
    assert ctx["first_pitch_phoenix"] == "4:15 PM MST"


def test_identity_fails_closed_on_team_mismatch():
    row = _official_row()
    row["home_team_id"] = 999
    ctx = step1._identity_context(_result(), {123456: row}, {})
    assert ctx["grade"] == "CHECK IDENTITY"
    assert ctx["teams_match"] is False


def test_step1_html_has_both_teams_verification_and_readiness():
    ctx = step1._identity_context(
        _result(),
        {123456: _official_row()},
        {123456: {"away": 9, "home": 0}},
    )
    html = step1._step1_html(ctx, lambda tid: f'<img data-team="{tid}">')
    assert "STEP 1 • OFFICIAL GAME IDENTITY + VERIFICATION" in html
    assert 'data-team="110"' in html
    assert 'data-team="147"' in html
    assert "4:15 PM MST" in html
    assert "MLB GAME 123456" in html
    assert "Away Starter" in html and "Home Starter" in html
    assert "1/2 LINEUPS CONFIRMED" in html
    assert "no Moneyline probability adjustment" in html


def test_step1_injection_stays_inside_existing_card():
    card = '<div class="ks-pick-card"><div class="ks-card-main">A</div><div class="ks-right">B</div></div>'
    step = '<div class="ml166-step1">STEP</div>'
    combined = step1._inject_step1(card, step)
    assert combined.count("ml166-step1") == 1
    assert combined.endswith("</div>")
    assert combined.index("ml166-step1") < combined.rindex("</div>")


def test_step1_is_presentation_only_and_builds_on_v165():
    source = inspect.getsource(step1)
    assert step1.FROZEN_MONEYLINE_PRESENTATION == "mlb_moneyline_hub_v165"
    assert "simulate_run_line" not in source
    assert "history_adjustment(" not in source
    assert "_moneyline_probabilities(" not in source
    assert "fair_odds" not in source


def test_router_v4_delegates_every_non_moneyline_route(monkeypatch):
    calls = []
    monkeypatch.setattr(router, "_BASE_MLB_ROUTE", lambda market: calls.append(market))
    router._render_mlb_v4_base("Matchup Explorer")
    router._render_mlb_v4_base("1+ Hit")
    assert calls == ["Matchup Explorer", "1+ Hit"]


def test_router_v4_routes_only_moneyline_to_v166(monkeypatch):
    calls = []

    class MoneylineModule:
        @staticmethod
        def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
            calls.append((games_df, section_header, status_info, team_logo, h))

    monkeypatch.setattr(router.frozen, "_load_mlb_schedule", lambda: ("GAMES", "2026-09-03"))
    monkeypatch.setattr(router.frozen, "_import", lambda name: MoneylineModule if name == "mlb_moneyline_hub_v166" else None)
    monkeypatch.setattr(router.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(router.frozen, "section_header", "SECTION")
    monkeypatch.setattr(router.frozen, "status_info", "STATUS")
    monkeypatch.setattr(router.frozen, "team_logo", "LOGO")
    monkeypatch.setattr(router.frozen, "h", "ESCAPE")

    router._render_mlb_v4_base("Moneyline")
    assert calls == [("GAMES", "SECTION", "STATUS", "LOGO", "ESCAPE")]
