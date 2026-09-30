from __future__ import annotations

from pathlib import Path
import importlib


ROOT = Path(__file__).resolve().parents[1]
API_ROUTE = ROOT / "sports_api" / "api" / "wnba_pra_detail_bundle.py"
STEP3 = ROOT / "wnba_pra_speed_v3_step3_bundle.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_wnba_pra_speed_v3_step3.py"
PUBLIC = ROOT / "devsystem" / "wnba_pra_speed_v3_step3_public_profile.py"
ESPN_HISTORY = ROOT / "sports_api" / "wnba_pra_speed_v3_step3_espn_history.py"
MAIN = ROOT / "sports_api" / "main.py"
APP = ROOT / "app.py"


def test_step3_surfaces_exist():
    assert API_ROUTE.exists(), "Step-3 backend PRA detail bundle route is missing"
    assert STEP3.exists(), "Step-3 Streamlit bundle loader is missing"
    assert ROUTER.exists(), "Step-3 router is missing"
    assert PUBLIC.exists(), "Step-3 public proof is missing"
    assert ESPN_HISTORY.exists(), "Step-3 ESPN history adapter is missing"


def test_step3_backend_bundle_uses_same_certified_sources():
    source = API_ROUTE.read_text(encoding="utf-8")
    assert '@router.get("/players/{player_id}/pra-detail")' in source
    assert "ThreadPoolExecutor(max_workers=2)" in source
    assert "build_step18a_consumer_latest" in source
    assert "get_step3_espn_player_game_log_dataset" in source
    assert '"streamlit_hosted_reads_required": 1' in source
    assert '"projection_run": False' in source
    assert '"sportsbook_network_called": False' in source
    assert '"monte_carlo_run": False' in source


def test_step3_backend_bundle_preserves_component_payloads(monkeypatch):
    module = importlib.import_module("sports_api.api.wnba_pra_detail_bundle")
    raw_consumer = {"data_type": "wnba_step18a_streamlit_consumer_latest", "board": {"available": True}}
    raw_history = {"data_type": "official_player_game_log", "player_id": 123, "games": [{"game_id": "1"}]}

    monkeypatch.setattr(module, "build_step18a_consumer_latest", lambda: raw_consumer)
    observed = {}

    def fake_history(player_id, season):
        observed["player_id"] = player_id
        observed["season"] = season
        return raw_history

    monkeypatch.setattr(
        module,
        "get_step3_espn_player_game_log_dataset",
        fake_history,
    )

    result = module.build_pra_detail_bundle(123, 2026)
    assert result["consumer"] == raw_consumer
    assert result["history"] == raw_history
    assert result["consumer_error"] == ""
    assert result["history_error"] == ""
    assert result["player_id"] == 123
    assert result["season"] == 2026
    assert result["semantics"]["streamlit_hosted_reads_required"] == 1
    assert result["semantics"]["history_source"] == "espn_wnba_athlete_gamelog"
    assert observed == {"player_id": 123, "season": 2026}


def test_step3_current_stats_host_override_is_isolated(monkeypatch):
    history = importlib.import_module("sports_api.wnba_game_history")
    observed = {}

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "resultSets": [
                    {
                        "name": "PlayerGameLog",
                        "headers": [],
                        "rowSet": [],
                    }
                ]
            }

    def fake_get(url, **kwargs):
        observed["url"] = url
        return Response()

    monkeypatch.setattr(history.httpx, "get", fake_get)
    history._CACHE.clear()
    history._request_stats_json(
        history.PLAYER_GAME_LOG_ENDPOINT,
        [("PlayerID", "123")],
        base_url=history.WNBA_CURRENT_STATS_BASE_URL,
    )

    assert observed["url"] == "https://stats.nba.com/stats/playergamelog"
    assert history.WNBA_STATS_BASE_URL == "https://stats.wnba.com/stats"


def test_step3_streamlit_bundle_normalizes_consumer_and_reports_one_read(monkeypatch):
    module = importlib.import_module("wnba_pra_speed_v3_step3_bundle")
    raw_consumer = {"data_type": "wnba_step18a_streamlit_consumer_latest", "board": {"available": True}}
    normalized = {"state": "ready", "cards": [{"player_id": 123}]}
    history = {"data_type": "official_player_game_log", "player_id": 123, "games": []}
    body = {
        "data_type": module.EXPECTED_DATA_TYPE,
        "schema_version": module.EXPECTED_SCHEMA_VERSION,
        "player_id": 123,
        "season": 2026,
        "consumer": raw_consumer,
        "history": history,
        "consumer_error": "",
        "history_error": "",
    }
    monkeypatch.setattr(module, "_read_bundle", lambda player_id: body)
    monkeypatch.setattr(module, "normalize_consumer_payload", lambda value: normalized)

    payload = module.load_bundle_pair("game-1", 123)
    assert payload["consumer"] == normalized
    assert payload["history"] == history
    assert payload["network_reads"] == 1
    assert payload["projection_runs"] == 0
    assert payload["sportsbook_calls"] == 0
    assert payload["ranking_runs"] == 0
    assert payload["monte_carlo_runs"] == 0


def test_step3_router_intercepts_only_frozen_cold_pair_loader():
    source = ROUTER.read_text(encoding="utf-8")
    assert "import streamlit_memory_lazy_router_wnba_pra_speed_v3_step2 as frozen_step2" in source
    assert "import wnba_pra_performance_v2_step5 as performance" in source
    assert "original_cold_loader = performance._FROZEN_PLAYER_LOADER" in source
    assert "performance._FROZEN_PLAYER_LOADER = bundle.load_bundle_pair" in source
    assert "performance._FROZEN_PLAYER_LOADER = original_cold_loader" in source
    assert "finally:" in source
    assert "MAY_MODIFY_WNBA_MODEL = False" in source


def test_step3_backend_router_and_streamlit_activation_are_wired():
    main_source = MAIN.read_text(encoding="utf-8")
    app_source = APP.read_text(encoding="utf-8")
    assert "from sports_api.api.wnba_pra_detail_bundle import router as wnba_pra_detail_bundle_router" in main_source
    assert "app.include_router(wnba_pra_detail_bundle_router)" in main_source
    assert "from streamlit_memory_lazy_router_wnba_pra_speed_v3_step3 import record_bootstrap_import_ms, render_app" in app_source
    assert "Frozen WNBA PRA Speed V3 Step 2 compatibility" in app_source


def test_step3_espn_history_normalizes_current_common_v3_shape(monkeypatch):
    module = importlib.import_module("sports_api.wnba_pra_speed_v3_step3_espn_history")
    monkeypatch.setattr(
        module,
        "get_wnba_teams",
        lambda season: [
            {
                "team_key": "atlanta-dream",
                "slug": "dream",
                "abbreviation": "ATL",
                "nickname": "Dream",
                "full_name": "Atlanta Dream",
            },
            {
                "team_key": "new-york-liberty",
                "slug": "liberty",
                "abbreviation": "NYL",
                "nickname": "Liberty",
                "full_name": "New York Liberty",
            },
        ],
    )
    payload = {
        "team": {"abbreviation": "ATL"},
        "labels": [
            "DATE", "OPP", "RESULT", "MIN", "FG", "3PT", "FT",
            "REB", "AST", "STL", "BLK", "PTS",
        ],
        "names": [
            "date", "opponent", "gameResult", "minutes", "fieldGoals",
            "threePointFieldGoals", "freeThrows", "rebounds", "assists",
            "steals", "blocks", "points",
        ],
        "events": [
            {
                "id": "401000001",
                "date": "2026-09-27T00:00Z",
                "opponent": {"abbreviation": "NYL"},
                "gameResult": "W",
                "atVs": "vs",
                "stats": [
                    "35", "7-14", "2-5", "4-4", "8", "6", "2", "1", "20",
                ],
            }
        ],
    }

    result = module.normalize_espn_wnba_gamelog(
        payload,
        player_id=4398674,
        season=2026,
        retrieved_at_utc="2026-09-30T00:00:00+00:00",
    )

    assert result["data_type"] == "official_player_game_log"
    assert result["source"] == module.ESPN_HISTORY_SOURCE
    assert result["player_id"] == 4398674
    assert result["game_count"] == 1
    game = result["games"][0]
    assert game["game_date"] == "2026-09-27"
    assert game["minutes"] == 35.0
    assert game["field_goals_made"] == 7
    assert game["field_goals_attempted"] == 14
    assert game["three_pointers_made"] == 2
    assert game["three_pointers_attempted"] == 5
    assert game["free_throws_made"] == 4
    assert game["free_throws_attempted"] == 4
    assert game["rebounds"] == 8
    assert game["assists"] == 6
    assert game["steals"] == 2
    assert game["blocks"] == 1
    assert game["points"] == 20
    assert game["matchup"]["team_key"] == "atlanta-dream"
    assert game["matchup"]["opponent_team_key"] == "new-york-liberty"


def test_step3_espn_history_request_is_bounded():
    module = importlib.import_module("sports_api.wnba_pra_speed_v3_step3_espn_history")
    assert module.REQUEST_TIMEOUT_SECONDS < 5.0
    assert module.CACHE_TTL_SECONDS >= 60
