from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
import sys

import pytest

import mlb_step9c_live_state_consumer_v1 as step9c


GAME_ID = 824911


def _context(game_id=GAME_ID):
    return {
        "official_game_id": game_id,
        "status": "In Progress",
        "state": "LIVE",
        "away_team": "Away Club",
        "home_team": "Home Club",
        "away_runs": 3,
        "home_runs": 2,
        "away_hits": 7,
        "home_hits": 6,
        "away_errors": 0,
        "home_errors": 1,
        "inning": "7th",
        "inning_state": "Top",
        "balls": 2,
        "strikes": 1,
        "outs": 1,
        "batter_id": 101,
        "batter": "Batter Display",
        "pitcher_id": 202,
        "pitcher": "Pitcher Display",
        "on_deck": "On Deck",
        "in_hole": "In Hole",
        "runner_first_id": 303,
        "first": "Runner One",
        "runner_second_id": None,
        "second": None,
        "runner_third_id": 404,
        "third": None,
        "last_play": "Single to right.",
        "last_pitch_desc": "Ball",
        "last_pitch_type": "Four-Seam Fastball",
        "last_pitch_speed": 96.4,
        "recent_plays": [
            {"Inning": "Top 7", "Play": "Single to right.", "Score": "3-2"}
        ],
        "match_method": "official_mlb_game_id_exact",
        "fallback_matching_used": False,
        "team_name_matching_used": False,
        "data_type": "mlb_step9a_live_game_state_context_v1",
        "schema_version": 1,
        "source": "MLB Stats API",
        "feed_fresh": True,
        "player_name_matching_used": False,
        "fuzzy_matching_allowed": False,
        "synthetic_game_id_allowed": False,
        "sportsbook_price_model_input": False,
    }


def _api_payload(game_id=GAME_ID):
    game = _context(game_id)
    for key in (
        "match_method",
        "fallback_matching_used",
        "team_name_matching_used",
        "data_type",
        "schema_version",
        "source",
        "feed_fresh",
        "player_name_matching_used",
        "fuzzy_matching_allowed",
        "synthetic_game_id_allowed",
        "sportsbook_price_model_input",
    ):
        game.pop(key, None)
    return {
        "data_type": "mlb_live_game_state_api_response_v1",
        "schema_version": 1,
        "source": "MLB Stats API",
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "games": [game],
    }


def _fake_v19(monkeypatch):
    fake = ModuleType("live_game_hub_v19")
    calls = {"feed": [], "state": [], "render": [], "clear": 0}

    def legacy_feed(game_pk):
        calls["feed"].append(game_pk)
        return {"legacy": True, "game_pk": game_pk}

    def clear():
        calls["clear"] += 1

    legacy_feed.clear = clear

    def legacy_state(feed):
        calls["state"].append(deepcopy(feed))
        return {"legacy_state": deepcopy(feed)}

    def parse_inning(value):
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())
        return max(1, int(digits)) if digits else 1

    fake.fetch_live_feed = legacy_feed
    fake._state = legacy_state
    fake._parse_inning = parse_inning
    fake.ET = timezone.utc

    def legacy_render(game, section_header):
        calls["render"].append(deepcopy(game))
        return fake._state(fake.fetch_live_feed(game["game_pk"]))

    fake._render_selected = legacy_render
    monkeypatch.setitem(sys.modules, "live_game_hub_v19", fake)
    return fake, calls


def _game(game_id=GAME_ID):
    return {
        "game_pk": game_id,
        "game_date": "2026-08-31",
        "away_team_id": 10,
        "home_team_id": 20,
        "away_team": "Legacy Away",
        "home_team": "Legacy Home",
        "away_pitcher_id": 700,
        "home_pitcher_id": 800,
        "venue_name": "Legacy Park",
    }


def test_certified_context_uses_frozen_step9a_contract():
    seen = {}

    def getter(game_id, *, game_date):
        seen.update({"game_id": game_id, "game_date": game_date})
        return _api_payload(game_id)

    result = step9c._certified_context(
        GAME_ID,
        game_date="2026-08-31",
        payload_getter=getter,
    )
    assert result is not None
    assert result["official_game_id"] == GAME_ID
    assert result["match_method"] == "official_mlb_game_id_exact"
    assert result["feed_fresh"] is True
    assert seen == {"game_id": GAME_ID, "game_date": "2026-08-31"}


def test_certified_context_rejects_wrong_exact_game_id():
    def getter(game_id, *, game_date):
        return _api_payload(game_id + 1)

    assert step9c._certified_context(
        GAME_ID,
        game_date="2026-08-31",
        payload_getter=getter,
    ) is None


def test_state_mapping_preserves_v19_shape_and_exact_legacy_team_ids():
    fake = SimpleNamespace(
        _parse_inning=lambda value: 7,
        ET=timezone.utc,
    )
    source = _context()
    source_copy = deepcopy(source)
    state = step9c._state_from_context(source, _game(), v19_module=fake)

    assert state["state"] == "LIVE"
    assert state["away_team_id"] == 10
    assert state["home_team_id"] == 20
    assert state["pitcher_id"] == 202
    assert state["batter_id"] == 101
    assert state["inning_num"] == 7
    assert state["first"] == "Runner One"
    assert state["second"] == "Empty"
    assert state["third"] == "Occupied"
    assert state["recent"] == source["recent_plays"]
    state["recent"][0]["Play"] = "mutated"
    assert source == source_copy


def test_state_mapping_rejects_metadata_game_id_mismatch():
    with pytest.raises(RuntimeError, match="gamePk"):
        step9c._state_from_context(
            _context(),
            _game(GAME_ID + 1),
            v19_module=SimpleNamespace(_parse_inning=lambda value: 7, ET=timezone.utc),
        )


def test_state_mapping_requires_legacy_team_ids():
    game = _game()
    game["away_team_id"] = None
    with pytest.raises(RuntimeError, match="team-ID"):
        step9c._state_from_context(
            _context(),
            game,
            v19_module=SimpleNamespace(_parse_inning=lambda value: 7, ET=timezone.utc),
        )


def test_installer_api_first_exact_id_and_no_model_mutation(monkeypatch):
    fake, calls = _fake_v19(monkeypatch)
    monkeypatch.setattr(step9c, "_certified_context", lambda game_id, game_date=None: _context(game_id))

    result = step9c.install_step9c_live_state_consumer()
    state = fake._render_selected(_game(), None)

    assert result["installed"] is True
    assert result["selected_game_state_api_first"] is True
    assert result["legacy_verified_slate_preserved"] is True
    assert calls["feed"] == []
    assert state["away_runs"] == 3
    assert state["home_runs"] == 2
    assert state["pitcher_id"] == 202
    status = step9c.consumer_status()
    assert status["api_used"] is True
    assert status["legacy_fallback_used"] is False
    for flag in step9c.PROTECTED_FALSE_FLAGS:
        assert result[flag] is False
        assert status[flag] is False


def test_api_rejection_falls_back_to_exact_legacy_feed(monkeypatch):
    fake, calls = _fake_v19(monkeypatch)
    monkeypatch.setattr(step9c, "_certified_context", lambda game_id, game_date=None: None)
    step9c.install_step9c_live_state_consumer()

    result = fake._render_selected(_game(), None)
    assert result == {"legacy_state": {"legacy": True, "game_pk": GAME_ID}}
    assert calls["feed"] == [GAME_ID]
    assert step9c.consumer_status()["legacy_fallback_used"] is True


def test_network_exception_falls_back_to_exact_legacy_feed(monkeypatch):
    fake, calls = _fake_v19(monkeypatch)

    def fail(*args, **kwargs):
        raise TimeoutError("offline")

    monkeypatch.setattr(step9c, "_certified_context", fail)
    step9c.install_step9c_live_state_consumer()
    result = fake._render_selected(_game(), None)
    assert result["legacy_state"]["game_pk"] == GAME_ID
    assert calls["feed"] == [GAME_ID]
    assert step9c.consumer_status()["failure"] == "TimeoutError"


def test_wrong_context_game_id_falls_back(monkeypatch):
    fake, calls = _fake_v19(monkeypatch)
    monkeypatch.setattr(step9c, "_certified_context", lambda game_id, game_date=None: _context(game_id + 1))
    step9c.install_step9c_live_state_consumer()
    fake._render_selected(_game(), None)
    assert calls["feed"] == [GAME_ID]
    assert step9c.consumer_status()["legacy_fallback_used"] is True


def test_missing_team_metadata_falls_back_without_api_call(monkeypatch):
    fake, calls = _fake_v19(monkeypatch)
    api_calls = []
    monkeypatch.setattr(step9c, "_certified_context", lambda *args, **kwargs: api_calls.append(args) or _context())
    step9c.install_step9c_live_state_consumer()
    game = _game()
    game["home_team_id"] = None
    fake._render_selected(game, None)
    assert api_calls == []
    assert calls["feed"] == [GAME_ID]


def test_invalid_identity_types_do_not_create_api_identity(monkeypatch):
    fake, calls = _fake_v19(monkeypatch)
    api_calls = []
    monkeypatch.setattr(step9c, "_certified_context", lambda *args, **kwargs: api_calls.append(args) or _context())
    step9c.install_step9c_live_state_consumer()

    fake.fetch_live_feed(True)
    fake.fetch_live_feed(824911.0)
    fake.fetch_live_feed("８２４９１１")
    assert api_calls == []
    assert calls["feed"] == [True, 824911.0, "８２４９１１"]


def test_serialized_ascii_integer_identity_is_allowed(monkeypatch):
    fake, calls = _fake_v19(monkeypatch)
    monkeypatch.setattr(step9c, "_certified_context", lambda game_id, game_date=None: _context(game_id))
    step9c.install_step9c_live_state_consumer()
    game = _game()
    game["game_pk"] = str(GAME_ID)
    state = fake._render_selected(game, None)
    assert state["away_runs"] == 3
    assert calls["feed"] == []


def test_mapping_exception_falls_back_to_direct_feed(monkeypatch):
    fake, calls = _fake_v19(monkeypatch)
    monkeypatch.setattr(step9c, "_certified_context", lambda game_id, game_date=None: _context(game_id))
    monkeypatch.setattr(step9c, "_state_from_context", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("mapping")))
    step9c.install_step9c_live_state_consumer()
    result = fake._render_selected(_game(), None)
    assert result == {"legacy_state": {"legacy": True, "game_pk": GAME_ID}}
    assert calls["feed"] == [GAME_ID]
    assert step9c.consumer_status()["legacy_fallback_used"] is True
    assert step9c.consumer_status()["failure"] == "ValueError"


def test_raw_legacy_feed_state_parser_is_preserved(monkeypatch):
    fake, calls = _fake_v19(monkeypatch)
    step9c.install_step9c_live_state_consumer()
    raw = {"raw": "official MLB feed"}
    assert fake._state(raw) == {"legacy_state": raw}
    assert calls["state"] == [raw]


def test_clear_delegates_to_original_live_feed_cache(monkeypatch):
    fake, calls = _fake_v19(monkeypatch)
    step9c.install_step9c_live_state_consumer()
    fake.fetch_live_feed.clear()
    assert calls["clear"] == 1
    assert step9c.consumer_status()["api_attempted"] is False


def test_double_install_is_idempotent_and_does_not_stack(monkeypatch):
    fake, calls = _fake_v19(monkeypatch)
    monkeypatch.setattr(step9c, "_certified_context", lambda game_id, game_date=None: None)
    step9c.install_step9c_live_state_consumer()
    step9c.install_step9c_live_state_consumer()
    fake._render_selected(_game(), None)
    assert calls["render"] == [_game()]
    assert calls["feed"] == [GAME_ID]


def test_render_metadata_context_does_not_leak_between_calls(monkeypatch):
    fake, calls = _fake_v19(monkeypatch)
    monkeypatch.setattr(step9c, "_certified_context", lambda game_id, game_date=None: _context(game_id))
    step9c.install_step9c_live_state_consumer()
    fake._render_selected(_game(), None)
    assert step9c._CURRENT_GAME.get() is None


def test_installer_does_not_patch_verified_slate_transport(monkeypatch):
    fake, calls = _fake_v19(monkeypatch)
    sentinel = object()
    fake.fetch_live_slate = sentinel
    step9c.install_step9c_live_state_consumer()
    assert fake.fetch_live_slate is sentinel
