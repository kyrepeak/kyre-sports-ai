from datetime import date

import pandas as pd

import nfl_passing_yards_hub_v42 as hub


class _FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.selectbox = None

    def markdown(self, *args, **kwargs):
        return None

    def caption(self, *args, **kwargs):
        return None


def test_visible_selector_uses_full_verified_slate_and_forwards_choice(monkeypatch):
    fake = _FakeStreamlit()
    observed = {}

    games = pd.DataFrame(
        [
            {"away_team": "Alpha", "home_team": "One", "tip_et": "1:00 PM ET"},
            {"away_team": "Bravo", "home_team": "Two", "tip_et": "4:05 PM ET"},
            {"away_team": "Charlie", "home_team": "Three", "tip_et": "8:20 PM ET"},
        ]
    )

    def original_selectbox(label, options, *args, **kwargs):
        observed["label"] = label
        observed["options"] = list(options)
        observed["format_func"] = kwargs.get("format_func")
        return list(options)[1]

    fake.selectbox = original_selectbox
    monkeypatch.setattr(hub, "st", fake)
    monkeypatch.setattr(hub.prior, "_selected_date", lambda: date(2026, 9, 20))
    monkeypatch.setattr(
        hub.nfl,
        "load_nfl_slate",
        lambda day: (games, {"request_ok": True, "games": 3}),
    )
    monkeypatch.setattr(
        hub.phoenix_display,
        "_phoenix_matchup_option",
        lambda option, slate_date: f"PHX::{option}",
    )

    chosen = hub._render_visible_matchup_navigation(original_selectbox)

    assert observed["label"] == "Choose matchup • 3 verified games"
    assert observed["options"] == [
        "Alpha @ One • 1:00 PM ET",
        "Bravo @ Two • 4:05 PM ET",
        "Charlie @ Three • 8:20 PM ET",
    ]
    assert chosen == "Bravo @ Two • 4:05 PM ET"
    assert fake.session_state[hub.prior.V8_MATCHUP_KEY] == chosen
    assert observed["format_func"](observed["options"][0]) == (
        "PHX::Alpha @ One • 1:00 PM ET"
    )


def test_visible_choice_drives_frozen_v8_selector_and_restores_guard(monkeypatch):
    fake = _FakeStreamlit()
    original_selectbox = lambda label, options, *args, **kwargs: list(options)[0]
    fake.selectbox = original_selectbox
    monkeypatch.setattr(hub, "st", fake)

    chosen = "Bravo @ Two • 4:05 PM ET"
    monkeypatch.setattr(
        hub,
        "_render_visible_matchup_navigation",
        lambda selectbox: chosen,
    )

    original_identity = lambda game, season_year: {"ready": True}
    monkeypatch.setattr(hub.identity, "resolve_matchup_identity", original_identity)

    observed = {}

    def prior_render():
        observed["choice"] = fake.selectbox(
            "Verified matchup",
            ["Alpha @ One • 1:00 PM ET", chosen],
        )
        observed["identity_during"] = hub.identity.resolve_matchup_identity
        return "rendered"

    monkeypatch.setattr(hub.prior, "render_nfl_passing_yards_hub", prior_render)

    result = hub.render_nfl_passing_yards_hub()

    assert result == "rendered"
    assert observed["choice"] == chosen
    assert observed["identity_during"] is hub._resolve_matchup_identity_step7
    assert fake.selectbox is original_selectbox
    assert hub.identity.resolve_matchup_identity is original_identity
