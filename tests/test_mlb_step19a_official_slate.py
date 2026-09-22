from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api.collectors.mlb_official_slate import (
    MLBOfficialSlateError,
    SCHEDULE_URL,
    collect_official_mlb_slate,
)


class FakeResponse:
    def __init__(self, payload=None, *, status_code=200, json_error=None):
        self._payload = payload
        self.status_code = status_code
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return deepcopy(self._payload)


class FakeSession:
    def __init__(self, response=None, *, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append({"url": url, "params": deepcopy(params), "timeout": timeout})
        if self.error is not None:
            raise self.error
        return self.response


def _side(team_id, team_name, *, pitcher_id=None, pitcher_name=None):
    side = {"team": {"id": team_id, "name": team_name}}
    if pitcher_id is not None or pitcher_name is not None:
        side["probablePitcher"] = {"id": pitcher_id, "fullName": pitcher_name}
    return side


def _game(
    game_pk,
    away_id,
    away_name,
    home_id,
    home_name,
    *,
    game_date="2026-09-02T23:10:00Z",
    detailed_state="Scheduled",
    abstract_state="Preview",
    status_code="S",
    double_header="N",
    game_number=1,
    away_pitcher=(101, "Away Starter"),
    home_pitcher=(202, "Home Starter"),
    reschedule_date=None,
):
    game = {
        "gamePk": game_pk,
        "gameDate": game_date,
        "officialDate": "2026-09-02",
        "gameType": "R",
        "status": {
            "abstractGameState": abstract_state,
            "detailedState": detailed_state,
            "statusCode": status_code,
            "startTimeTBD": False,
        },
        "teams": {
            "away": _side(
                away_id,
                away_name,
                pitcher_id=away_pitcher[0] if away_pitcher else None,
                pitcher_name=away_pitcher[1] if away_pitcher else None,
            ),
            "home": _side(
                home_id,
                home_name,
                pitcher_id=home_pitcher[0] if home_pitcher else None,
                pitcher_name=home_pitcher[1] if home_pitcher else None,
            ),
        },
        "doubleHeader": double_header,
        "gameNumber": game_number,
        "seriesGameNumber": game_number,
        "scheduledInnings": 9,
    }
    if reschedule_date is not None:
        game["rescheduleDate"] = reschedule_date
    return game


def _payload(*games):
    return {
        "totalGames": len(games),
        "dates": [] if not games else [{"date": "2026-09-02", "games": list(games)}],
    }


def _collect(payload, *, timeout_seconds=7.5):
    session = FakeSession(FakeResponse(payload))
    result = collect_official_mlb_slate(
        slate_date="2026-09-02",
        session=session,
        timeout_seconds=timeout_seconds,
    )
    return result, session


def test_collects_official_slate_with_exact_request_contract():
    result, session = _collect(
        _payload(_game(777001, 10, "Away Club", 20, "Home Club"))
    )

    assert result["sport"] == "MLB"
    assert result["slate_date"] == "2026-09-02"
    assert result["game_count"] == 1
    assert result["source"] == "MLB Stats API"
    assert result["collected_at_utc"].endswith("+00:00")
    assert session.calls == [
        {
            "url": SCHEDULE_URL,
            "params": {
                "sportId": 1,
                "date": "2026-09-02",
                "hydrate": "team,probablePitcher",
            },
            "timeout": 7.5,
        }
    ]


def test_normalizes_exact_game_team_and_probable_pitcher_identity():
    result, _ = _collect(_payload(_game(777001, 10, "Away Club", 20, "Home Club")))
    game = result["games"][0]

    assert game["game_pk"] == 777001
    assert game["away_team"] == {"id": 10, "name": "Away Club"}
    assert game["home_team"] == {"id": 20, "name": "Home Club"}
    assert game["away_probable_pitcher"] == {"id": 101, "name": "Away Starter"}
    assert game["home_probable_pitcher"] == {"id": 202, "name": "Home Starter"}
    assert game["status"] == "scheduled"
    assert game["doubleheader"] is False


def test_probable_pitchers_may_be_absent_without_fabrication():
    result, _ = _collect(
        _payload(
            _game(
                777001,
                10,
                "Away Club",
                20,
                "Home Club",
                away_pitcher=None,
                home_pitcher=None,
            )
        )
    )
    game = result["games"][0]
    assert game["away_probable_pitcher"] is None
    assert game["home_probable_pitcher"] is None


def test_postponed_game_is_preserved_not_dropped():
    result, _ = _collect(
        _payload(
            _game(
                777010,
                10,
                "Away Club",
                20,
                "Home Club",
                detailed_state="Postponed",
                abstract_state="Preview",
                status_code="P",
                reschedule_date="2026-09-04T18:10:00Z",
            )
        )
    )
    game = result["games"][0]
    assert game["status"] == "postponed"
    assert game["is_postponed"] is True
    assert game["is_cancelled"] is False
    assert game["reschedule_date"] == "2026-09-04T18:10:00Z"


def test_cancelled_game_is_preserved_not_dropped():
    result, _ = _collect(
        _payload(
            _game(
                777011,
                10,
                "Away Club",
                20,
                "Home Club",
                detailed_state="Cancelled",
                abstract_state="Final",
                status_code="C",
            )
        )
    )
    game = result["games"][0]
    assert game["status"] == "cancelled"
    assert game["is_cancelled"] is True


def test_doubleheader_keeps_both_exact_game_ids_for_same_clubs():
    first = _game(
        777021,
        10,
        "Away Club",
        20,
        "Home Club",
        game_date="2026-09-02T17:10:00Z",
        double_header="Y",
        game_number=1,
    )
    second = _game(
        777022,
        10,
        "Away Club",
        20,
        "Home Club",
        game_date="2026-09-02T23:40:00Z",
        double_header="Y",
        game_number=2,
    )
    result, _ = _collect(_payload(second, first))

    assert result["game_count"] == 2
    assert [game["game_pk"] for game in result["games"]] == [777021, 777022]
    assert [game["game_number"] for game in result["games"]] == [1, 2]
    assert all(game["doubleheader"] is True for game in result["games"])


def test_empty_official_slate_is_valid():
    result, _ = _collect({"totalGames": 0, "dates": []})
    assert result["game_count"] == 0
    assert result["games"] == []


def test_unknown_provider_status_is_preserved_as_unknown_with_detail():
    result, _ = _collect(
        _payload(
            _game(
                777030,
                10,
                "Away Club",
                20,
                "Home Club",
                detailed_state="Future MLB State",
                abstract_state="Mystery",
                status_code="X",
            )
        )
    )
    game = result["games"][0]
    assert game["status"] == "unknown"
    assert game["status_detail"] == "Future MLB State"


def test_duplicate_game_pk_fails_closed():
    duplicate = _game(777040, 10, "Away Club", 20, "Home Club")
    with pytest.raises(MLBOfficialSlateError, match="duplicate gamePk") as exc_info:
        _collect(_payload(duplicate, deepcopy(duplicate)))
    assert exc_info.value.category == "malformed_payload"


def test_declared_total_games_mismatch_fails_closed():
    payload = _payload(_game(777041, 10, "Away Club", 20, "Home Club"))
    payload["totalGames"] = 2
    with pytest.raises(MLBOfficialSlateError, match="totalGames mismatch") as exc_info:
        _collect(payload)
    assert exc_info.value.category == "malformed_payload"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda game: game.pop("gamePk"),
        lambda game: game["teams"]["away"]["team"].pop("id"),
        lambda game: game["teams"]["home"]["team"].update(name=""),
        lambda game: game.update(status=None),
        lambda game: game["teams"]["away"].update(probablePitcher={"id": 101}),
        lambda game: game["status"].update(startTimeTBD="false"),
    ],
)
def test_incomplete_or_type_corrupt_official_identity_fails_closed(mutator):
    game = _game(777050, 10, "Away Club", 20, "Home Club")
    mutator(game)
    with pytest.raises(MLBOfficialSlateError) as exc_info:
        _collect(_payload(game))
    assert exc_info.value.category == "malformed_payload"


@pytest.mark.parametrize("value", ["", "2026/09/02", "09-02-2026", "not-a-date"])
def test_invalid_date_is_rejected_before_network(value):
    session = FakeSession(FakeResponse({"totalGames": 0, "dates": []}))
    with pytest.raises(MLBOfficialSlateError) as exc_info:
        collect_official_mlb_slate(slate_date=value, session=session)
    assert exc_info.value.category == "invalid_request"
    assert session.calls == []


def test_http_failure_is_categorized_fail_closed():
    session = FakeSession(FakeResponse({}, status_code=503))
    with pytest.raises(MLBOfficialSlateError) as exc_info:
        collect_official_mlb_slate(slate_date="2026-09-02", session=session)
    assert exc_info.value.category == "http_error"


def test_json_parse_failure_is_categorized_fail_closed():
    session = FakeSession(FakeResponse(json_error=ValueError("bad json")))
    with pytest.raises(MLBOfficialSlateError) as exc_info:
        collect_official_mlb_slate(slate_date="2026-09-02", session=session)
    assert exc_info.value.category == "parse_error"


def test_transport_failure_is_categorized_fail_closed():
    session = FakeSession(error=TimeoutError("timed out"))
    with pytest.raises(MLBOfficialSlateError) as exc_info:
        collect_official_mlb_slate(slate_date="2026-09-02", session=session)
    assert exc_info.value.category == "transport_error"


def test_bad_timeout_env_falls_back_to_safe_default(monkeypatch):
    monkeypatch.setenv("MLB_OFFICIAL_SLATE_TIMEOUT_SECONDS", "bad")
    session = FakeSession(FakeResponse({"totalGames": 0, "dates": []}))
    collect_official_mlb_slate(slate_date="2026-09-02", session=session)
    assert session.calls[0]["timeout"] == 10.0
