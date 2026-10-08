from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "cfb_game_total_page1_multisource_v1.py"
PAGE = ROOT / "cfb_game_total_clean_page_v35.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_v190.py"


def test_step2_implementation_files_exist() -> None:
    assert ENGINE.is_file(), "Step-2 multi-source Page-1 engine must exist"
    assert PAGE.is_file(), "Step-2 Page V35 successor must exist"


def test_step2_engine_fills_third_down_and_truthful_history(monkeypatch) -> None:
    import cfb_game_total_page1_multisource_v1 as engine

    fallback = {
        "ready": True,
        "source": "multi-source: official audit + cfbstats.com",
        "away_metrics": {
            "third_down_offense_pct": 41.2,
            "third_down_defense_pct": 34.8,
            "red_zone_offense_pct": 88.0,
            "red_zone_defense_pct": 71.0,
            "turnovers_lost_pg": 1.0,
            "turnovers_gained_pg": 1.5,
        },
        "home_metrics": {
            "third_down_offense_pct": 46.5,
            "third_down_defense_pct": 38.1,
            "red_zone_offense_pct": 91.0,
            "red_zone_defense_pct": 75.0,
            "turnovers_lost_pg": 0.8,
            "turnovers_gained_pg": 1.2,
        },
    }
    monkeypatch.setattr(engine.multisource, "build_display_fallback", lambda *args, **kwargs: fallback)

    game = {"away_team": "Sam Houston", "home_team": "Liberty", "game_date": "2026-10-08"}
    away = {
        "team": "Sam Houston",
        "official_stats": {},
        "completed_games": [{"opponent": "UTEP", "result": "W", "score": "28-21"}],
    }
    home = {
        "team": "Liberty",
        "official_stats": {},
        "completed_games": [{"opponent": "Old Dominion", "result": "W", "score": "31-17"}],
    }

    out_game, out_away, out_home, diag = engine.enrich_display_bundle(game, "2026-10-08", away, home, {})

    away_labels = " ".join(str(row.get("label") or "") for row in out_away["official_stats"].values())
    home_labels = " ".join(str(row.get("label") or "") for row in out_home["official_stats"].values())
    assert "3rd Down Offense" in away_labels and "3rd Down Defense" in away_labels
    assert "3rd Down Offense" in home_labels and "3rd Down Defense" in home_labels
    assert out_game["history"]["status"] == "No recent meeting in verified completed-game samples"
    assert out_game["history"]["source"] == "verified completed-game samples"
    assert diag["sportsbook_projection_influence"] == 0.0
    assert diag["may_modify_projection"] is False


def test_step2_preserves_existing_verified_rows(monkeypatch) -> None:
    import cfb_game_total_page1_multisource_v1 as engine

    monkeypatch.setattr(
        engine.multisource,
        "build_display_fallback",
        lambda *args, **kwargs: {
            "ready": True,
            "source": "cfbstats.com",
            "away_metrics": {"third_down_offense_pct": 40.0, "third_down_defense_pct": 35.0},
            "home_metrics": {"third_down_offense_pct": 45.0, "third_down_defense_pct": 39.0},
        },
    )
    away = {"team": "Away", "official_stats": {"official-third": {"label": "3rd Down Offense", "value": "51.0%", "source": "official"}}}
    home = {"team": "Home", "official_stats": {}}
    _, out_away, _, _ = engine.enrich_display_bundle({"away_team": "Away", "home_team": "Home"}, "2026-10-08", away, home, {})
    assert out_away["official_stats"]["official-third"]["value"] == "51.0%"


def test_step2_removes_generic_data_limited_for_third_down_and_history(monkeypatch) -> None:
    import cfb_game_total_clean_page_v9 as compact
    import cfb_game_total_page1_multisource_v1 as engine

    monkeypatch.setattr(
        engine.multisource,
        "build_display_fallback",
        lambda *args, **kwargs: {
            "ready": True,
            "source": "official + cfbstats.com",
            "away_metrics": {"third_down_offense_pct": 41.0, "third_down_defense_pct": 36.0},
            "home_metrics": {"third_down_offense_pct": 44.0, "third_down_defense_pct": 39.0},
        },
    )
    game, away, home, _ = engine.enrich_display_bundle(
        {"away_team": "Away", "home_team": "Home"},
        "2026-10-08",
        {"team": "Away", "official_stats": {}, "completed_games": []},
        {"team": "Home", "official_stats": {}, "completed_games": []},
        {},
    )
    identity = {"away": {"team": "Away"}, "home": {"team": "Home"}}
    _, third_body = compact._step_body(7, "third-down check", identity, away, home, game, {})
    _, history_body = compact._step_body(10, "history check", identity, away, home, game, {})
    assert "DATA LIMITED" not in third_body
    assert "DATA LIMITED" not in history_body


def test_step2_page_wrapper_and_router_are_cfb_only() -> None:
    page = PAGE.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    assert "import cfb_game_total_clean_page_v34 as prior" in page
    assert "import cfb_game_total_clean_page_v24 as data_owner" in page
    assert "cfb_game_total_page1_multisource_v1" in page
    assert 'GAME_TOTAL_PAGE = "cfb_game_total_clean_page_v35"' in router
    assert "MAY_MODIFY_PROJECTION = False" in page
