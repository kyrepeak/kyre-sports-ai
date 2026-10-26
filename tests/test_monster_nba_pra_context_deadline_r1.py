from __future__ import annotations

from datetime import date


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


def test_player_context_client_forwards_include_usage_false():
    import nba_pra_player_context_api_v1 as client

    captured: dict[str, object] = {}

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
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

    def fake_post(_url, **kwargs):
        captured.update(kwargs)
        return Response()

    out = client.load_kyre_sports_api_player_context(
        date(2026, 10, 26),
        ["Aaron Gordon"],
        team_codes=["DEN"],
        include_usage=False,
        request_post=fake_post,
    )

    assert out["verified_players"] == 1
    assert (captured["json"] or {})["include_usage"] is False


def test_player_context_route_forwards_include_usage_false():
    from sports_api.api import nba_pra_player_context_v1 as api

    captured: dict[str, object] = {}
    original = api.collect_nba_pra_player_context

    def fake_collect(slate_date, player_names, **kwargs):
        captured["date"] = slate_date
        captured["player_names"] = list(player_names)
        captured.update(kwargs)
        return {"fabrication": False, "profiles": {}}

    api.collect_nba_pra_player_context = fake_collect
    try:
        request = api.NbaPraPlayerContextRequest(
            date=date(2026, 10, 26),
            player_names=["Aaron Gordon"],
            team_codes=["DEN"],
            include_usage=False,
        )
        api.player_context(request)
    finally:
        api.collect_nba_pra_player_context = original

    assert captured["include_usage"] is False


def test_usage_enrichment_skips_provider_when_field_not_requested():
    from sports_api.api import nba_pra_player_context_enrichment_v2 as enrichment

    original = enrichment._BASE_COLLECT
    calls = {"usage": 0}

    def base_collect(_slate_date, player_names, **_kwargs):
        name = player_names[0]
        return {
            "fabrication": False,
            "profiles": {
                "aarongordon": {
                    "player_name": name,
                    "current_games": [{"points": 10, "rebounds": 5, "assists": 3}],
                    "prior_games": [],
                }
            },
            "provider_health": {},
        }

    def usage_loader(*_args, **_kwargs):
        calls["usage"] += 1
        raise AssertionError("usage provider must not run")

    enrichment._BASE_COLLECT = base_collect
    try:
        out = enrichment.collect_nba_pra_player_context(
            date(2026, 10, 26),
            ["Aaron Gordon"],
            team_codes=["DEN"],
            include_usage=False,
            usage_loader=usage_loader,
        )
    finally:
        enrichment._BASE_COLLECT = original

    assert calls["usage"] == 0
    assert out["provider_health"]["nba_usage"]["attempted"] is False
    assert out["provider_health"]["nba_usage"]["detail"] == "FIELD_NOT_REQUESTED"


def test_page1_requests_history_without_usage_but_page2_keeps_usage():
    import nba_pra_page1_api_only_v1 as page1
    import nba_pra_page2_api_only_v1 as page2

    page1_source = open(page1.__file__, encoding="utf-8").read()
    page2_source = open(page2.__file__, encoding="utf-8").read()

    assert "include_usage=False" in page1_source
    assert "include_usage=True" in page2_source
