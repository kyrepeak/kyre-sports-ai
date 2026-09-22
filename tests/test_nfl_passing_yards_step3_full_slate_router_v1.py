import pandas as pd

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
