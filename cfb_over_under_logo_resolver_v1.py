"""CFB O/U ESPN logo resolver hotfix V1.

Additive presentation-only hotfix above permanently frozen O/U Upgrade Steps 1-3.

Why this exists
---------------
The frozen Step-1 logo matcher requires exact normalized team-name/slug matches.
NCAA and ESPN can disagree on aliases such as "Miami (FL)" vs "Miami" and
"Florida A&M" vs "Florida A&M Rattlers". The schedule layer already uses a
careful overlap matcher for those identity enrichments, so this resolver applies
that same idea to presentation-only logo lookup.

Resolution order
----------------
1. Exact ESPN event_id when the schedule already has it.
2. Same-date ESPN scoreboard event matched with safe normalized aliases.
3. ESPN event summary lookup when an event_id exists but scoreboard extraction
   is incomplete.
4. Standard ESPN NCAA logo CDN derived from verified ESPN team_id when the
   payload omits an explicit logo href.

No projection, probability, selection, ranking, sportsbook, EV, or simulation
logic is touched.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_matchup_ui_v1 as frozen_ui
import cfb_schedule_v3 as schedule

MODEL_VERSION = "CFB O/U ESPN LOGO RESOLVER V1 • PRESENTATION HOTFIX"
FROZEN_STEP1_UI = "cfb_over_under_matchup_ui_v1"

ESPN_SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _name_key(value: Any) -> str:
    text = _clean(value).lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "", text)


def _aliases(value: Any) -> set[str]:
    text = _clean(value)
    if not text:
        return set()

    variants = {text}
    base = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    if base:
        variants.add(base)

    lower = base.lower()
    nickname_suffixes = (
        " rattlers", " hurricanes", " crimson tide", " bulldogs", " tigers",
        " wildcats", " eagles", " panthers", " seminoles", " gators",
        " buckeyes", " wolverines", " longhorns", " sooners", " aggies",
        " trojans", " bruins", " ducks", " beavers", " cardinals",
        " mountaineers", " cowboys", " knights", " cougars", " bears",
        " horned frogs", " yellow jackets", " blue devils", " tar heels",
        " hokies", " cavaliers", " demon deacons", " orange", " mustangs",
        " cyclones", " jayhawks", " red raiders", " cornhuskers",
        " golden gophers", " badgers", " spartans", " terrapins",
        " fighting illini", " boilermakers", " hoosiers", " nittany lions",
        " hawkeyes", " scarlet knights", " huskies", " golden bears",
        " buffaloes", " sun devils", " utes", " razorbacks", " volunteers",
        " commodores", " gamecocks", " rebels", " missouri tigers",
    )
    for suffix in nickname_suffixes:
        if lower.endswith(suffix):
            stripped = base[: -len(suffix)].strip()
            if stripped:
                variants.add(stripped)

    return {key for key in (_name_key(v) for v in variants) if key}


def _overlap(left: set[str], right: set[str]) -> bool:
    if left & right:
        return True
    for a in left:
        for b in right:
            if len(a) >= 5 and len(b) >= 5 and (a in b or b in a):
                return True
    return False


def _event_sides(event: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    competitions = event.get("competitions") or []
    if not competitions or not isinstance(competitions[0], Mapping):
        return {}
    sides: dict[str, Mapping[str, Any]] = {}
    for competitor in competitions[0].get("competitors") or []:
        if not isinstance(competitor, Mapping):
            continue
        side = _clean(competitor.get("homeAway")).lower()
        if side in {"away", "home"}:
            sides[side] = competitor
    return sides


def _competitor_aliases(competitor: Mapping[str, Any]) -> set[str]:
    team = competitor.get("team") or {}
    if not isinstance(team, Mapping):
        return set()
    values = (
        team.get("location"),
        team.get("shortDisplayName"),
        team.get("displayName"),
        team.get("name"),
        team.get("abbreviation"),
        team.get("slug"),
    )
    out: set[str] = set()
    for value in values:
        out |= _aliases(value)
    return out


def _game_aliases(game: Mapping[str, Any], side: str) -> set[str]:
    out = set()
    for value in (
        game.get(f"{side}_team"),
        game.get(f"{side}_team_slug"),
    ):
        out |= _aliases(value)
    return out


def _event_matches_game(
    event: Mapping[str, Any],
    game: Mapping[str, Any],
) -> bool:
    event_id = _clean(event.get("id"))
    game_event_id = _clean(game.get("espn_event_id"))
    if game_event_id and event_id == game_event_id:
        return True

    sides = _event_sides(event)
    if not sides:
        return False
    return (
        _overlap(
            _game_aliases(game, "away"),
            _competitor_aliases(sides.get("away") or {}),
        )
        and _overlap(
            _game_aliases(game, "home"),
            _competitor_aliases(sides.get("home") or {}),
        )
    )


def _safe_logo_url(team: Mapping[str, Any]) -> str:
    explicit = frozen_ui._safe_logo_url(team)
    if explicit:
        return explicit

    team_id = _clean(team.get("id"))
    if team_id.isdigit():
        return f"https://a.espncdn.com/i/teamlogos/ncaa/500/{team_id}.png"
    return ""


def _visual_from_competitor(competitor: Mapping[str, Any]) -> dict[str, Any]:
    visual = dict(frozen_ui._visual_from_competitor(competitor))
    team = competitor.get("team") or {}
    if not isinstance(team, Mapping):
        team = {}
    visual["logo"] = _safe_logo_url(team)
    visual["team_id"] = _clean(team.get("id")) or _clean(visual.get("team_id"))
    visual["source"] = "ESPN College Football"
    return visual


def _extract_from_event(
    event: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    sides = _event_sides(event)
    return {
        "away": _visual_from_competitor(sides.get("away") or {}),
        "home": _visual_from_competitor(sides.get("home") or {}),
    }


def _has_both_logos(visuals: Mapping[str, Mapping[str, Any]]) -> bool:
    return bool(
        _clean((visuals.get("away") or {}).get("logo"))
        and _clean((visuals.get("home") or {}).get("logo"))
    )


def _extract_from_scoreboard(
    payload: Mapping[str, Any],
    game: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    for event in payload.get("events") or []:
        if isinstance(event, Mapping) and _event_matches_game(event, game):
            return _extract_from_event(event)
    return {"away": {}, "home": {}}


def _summary_event(
    payload: Mapping[str, Any],
) -> Mapping[str, Any]:
    header = payload.get("header") or {}
    if isinstance(header, Mapping):
        competitions = header.get("competitions") or []
        if competitions and isinstance(competitions[0], Mapping):
            return {
                "id": _clean(payload.get("id") or header.get("id")),
                "competitions": [competitions[0]],
            }

    competitions = payload.get("competitions") or []
    if competitions and isinstance(competitions[0], Mapping):
        return {
            "id": _clean(payload.get("id")),
            "competitions": [competitions[0]],
        }
    return {}


@st.cache_data(ttl=300, show_spinner=False)
def _summary_payload(
    event_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not _clean(event_id):
        return {}, []
    return schedule.frozen.frozen._fetch_json_with_fallback(
        ESPN_SUMMARY_URL,
        {"event": _clean(event_id)},
        "ESPN CFB event summary logo fallback",
    )


def resolve_visuals(
    game: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    day = _clean(game.get("game_date"))
    if not day:
        return {"away": {}, "home": {}}

    scoreboard: dict[str, Any] = {}
    try:
        scoreboard, _ = schedule.frozen._fetch_espn_fbs_payload(day)
    except Exception:
        scoreboard = {}

    if isinstance(scoreboard, Mapping) and scoreboard:
        visuals = _extract_from_scoreboard(scoreboard, game)
        if _has_both_logos(visuals):
            return visuals
        if any(_clean((visuals.get(side) or {}).get("logo")) for side in ("away", "home")):
            partial = visuals
        else:
            partial = {"away": {}, "home": {}}
    else:
        partial = {"away": {}, "home": {}}

    event_id = _clean(game.get("espn_event_id"))
    if not event_id:
        identity = _clean(game.get("identity_key"))
        if identity.startswith("espn:"):
            event_id = identity.split(":", 1)[1]

    if event_id:
        try:
            summary, _ = _summary_payload(event_id)
        except Exception:
            summary = {}
        event = _summary_event(summary) if isinstance(summary, Mapping) else {}
        if event:
            resolved = _extract_from_event(event)
            for side in ("away", "home"):
                if not _clean((resolved.get(side) or {}).get("logo")):
                    resolved[side] = partial.get(side) or {}
            if any(_clean((resolved.get(side) or {}).get("logo")) for side in ("away", "home")):
                return resolved

    return partial


def clear_logo_cache() -> None:
    try:
        _summary_payload.clear()
    except Exception:
        pass


__all__ = [
    "ESPN_SUMMARY_URL",
    "FROZEN_STEP1_UI",
    "MODEL_VERSION",
    "_aliases",
    "_event_matches_game",
    "_extract_from_scoreboard",
    "_safe_logo_url",
    "clear_logo_cache",
    "resolve_visuals",
]
