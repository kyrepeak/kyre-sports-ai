from __future__ import annotations

import importlib
import importlib.util
from datetime import datetime, timezone


def _module():
    spec = importlib.util.find_spec("nba_spread_sportsbook_observations_v2")
    assert spec is not None, "nba_spread_sportsbook_observations_v2 must exist"
    return importlib.import_module("nba_spread_sportsbook_observations_v2")


def _schedule():
    return [
        {
            "game_key": "BOS@DET:2026-10-20",
            "game_date_phoenix": "2026-10-20",
            "away_tricode": "BOS",
            "home_tricode": "DET",
            "away_name": "Boston Celtics",
            "home_name": "Detroit Pistons",
            "status": "UPCOMING",
        },
        {
            "game_key": "PHI@NYK:2026-10-20",
            "game_date_phoenix": "2026-10-20",
            "away_tricode": "PHI",
            "home_tricode": "NYK",
            "away_name": "Philadelphia 76ers",
            "home_name": "New York Knicks",
            "status": "UPCOMING",
        },
    ]


def _event(*, away=-1.5, home=1.5, timestamp="2026-10-19T22:00:00Z", price=-110):
    return {
        "eventID": "evt-bos-det",
        "leagueID": "NBA",
        "teams": {
            "away": {"names": {"long": "Boston Celtics"}},
            "home": {"names": {"long": "Detroit Pistons"}},
        },
        "odds": {
            "away-a": {
                "periodID": "game",
                "betTypeID": "sp",
                "sideID": "away",
                "byBookmaker": {
                    "fanduel": {"available": True, "spread": away, "odds": price, "lastUpdatedAt": timestamp},
                    "draftkings": {"available": True, "spread": away - 0.5, "odds": -105, "lastUpdatedAt": timestamp},
                },
            },
            "home-a": {
                "periodID": "game",
                "betTypeID": "sp",
                "sideID": "home",
                "byBookmaker": {
                    "fanduel": {"available": True, "spread": home, "odds": price, "lastUpdatedAt": timestamp},
                    "draftkings": {"available": True, "spread": -(away - 0.5), "odds": -115, "lastUpdatedAt": timestamp},
                },
            },
        },
    }


def test_normalization_attaches_exact_game_identity_prices_and_times():
    mod = _module()
    rows = mod.normalize_sportsgameodds_spread_observations_v2(
        [_event()], _schedule(), retrieved_at_utc="2026-10-19T22:00:30Z"
    )
    assert len(rows) == 2
    fanduel = next(row for row in rows if row["sportsbook"] == "FanDuel")
    assert fanduel["game_key"] == "BOS@DET:2026-10-20"
    assert fanduel["game_date_phoenix"] == "2026-10-20"
    assert fanduel["away_spread"] == -1.5 and fanduel["home_spread"] == 1.5
    assert fanduel["away_price"] == -110 and fanduel["home_price"] == -110
    assert fanduel["observed_at_utc"] == "2026-10-19T22:00:00Z"
    assert fanduel["retrieved_at_utc"] == "2026-10-19T22:00:30Z"
    assert fanduel["source_transport"] == "SportsGameOdds"


def test_invalid_american_price_is_omitted_not_invented():
    mod = _module()
    rows = mod.normalize_sportsgameodds_spread_observations_v2(
        [_event(price=0)], _schedule(), retrieved_at_utc="2026-10-19T22:00:30Z"
    )
    fanduel = next(row for row in rows if row["sportsbook"] == "FanDuel")
    assert fanduel["away_price"] is None
    assert fanduel["home_price"] is None


def test_conflicting_duplicate_same_book_quote_fails_closed_for_that_book():
    mod = _module()
    event = _event()
    event["odds"]["away-conflict"] = {
        "periodID": "game",
        "betTypeID": "spread",
        "sideID": "away",
        "byBookmaker": {
            "fanduel": {"available": True, "spread": -4.0, "odds": -110, "lastUpdatedAt": "2026-10-19T22:00:00Z"}
        },
    }
    rows = mod.normalize_sportsgameodds_spread_observations_v2(
        [event], _schedule(), retrieved_at_utc="2026-10-19T22:00:30Z"
    )
    assert all(row["sportsbook"] != "FanDuel" for row in rows)
    assert any(row["sportsbook"] == "DraftKings" for row in rows)


def test_wrong_game_identity_and_one_sided_pair_are_rejected():
    mod = _module()
    wrong = _event()
    wrong["teams"]["home"]["names"]["long"] = "Chicago Bulls"
    one_sided = _event()
    del one_sided["odds"]["home-a"]["byBookmaker"]["fanduel"]
    rows = mod.normalize_sportsgameodds_spread_observations_v2(
        [wrong, one_sided], _schedule(), retrieved_at_utc="2026-10-19T22:00:30Z"
    )
    assert all(row["sportsbook"] != "FanDuel" for row in rows)


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_loader_gates_stale_market_instead_of_publishing_it_as_current():
    mod = _module()

    def request_get(*args, **kwargs):
        return _Response({"data": [_event(timestamp="2026-10-19T21:50:00Z")]})

    result = mod.load_verified_sportsbook_observations_v2(
        _schedule(),
        secret_getter=lambda name: "secret" if name == "SPORTSGAMEODDS_API_KEY" else None,
        request_get=request_get,
        now_utc=datetime(2026, 10, 19, 22, 0, 0, tzinfo=timezone.utc),
    )
    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "SPORTSGAMEODDS_STALE_MARKET"
    assert result["observations"] == []


def test_loader_fails_closed_when_credential_missing():
    mod = _module()
    result = mod.load_verified_sportsbook_observations_v2(
        _schedule(), secret_getter=lambda name: None, request_get=lambda *a, **k: None
    )
    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "SPORTSGAMEODDS_CREDENTIAL_UNAVAILABLE"
    assert result["observations"] == []


def test_live_data_repair_v2_binds_v2_transport_without_model_mutation(monkeypatch):
    spec = importlib.util.find_spec("nba_spread_live_data_repair_v2")
    assert spec is not None, "nba_spread_live_data_repair_v2 must exist"
    repair = importlib.import_module("nba_spread_live_data_repair_v2")
    assert repair.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert repair.MAY_MODIFY_MODEL is False
    assert repair.MAY_MODIFY_PROJECTION is False
    assert repair.MAY_MODIFY_PROBABILITY is False

    monkeypatch.setattr(repair, "resolve_sgo_api_key", lambda: "safe-key")
    seen = {}

    def fake_loader(schedule_games, *, secret_getter, **kwargs):
        seen["key"] = secret_getter("SPORTSGAMEODDS_API_KEY")
        return {"verification": "VERIFIED", "diagnostic_state": "OK", "observations": []}

    monkeypatch.setattr(repair, "load_verified_sportsbook_observations_v2", fake_loader)
    result = repair.load_market_payload_v2(_schedule())
    assert seen["key"] == "safe-key"
    assert result["verification"] == "VERIFIED"


def test_transport_verifier_summary_never_echoes_credentials_and_counts_exact_games():
    spec = importlib.util.find_spec("devsystem.verify_nba_spread_market_transport_v1")
    assert spec is not None, "market transport verifier must exist"
    verifier = importlib.import_module("devsystem.verify_nba_spread_market_transport_v1")
    payload = {
        "verification": "VERIFIED",
        "diagnostic_state": "OK",
        "observations": [
            {
                "game_key": "BOS@DET:2026-10-20",
                "sportsbook": "FanDuel",
                "observed_at_utc": "2026-10-19T22:00:00Z",
            },
            {
                "game_key": "BOS@DET:2026-10-20",
                "sportsbook": "DraftKings",
                "observed_at_utc": "2026-10-19T22:00:00Z",
            },
        ],
        "secret": "must-not-leak",
    }
    summary = verifier.summarize_transport_result(payload, credential_resolved=True)
    assert summary["credential_resolved"] is True
    assert summary["games"]["BOS@DET:2026-10-20"]["book_count"] == 2
    assert "secret" not in str(summary).lower()
    assert "must-not-leak" not in str(summary)
