"""Live cert for the Render-safe NFL Passing Yards ESPN transport V2."""
from __future__ import annotations

import json

from nfl_passing_yards_api_live_cert_v1 import _pregame_event_ids
from sports_api.collectors import nfl_passing_yards_render_espn_v2 as hosted


def run() -> dict:
    event_ids = _pregame_event_ids()
    if not event_ids:
        raise SystemExit("NFL_PASSING_YARDS_RENDER_V2_FAIL: no upcoming verified ESPN NFL events")

    diagnostics: list[dict] = []
    for event_id in event_ids[:16]:
        try:
            payload = hosted.collect_fanduel_nfl_passing_yards_hosted(event_id)
        except Exception as exc:
            diagnostics.append({"event_id": event_id, "error": f"{type(exc).__name__}: {exc}"[:300]})
            continue

        props = payload.get("props") or []
        provider = payload.get("provider_diagnostics") or {}
        diagnostics.append({
            "event_id": event_id,
            "ready": payload.get("ready"),
            "market_available": payload.get("market_available"),
            "props": len(props),
            "espn_sources": provider.get("espn_transport_sources"),
            "provider_event_id": provider.get("provider_event_id"),
            "selected_tab": provider.get("selected_tab"),
            "reason": payload.get("reason"),
        })
        if not props:
            continue

        identity = payload.get("identity") or {}
        semantics = payload.get("market_semantics") or {}
        assert payload.get("official_event_id") == event_id
        assert payload.get("sportsbook") == "FanDuel"
        assert provider.get("espn_transport_version") == hosted.MODEL_VERSION
        assert provider.get("espn_transport_sources")
        assert semantics.get("projection_weight") == 0.0
        assert semantics.get("market_context_only") is True
        assert semantics.get("may_modify_projection") is False
        assert semantics.get("stake_sizing_enabled") is False
        assert identity.get("fuzzy_matching") is False
        assert identity.get("player_name_matching") is False
        assert identity.get("synthetic_event_ids") is False
        assert identity.get("synthetic_player_ids") is False

        for prop in props:
            assert str(prop.get("official_event_id") or "") == event_id
            assert str(prop.get("official_athlete_id") or "").isdigit()
            assert str(prop.get("official_team_id") or "").isdigit()
            assert prop.get("market_type") == "passing_yards"
            assert float(prop.get("line")) > 0
            assert abs(int(prop.get("over_odds"))) >= 100
            assert abs(int(prop.get("under_odds"))) >= 100
            assert prop.get("sportsbook") == "FanDuel"

        result = {
            "status": "GREEN",
            "official_event_id": event_id,
            "verified_prop_count": len(props),
            "official_athlete_ids": [prop["official_athlete_id"] for prop in props],
            "espn_transport_sources": provider.get("espn_transport_sources"),
            "sportsbook": "FanDuel",
            "projection_weight": 0.0,
            "player_name_matching": False,
            "fuzzy_matching": False,
            "synthetic_ids": False,
            "wager_actions": False,
            "diagnostics_before_success": diagnostics,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        print("NFL_PASSING_YARDS_RENDER_V2_LIVE_CERT_GREEN")
        return result

    print(json.dumps({"status": "FAIL", "diagnostics": diagnostics}, indent=2, sort_keys=True))
    raise SystemExit("NFL_PASSING_YARDS_RENDER_V2_FAIL: no exact-ID Passing Yards prop certified")


if __name__ == "__main__":
    run()
