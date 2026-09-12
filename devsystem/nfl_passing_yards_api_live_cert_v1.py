"""Live read-only certification for the Kyre NFL Passing Yards market API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from sports_api.collectors import nfl_fanduel_passing_yards as collector


def _pregame_event_ids(days: int = 8) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    start = datetime.now(timezone.utc).date()
    for offset in range(days):
        day = start + timedelta(days=offset)
        payload = collector._get_json(  # certification-only exact ESPN schedule read
            f"{collector.ESPN_SITE_BASE}/scoreboard",
            {"dates": day.strftime("%Y%m%d")},
            headers=collector.ESPN_HEADERS,
            timeout=collector.DEFAULT_TIMEOUT_SECONDS,
        )
        for event in payload.get("events") or []:
            if not isinstance(event, dict):
                continue
            event_id = str(event.get("id") or "").strip()
            comps = event.get("competitions") or []
            comp = comps[0] if comps and isinstance(comps[0], dict) else {}
            state = str((((comp.get("status") or {}).get("type") or {}).get("state") or "")).lower()
            if event_id.isdigit() and state == "pre" and event_id not in seen:
                seen.add(event_id)
                ids.append(event_id)
    return ids


def run() -> dict:
    event_ids = _pregame_event_ids()
    if not event_ids:
        raise SystemExit("NFL_PASSING_YARDS_API_LIVE_CERT_FAIL: no upcoming verified ESPN NFL events")

    diagnostics: list[dict] = []
    for event_id in event_ids[:16]:
        try:
            payload = collector.collect_fanduel_nfl_passing_yards(event_id)
        except Exception as exc:
            diagnostics.append({"event_id": event_id, "error": f"{type(exc).__name__}: {exc}"[:280]})
            continue

        props = payload.get("props") or []
        diagnostics.append({
            "event_id": event_id,
            "ready": payload.get("ready"),
            "market_available": payload.get("market_available"),
            "props": len(props),
            "provider": (payload.get("provider_diagnostics") or {}).get("provider_event_id"),
            "selected_tab": (payload.get("provider_diagnostics") or {}).get("selected_tab"),
            "attempted_tabs": (payload.get("provider_diagnostics") or {}).get("attempted_tabs"),
            "reason": payload.get("reason"),
        })
        if not props:
            continue

        identity = payload.get("identity") or {}
        semantics = payload.get("market_semantics") or {}
        assert payload.get("official_event_id") == event_id
        assert payload.get("sportsbook") == "FanDuel"
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
            "sportsbook": "FanDuel",
            "projection_weight": 0.0,
            "player_name_matching": False,
            "fuzzy_matching": False,
            "synthetic_ids": False,
            "wager_actions": False,
            "diagnostics_before_success": diagnostics,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        print("NFL_PASSING_YARDS_API_LIVE_CERT_GREEN")
        return result

    print(json.dumps({"status": "FAIL", "diagnostics": diagnostics}, indent=2, sort_keys=True))
    raise SystemExit(
        "NFL_PASSING_YARDS_API_LIVE_CERT_FAIL: no exact-ID FanDuel Passing Yards prop was certified in the upcoming ESPN window"
    )


if __name__ == "__main__":
    run()
