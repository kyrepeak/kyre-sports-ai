from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import nfl_passing_yards_hub_v20 as hub
import nfl_passing_yards_market_api_v1 as api_client

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 12, 16, 0, tzinfo=timezone.utc)
EVENT_ID = "401872925"
AWAY_QB_ID = "3052587"
HOME_QB_ID = "3915511"


def _prop(athlete_id: str, team_id: str, line: float = 249.5) -> dict:
    return {
        "official_event_id": EVENT_ID,
        "official_athlete_id": athlete_id,
        "official_team_id": team_id,
        "player_name": "Verified QB",
        "position": "QB",
        "market_type": "passing_yards",
        "line": line,
        "over_odds": -110,
        "under_odds": -110,
        "sportsbook": "FanDuel",
        "line_status": "active",
        "provider_event_id": "36053582",
        "provider_market_id": f"m-{athlete_id}",
        "captured_at_utc": NOW.isoformat(),
    }


def _payload(*, captured_at: datetime = NOW, event_id: str = EVENT_ID, props=None) -> dict:
    return {
        "schema_version": "nfl_passing_yards_market_v1",
        "ready": True,
        "market_available": True,
        "official_event_id": event_id,
        "sportsbook": "FanDuel",
        "captured_at_utc": captured_at.isoformat(),
        "props": props if props is not None else [
            _prop(AWAY_QB_ID, "27"),
            _prop(HOME_QB_ID, "4", 275.5),
        ],
        "identity": {
            "fuzzy_matching": False,
            "player_name_matching": False,
            "synthetic_event_ids": False,
            "synthetic_player_ids": False,
        },
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "stake_sizing_enabled": False,
        },
    }


def test_fresh_exact_id_event_payload_is_accepted_post_model_only():
    result = api_client.validate_event_payload(_payload(), EVENT_ID, now_utc=NOW)
    assert result["ready"] is True
    assert result["market_available"] is True
    assert len(result["props"]) == 2
    assert result["projection_weight"] == 0.0
    assert result["market_context_only"] is True
    assert result["stake_sizing_enabled"] is False


def test_stale_market_fails_closed():
    stale = NOW - timedelta(seconds=api_client.MAX_MARKET_AGE_SECONDS + 1)
    result = api_client.validate_event_payload(_payload(captured_at=stale), EVENT_ID, now_utc=NOW)
    assert result["ready"] is False
    assert "stale" in result["reason"].lower()
    assert result["projection_weight"] == 0.0


def test_future_market_beyond_clock_skew_fails_closed():
    future = NOW + timedelta(seconds=api_client.MAX_FUTURE_SKEW_SECONDS + 1)
    result = api_client.validate_event_payload(_payload(captured_at=future), EVENT_ID, now_utc=NOW)
    assert result["ready"] is False
    assert "future" in result["reason"].lower()


def test_event_identity_mismatch_fails_closed():
    result = api_client.validate_event_payload(_payload(event_id="401999999"), EVENT_ID, now_utc=NOW)
    assert result["ready"] is False
    assert "event identity mismatch" in result["reason"].lower()


def test_weakened_market_safety_contract_fails_closed():
    payload = _payload()
    payload["market_semantics"]["projection_weight"] = 0.01
    result = api_client.validate_event_payload(payload, EVENT_ID, now_utc=NOW)
    assert result["ready"] is False
    assert "safety contract" in result["reason"].lower()

    payload = _payload()
    payload["identity"]["fuzzy_matching"] = True
    result = api_client.validate_event_payload(payload, EVENT_ID, now_utc=NOW)
    assert result["ready"] is False
    assert "safety contract" in result["reason"].lower()


def test_duplicate_athlete_market_fails_closed_instead_of_choosing_one():
    duplicate = _prop(AWAY_QB_ID, "27")
    payload = _payload(props=[duplicate, dict(duplicate, provider_market_id="m-duplicate")])
    result = api_client.validate_event_payload(payload, EVENT_ID, now_utc=NOW)
    assert result["ready"] is False
    assert "ambiguous duplicate" in result["reason"].lower()


def test_exact_athlete_lookup_succeeds_and_missing_athlete_fails_closed():
    event_market = api_client.validate_event_payload(_payload(), EVENT_ID, now_utc=NOW)
    away = api_client.market_for_athlete(event_market, AWAY_QB_ID)
    assert away["ready"] is True
    assert away["official_athlete_id"] == AWAY_QB_ID
    assert away["line"] == 249.5
    assert away["projection_weight"] == 0.0

    missing = api_client.market_for_athlete(event_market, "123456789")
    assert missing["ready"] is False
    assert "unavailable" in missing["reason"].lower()


def test_qb_ids_are_taken_from_verified_identity_result_not_names():
    resolved = {
        "away": {"qb1": {"athlete_id": AWAY_QB_ID, "name": "Any Name"}},
        "home": {"qb1": {"athlete_id": HOME_QB_ID, "name": "Another Name"}},
    }
    assert hub._qb_athlete_ids(resolved) == [AWAY_QB_ID, HOME_QB_ID]
    assert hub._qb_athlete_ids({"away": {"qb1": {"name": "Name Only"}}, "home": {}}) == ["", ""]


class _FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.calls = []
        self.infos = []

    def text_input(self, label, value="", *args, **kwargs):
        key = kwargs.get("key")
        self.calls.append({"label": label, "value": value, "key": key, "kwargs": dict(kwargs)})
        if key in self.session_state:
            return self.session_state[key]
        if key:
            self.session_state[key] = value
        return value

    def info(self, body, *args, **kwargs):
        self.infos.append(str(body))
        return None


def test_step10_proxy_autofills_fresh_api_market_and_disables_only_market_field(monkeypatch):
    fake = _FakeStreamlit()
    context = {"event_id": EVENT_ID, "athlete_ids": [AWAY_QB_ID, HOME_QB_ID]}
    proxy = hub._Step10StreamlitProxy(fake, context)
    row = dict(_prop(AWAY_QB_ID, "27"), ready=True, captured_at_utc=NOW.isoformat())
    monkeypatch.setattr(hub, "_market_row_for_index", lambda _ctx, index: row if index == 0 else {"ready": False})

    key = "kpy10_0_verified_qb_line"
    value = proxy.text_input("Passing yards line", value="", key=key)
    assert value == "249.5"
    assert fake.session_state[key] == "249.5"
    assert fake.calls[-1]["kwargs"]["disabled"] is True
    assert "projection influence remains 0.0%" in fake.calls[-1]["kwargs"]["help"]

    proxy.text_input("Unrelated input", value="manual", key="unrelated")
    assert fake.calls[-1]["kwargs"].get("disabled") is not True
    assert fake.session_state["unrelated"] == "manual"


def test_step10_proxy_clears_old_api_autofill_when_market_is_no_longer_ready(monkeypatch):
    fake = _FakeStreamlit()
    context = {"event_id": EVENT_ID, "athlete_ids": [AWAY_QB_ID, HOME_QB_ID]}
    proxy = hub._Step10StreamlitProxy(fake, context)
    key = "kpy10_0_verified_qb_over"
    marker = f"_kpy20_api_autofill_{key}"
    fake.session_state[key] = "-110"
    fake.session_state[marker] = True
    monkeypatch.setattr(hub, "_market_row_for_index", lambda _ctx, index: {"ready": False, "reason": "stale"})

    value = proxy.text_input("Over American odds", value="", key=key)
    assert value == ""
    assert marker not in fake.session_state
    assert fake.calls[-1]["kwargs"].get("disabled") is not True


def test_v20_routes_only_passing_yards_and_keeps_v19_as_frozen_prior():
    hub_source = (ROOT / "nfl_passing_yards_hub_v20.py").read_text(encoding="utf-8")
    route_source = (ROOT / "nfl_hub_v35.py").read_text(encoding="utf-8")
    client_source = (ROOT / "nfl_passing_yards_market_api_v1.py").read_text(encoding="utf-8")

    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v19"' in hub_source
    assert "from nfl_passing_yards_hub_v20 import render_nfl_passing_yards_hub" in route_source
    assert 'if market == "Passing Yards"' in route_source
    assert "return base.render_nfl_hub(market)" in route_source
    assert '"projection_weight": 0.0' in client_source
    assert '"stake_sizing_enabled": False' in client_source
    assert "fuzzy_matching" in client_source
    assert "synthetic_event_ids" in client_source


def test_market_input_key_shape_matches_certified_step10_widgets():
    assert hub._STEP10_KEY.match("kpy10_0_baker_mayfield_source")
    assert hub._STEP10_KEY.match("kpy10_0_baker_mayfield_line")
    assert hub._STEP10_KEY.match("kpy10_1_joe_burrow_over")
    assert hub._STEP10_KEY.match("kpy10_1_joe_burrow_under")
    assert hub._STEP10_KEY.match("kpy10_1_joe_burrow_timestamp")
    assert hub._STEP10_KEY.match("kpy9_0_baker_line") is None
