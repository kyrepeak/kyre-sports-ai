from __future__ import annotations

from datetime import datetime, timezone
import importlib.util


NOW = datetime(2026, 10, 18, 18, 30, tzinfo=timezone.utc)


def _collector():
    module_name = "sports_api.collectors.wnba_fanduel_direct"
    assert importlib.util.find_spec(module_name) is not None, "WNBA FanDuel collector is not implemented yet"
    from sports_api.collectors.wnba_fanduel_direct import collect_fanduel_wnba_feed

    return collect_fanduel_wnba_feed


def _runner(runner_id: str, side: str, line=31.5, odds=-110):
    return {
        "runnerId": runner_id,
        "runnerStatus": "ACTIVE",
        "result": {"type": side},
        "handicap": line,
        "winRunnerOdds": {"americanDisplayOdds": {"americanOdds": odds}},
    }


def _event(event_id="9001", name="Atlanta Dream @ Golden State Valkyries"):
    return {
        "eventId": event_id,
        "name": name,
        "openDate": "2026-10-19T00:00:00Z",
        "eventStatus": "OPEN",
    }


def _pra_market(
    market_id="m-pra-gray",
    event_id="9001",
    player="Allisha Gray",
    *,
    status="OPEN",
    in_play=False,
    line=31.5,
    updated="2026-10-18T18:29:00Z",
):
    return {
        "marketId": market_id,
        "eventId": event_id,
        "marketName": f"{player} - Points + Rebounds + Assists",
        "marketStatus": status,
        "inPlay": in_play,
        "lastUpdate": updated,
        "runners": {
            "o": _runner(f"{market_id}-o", "OVER", line=line, odds=-108),
            "u": _runner(f"{market_id}-u", "UNDER", line=line, odds=-112),
        },
    }


def _requester(landing, event_page):
    calls = []

    def request(path, params):
        calls.append((path, dict(params)))
        if path.endswith("content-managed-page"):
            return landing
        if path.endswith("event-page"):
            return event_page
        raise AssertionError(path)

    request.calls = calls
    return request


def _landing(events):
    return {"attachments": {"events": events}}


def _event_page(markets, events=None):
    return {"attachments": {"events": events or [_event()], "markets": markets}}


def test_collect_fanduel_wnba_feed_emits_only_pregame_pra_offers():
    collect_fanduel_wnba_feed = _collector()
    open_pra = _pra_market()
    in_play = _pra_market("m-live", player="Rhyne Howard", in_play=True)
    closed = _pra_market("m-closed", player="Veronica Burton", status="SUSPENDED")
    points = {
        **_pra_market("m-points", player="Gabby Williams"),
        "marketName": "Gabby Williams - Points",
    }
    requester = _requester(_landing({"9001": _event()}), _event_page([open_pra, in_play, closed, points]))

    out = collect_fanduel_wnba_feed(
        date="2026-10-19",
        season=2026,
        requester=requester,
        now_utc=NOW,
    )

    offers = out["raw_feed"]["offers"]
    assert len(offers) == 2
    assert {row["side"] for row in offers} == {"over", "under"}
    assert {row["stat"] for row in offers} == {"pra"}
    assert {row["player_name"] for row in offers} == {"Allisha Gray"}
    assert out["provider_id"] == "fanduel"
    assert out["feed_format"] == "canonical_offers_v1"
    assert out["odds_format"] == "american"


def test_collect_fanduel_wnba_feed_preserves_source_ids_and_timestamps():
    collect_fanduel_wnba_feed = _collector()
    requester = _requester(_landing([_event()]), _event_page([_pra_market()]))

    out = collect_fanduel_wnba_feed(
        date="2026-10-19",
        requester=requester,
        now_utc=NOW,
    )

    over = next(row for row in out["raw_feed"]["offers"] if row["side"] == "over")
    assert over["source_event_id"] == "9001"
    assert over["source_market_id"] == "m-pra-gray"
    assert over["source_offer_id"] == "m-pra-gray-o"
    assert over["market_captured_at_utc"] == "2026-10-18T18:29:00+00:00"
    assert over["sportsbook"] == "FanDuel"
    assert over["away_team"] == "Atlanta Dream"
    assert over["home_team"] == "Golden State Valkyries"


def test_collect_fanduel_wnba_feed_does_not_invent_missing_lines():
    collect_fanduel_wnba_feed = _collector()
    market = _pra_market()
    market["runners"]["o"].pop("handicap")
    requester = _requester(_landing([_event()]), _event_page([market]))

    out = collect_fanduel_wnba_feed(
        date="2026-10-19",
        requester=requester,
        now_utc=NOW,
    )

    assert [row["side"] for row in out["raw_feed"]["offers"]] == ["under"]
    assert out["raw_feed"]["offers"][0]["line"] == 31.5


def test_collect_fanduel_wnba_feed_handles_attachment_maps_and_lists():
    collect_fanduel_wnba_feed = _collector()
    map_requester = _requester(
        _landing({"9001": _event()}),
        {"attachments": {"events": {"9001": _event()}, "markets": {"m": _pra_market()}}},
    )
    list_requester = _requester(
        _landing([_event()]),
        {"attachments": {"events": [_event()], "markets": [_pra_market()]}},
    )

    mapped = collect_fanduel_wnba_feed(date="2026-10-19", requester=map_requester, now_utc=NOW)
    listed = collect_fanduel_wnba_feed(date="2026-10-19", requester=list_requester, now_utc=NOW)

    assert mapped["raw_feed"]["offers"] == listed["raw_feed"]["offers"]


def test_collect_fanduel_wnba_feed_excludes_non_pra_player_markets():
    collect_fanduel_wnba_feed = _collector()
    markets = [
        {**_pra_market("m-reb", player="Allisha Gray"), "marketName": "Allisha Gray - Rebounds"},
        {**_pra_market("m-ast", player="Rhyne Howard"), "marketName": "Rhyne Howard - Assists"},
        {**_pra_market("m-pra", player="Veronica Burton"), "marketName": "Veronica Burton - PRA"},
    ]
    requester = _requester(_landing([_event()]), _event_page(markets))

    out = collect_fanduel_wnba_feed(date="2026-10-19", requester=requester, now_utc=NOW)

    assert {row["player_name"] for row in out["raw_feed"]["offers"]} == {"Veronica Burton"}
    assert all(row["stat"] == "pra" for row in out["raw_feed"]["offers"])
