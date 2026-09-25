import pandas as pd

import nfl_hub_v1 as nfl_base
import nfl_passing_yards_hub_v8 as frozen_v8
import nfl_passing_yards_full_slate_router_v1 as router
import nfl_passing_yards_hub_v42 as hub


def _frame(ids):
    return pd.DataFrame(
        [
            {
                "game_id": str(game_id),
                "game_date": "2026-09-20",
                "away_team": f"Away {game_id}",
                "home_team": f"Home {game_id}",
                "tip_et": "1:00 PM ET",
            }
            for game_id in ids
        ]
    )


def test_incomplete_daily_slate_is_completed_by_official_week_route():
    primary = _frame(range(1, 12))
    weekly = _frame(range(1, 15))

    games, diag = router.load_full_slate(
        "2026-09-20",
        primary_loader=lambda day: (
            primary,
            {"request_ok": True, "provider": "daily", "games": len(primary)},
        ),
        schedule_loader=lambda day: {
            "ready": True,
            "expected_games": 14,
            "season": 2026,
            "week": 3,
            "season_type": 2,
        },
        weekly_loader=lambda day, meta: (
            weekly,
            {"request_ok": True, "provider": "weekly", "games": len(weekly), "http": 200},
        ),
    )

    assert len(games) == 14
    assert games["game_id"].nunique() == 14
    assert diag["fallback_used"] is True
    assert diag["primary_games"] == 11
    assert diag["weekly_games"] == 14
    assert diag["expected_games"] == 14


def test_complete_daily_slate_does_not_call_fallback():
    primary = _frame(range(1, 15))

    def forbidden_weekly(day, meta):
        raise AssertionError("weekly fallback must not run for complete primary slate")

    games, diag = router.load_full_slate(
        "2026-09-20",
        primary_loader=lambda day: (
            primary,
            {"request_ok": True, "provider": "daily", "games": len(primary)},
        ),
        schedule_loader=lambda day: {
            "ready": True,
            "expected_games": 14,
            "season": 2026,
            "week": 3,
            "season_type": 2,
        },
        weekly_loader=forbidden_weekly,
    )

    assert len(games) == 14
    assert diag["fallback_used"] is False


def test_v42_scopes_full_slate_loader_through_frozen_render(monkeypatch):
    chosen = "Away 14 @ Home 14 • 1:00 PM ET"
    original_loader = hub.nfl.load_nfl_slate
    observed = {}

    monkeypatch.setattr(hub, "_render_visible_matchup_navigation", lambda selectbox: chosen)

    def prior_render():
        observed["loader_is_full"] = hub.nfl.load_nfl_slate is hub._load_full_slate
        observed["selected"] = hub.st.selectbox(
            "Verified matchup",
            ["Away 1 @ Home 1 • 1:00 PM ET", chosen],
        )
        return "rendered"

    monkeypatch.setattr(hub.prior, "render_nfl_passing_yards_hub", prior_render)
    monkeypatch.setattr(hub.identity, "resolve_matchup_identity", lambda game, year: {})
    monkeypatch.setattr(
        hub.st,
        "selectbox",
        lambda label, options, *args, **kwargs: list(options)[0],
    )

    result = hub.render_nfl_passing_yards_hub()

    assert result == "rendered"
    assert observed["loader_is_full"] is True
    assert observed["selected"] == chosen
    assert hub.nfl.load_nfl_slate is original_loader


def test_v42_pins_primary_loader_to_immutable_nfl_base():
    assert hub._ORIGINAL_LOAD_NFL_SLATE is nfl_base.load_nfl_slate


def test_v42_visible_labels_do_not_read_mutable_shared_alias(monkeypatch):
    frame = pd.DataFrame(
        [
            {
                "game_id": "2026_03_ATL_GB",
                "away_team": "Atlanta Falcons",
                "home_team": "Green Bay Packers",
                "tip_et": "8:15 PM ET",
            }
        ]
    )
    seen = {}

    def fake_full_slate(day_str, *, primary_loader):
        seen["day"] = day_str
        seen["primary_loader"] = primary_loader
        return frame, {"request_ok": True, "games": 1}

    monkeypatch.setattr(hub.full_slate, "load_full_slate", fake_full_slate)
    monkeypatch.setattr(
        hub.nfl,
        "load_nfl_slate",
        lambda day: (pd.DataFrame(), {"request_ok": True, "games": 0}),
    )

    labels, diag = hub._verified_matchup_labels(pd.Timestamp("2026-09-24").date())

    assert labels == ["Atlanta Falcons @ Green Bay Packers • 8:15 PM ET"]
    assert diag["request_ok"] is True
    assert seen["day"] == "2026-09-24"
    assert seen["primary_loader"] is nfl_base.load_nfl_slate


def test_v42_render_uses_v8_proxy_without_mutating_shared_nfl_module(monkeypatch):
    original_shared_loader = hub.nfl.load_nfl_slate
    original_v8_nfl = frozen_v8.nfl
    chosen = "Atlanta Falcons @ Green Bay Packers • 8:15 PM ET"
    observed = {"prior_called": False}

    monkeypatch.setattr(hub, "_render_visible_matchup_navigation", lambda selectbox: chosen)
    monkeypatch.setattr(hub.identity, "resolve_matchup_identity", lambda game, year: {})
    monkeypatch.setattr(
        hub.st,
        "selectbox",
        lambda label, options, *args, **kwargs: list(options)[0],
    )

    def fake_prior_render():
        observed["prior_called"] = True
        assert hub.nfl.load_nfl_slate is original_shared_loader
        assert frozen_v8.nfl is not original_v8_nfl
        assert frozen_v8.nfl.load_nfl_slate is hub._load_full_slate
        return "rendered"

    monkeypatch.setattr(hub.prior, "render_nfl_passing_yards_hub", fake_prior_render)

    result = hub.render_nfl_passing_yards_hub()

    assert result == "rendered"
    assert observed["prior_called"] is True
    assert hub.nfl.load_nfl_slate is original_shared_loader
    assert frozen_v8.nfl is original_v8_nfl
