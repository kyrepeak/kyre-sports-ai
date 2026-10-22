from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "sports_api/api/cfb_top_picks_page1_v1.py"
PAGE = ROOT / "cfb_top_picks_page_v12.py"
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py"
VERCEL = ROOT / "kyre_sports_api_vercel_v1.py"


def _load_api():
    assert API.exists(), "CFB Top Picks Kyre Sports API route must exist"
    spec = importlib.util.spec_from_file_location("cfb_top_picks_page1_v1_test_target", API)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_game(idx: int, *, game_id: str | None = None, with_market: bool = True) -> dict:
    gid = game_id or f"ncaa-{idx:02d}"
    away_price = -110 - idx
    home_price = 100 + idx
    quotes = []
    if with_market:
        quotes = [
            {
                "sportsbook": "FanDuel",
                "away_price": away_price,
                "home_price": home_price,
                "observed_at_utc": f"2026-10-22T08:{idx:02d}:00+00:00",
                "provider_event_id": f"fd-{idx}",
                "provider_market_id": f"fdm-{idx}",
            },
            {
                "sportsbook": "DraftKings",
                "away_price": away_price + 5,
                "home_price": home_price - 5,
                "observed_at_utc": f"2026-10-22T08:{idx:02d}:30+00:00",
                "provider_event_id": f"dk-{idx}",
                "provider_market_id": f"dkm-{idx}",
            },
        ]
    return {
        "game_id": gid,
        "identity_key": gid,
        "away_team": f"Away {idx}",
        "home_team": f"Home {idx}",
        "kickoff_iso": f"2026-10-24T{10 + (idx % 10):02d}:00:00+00:00",
        "market_quotes": quotes,
    }


def _analysis(idx: int, *, ready: bool = True) -> dict:
    away_wins = idx % 2 == 0
    winner_p = 0.60 + idx / 100.0
    return {
        "final": {
            "ready": ready,
            "final_pick_ready": ready,
            "winner_side": "away" if away_wins else "home",
            "winner_team": f"Away {idx}" if away_wins else f"Home {idx}",
            "winner_probability_final": winner_p,
            "away_fair_moneyline": -200 - idx,
            "home_fair_moneyline": 150 + idx,
            "reliability": 0.80 + idx / 1000.0,
        }
    }


def test_top_picks_api_dedupes_by_canonical_ncaa_game_id_and_backfills_to_ten():
    api = _load_api()
    games = [_fake_game(i) for i in range(1, 12)]
    games.insert(5, _fake_game(99, game_id="ncaa-03"))
    analyses = {f"ncaa-{i:02d}": _analysis(i) for i in range(1, 12)}

    picks = api.rank_moneyline_games(games, analyses, limit=10)

    assert len(picks) == 10
    event_ids = [pick["event_id"] for pick in picks]
    assert len(event_ids) == len(set(event_ids)) == 10
    assert event_ids.count("ncaa-03") == 1
    assert all(pick["event_id"].startswith("ncaa-") for pick in picks)


def test_top_picks_preserves_one_exact_sportsbook_quote_and_never_averages_prices():
    api = _load_api()
    game = _fake_game(4)
    picks = api.rank_moneyline_games([game], {"ncaa-04": _analysis(4)}, limit=10)
    assert len(picks) == 1
    pick = picks[0]
    assert pick["best_price"]["sportsbook"] in {"FanDuel", "DraftKings"}
    assert pick["best_price"]["price"] in {-109, -114, 96, 104}
    assert pick["best_price"]["updated_at"]
    assert pick["market_implied_probability"] is not None
    assert pick["model_edge_pp"] is not None
    assert "average" not in str(pick).lower()


def test_missing_market_data_stays_null_not_zero_and_does_not_fabricate_edge():
    api = _load_api()
    game = _fake_game(2, with_market=False)
    picks = api.rank_moneyline_games([game], {"ncaa-02": _analysis(2)}, limit=10)
    assert len(picks) == 1
    pick = picks[0]
    assert pick["best_price"] is None
    assert pick["market_implied_probability"] is None
    assert pick["model_edge_pp"] is None


def test_fanduel_matcher_normalizes_ncaa_display_aliases_without_fuzzy_guessing():
    from sports_api.collectors.cfb_fanduel_moneyline_v1 import match_moneylines_to_ncaa_games

    games = [
        {"game_id": "fa", "away_team": "Rice", "home_team": "Fla. Atlantic"},
        {"game_id": "mia", "away_team": "Pittsburgh", "home_team": "Miami (FL)"},
        {"game_id": "troy", "away_team": "ULM", "home_team": "Troy"},
    ]
    rows = [
        {"sportsbook": "FanDuel", "provider_event_id": "1", "provider_market_id": "m1", "away_team": "Rice", "home_team": "Florida Atlantic", "away_price": 255, "home_price": -320},
        {"sportsbook": "FanDuel", "provider_event_id": "2", "provider_market_id": "m2", "away_team": "Pittsburgh", "home_team": "Miami Florida", "away_price": 980, "home_price": -2000},
        {"sportsbook": "FanDuel", "provider_event_id": "3", "provider_market_id": "m3", "away_team": "UL Monroe", "home_team": "Troy", "away_price": 460, "home_price": -650},
    ]

    matched = match_moneylines_to_ncaa_games(games, rows)
    assert set(matched) == {"fa", "mia", "troy"}
    assert matched["fa"][0]["home_price"] == -320
    assert matched["mia"][0]["home_price"] == -2000
    assert matched["troy"][0]["home_price"] == -650


def test_page_is_kyre_api_only_and_exposes_professional_decision_metrics():
    assert PAGE.exists(), "S-tier CFB Top Picks Page 1 successor must exist"
    text = PAGE.read_text(encoding="utf-8")
    low = text.lower()
    assert 'PAGE1_ENDPOINT = "/api/v1/cfb/top-picks/page1"' in text
    assert "KYRE_SPORTS_API_BASE_URL" in text
    assert "cfb_top_picks_engine_v1" not in text
    assert "Market Edge" in text
    assert "Best Price" in text
    assert "Model" in text
    assert "WHY THIS PICK" in text
    for forbidden in ("sportsgameodds", "sgo", "espn"):
        assert forbidden not in low


def test_terminal_and_vercel_register_exact_top_picks_successor():
    terminal = TERMINAL.read_text(encoding="utf-8")
    vercel = VERCEL.read_text(encoding="utf-8")
    assert 'route.sport_id == "cfb" and route.market_id == "top-picks"' in terminal
    assert 'importlib.import_module("cfb_top_picks_page_v12")' in terminal
    assert "cfb_top_picks_page1_v1" in vercel
    assert "cfb_top_picks_page1_router" in vercel
