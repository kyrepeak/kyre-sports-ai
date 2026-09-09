import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sports_api.api import cfb_market_identity_v1 as identity


def _verified_game(
    event_id="401858213",
    game_date="2026-09-10",
    away_team="Florida A&M",
    home_team="Miami",
):
    return {
        "event_id": event_id,
        "game_date": game_date,
        "away_team": away_team,
        "home_team": home_team,
        "away_team_id": "50",
        "home_team_id": "2390",
        "venue": "Hard Rock Stadium",
        "broadcast": "ACC Network",
        "status": "Scheduled",
        "sources": ["verified fixture"],
    }


def _market(
    *,
    game_id="provider-123",
    away_team="Florida A&M Rattlers",
    home_team="Miami Hurricanes",
    start_time_utc="2026-09-11T00:00:00+00:00",
    sportsbook="DraftKings",
    total=54.5,
):
    return {
        "game_id": game_id,
        "home_team": home_team,
        "away_team": away_team,
        "start_time_utc": start_time_utc,
        "total": total,
        "sportsbook": sportsbook,
        "updated_at_utc": "2026-09-09T18:00:00+00:00",
        "line_status": "active",
    }


def _feed(*markets):
    return {
        "schema_version": "cfb_market_feed_v1",
        "captured_at_utc": "2026-09-09T18:00:00+00:00",
        "source": "Step 2 test feed",
        "games": list(markets),
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
    }


def test_exact_verified_identity_attaches_official_game_id():
    result = identity.reconcile_market_feed(
        _feed(_market(away_team="Florida A&M", home_team="Miami")),
        [_verified_game()],
    )
    assert result["diagnostics"]["all_lines_identity_verified"] is True
    assert result["diagnostics"]["synthetic_official_ids"] is False
    assert result["diagnostics"]["fuzzy_matching"] is False
    assert result["lines"][0]["official_game_id"] == "401858213"
    assert result["lines"][0]["provider_game_id"] == "provider-123"
    assert result["lines"][0]["identity_verified"] is True


def test_common_mascot_suffixes_match_deterministically():
    result = identity.reconcile_market_feed(
        _feed(_market()),
        [_verified_game()],
    )
    assert result["unmatched"] == []
    line = result["lines"][0]
    assert line["official_away_team"] == "Florida A&M"
    assert line["official_home_team"] == "Miami"
    assert line["away_name_score"] >= identity.MATCH_THRESHOLD
    assert line["home_name_score"] >= identity.MATCH_THRESHOLD


def test_known_school_aliases_are_supported_without_fuzzy_matching():
    verified = _verified_game(
        event_id="usc-1",
        game_date="2026-09-12",
        away_team="USC",
        home_team="Oregon State",
    )
    market = _market(
        game_id="book-usc",
        away_team="Southern California Trojans",
        home_team="Oregon State Beavers",
        start_time_utc="2026-09-12T23:30:00+00:00",
    )
    result = identity.reconcile_market_feed(_feed(market), [verified])
    assert result["unmatched"] == []
    assert result["lines"][0]["official_game_id"] == "usc-1"
    assert result["diagnostics"]["fuzzy_matching"] is False


def test_market_date_is_resolved_in_eastern_time():
    verified = _verified_game(game_date="2026-09-10")
    # 00:00 UTC on Sept 11 is still Sept 10 in Eastern time.
    market = _market(start_time_utc="2026-09-11T00:00:00+00:00")
    result = identity.reconcile_market_feed(_feed(market), [verified])
    assert result["lines"][0]["game_date"] == "2026-09-10"


def test_wrong_or_off_date_market_fails_closed():
    verified = _verified_game()
    wrong_team = _market(home_team="Florida State Seminoles")
    off_date = _market(
        game_id="provider-456",
        start_time_utc="2026-09-12T00:00:00+00:00",
    )
    result = identity.reconcile_market_feed(_feed(wrong_team, off_date), [verified])
    assert result["lines"] == []
    assert len(result["unmatched"]) == 2
    assert {row["reason"] for row in result["unmatched"]} == {"no_verified_match"}
    assert result["diagnostics"]["all_lines_identity_verified"] is False
    assert result["diagnostics"]["fail_closed"] is True


def test_ambiguous_identity_never_emits_an_official_id():
    market = _market(away_team="Georgia Bulldogs", home_team="Clemson Tigers")
    verified = [
        _verified_game(
            event_id="game-a",
            away_team="Georgia",
            home_team="Clemson",
        ),
        _verified_game(
            event_id="game-b",
            away_team="Georgia",
            home_team="Clemson",
        ),
    ]
    result = identity.reconcile_market_feed(_feed(market), verified)
    assert result["lines"] == []
    assert result["unmatched"][0]["reason"] == "ambiguous_verified_match"
    assert result["unmatched"][0]["candidate_official_game_ids"] == ["game-a", "game-b"]


def test_multiple_sportsbooks_can_attach_to_the_same_verified_game():
    dk = _market(game_id="dk-1", sportsbook="DraftKings", total=54.5)
    fd = _market(game_id="fd-1", sportsbook="FanDuel", total=55.0)
    result = identity.reconcile_market_feed(_feed(dk, fd), [_verified_game()])
    assert len(result["lines"]) == 2
    assert {row["sportsbook"] for row in result["lines"]} == {"DraftKings", "FanDuel"}
    assert {row["official_game_id"] for row in result["lines"]} == {"401858213"}
    assert result["diagnostics"]["unique_official_games_matched"] == 1


def test_snapshot_loader_rejects_duplicates_and_malformed_rows(monkeypatch, tmp_path):
    path = tmp_path / "cfb_snapshot.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "generated_at": "2026-09-09T18:00:00Z",
                "window": {"start": "2026-09-09", "end": "2026-09-15"},
                "games": [
                    {
                        "event_id": "1",
                        "game_date": "2026-09-10",
                        "away_team": "A",
                        "home_team": "B",
                    },
                    {
                        "event_id": "1",
                        "game_date": "2026-09-10",
                        "away_team": "A",
                        "home_team": "B",
                    },
                    {"event_id": "", "game_date": "2026-09-10"},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(identity.SNAPSHOT_PATH_ENV, str(path))
    games, diag = identity.load_verified_games()
    assert len(games) == 1
    assert diag["duplicate_event_ids_ignored"] == 1
    assert diag["malformed_games_ignored"] == 1


def test_reconciled_endpoint_filters_by_verified_official_game_id(monkeypatch, tmp_path):
    snapshot = tmp_path / "cfb_snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "version": 1,
                "generated_at": "2026-09-09T18:00:00Z",
                "window": {"start": "2026-09-09", "end": "2026-09-15"},
                "games": [
                    {
                        "event_id": "401858213",
                        "game_date": "2026-09-10",
                        "away_team": "Florida A&M",
                        "home_team": "Miami",
                        "away": {"team_id": "50"},
                        "home": {"team_id": "2390"},
                        "venue": "Hard Rock Stadium",
                        "broadcast": "ACC Network",
                        "status": "Scheduled",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(identity.SNAPSHOT_PATH_ENV, str(snapshot))
    monkeypatch.setattr(identity, "_load_feed", lambda: _feed(_market()))

    app = FastAPI()
    app.include_router(identity.router)
    response = TestClient(app).get(
        "/api/v1/cfb/markets/reconciled?official_game_id=401858213"
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["lines"]) == 1
    assert body["lines"][0]["official_game_id"] == "401858213"
    assert body["market_semantics"]["projection_weight"] == 0.0
    assert body["market_semantics"]["may_modify_projection"] is False


def test_reconciled_endpoint_returns_404_for_unverified_filter(monkeypatch, tmp_path):
    snapshot = tmp_path / "cfb_snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "version": 1,
                "games": [
                    {
                        "event_id": "401858213",
                        "game_date": "2026-09-10",
                        "away_team": "Florida A&M",
                        "home_team": "Miami",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(identity.SNAPSHOT_PATH_ENV, str(snapshot))
    monkeypatch.setattr(identity, "_load_feed", lambda: _feed(_market()))

    app = FastAPI()
    app.include_router(identity.router)
    response = TestClient(app).get(
        "/api/v1/cfb/markets/reconciled?official_game_id=does-not-exist"
    )
    assert response.status_code == 404


def test_shared_host_lifespan_starts_with_step2_routes():
    """Regression for the shared Render lifespan recursion fixed after Step 1."""
    from sports_api.main import app as shared_host_app

    with TestClient(shared_host_app) as client:
        health = client.get("/health")
        identity_status = client.get("/api/v1/cfb/markets/identity-status")

    assert health.status_code == 200
    assert identity_status.status_code == 200
    body = identity_status.json()
    assert body["step"] == 2
    assert body["identity_ready"] is True
    assert body["market_semantics"]["projection_weight"] == 0.0
