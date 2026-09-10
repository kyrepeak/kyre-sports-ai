"""Build the additive College Football runtime snapshot V2 from public current feeds.

The snapshot exists so Streamlit rendering is not dependent on live access to
every upstream provider. This builder runs in GitHub Actions, where the provider
paths are already certified to be reachable.

Window
------
- 7 days behind the current Eastern date
- 21 days ahead

Sources
-------
- ESPN college-football FBS + FCS scoreboards: event identity, current records, rank,
  venue, broadcast, status, week
- ESPN team schedule: completed-game W/L, splits, recent form, scoring
- ESPN Core: current head coach and latest available AP/Coaches/CFP rank set

The script only rewrites the snapshot when substantive game data changes, so an
hourly workflow does not force needless Streamlit redeploys.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cfb_over_under_deep_data_reconciliation_v1 as project_deep

OUT = ROOT / "data" / "cfb_runtime_snapshot_v2.json"

ET = ZoneInfo("America/New_York")
TIMEOUT = 18
RUNTIME_SNAPSHOT_PAST_DAYS = 7
RUNTIME_SNAPSHOT_FUTURE_DAYS = 21
HEADERS = {
    "User-Agent": "KyreSportsAI/CFB-Step2",
    "Accept": "application/json",
}

SCOREBOARD = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
)
TEAM_SCHEDULE = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{team_id}/schedule"
)
CORE_ROOT = (
    "https://sports.core.api.espn.com/v2/sports/football/leagues/college-football"
)

_SCHEDULE_CACHE: dict[tuple[str, int], list[dict[str, Any]]] = {}
_COACH_CACHE: dict[tuple[str, int], str] = {}
_POLL_CACHE: dict[tuple[str, int, int], dict[str, int | None]] = {}


def snapshot_dates(now_et: datetime) -> list[str]:
    """Return the documented date-driven runtime window, inclusive."""
    anchor = now_et.date()
    return [
        (anchor + timedelta(days=offset)).isoformat()
        for offset in range(
            -RUNTIME_SNAPSHOT_PAST_DAYS,
            RUNTIME_SNAPSHOT_FUTURE_DAYS + 1,
        )
    ]


def clean(value: Any) -> str:
    return str(value or "").strip()


def get_json(url: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    query = dict(params or {})
    errors: list[str] = []

    header_sets = (
        HEADERS,
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/140 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://www.espn.com/",
        },
    )

    for headers in header_sets:
        try:
            response = requests.get(
                url,
                params=query,
                timeout=TIMEOUT,
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("non-object JSON")
            return payload
        except Exception as exc:
            errors.append(f"requests {type(exc).__name__}: {exc}")

    full = url + (("?" + urlencode(query)) if query else "")
    for headers in header_sets:
        try:
            request = Request(
                full,
                headers={
                    **headers,
                    "Cache-Control": "no-cache",
                },
            )
            with urlopen(request, timeout=TIMEOUT) as response:
                raw = response.read()
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("non-object JSON")
            return payload
        except Exception as exc:
            errors.append(f"urllib {type(exc).__name__}: {exc}")

    raise RuntimeError("; ".join(errors)[-1200:])


def parse_dt(value: Any) -> datetime | None:
    text = clean(value)
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def record_summary(competitor: Mapping[str, Any], wanted: set[str]) -> str:
    records = competitor.get("record") or competitor.get("records") or []
    if isinstance(records, Mapping):
        records = [records]
    for item in records if isinstance(records, list) else []:
        if not isinstance(item, Mapping):
            continue
        typ = clean(item.get("type") or item.get("name")).lower()
        if typ not in wanted:
            continue
        text = clean(
            item.get("summary")
            or item.get("displayValue")
            or item.get("record")
        )
        if text:
            return text
    return ""


def rank_value(competitor: Mapping[str, Any]) -> int | None:
    try:
        value = int((competitor.get("curatedRank") or {}).get("current"))
    except Exception:
        return None
    return value if 0 < value < 99 else None


def event_sides(event: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    comps = event.get("competitions") or []
    comp = comps[0] if comps and isinstance(comps[0], Mapping) else {}
    away: Mapping[str, Any] = {}
    home: Mapping[str, Any] = {}
    for competitor in comp.get("competitors") or []:
        if not isinstance(competitor, Mapping):
            continue
        side = clean(competitor.get("homeAway")).lower()
        if side == "away":
            away = competitor
        elif side == "home":
            home = competitor
    return away, home, comp


def team_name(competitor: Mapping[str, Any]) -> str:
    team = competitor.get("team") or {}
    if not isinstance(team, Mapping):
        team = {}
    return clean(
        team.get("location")
        or team.get("shortDisplayName")
        or team.get("displayName")
        or team.get("name")
    )


def team_id(competitor: Mapping[str, Any]) -> str:
    team = competitor.get("team") or {}
    if not isinstance(team, Mapping):
        return ""
    return clean(team.get("id"))


def broadcast(comp: Mapping[str, Any]) -> str:
    names: list[str] = []
    for row in comp.get("broadcasts") or []:
        if not isinstance(row, Mapping):
            continue
        for name in row.get("names") or []:
            text = clean(name)
            if text:
                names.append(text)
        media = row.get("media") or {}
        if isinstance(media, Mapping):
            text = clean(media.get("shortName") or media.get("name"))
            if text:
                names.append(text)
    return ", ".join(dict.fromkeys(names))


def week_number(event: Mapping[str, Any]) -> int:
    week = event.get("week")
    if isinstance(week, Mapping):
        try:
            return int(week.get("number") or 0)
        except Exception:
            return 0
    try:
        return int(week or 0)
    except Exception:
        return 0


def status_name(event: Mapping[str, Any], comp: Mapping[str, Any]) -> str:
    raw = event.get("status") or comp.get("status") or {}
    typ = raw.get("type") if isinstance(raw, Mapping) else {}
    if not isinstance(typ, Mapping):
        typ = {}
    return clean(
        typ.get("description")
        or typ.get("name")
        or typ.get("detail")
        or typ.get("shortDetail")
    )


def completed(event: Mapping[str, Any]) -> bool:
    raw = event.get("status") or {}
    typ = raw.get("type") if isinstance(raw, Mapping) else {}
    if not isinstance(typ, Mapping):
        return False
    if typ.get("completed") is True:
        return True
    state = clean(typ.get("state")).lower()
    name = clean(typ.get("name")).lower()
    return state == "post" or "final" in name


def competitor_score(competitor: Mapping[str, Any]) -> float | None:
    score = competitor.get("score")
    if isinstance(score, Mapping):
        score = score.get("value") or score.get("displayValue")
    try:
        return float(score)
    except Exception:
        return None


def schedule_rows(team_id_value: str, season: int, now_utc: datetime) -> list[dict[str, Any]]:
    cache_key = (team_id_value, int(season))
    if cache_key in _SCHEDULE_CACHE:
        return [dict(row) for row in _SCHEDULE_CACHE[cache_key]]

    # Use the same certified schedule parser as the runtime reconciliation layer.
    try:
        current_rows, _, _ = project_deep._current_rows(
            team_id_value,
            int(season),
            now_utc,
            "",
        )
        rows: list[dict[str, Any]] = []
        for row in current_rows:
            pf = float(row.get("points_for") or 0.0)
            pa = float(row.get("points_against") or 0.0)
            rows.append({
                "event_id": clean(row.get("event_id")),
                "date": clean(row.get("date") or row.get("date_dt")),
                "location": clean(row.get("location") or row.get("home_away")).lower(),
                "points_for": pf,
                "points_against": pa,
                "opponent": clean(row.get("opponent_name")),
                "opponent_id": clean(row.get("opponent_id")),
            })
        rows = [
            row for row in rows
            if row["event_id"]
            and (row["points_for"] != 0.0 or row["points_against"] != 0.0)
        ]
        if rows:
            rows.sort(key=lambda row: row["date"])
            _SCHEDULE_CACHE[cache_key] = [dict(row) for row in rows]
            return rows
    except Exception as exc:
        print(
            f"WARN certified schedule parser {team_id_value}: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )

    # Lower-level transport fallback.
    payload = get_json(
        TEAM_SCHEDULE.format(team_id=team_id_value),
        {"season": season},
    )
    rows: list[dict[str, Any]] = []
    for event in payload.get("events") or []:
        if not isinstance(event, Mapping) or not completed(event):
            continue
        dt = parse_dt(event.get("date"))
        if dt is None or dt > now_utc:
            continue
        away, home, comp = event_sides(event)
        if not away or not home:
            continue

        if team_id(away) == team_id_value:
            self_comp, opp_comp = away, home
            loc = "neutral" if comp.get("neutralSite") is True else "away"
        elif team_id(home) == team_id_value:
            self_comp, opp_comp = home, away
            loc = "neutral" if comp.get("neutralSite") is True else "home"
        else:
            continue

        pf = competitor_score(self_comp)
        pa = competitor_score(opp_comp)
        if pf is None or pa is None:
            continue

        rows.append({
            "event_id": clean(event.get("id")),
            "date": dt.isoformat(),
            "location": loc,
            "points_for": pf,
            "points_against": pa,
            "opponent": team_name(opp_comp),
            "opponent_id": team_id(opp_comp),
        })

    rows.sort(key=lambda row: row["date"])
    _SCHEDULE_CACHE[cache_key] = [dict(row) for row in rows]
    return rows


def record_from_rows(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    wins = losses = ties = 0
    for row in rows:
        pf = float(row.get("points_for") or 0.0)
        pa = float(row.get("points_against") or 0.0)
        if pf > pa:
            wins += 1
        elif pf < pa:
            losses += 1
        else:
            ties += 1
    return {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "games": wins + losses + ties,
    }


def split_record(rows: list[Mapping[str, Any]], location: str) -> dict[str, int]:
    return record_from_rows([
        row for row in rows if clean(row.get("location")).lower() == location
    ])


def record_text(record: Mapping[str, Any]) -> str:
    wins = int(record.get("wins") or 0)
    losses = int(record.get("losses") or 0)
    ties = int(record.get("ties") or 0)
    return f"{wins}-{losses}" + (f"-{ties}" if ties else "")


def head_coach(team_id_value: str, season: int) -> str:
    cache_key = (team_id_value, int(season))
    if cache_key in _COACH_CACHE:
        return _COACH_CACHE[cache_key]
    try:
        collection = get_json(
            f"{CORE_ROOT}/seasons/{season}/teams/{team_id_value}/coaches",
            {"lang": "en", "region": "us"},
        )
        items = collection.get("items") or []
        first = items[0] if items and isinstance(items[0], Mapping) else {}
        ref = clean(first.get("$ref"))
        if not ref:
            return ""
        detail = get_json(ref.replace("http://", "https://", 1))
        value = " ".join(
            x for x in (
                clean(detail.get("firstName")),
                clean(detail.get("lastName")),
            )
            if x
        )
        _COACH_CACHE[cache_key] = value
        return value
    except Exception:
        _COACH_CACHE[cache_key] = ""
        return ""


def latest_polls(team_id_value: str, season: int, preferred_week: int) -> dict[str, int | None]:
    cache_key = (team_id_value, int(season), int(preferred_week))
    if cache_key in _POLL_CACHE:
        return dict(_POLL_CACHE[cache_key])

    result: dict[str, int | None] = {
        "ap_rank": None,
        "coaches_poll_rank": None,
        "cfp_rank": None,
    }
    for week in range(max(1, preferred_week), 0, -1):
        try:
            collection = get_json(
                f"{CORE_ROOT}/seasons/{season}/types/2/weeks/{week}/teams/{team_id_value}/ranks",
                {"lang": "en", "region": "us"},
            )
        except Exception:
            continue
        items = collection.get("items") or []
        if not items:
            continue

        found_any = False
        for item in items:
            if not isinstance(item, Mapping):
                continue
            ref = clean(item.get("$ref"))
            if not ref:
                continue
            try:
                detail = get_json(ref.replace("http://", "https://", 1))
            except Exception:
                continue
            typ = clean(detail.get("type")).lower()
            name = clean(detail.get("shortName") or detail.get("name")).lower()
            rank_obj = detail.get("rank") or {}
            if not isinstance(rank_obj, Mapping):
                rank_obj = {}
            try:
                current = int(rank_obj.get("current"))
                if current <= 0 or current >= 99:
                    current = None
            except Exception:
                current = None

            if typ == "ap" or "ap poll" in name:
                result["ap_rank"] = current
                found_any = True
            elif typ == "usa" or "coach" in name:
                result["coaches_poll_rank"] = current
                found_any = True
            elif typ == "cfp" or "playoff" in name:
                result["cfp_rank"] = current
                found_any = True

        if found_any:
            _POLL_CACHE[cache_key] = dict(result)
            return result
    _POLL_CACHE[cache_key] = dict(result)
    return result


def side_snapshot(
    competitor: Mapping[str, Any],
    current_week: int,
    season: int,
    now_utc: datetime,
) -> dict[str, Any]:
    tid = team_id(competitor)
    overall = record_summary(competitor, {"overall", "total"})
    conf = record_summary(
        competitor,
        {"vsconf", "conference", "conference record"},
    )

    rows: list[dict[str, Any]] = []
    if tid.isdigit():
        try:
            rows = schedule_rows(tid, season, now_utc)
        except Exception:
            rows = []

    derived = record_from_rows(rows)
    if not overall and int(derived.get("games") or 0) > 0:
        overall = record_text(derived)

    recent = rows[-5:]
    recent_form = "".join(
        "W" if float(row["points_for"]) > float(row["points_against"])
        else "L" if float(row["points_for"]) < float(row["points_against"])
        else "T"
        for row in recent
    )

    if rows:
        ppg = sum(float(r["points_for"]) for r in rows) / len(rows)
        pa = sum(float(r["points_against"]) for r in rows) / len(rows)
    else:
        ppg = pa = None

    coach = head_coach(tid, season) if tid.isdigit() else ""
    polls = latest_polls(tid, season, current_week) if tid.isdigit() else {
        "ap_rank": None,
        "coaches_poll_rank": None,
        "cfp_rank": None,
    }

    event_rank = rank_value(competitor)
    if polls.get("ap_rank") is None and event_rank is not None:
        polls["ap_rank"] = event_rank

    return {
        "team_id": tid,
        "record_text": overall,
        "conference_record_text": conf,
        "home_record": split_record(rows, "home"),
        "away_record": split_record(rows, "away"),
        "neutral_record": split_record(rows, "neutral"),
        "recent_form": recent_form or "—",
        "ppg": round(ppg, 6) if ppg is not None else None,
        "points_allowed_pg": round(pa, 6) if pa is not None else None,
        "point_diff_pg": round(ppg - pa, 6) if ppg is not None and pa is not None else None,
        "head_coach": coach,
        **polls,
        "completed_games": rows,
    }


def build_snapshot() -> dict[str, Any]:
    now_et = datetime.now(ET)
    now_utc = now_et.astimezone(timezone.utc)
    season = now_et.year if now_et.month >= 7 else now_et.year - 1

    dates = snapshot_dates(now_et)

    raw_events: dict[str, dict[str, Any]] = {}
    team_inputs: dict[str, dict[str, Any]] = {}

    # Phase 1: date-scoped Division I scoreboards only. FanDuel's NCAAF
    # board contains FBS and FCS games, including cross-division matchups, so
    # both ESPN groups are required for complete identity coverage.
    for day in dates:
        ymd = day.replace("-", "")
        for group_id, division in ((80, "FBS"), (81, "FCS")):
            try:
                payload = get_json(
                    SCOREBOARD,
                    {"dates": ymd, "limit": 500, "groups": group_id},
                )
            except Exception as exc:
                print(
                    f"WARN scoreboard {day} {division}: "
                    f"{type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                continue

            for event in payload.get("events") or []:
                if not isinstance(event, Mapping):
                    continue
                event_id = clean(event.get("id"))
                if not event_id:
                    continue
                away, home, comp = event_sides(event)
                if not away or not home:
                    continue

                dt = parse_dt(event.get("date"))
                event_day = (
                    dt.astimezone(ET).date().isoformat()
                    if dt is not None
                    else day
                )
                week = week_number(event)
                venue = comp.get("venue") or {}
                if not isinstance(venue, Mapping):
                    venue = {}

                existing_event = raw_events.get(event_id)
                if existing_event is None:
                    raw_events[event_id] = {
                        "event_id": event_id,
                        "game_date": event_day,
                        "away_team": team_name(away),
                        "home_team": team_name(home),
                        "kickoff_iso": dt.isoformat() if dt is not None else "",
                        "kickoff_et": (
                            dt.astimezone(ET).strftime("%I:%M %p").lstrip("0")
                            + " ET"
                            if dt is not None
                            else ""
                        ),
                        "venue": clean(
                            venue.get("fullName") or venue.get("name")
                        ),
                        "broadcast": broadcast(comp),
                        "status": status_name(event, comp),
                        "neutral_site": comp.get("neutralSite") is True,
                        "espn_week": week,
                        "_away_comp": dict(away),
                        "_home_comp": dict(home),
                    }

                for comp_side in (away, home):
                    tid = team_id(comp_side)
                    if not tid:
                        continue
                    existing = team_inputs.get(tid)
                    if (
                        existing is None
                        or int(week or 0) >= int(existing.get("week") or 0)
                    ):
                        team_inputs[tid] = {
                            "competitor": dict(comp_side),
                            "week": int(week or 0),
                        }

    if not raw_events:
        raise SystemExit(
            "No CFB events were retrieved; refusing to overwrite runtime snapshot"
        )

    # Phase 2: enrich each unique team once, in parallel. Team schedules,
    # coaches and poll collections are the expensive provider calls.
    team_snapshots: dict[str, dict[str, Any]] = {}
    max_workers = max(1, min(16, len(team_inputs)))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                side_snapshot,
                item["competitor"],
                int(item.get("week") or 0),
                season,
                now_utc,
            ): tid
            for tid, item in team_inputs.items()
        }
        for future in as_completed(futures):
            tid = futures[future]
            try:
                team_snapshots[tid] = future.result()
            except Exception as exc:
                print(
                    f"WARN team snapshot {tid}: {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                item = team_inputs[tid]
                comp = item["competitor"]
                team_snapshots[tid] = {
                    "team_id": tid,
                    "record_text": record_summary(comp, {"overall", "total"}),
                    "conference_record_text": record_summary(
                        comp,
                        {"vsconf", "conference", "conference record"},
                    ),
                    "home_record": {},
                    "away_record": {},
                    "neutral_record": {},
                    "recent_form": "—",
                    "ppg": None,
                    "points_allowed_pg": None,
                    "point_diff_pg": None,
                    "head_coach": "",
                    "ap_rank": rank_value(comp),
                    "coaches_poll_rank": None,
                    "cfp_rank": None,
                    "completed_games": [],
                }

    # Phase 3: join team snapshots back to each event.
    events: list[dict[str, Any]] = []
    for event_id, row in raw_events.items():
        away_comp = row.pop("_away_comp")
        home_comp = row.pop("_home_comp")
        away_id = team_id(away_comp)
        home_id = team_id(home_comp)

        away_snapshot = dict(team_snapshots.get(away_id) or {})
        home_snapshot = dict(team_snapshots.get(home_id) or {})

        # Event-carried record/rank is authoritative current context for this
        # exact matchup when the team-level enrichment did not return it.
        away_snapshot["record_text"] = (
            record_summary(away_comp, {"overall", "total"})
            or away_snapshot.get("record_text")
            or ""
        )
        away_snapshot["conference_record_text"] = (
            record_summary(
                away_comp,
                {"vsconf", "conference", "conference record"},
            )
            or away_snapshot.get("conference_record_text")
            or ""
        )
        home_snapshot["record_text"] = (
            record_summary(home_comp, {"overall", "total"})
            or home_snapshot.get("record_text")
            or ""
        )
        home_snapshot["conference_record_text"] = (
            record_summary(
                home_comp,
                {"vsconf", "conference", "conference record"},
            )
            or home_snapshot.get("conference_record_text")
            or ""
        )

        away_rank = rank_value(away_comp)
        home_rank = rank_value(home_comp)
        if away_snapshot.get("ap_rank") is None and away_rank is not None:
            away_snapshot["ap_rank"] = away_rank
        if home_snapshot.get("ap_rank") is None and home_rank is not None:
            home_snapshot["ap_rank"] = home_rank

        row["away"] = away_snapshot
        row["home"] = home_snapshot
        row["sources"] = [
            "ESPN college-football scoreboard",
            "ESPN current team schedules",
            "ESPN Core current coaches and polls",
        ]
        events.append(row)

    return {
        "version": 2,
        "generated_at": now_utc.replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "purpose": (
            "Current-data V2 fallback for deployed Streamlit/API runtimes. "
            "Auto-refreshed only when substantive game data changes."
        ),
        "window": {
            "start": dates[0],
            "end": dates[-1],
        },
        "games": sorted(
            events,
            key=lambda row: (
                row.get("game_date") or "",
                row.get("event_id") or "",
            ),
        ),
    }


def normalize_for_compare(payload: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out.pop("generated_at", None)
    return out


def main() -> int:
    new = build_snapshot()
    old: dict[str, Any] = {}
    if OUT.exists():
        try:
            parsed = json.loads(OUT.read_text(encoding="utf-8"))
            old = parsed if isinstance(parsed, dict) else {}
        except Exception:
            old = {}

    if normalize_for_compare(old) == normalize_for_compare(new):
        print("CFB_RUNTIME_SNAPSHOT_NO_SUBSTANTIVE_CHANGE")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(new, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(
        "CFB_RUNTIME_SNAPSHOT_UPDATED",
        f"games={len(new.get('games') or [])}",
        f"window={new.get('window')}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())