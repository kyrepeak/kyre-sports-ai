from __future__ import annotations

from datetime import date
from threading import Lock


def _profile(name: str) -> dict:
    return {
        "player_name": name,
        "team": "TST",
        "current_games": [{"game_date": "2026-10-25", "points": 20, "rebounds": 5, "assists": 5}],
        "prior_games": [],
        "data_state": "VERIFIED",
        "stats_source": "TEST",
    }


def test_history_only_client_batches_large_player_pool_in_parallel_safe_chunks():
    import nba_pra_player_context_api_v1 as client

    client._clear_player_context_cache()
    names = [f"Player {index}" for index in range(40)]
    calls: list[dict] = []
    lock = Lock()

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_post(url, **kwargs):
        requested = list((kwargs.get("json") or {}).get("player_names") or [])
        with lock:
            calls.append({"url": url, "names": requested})
        profiles = {
            "".join(ch for ch in name.casefold() if ch.isalnum()): _profile(name)
            for name in requested
        }
        return Response(
            {
                "fabrication": False,
                "verification": "VERIFIED",
                "profiles": profiles,
                "provider_health": {},
                "requested_players": len(requested),
                "verified_players": len(requested),
                "identified_players": len(requested),
            }
        )

    out = client.load_kyre_sports_api_player_context(
        date(2026, 10, 26),
        names,
        team_codes=["TST"],
        request_post=fake_post,
    )

    assert out["verification"] == "VERIFIED"
    assert out["requested_players"] == 40
    assert out["verified_players"] == 40
    assert len(out["profiles"]) == 40
    assert 2 <= len(calls) <= 4
    assert max(len(call["names"]) for call in calls) <= 16
    assert all(str(call["url"]).endswith("/api/v1/nba/pra/player-context/history") for call in calls)


def test_full_context_mode_stays_single_request_for_page2():
    import nba_pra_player_context_api_v1 as client

    client._clear_player_context_cache()
    calls: list[list[str]] = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "fabrication": False,
                "verification": "VERIFIED",
                "profiles": {"aarongordon": _profile("Aaron Gordon")},
                "provider_health": {},
                "requested_players": 1,
                "verified_players": 1,
                "identified_players": 1,
            }

    def fake_post(url, **kwargs):
        assert str(url).endswith("/api/v1/nba/pra/player-context")
        calls.append(list((kwargs.get("json") or {}).get("player_names") or []))
        return Response()

    out = client.load_kyre_sports_api_player_context(
        date(2026, 10, 26),
        ["Aaron Gordon"],
        team_codes=["DEN"],
        include_usage=True,
        request_post=fake_post,
    )

    assert calls == [["Aaron Gordon"]]
    assert out["verified_players"] == 1


def test_history_batch_failure_fails_closed_without_fabricating_profiles():
    import nba_pra_player_context_api_v1 as client

    client._clear_player_context_cache()
    names = [f"Player {index}" for index in range(20)]

    def failing_post(*_args, **_kwargs):
        raise TimeoutError("chunk unavailable")

    out = client.load_kyre_sports_api_player_context(
        date(2026, 10, 26),
        names,
        team_codes=["TST"],
        request_post=failing_post,
    )

    assert out["verification"] == "DATA_UNAVAILABLE"
    assert out["profiles"] == {}
    assert out["fabrication"] is False
    assert "TimeoutError" in out["diagnostic_state"]
