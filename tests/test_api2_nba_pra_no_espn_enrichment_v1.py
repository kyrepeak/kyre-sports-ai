from __future__ import annotations

from datetime import date
import inspect


def test_player_context_source_has_no_espn_or_sgo_active_dependency():
    import runless_v2.nba_pra_player_context_v1 as context
    source = inspect.getsource(context).casefold()
    assert "espn" not in source
    assert "sportsgameodds" not in source
    assert "sgo" not in source


def test_canonical_kyre_player_id_is_provider_independent():
    from runless_v2.nba_pra_player_context_v1 import kyre_player_id
    a = kyre_player_id("Andrew Wiggins", "MIA", "nba")
    b = kyre_player_id(" Andrew  Wiggins ", "mia", "NBA")
    assert a == b
    assert a.startswith("KPID-NBA-")


def test_router_falls_through_degraded_official_to_bref_and_preserves_history():
    from runless_v2.nba_pra_player_context_v1 import collect_nba_pra_player_context

    def official(_day, _names):
        return {"status": "DEGRADED", "profiles": {}, "diagnostic_state": "TIMEOUT"}

    def bref(_day, names):
        assert names == ["Andrew Wiggins"]
        return {
            "status": "HEALTHY",
            "profiles": {
                "andrewwiggins": {
                    "player_name": "Andrew Wiggins",
                    "team": "MIA",
                    "position": "SF",
                    "provider_ids": {"basketball_reference": "wiggian01"},
                    "headshot": "https://cdn.example/wiggian01.jpg",
                    "current_games": [],
                    "prior_games": [
                        {"game_date": "2026-04-10", "minutes": 34, "points": 22, "rebounds": 6, "assists": 4},
                        {"game_date": "2026-04-08", "minutes": 36, "points": 25, "rebounds": 5, "assists": 3},
                        {"game_date": "2026-04-06", "minutes": 35, "points": 20, "rebounds": 7, "assists": 5},
                    ],
                }
            },
        }

    out = collect_nba_pra_player_context(
        date(2026, 10, 21),
        ["Andrew Wiggins"],
        official_loader=official,
        licensed_loaders=[],
        basketball_reference_loader=bref,
    )
    profile = out["profiles"]["andrewwiggins"]
    assert out["provider_health"]["nba_official"]["status"] == "DEGRADED"
    assert out["provider_health"]["basketball_reference"]["status"] == "HEALTHY"
    assert profile["kyre_player_id"].startswith("KPID-NBA-")
    assert profile["provider_ids"]["basketball_reference"] == "wiggian01"
    assert len(profile["prior_games"]) == 3
    assert profile["headshot"]


def test_api_overlay_uses_kyre_api_for_player_context_and_model_edges_populate():
    import nba_pra_page1_api_only_v1 as overlay
    from nba_pra_page1_v2 import build_items

    market_payload = {
        "source": "Kyre Sports API — Vercel",
        "verification": "VERIFIED",
        "observations": [
            {"provider":"FanDuel","player_name":"Andrew Wiggins","sportsbook":"FanDuel","side":"over","line":19.5,"price":-130,"observed_at_utc":"2026-10-21T03:00:00Z","away_team":"MIA","home_team":"ORL"},
            {"provider":"FanDuel","player_name":"Andrew Wiggins","sportsbook":"FanDuel","side":"under","line":19.5,"price":-102,"observed_at_utc":"2026-10-21T03:00:00Z","away_team":"MIA","home_team":"ORL"},
        ],
    }
    context_payload = {
        "verification": "VERIFIED",
        "profiles": {
            "andrewwiggins": {
                "kyre_player_id":"KPID-NBA-ABC",
                "player_name":"Andrew Wiggins","team":"MIA","position":"SF",
                "headshot":"https://cdn.example/wiggins.jpg","stats_source":"Basketball-Reference",
                "provider_ids":{"basketball_reference":"wiggian01"},
                "current_games":[],
                "prior_games":[
                    {"game_date":"2026-04-10","minutes":34,"points":22,"rebounds":6,"assists":4},
                    {"game_date":"2026-04-08","minutes":36,"points":25,"rebounds":5,"assists":3},
                    {"game_date":"2026-04-06","minutes":35,"points":20,"rebounds":7,"assists":5},
                ],
            }
        },
        "provider_health": {"nba_official":{"status":"DEGRADED"},"basketball_reference":{"status":"HEALTHY"}},
    }
    schedule = {"verification":"VERIFIED","games":[{"gameStatus":1,"status":"UPCOMING","game_date":"2026-10-21","away_tricode":"MIA","home_tricode":"ORL"}]}
    snapshot = overlay.load_page1_snapshot_v2(
        now=__import__("datetime").datetime(2026,10,21,1,0,tzinfo=__import__("datetime").timezone.utc),
        schedule_loader=lambda **_: schedule,
        api_loader=lambda _day: market_payload,
        player_context_loader=lambda _day, _names: context_payload,
        injury_loader=lambda *_args, **_kwargs: {"verification":"UNAVAILABLE","features":[]},
    )
    item = build_items(snapshot)[0]
    assert snapshot["profiles"]["andrewwiggins"]["kyre_player_id"] == "KPID-NBA-ABC"
    assert item["headshot"]
    assert item["model"]["projection"] is not None
    assert item["grade"]["over_probability"] is not None
    assert item["grade"]["edge"] is not None


def test_market_server_source_has_no_sgo_path():
    import runless_v2.nba_pra_market_v1 as market
    source = inspect.getsource(market).casefold()
    assert "sportsgameodds" not in source
    assert "sgo_base" not in source
    assert "_fetch_sgo_events" not in source
