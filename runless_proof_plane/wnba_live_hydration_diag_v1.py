from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/summary"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
    "Accept": "application/json,text/plain,*/*",
}


def _get_json(url: str, params: dict | None = None, timeout: int = 15):
    if params:
        url = url + "?" + urlencode(params)
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _is_final(event: dict) -> bool:
    comps = event.get("competitions") or []
    status = ((comps[0].get("status") if comps else None) or event.get("status") or {})
    stype = status.get("type") or {}
    state = str(stype.get("state") or "").lower()
    desc = str(stype.get("description") or stype.get("shortDetail") or "").lower()
    return bool(stype.get("completed")) or state in {"post", "final"} or "final" in desc


def _num(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _minutes(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("PT"):
        try:
            body = text[2:]
            mins = float(body.split("M")[0]) if "M" in body else 0.0
            secs = float(body.split("M", 1)[1].rstrip("S")) if "M" in body else 0.0
            return mins + secs / 60.0
        except Exception:
            return None
    if ":" in text:
        try:
            m, s = text.split(":", 1)
            return float(m) + float(s) / 60.0
        except Exception:
            return None
    return _num(text)


def _stat_map(group: dict, item: dict) -> dict:
    labels = group.get("labels") or []
    keys = group.get("keys") or group.get("names") or []
    vals = item.get("stats") or []
    out = {}
    for i, value in enumerate(vals):
        if i < len(labels):
            out[str(labels[i]).upper()] = value
        if i < len(keys):
            out[str(keys[i]).upper()] = value
    return out


def _pick(mapping: dict, names):
    for name in names:
        key = str(name).upper()
        if key in mapping:
            return mapping[key]
    return None


def _inspect_summary(payload: dict) -> dict:
    team_results = []
    current_total = 0
    robust_total = 0
    for team_block in ((payload.get("boxscore") or {}).get("players") or []):
        team = team_block.get("team") or {}
        group_results = []
        first_athlete_group_valid = None
        for idx, group in enumerate(team_block.get("statistics") or []):
            athletes = group.get("athletes") or []
            valid = 0
            sample = None
            for item in athletes:
                if not isinstance(item, dict) or bool(item.get("didNotPlay")):
                    continue
                athlete = item.get("athlete") or {}
                if not athlete.get("id"):
                    continue
                mapping = _stat_map(group, item)
                mins = _minutes(_pick(mapping, ["MIN", "MINUTES"]))
                pts = _num(_pick(mapping, ["PTS", "POINTS"]))
                reb = _num(_pick(mapping, ["REB", "REBOUNDS", "REBOUNDSTOTAL"]))
                ast = _num(_pick(mapping, ["AST", "ASSISTS"]))
                if all(v is None for v in (mins, pts, reb, ast)):
                    continue
                valid += 1
                if sample is None:
                    sample = {
                        "player": str(athlete.get("displayName") or athlete.get("fullName") or ""),
                        "min": mins,
                        "pts": pts,
                        "reb": reb,
                        "ast": ast,
                    }
            if athletes and first_athlete_group_valid is None:
                first_athlete_group_valid = valid
            group_results.append({
                "index": idx,
                "name": str(group.get("name") or group.get("displayName") or ""),
                "athletes": len(athletes),
                "labels": [str(x) for x in (group.get("labels") or [])],
                "keys": [str(x) for x in (group.get("keys") or group.get("names") or [])],
                "valid_pra_rows": valid,
                "sample": sample,
            })
        current_rows = int(first_athlete_group_valid or 0)
        robust_rows = max([int(g["valid_pra_rows"]) for g in group_results] or [0])
        current_total += current_rows
        robust_total += robust_rows
        team_results.append({
            "espn_team_id": str(team.get("id") or ""),
            "abbr": str(team.get("abbreviation") or ""),
            "name": str(team.get("displayName") or team.get("shortDisplayName") or team.get("name") or ""),
            "current_parser_rows": current_rows,
            "robust_group_rows": robust_rows,
            "groups": group_results,
        })
    return {
        "team_blocks": len(team_results),
        "current_parser_rows": current_total,
        "robust_group_rows": robust_total,
        "teams": team_results,
    }


def run_diagnostic() -> dict:
    out = {
        "season": 2026,
        "scoreboard": {},
        "summaries": [],
        "classification": "UNKNOWN",
    }
    try:
        season = _get_json(ESPN_SCOREBOARD, {"dates": "2026", "limit": 1000})
    except Exception as exc:
        out["scoreboard"] = {"error": type(exc).__name__, "detail": str(exc)[:300]}
        out["classification"] = "SEASON_HISTORY_TRANSPORT_ERROR"
        return out

    events = season.get("events") or []
    finals = [event for event in events if _is_final(event)]
    finals.sort(key=lambda e: str(e.get("date") or ""), reverse=True)
    out["scoreboard"] = {
        "event_count": len(events),
        "final_count": len(finals),
        "sample_event_ids": [str(e.get("id") or "") for e in finals[:5]],
    }
    if not finals:
        out["classification"] = "SEASON_HISTORY_EMPTY"
        return out

    transport_ok = 0
    current_rows = 0
    robust_rows = 0
    for event in finals[:3]:
        gid = str(event.get("id") or "")
        record = {"game_id": gid, "date": str(event.get("date") or "")}
        try:
            payload = _get_json(ESPN_SUMMARY, {"event": gid})
            transport_ok += 1
            inspected = _inspect_summary(payload)
            record.update(inspected)
            current_rows += int(inspected["current_parser_rows"])
            robust_rows += int(inspected["robust_group_rows"])
        except Exception as exc:
            record["error"] = type(exc).__name__
            record["detail"] = str(exc)[:300]
        out["summaries"].append(record)

    if transport_ok == 0:
        out["classification"] = "SUMMARY_TRANSPORT_EMPTY"
    elif current_rows == 0 and robust_rows > 0:
        out["classification"] = "FIRST_GROUP_BREAK_DROPS_STATS"
    elif robust_rows == 0:
        out["classification"] = "SUMMARY_SCHEMA_UNPARSED"
    else:
        out["classification"] = "PARSER_HEALTHY_CHECK_DOWNSTREAM"
    out["transport_ok"] = transport_ok
    out["current_parser_rows"] = current_rows
    out["robust_group_rows"] = robust_rows
    return out


def install_hydration_diag(app):
    @app.get("/wnba-hydration-diagnostic")
    def _diag():
        return run_diagnostic()
    return app
