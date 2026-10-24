from datetime import datetime, timezone
from pathlib import Path

import sports_api.api.cfb_game_total_page1_v1 as api

ROOT = Path(__file__).resolve().parents[1]


def _game():
    return {
        "game_id": "ncaa-1",
        "identity_key": "ncaa:ncaa-1",
        "away_team": "Duke",
        "away_team_slug": "duke",
        "home_team": "Virginia",
        "home_team_slug": "virginia",
        "kickoff_iso": "2026-10-23T19:00:00-04:00",
        "identity_verified": True,
        "date_matches_query": True,
    }


def _quote(book, line, over=-110, under=-110, stamp="2026-10-23T15:00:00+00:00", **extra):
    row = {
        "sportsbook": book,
        "market": "game_total",
        "provider_event_id": f"event-{book}",
        "provider_market_id": f"market-{book}",
        "total_line": line,
        "over_price": over,
        "under_price": under,
        "observed_at_utc": stamp,
        "line_status": "open",
        "source_provider": "approved",
    }
    row.update(extra)
    return row


def test_ncaa_identity_assets_and_kyre_team_ids_are_api_owned():
    public = api._public_game(_game(), [])
    identity = public["team_identity"]
    assert identity["away"]["kyre_team_id"] == "KYRE-CFB-duke"
    assert identity["home"]["kyre_team_id"] == "KYRE-CFB-virginia"
    assert identity["away"]["logo_url"].endswith("/duke.svg")
    assert identity["home"]["logo_url"].endswith("/virginia.svg")
    assert "ncaa.com/sites/default/files/images/logos/schools/bgl/" in identity["away"]["logo_url"]
    source = (ROOT / "sports_api/api/cfb_game_total_page1_v1.py").read_text(encoding="utf-8").casefold()
    assert "cfb_team_identity_v1" not in source
    assert "a.espncdn.com" not in source
    assert "site.api.espn" not in source


def test_consensus_uses_exact_mode_and_never_averages_conflicting_lines():
    result = api._market_consensus([
        _quote("FanDuel", 46.5),
        _quote("DraftKings", 46.5),
        _quote("BetMGM", 47.5),
    ])
    assert result["status"] == "VERIFIED_EXACT_CLUSTER"
    assert result["consensus_line"] == 46.5
    assert result["books_reporting"] == 3
    assert result["method"] == "EXACT_MODE_NO_AVERAGE"
    assert sorted(result["book_lines"], key=lambda row: row["sportsbook"])[0]["total_line"] in {46.5, 47.5}

    tied = api._market_consensus([_quote("FanDuel", 46.5), _quote("DraftKings", 47.5)])
    assert tied["status"] == "NO_CLEAR_CONSENSUS"
    assert tied["consensus_line"] is None
    assert tied["books_reporting"] == 2


def test_line_movement_never_infers_opener_from_first_seen_current_quotes():
    current = _quote("FanDuel", 46.5, stamp="2026-10-23T15:00:00+00:00")
    earlier = _quote("DraftKings", 45.5, stamp="2026-10-23T12:00:00+00:00")
    movement = api._line_movement(current, [earlier, current])
    assert movement["status"] == "OPENING_LINE_NOT_VERIFIED"
    assert movement["opening_total"] is None
    assert movement["move"] is None
    assert movement["current_total"] == 46.5

    verified = _quote(
        "FanDuel",
        46.5,
        opening_total=45.5,
        opening_total_verified=True,
        opening_observed_at_utc="2026-10-20T14:00:00+00:00",
    )
    movement = api._line_movement(verified, [verified])
    assert movement["status"] == "VERIFIED_MOVEMENT"
    assert movement["opening_total"] == 45.5
    assert movement["current_total"] == 46.5
    assert movement["move"] == 1.0


def test_payload_enriches_only_through_kyre_api(monkeypatch):
    game = _game()
    primary = _quote("FanDuel", 46.5, over=-118, under=-104)
    consensus_rows = [
        _quote("FanDuel", 46.5, over=-118, under=-104),
        _quote("DraftKings", 46.5),
        _quote("BetMGM", 47.5),
    ]
    monkeypatch.setattr(api, "_resolve_slate_date", lambda requested, now: ("2026-10-23", [game]))
    monkeypatch.setattr(api, "_market_state", lambda games: ({"ncaa-1": [primary]}, ["FanDuel"]))
    monkeypatch.setattr(api, "collect_consensus_market_rows", lambda games: ({"ncaa-1": consensus_rows}, ["Action Network"]))
    payload = api.build_page1_payload(
        game_date="2026-10-23",
        now_provider=lambda: datetime(2026, 10, 23, 18, 0, tzinfo=timezone.utc),
    )
    row = payload["games"][0]
    assert row["team_identity"]["away"]["kyre_team_id"] == "KYRE-CFB-duke"
    assert row["market_consensus"]["consensus_line"] == 46.5
    assert row["market_consensus"]["books_reporting"] == 3
    assert row["line_movement"]["status"] == "OPENING_LINE_NOT_VERIFIED"
    assert payload["routing"]["application_gateway"] == "Kyre Sports API"
    assert payload["routing"]["consensus_averaging"] is False
    assert payload["routing"]["frontend_provider_selection"] is False
    assert payload["routing"]["forbidden_providers"] == ["SGO", "ESPN", "ESPN BET"]


def test_v3_presentation_contract_is_preserved_under_v5_activation():
    path = ROOT / "cfb_game_total_page1_atier_v3.py"
    assert path.exists(), "V3 final-polish successor has not been implemented yet"
    source = path.read_text(encoding="utf-8")
    folded = source.casefold()
    assert "cfbgt3-team-logo" in source
    assert "cfbgt3-prob-labels" in source
    assert "cfbgt3-marketrow" in source
    assert "grid-template-columns:repeat(3,minmax(0,1fr))" in source.replace(" ", "")
    assert "cfbgt3-total" in source
    assert "cfbgt3-over" in source
    assert "cfbgt3-under" in source
    assert "cfbgt3-probbar" in source
    assert "cfbgt3-probfill" in source
    assert "consensus" in folded
    assert "opening line" in folded
    assert 'target="_self"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_PROBABILITY = False" in source
    assert "MAY_MODIFY_RANKING = False" in source
    assert "requests." not in folded
    assert "actionnetwork.com" not in folded
    assert "the-odds-api" not in folded
    assert "espncdn" not in folded

    successor = (ROOT / "cfb_game_total_page1_atier_v5.py").read_text(encoding="utf-8")
    assert "import cfb_game_total_page1_atier_v3 as card" in successor
    wrapper = (ROOT / "cfb_game_total_page1_api_bootstrap_repair_r1.py").read_text(encoding="utf-8")
    assert "cfb_game_total_page1_atier_v5" in wrapper
    assert "cfb_game_total_page1_atier_v2" not in wrapper
