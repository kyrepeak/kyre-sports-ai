from __future__ import annotations

from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "sports_api" / "api" / "nba_pra_injury_official_v2.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("nba_pra_injury_official_v2_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _game() -> dict[str, str]:
    return {
        "game_key": "CHI@BOS:2026-10-26",
        "away_tricode": "CHI",
        "away_name": "Chicago Bulls",
        "home_tricode": "BOS",
        "home_name": "Boston Celtics",
    }


def test_official_parser_uses_all_team_headers_before_filtering_selected_game() -> None:
    parser = _load_module()
    text = """
    Boston Celtics
    White, Derrick Available Personal Reasons
    Denver Nuggets
    Jokic, Nikola Probable Left Ankle
    Chicago Bulls
    Giddey, Josh Questionable Right Knee
    """

    rows = parser.parse_official_injury_report_text_v2(text, games=[_game()])

    assert [(row["team_tricode"], row["player_name"]) for row in rows] == [
        ("BOS", "Derrick White"),
        ("CHI", "Josh Giddey"),
    ]
    assert all(row["game_key"] == "CHI@BOS:2026-10-26" for row in rows)
    assert all(row["team_tricode"] in {"BOS", "CHI"} for row in rows)
    assert not any("Jokic" in row["player_name"] for row in rows)


def test_nba_pra_route_uses_official_v2_fetcher_and_keeps_espn_out() -> None:
    source = (ROOT / "sports_api" / "api" / "nba_pra_injury_v1.py").read_text(encoding="utf-8")
    assert "nba_pra_injury_official_v2 import fetch_official_rows_v2" in source
    assert "rows, meta = fetch_official_rows_v2" in source
    lowered = source.casefold()
    assert "espn" not in lowered
    assert "sportsgameodds" not in lowered
    assert "sgo" not in lowered
