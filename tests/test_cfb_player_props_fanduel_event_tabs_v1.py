import threading

import cfb_player_props_fanduel_bound_v2 as fanduel


def _runner(name, side, line, price):
    return {
        "runnerName": f"{name} {side.title()}",
        "handicap": line,
        "runnerStatus": "ACTIVE",
        "result": {"type": side.upper()},
        "winRunnerOdds": {
            "americanDisplayOdds": {
                "americanOdds": price,
                "americanOddsInt": price,
            }
        },
    }


def test_fetch_uses_popular_event_tab_and_normalizes_standard_player_props(monkeypatch):
    game = {
        "official_game_id": "401765432",
        "away_team": "Middle Tennessee",
        "home_team": "FIU",
        "kickoff_iso": "2026-10-20T23:00:00Z",
    }
    landing = {
        "attachments": {
            "events": {
                "36194208": {
                    "eventId": "36194208",
                    "name": "Middle Tennessee @ FIU",
                    "openDate": "2026-10-20T23:00:00Z",
                }
            },
            "markets": {},
        }
    }
    popular = {
        "attachments": {
            "events": landing["attachments"]["events"],
            "markets": {
                "pass": {
                    "marketId": "pass",
                    "eventId": "36194208",
                    "marketName": "Roman Gagliano - Passing Yds",
                    "marketStatus": "OPEN",
                    "inPlay": False,
                    "runners": [
                        _runner("Roman Gagliano", "over", 194.5, -114),
                        _runner("Roman Gagliano", "under", 194.5, -114),
                    ],
                },
                "rush": {
                    "marketId": "rush",
                    "eventId": "36194208",
                    "marketName": "Roman Gagliano - Rushing Yds",
                    "marketStatus": "OPEN",
                    "inPlay": False,
                    "runners": [
                        _runner("Roman Gagliano", "over", 11.5, -114),
                        _runner("Roman Gagliano", "under", 11.5, -114),
                    ],
                },
                "pass_td": {
                    "marketId": "pass_td",
                    "eventId": "36194208",
                    "marketName": "Roman Gagliano - Passing TDs",
                    "marketStatus": "OPEN",
                    "inPlay": False,
                    "runners": [
                        _runner("Roman Gagliano", "over", 0.5, 178),
                        _runner("Roman Gagliano", "under", 0.5, -245),
                    ],
                },
                "alt": {
                    "marketId": "alt",
                    "eventId": "36194208",
                    "marketName": "Roman Gagliano - Alt Passing Yds",
                    "marketStatus": "OPEN",
                    "inPlay": False,
                    "runners": [
                        {
                            "runnerName": "Roman Gagliano 125+ Yards",
                            "handicap": 0,
                            "runnerStatus": "ACTIVE",
                            "result": {},
                        }
                    ],
                },
            },
        }
    }

    calls = []
    monkeypatch.setattr(fanduel, "_fetch_payload", lambda: landing)
    monkeypatch.setattr(
        fanduel,
        "_fetch_event_page",
        lambda event_id, tab="popular": calls.append((event_id, tab)) or popular,
        raising=False,
    )

    rows = fanduel.fetch_fanduel_cfb_player_props([game])

    assert calls == [("36194208", "popular")]
    assert len(rows) == 6
    assert {row["player_name"] for row in rows} == {"Roman Gagliano"}
    assert {row["official_game_id"] for row in rows} == {"401765432"}
    assert {(row["stat_id"], row["line"]) for row in rows} == {
        ("passing_yards", 194.5),
        ("rushing_yards", 11.5),
        ("passing_touchdowns", 0.5),
    }
    assert {(row["stat_id"], row["side"], row["price"]) for row in rows} >= {
        ("passing_yards", "over", -114),
        ("passing_yards", "under", -114),
        ("passing_touchdowns", "over", 178),
        ("passing_touchdowns", "under", -245),
    }


def test_fetch_rejects_two_way_alternate_ladder_markets(monkeypatch):
    game = {
        "official_game_id": "401765432",
        "away_team": "Middle Tennessee",
        "home_team": "FIU",
        "kickoff_iso": "2026-10-20T23:00:00Z",
    }
    events = {
        "36194208": {
            "eventId": "36194208",
            "name": "Middle Tennessee @ FIU",
            "openDate": "2026-10-20T23:00:00Z",
        }
    }
    landing = {"attachments": {"events": events, "markets": {}}}
    popular = {
        "attachments": {
            "events": events,
            "markets": {
                "canonical": {
                    "marketId": "canonical",
                    "eventId": "36194208",
                    "marketName": "Roman Gagliano - Passing Yds",
                    "marketStatus": "OPEN",
                    "inPlay": False,
                    "runners": [
                        _runner("Roman Gagliano", "over", 194.5, -114),
                        _runner("Roman Gagliano", "under", 194.5, -114),
                    ],
                },
                "alternate": {
                    "marketId": "alternate",
                    "eventId": "36194208",
                    "marketName": "Roman Gagliano - Alt Passing Yds",
                    "marketStatus": "OPEN",
                    "inPlay": False,
                    "runners": [
                        _runner("Roman Gagliano", "over", 224.5, 122),
                        _runner("Roman Gagliano", "under", 224.5, -156),
                    ],
                },
            },
        }
    }

    monkeypatch.setattr(fanduel, "_fetch_payload", lambda: landing)
    monkeypatch.setattr(fanduel, "_fetch_event_page", lambda *_args, **_kwargs: popular)

    rows = fanduel.fetch_fanduel_cfb_player_props([game])

    assert len(rows) == 2
    assert {row["provider_market_id"] for row in rows} == {"canonical"}
    assert {row["line"] for row in rows} == {194.5}


def test_full_slate_event_detail_fetches_overlap_instead_of_running_serially(monkeypatch):
    games = []
    events = {}
    for idx in range(4):
        event_id = str(9000 + idx)
        away = f"Away {idx}"
        home = f"Home {idx}"
        kickoff = f"2026-10-2{idx}T23:00:00Z"
        games.append(
            {
                "official_game_id": str(401700000 + idx),
                "away_team": away,
                "home_team": home,
                "kickoff_iso": kickoff,
            }
        )
        events[event_id] = {
            "eventId": event_id,
            "name": f"{away} @ {home}",
            "openDate": kickoff,
        }

    landing = {"attachments": {"events": events, "markets": {}}}
    monkeypatch.setattr(fanduel, "_fetch_payload", lambda: landing)

    lock = threading.Lock()
    release = threading.Event()
    active = 0
    max_active = 0

    def fake_fetch_event_page(_event_id, _tab="popular"):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
            if active >= 2:
                release.set()
        release.wait(0.08)
        with lock:
            active -= 1
        return {"attachments": {"markets": {}}}

    monkeypatch.setattr(fanduel, "_fetch_event_page", fake_fetch_event_page)

    fanduel.fetch_fanduel_cfb_player_props(games)

    assert max_active >= 2
