from __future__ import annotations

from datetime import date
from pathlib import Path


def _verified_payload():
    return {
        "fabrication": False,
        "verification": "VERIFIED",
        "profiles": {
            "aarongordon": {
                "player_name": "Aaron Gordon",
                "team": "DEN",
                "current_games": [{"points": 10, "rebounds": 5, "assists": 3}],
                "prior_games": [],
            }
        },
        "provider_health": {},
        "requested_players": 1,
        "verified_players": 1,
        "identified_players": 1,
    }


def test_nba_usage_stops_after_first_transport_failure():
    from sports_api.api import nba_pra_usage_v1 as usage

    calls: list[str] = []

    def failing_get(*_args, **kwargs):
        calls.append(str((kwargs.get("params") or {}).get("SeasonType")))
        raise TimeoutError("provider transport down")

    out = usage.load_nba_usage_context(
        date(2026, 10, 26),
        ["Aaron Gordon"],
        request_get=failing_get,
        timeout=0.01,
    )

    assert calls == ["Regular Season"]
    assert "CURRENT_REGULAR_TimeoutError" in out["diagnostic_state"]
    assert "CURRENT_PRESEASON" not in out["diagnostic_state"]
    assert "PRIOR_REGULAR" not in out["diagnostic_state"]


def test_player_context_client_defaults_to_history_only_route():
    import nba_pra_player_context_api_v1 as client

    captured: dict[str, object] = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return _verified_payload()

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    out = client.load_kyre_sports_api_player_context(
        date(2026, 10, 26),
        ["Aaron Gordon"],
        team_codes=["DEN"],
        request_post=fake_post,
    )

    assert out["verified_players"] == 1
    assert str(captured["url"]).endswith("/api/v1/nba/pra/player-context/history")


def test_player_context_client_full_mode_uses_full_route():
    import nba_pra_player_context_api_v1 as client

    captured: dict[str, object] = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return _verified_payload()

    def fake_post(url, **kwargs):
        captured["url"] = url
        return Response()

    client._clear_player_context_cache()
    client.load_kyre_sports_api_player_context(
        date(2026, 10, 26),
        ["Aaron Gordon"],
        team_codes=["DEN"],
        include_usage=True,
        request_post=fake_post,
    )

    assert str(captured["url"]).endswith("/api/v1/nba/pra/player-context")


def test_history_router_uses_field_first_cbs_path_without_redundant_bulk_sweep():
    from sports_api.api import nba_pra_player_context_history_v1 as history

    captured: dict[str, object] = {}
    original = history._HISTORY_COLLECT

    def fake_collect(slate_date, player_names, **kwargs):
        captured["date"] = slate_date
        captured["players"] = list(player_names)
        captured.update(kwargs)
        return {"fabrication": False, "profiles": {}}

    history._HISTORY_COLLECT = fake_collect
    try:
        request = history.NbaPraPlayerContextHistoryRequest(
            date=date(2026, 10, 26),
            player_names=["Aaron Gordon"],
            team_codes=["DEN"],
        )
        out = history.player_context_history(request)
    finally:
        history._HISTORY_COLLECT = original

    assert out["fabrication"] is False
    assert captured["players"] == ["Aaron Gordon"]
    assert captured["team_codes"] == ["DEN"]
    skip = captured["basketball_reference_bulk_history_loader"]
    state = skip(date(2026, 10, 26), ["Aaron Gordon"])
    assert state["profiles"] == {}
    assert state["diagnostic_state"] == "FIELD_FIRST_SKIP_BULK_HISTORY_1"


def test_nba_gateway_registers_history_only_capability_on_compiled_app():
    from sports_api.api import nba_gateway_v1 as gateway
    from kyre_sports_api_vercel_v1 import app

    assert "pra.player-context-history" in gateway.LIVE_CAPABILITIES
    paths = set(app.openapi().get("paths") or {})
    assert "/api/v1/nba/pra/player-context/history" in paths
    assert "/api/v1/nba/pra/player-context" in paths


def test_page1_uses_safe_default_and_page2_explicitly_requests_full_context():
    page1 = Path("nba_pra_page1_api_only_v1.py").read_text(encoding="utf-8")
    page2 = Path("nba_pra_page2_api_only_v1.py").read_text(encoding="utf-8")
    client = Path("nba_pra_player_context_api_v1.py").read_text(encoding="utf-8")

    assert "include_usage: bool = False" in client
    assert "include_usage=True" not in page1
    assert "include_usage=True" in page2
