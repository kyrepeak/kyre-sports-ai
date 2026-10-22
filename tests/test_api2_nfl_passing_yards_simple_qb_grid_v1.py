from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_FROZEN_API_BLOB = "a14d8c7f6105d48888e51596dd68cb357e601b63"
EXPECTED_FROZEN_RENDERER_BLOB = "eeadb5e5c3be680768916ea9ef8d8b121208c23b"


def _player(name="D.Maye", team="NE", opp="CHI", line=244.5, projection=258.7, over=0.64, under=0.36):
    return {
        "player_id": f"kyre:nfl:player:{name.lower().replace('.', '-')}",
        "qb_name": name,
        "team_abbr": team,
        "team_name": "New England Patriots" if team == "NE" else team,
        "opponent_abbr": opp,
        "identity_visuals": {
            "canonical_player_id": f"kyre:nfl:player:{name.lower().replace('.', '-')}",
            "identity_verified": True,
            "headshot_url": f"https://images.test/{name}.png",
            "team_logo_url": f"https://static.www.nfl.com/logos/{team}.png",
            "opponent_logo_url": f"https://static.www.nfl.com/logos/{opp}.png",
        },
        "context_projection": {"context_projection_yards": projection, "confidence": "HIGH"},
        "market": {
            "ready": True,
            "sportsbook": "FanDuel",
            "line": line,
            "over_odds": -110,
            "under_odds": -110,
            "source_timestamp": "2026-10-22T16:00:00Z",
        },
        "market_evaluation": {
            "ready": True,
            "model_over_probability": over,
            "model_under_probability": under,
            "sportsbook_projection_influence": 0.0,
        },
        "page1_decision_support": {"thesis": {"side": "OVER", "strength": "STRONG"}},
    }


def _game(game_id="kyre:nfl:game:g1", away="NE", home="CHI", kickoff="20:15"):
    return {
        "game_id": game_id,
        "date": "2026-10-22",
        "season": 2026,
        "week": 7,
        "away": away,
        "home": home,
        "kickoff": kickoff,
    }


def test_successor_files_exist_before_import():
    assert (ROOT / "sports_api/api/nfl_passing_yards_slate_v1.py").exists()
    assert (ROOT / "nfl_passing_yards_slate_gateway_v1.py").exists()
    assert (ROOT / "nfl_passing_yards_simple_qb_grid_v1.py").exists()


def test_public_card_contract_is_simple_complete_and_book_specific():
    api = importlib.import_module("sports_api.api.nfl_passing_yards_slate_v1")
    card = api.build_public_qb_card(_game(), _player())
    assert card["player_id"].startswith("kyre:nfl:player:")
    assert card["qb_name"] == "D.Maye"
    assert card["team_abbr"] == "NE"
    assert card["opponent_abbr"] == "CHI"
    assert card["game_time"] == "20:15"
    assert card["market"]["sportsbook"] == "FanDuel"
    assert card["market"]["line"] == 244.5
    assert card["projection_yards"] == 258.7
    assert card["edge_yards"] == 14.2
    assert card["over_probability"] == 0.64
    assert card["under_probability"] == 0.36
    assert card["favored_side"] == "OVER"
    assert card["confidence"] == "HIGH"
    assert card["headshot_url"].startswith("https://")
    assert card["team_logo_url"].startswith("https://")
    assert card["data_status"] == "VERIFIED"


def test_missing_market_is_explicit_not_zero_or_fake():
    api = importlib.import_module("sports_api.api.nfl_passing_yards_slate_v1")
    player = _player()
    player["market"] = None
    player["market_evaluation"] = {"ready": False}
    card = api.build_public_qb_card(_game(), player)
    assert card["market"]["status"] == "NOT_AVAILABLE"
    assert card["market"]["line"] is None
    assert card["over_probability"] is None
    assert card["under_probability"] is None
    assert card["favored_side"] == "NO_STRONG_SIDE"
    assert card["data_status"] == "PARTIAL"


def test_slate_contract_keeps_every_qb_and_sorts_by_kickoff_then_name(monkeypatch):
    api = importlib.import_module("sports_api.api.nfl_passing_yards_slate_v1")
    game1 = _game("kyre:nfl:game:g1", "NE", "CHI", "20:15")
    game2 = _game("kyre:nfl:game:g2", "BUF", "MIA", "13:00")
    bundles = [
        {"game": game1, "players": [_player("D.Maye", "NE", "CHI"), _player("C.Williams", "CHI", "NE", 250.5, 238.0, 0.39, 0.61)]},
        {"game": game2, "players": [_player("J.Allen", "BUF", "MIA", 271.5, 286.0, 0.63, 0.37), _player("T.Tagovailoa", "MIA", "BUF", 252.5, 249.0, 0.47, 0.53)]},
    ]
    monkeypatch.setattr(api, "build_game_bundles", lambda target_date=None: ("2026-10-22", bundles, {"provider": "NFLverse"}))
    slate = api.build_slate_bundle("2026-10-22")
    assert slate["ready"] is True
    assert slate["schema_version"] == "nfl_passing_yards_simple_qb_grid_v1"
    assert slate["gateway"] == "Kyre Sports API"
    assert slate["game_count"] == 2
    assert slate["quarterback_count"] == 4
    assert [row["qb_name"] for row in slate["quarterbacks"]] == ["J.Allen", "T.Tagovailoa", "C.Williams", "D.Maye"]
    assert slate["routing"]["sportsbook_line_averaging"] is False
    assert slate["routing"]["missing_to_zero"] is False
    assert "ESPN" not in repr(slate["routing"])
    assert "SGO" not in repr(slate["routing"])


def test_gateway_rejects_wrong_identity_and_accepts_explicit_unavailable():
    gateway = importlib.import_module("nfl_passing_yards_slate_gateway_v1")
    payload = {
        "ready": True,
        "schema_version": "nfl_passing_yards_simple_qb_grid_v1",
        "service": "kyre-sports-api",
        "gateway": "Kyre Sports API",
        "game_date": "2026-10-22",
        "game_count": 1,
        "quarterback_count": 1,
        "quarterbacks": [
            {
                "player_id": "kyre:nfl:player:test",
                "qb_name": "Test QB",
                "team_abbr": "NE",
                "opponent_abbr": "CHI",
                "game_id": "kyre:nfl:game:test",
                "game_time": "20:15",
                "market": {"status": "NOT_AVAILABLE", "sportsbook": None, "line": None, "odds": None, "timestamp": None},
                "projection_yards": 250.0,
                "over_probability": None,
                "under_probability": None,
                "favored_side": "NO_STRONG_SIDE",
                "data_status": "PARTIAL",
            }
        ],
        "routing": {"canonical_ids": True, "sportsbook_line_averaging": False, "missing_to_zero": False},
    }
    assert gateway.validate_payload(payload)["ready"] is True
    payload["quarterbacks"][0]["player_id"] = "wrong"
    assert gateway.validate_payload(payload)["ready"] is False


def test_card_html_has_s_tier_simple_fields_and_no_deep_page1_clutter():
    page = importlib.import_module("nfl_passing_yards_simple_qb_grid_v1")
    api = importlib.import_module("sports_api.api.nfl_passing_yards_slate_v1")
    card = api.build_public_qb_card(_game(), _player())
    html = page.build_qb_card_html(card)
    for text in ["D.Maye", "244.5", "258.7", "64%", "8:15 PM", "View Full Analysis"]:
        assert text in html
    for deep in ["QB vs Defense History", "Weather Breakdown", "Injury Breakdown", "Probability Ladder"]:
        assert deep not in html
    assert "--team-primary" in html and "--team-accent" in html


def test_runtime_loader_points_only_nfl_passing_yards_to_simple_successor():
    source = (ROOT / "universal_runtime_v5_loader.py").read_text()
    assert 'return _import("nfl_passing_yards_simple_qb_grid_v1")' in source
    assert 'return page.render_nfl_passing_yards_simple_qb_grid()' in source


def test_frozen_v2_successor_blobs_remain_unchanged():
    import subprocess
    api_blob = subprocess.check_output(["git", "hash-object", "sports_api/api/nfl_passing_yards_page_v1/__init__.py"], text=True).strip()
    renderer_blob = subprocess.check_output(["git", "hash-object", "nfl_passing_yards_professional_v1/__init__.py"], text=True).strip()
    assert api_blob == EXPECTED_FROZEN_API_BLOB
    assert renderer_blob == EXPECTED_FROZEN_RENDERER_BLOB


def test_schedule_expands_anchor_date_to_entire_regular_season_week(monkeypatch):
    import pandas as pd
    api = importlib.import_module("sports_api.api.nfl_passing_yards_slate_v1")
    frame = pd.DataFrame([
        {"game_id":"2026_07_NE_CHI","gameday":"2026-10-22","gametime":"20:15","season":2026,"week":7,"game_type":"REG","away_team":"NE","home_team":"CHI"},
        {"game_id":"2026_07_BUF_MIA","gameday":"2026-10-25","gametime":"13:00","season":2026,"week":7,"game_type":"REG","away_team":"BUF","home_team":"MIA"},
        {"game_id":"2026_07_DAL_NYG","gameday":"2026-10-26","gametime":"20:15","season":2026,"week":7,"game_type":"REG","away_team":"DAL","home_team":"NYG"},
        {"game_id":"2026_08_BAL_CIN","gameday":"2026-11-01","gametime":"13:00","season":2026,"week":8,"game_type":"REG","away_team":"BAL","home_team":"CIN"},
    ])
    monkeypatch.setattr(api.base._legacy, "_load_games_csv", lambda: frame)
    resolved, games = api._schedule_games("2026-10-22")
    assert resolved == "2026-10-22"
    assert len(games) == 3
    assert {g["date"] for g in games} == {"2026-10-22", "2026-10-25", "2026-10-26"}
    assert {g["week"] for g in games} == {7}


def test_starter_status_never_claims_official_verification_without_source():
    api = importlib.import_module("sports_api.api.nfl_passing_yards_slate_v1")
    listed = api.build_public_qb_card(_game(), _player())
    assert listed["starter_status"] == "MARKET_LISTED"
    missing = _player()
    missing["market"] = None
    missing["market_evaluation"] = {"ready": False}
    projected = api.build_public_qb_card(_game(), missing)
    assert projected["starter_status"] == "PROJECTED_RECENT_USAGE"
    assert projected["starter_status"] != "VERIFIED_STARTER"


def test_vercel_gateway_registers_simple_passing_yards_slate_router():
    source = (ROOT / "kyre_sports_api_vercel_v1.py").read_text()
    assert "import sports_api.api.nfl_passing_yards_slate_v1 as nfl_passing_yards_slate_module" in source
    assert "nfl_passing_yards_slate_router = nfl_passing_yards_slate_module.router" in source
    assert "app.include_router(nfl_passing_yards_slate_router)" in source
    assert '"nfl_passing_yards_slate": True' in source


def test_game_time_sort_keeps_week_chronological_before_clock_time():
    page = importlib.import_module("nfl_passing_yards_simple_qb_grid_v1")
    cards = [
        {"qb_name":"Sunday Early","game_date":"2026-10-25","game_time":"13:00","edge_yards":5},
        {"qb_name":"Thursday Night","game_date":"2026-10-22","game_time":"20:15","edge_yards":3},
        {"qb_name":"Monday Night","game_date":"2026-10-26","game_time":"20:15","edge_yards":9},
    ]
    ordered = page.sort_qb_cards(cards, "Game Time")
    assert [row["qb_name"] for row in ordered] == ["Thursday Night", "Sunday Early", "Monday Night"]
