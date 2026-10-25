from __future__ import annotations

from datetime import date
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _game(game_id: str = "g1") -> dict:
    return {
        "game_id": game_id,
        "identity_key": game_id,
        "away_team": "Brigham Young",
        "home_team": "Central Florida",
        "away_team_abbreviation": "BYU",
        "home_team_abbreviation": "UCF",
        "kickoff_iso": "2026-10-24T19:30:00+00:00",
        "team_identity": {
            "away": {
                "logo_url": "https://www.ncaa.com/sites/default/files/images/logos/schools/bgl/byu.svg",
                "fallback_monogram": "BYU",
            },
            "home": {
                "logo_url": "https://www.ncaa.com/sites/default/files/images/logos/schools/bgl/ucf.svg",
                "fallback_monogram": "UCF",
            },
        },
    }


def test_v5_logo_rail_successor_exists_and_bootstrap_activates_it():
    page = ROOT / "cfb_game_total_page1_atier_v5.py"
    assert page.exists(), "V5 premium logo rail successor has not been implemented yet"
    wrapper = (ROOT / "cfb_game_total_page1_api_bootstrap_repair_r1.py").read_text(encoding="utf-8")
    assert "cfb_game_total_page1_atier_v7" in wrapper
    assert "cfb_game_total_page1_atier_v4 as atier" not in wrapper


def test_rail_chip_is_logo_abbreviation_matchup_time_only():
    module = importlib.import_module("cfb_game_total_page1_atier_v5")
    game = _game()
    html = module._rail_html([game], game, date(2026, 10, 24))
    folded = html.casefold()

    assert "cfbgt5-team-logo" in html
    assert "byu.svg" in html
    assert "ucf.svg" in html
    assert "BYU" in html
    assert "UCF" in html
    assert " @ " in html
    assert "12:30 PM" in html
    assert "selected" in html

    # The matchup rail is selection-only. Analytics stay below the rail.
    assert "o/u" not in folded
    assert "probability" not in folded
    assert "confidence" not in folded
    assert "edge" not in folded
    assert "sportsbook" not in folded
    assert "venue" not in folded


def test_logo_fallback_never_renders_broken_image_placeholder():
    module = importlib.import_module("cfb_game_total_page1_atier_v5")
    game = _game("g2")
    game["team_identity"]["away"]["logo_url"] = None
    html = module._rail_html([game], game, date(2026, 10, 24))

    assert "BYU" in html
    assert '<img src=""' not in html
    assert "broken" not in html.casefold()


def test_logo_rail_css_is_compact_single_row_swipe_snap():
    source = (ROOT / "cfb_game_total_page1_atier_v5.py").read_text(encoding="utf-8")
    compact = "".join(source.split()).casefold()

    assert "overflow-x:auto" in compact
    assert "flex-wrap:nowrap" in compact
    assert "scroll-snap-type:xmandatory" in compact
    assert "scroll-snap-align:start" in compact
    assert "height:78px" in compact
    assert "width:176px" in compact
    assert ".cfbgt5-chip.selected" in source
    assert "#68d9ff" in source


def test_v5_preserves_frozen_boundaries_and_api_owned_identity():
    source = (ROOT / "cfb_game_total_page1_atier_v5.py").read_text(encoding="utf-8")
    folded = source.casefold()

    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_MODEL = False" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_PROBABILITY = False" in source
    assert "MAY_MODIFY_RANKING = False" in source
    assert "MAY_MODIFY_SELECTION = False" in source
    assert "MAY_MODIFY_SELECTED_GAME_RUNTIME = False" in source
    assert "team_identity" in source
    assert "requests." not in folded
    assert "urlopen(" not in folded
    assert "espn" not in folded
    assert "sgo" not in folded
