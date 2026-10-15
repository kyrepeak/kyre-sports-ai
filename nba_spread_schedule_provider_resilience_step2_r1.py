"""NBA Spread provider-resilience Step 2 R1.

Add CBS Sports as an independent schedule-only provider above the frozen
NBA Official + ESPN transport repair from Step 1. CBS is parsed from semantic
scoreboard game-card HTML and normalized into the existing KYRE schedule row
schema. Schedule certification requires any two independent providers to agree
on canonical matchup/date and tip time within the frozen 15-minute tolerance.

This module does not mutate Step 1, the frozen schedule parser, the production
router, model, projection, probability, sportsbook, injuries, or any other NBA
field ownership.
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from html.parser import HTMLParser
from itertools import combinations
import re
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import requests

import nba_spread_schedule_v1 as frozen_schedule
import nba_spread_schedule_provider_resilience_step1_r1 as step1

MODEL_VERSION = "NBA_SPREAD_PROVIDER_RESILIENCE_STEP2_R1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_STEP1 = False
MAY_MODIFY_PRODUCTION_ROUTER = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_SOURCE_OWNERSHIP = False
NETWORK_PROVIDER_COUNT_ADDED = 1

SCHEDULE_PROVIDERS = ("NBA Official", "ESPN NBA", "CBS Sports")
TIP_TOLERANCE_SECONDS = 15 * 60
PHOENIX_TZ = ZoneInfo("America/Phoenix")
CBS_SOURCE_TZ = "America/New_York"
CBS_SCOREBOARD_URL = "https://www.cbssports.com/nba/scoreboard/{date}/"
CBS_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Explicit CBS provider-code -> KYRE canonical NBA tricode mapping. Canonical
# spellings are included too so unknown values never fall through to fuzzy
# matching or name guessing.
CBS_TO_NBA_TRICODE: dict[str, str] = {
    "ATL": "ATL",
    "BOS": "BOS",
    "BKN": "BKN",
    "CHA": "CHA",
    "CHI": "CHI",
    "CLE": "CLE",
    "DAL": "DAL",
    "DEN": "DEN",
    "DET": "DET",
    "GS": "GSW",
    "GSW": "GSW",
    "HOU": "HOU",
    "IND": "IND",
    "LAC": "LAC",
    "LAL": "LAL",
    "MEM": "MEM",
    "MIA": "MIA",
    "MIL": "MIL",
    "MIN": "MIN",
    "NO": "NOP",
    "NOP": "NOP",
    "NY": "NYK",
    "NYK": "NYK",
    "OKC": "OKC",
    "ORL": "ORL",
    "PHI": "PHI",
    "PHO": "PHX",
    "PHX": "PHX",
    "POR": "POR",
    "SAC": "SAC",
    "SA": "SAS",
    "SAS": "SAS",
    "TOR": "TOR",
    "UTA": "UTA",
    "UTAH": "UTA",
    "WAS": "WAS",
    "WSH": "WAS",
}

_TEAM_URL_RE = re.compile(r"/nba/teams/([A-Za-z0-9]+)/([^/?#]+)/?")
_ROOT_MATCHUP_RE = re.compile(r"^NBA_\d{8}_([A-Za-z0-9]+)@([A-Za-z0-9]+)$", re.I)
_CLOCK_RE = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(AM|PM)\s*(ET|EST|EDT)?\b",
    re.I,
)
_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}
_BLOCKED_CONTEXT_TAGS = {"nav", "header", "footer", "aside"}


def normalize_cbs_team_code(value: Any) -> str | None:
    code = str(value or "").strip().upper()
    return CBS_TO_NBA_TRICODE.get(code)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _requested_date(value: str) -> datetime:
    text = str(value or "").strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed
        except ValueError:
            continue
    raise ValueError("CBS requested_date must be YYYYMMDD or YYYY-MM-DD")


def _slug_name(slug: str, fallback: str) -> str:
    cleaned = _clean_text(slug.replace("-", " "))
    return cleaned.title() if cleaned else fallback


def _parse_cbs_tip(
    *,
    requested_date: str,
    time_text: str = "",
    datetime_text: str = "",
    source_timezone: str = CBS_SOURCE_TZ,
) -> datetime | None:
    source_tz = ZoneInfo(source_timezone)
    raw_datetime = _clean_text(datetime_text)
    if raw_datetime:
        try:
            parsed = datetime.fromisoformat(raw_datetime.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=source_tz)
            return parsed.astimezone(timezone.utc)

    match = _CLOCK_RE.search(_clean_text(time_text))
    if match is None:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = match.group(3).upper()
    if not (1 <= hour <= 12 and 0 <= minute <= 59):
        return None
    if meridiem == "AM":
        hour = 0 if hour == 12 else hour
    else:
        hour = 12 if hour == 12 else hour + 12
    day = _requested_date(requested_date).date()
    local = datetime.combine(day, time(hour=hour, minute=minute), tzinfo=source_tz)
    return local.astimezone(timezone.utc)


class _CBSScoreboardParser(HTMLParser):
    """Extract only semantic CBS scoreboard game cards, never global navigation."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, dict[str, str]]] = []
        self.card: dict[str, Any] | None = None
        self.card_stack_index: int | None = None
        self.cards: list[dict[str, Any]] = []
        self._time_depth = 0
        self._status_depth = 0
        self._venue_depth = 0

    @staticmethod
    def _is_card(tag: str, attrs: dict[str, str]) -> bool:
        if tag not in {"div", "article", "section", "li"}:
            return False
        if attrs.get("data-role") == "game-card":
            return True
        classes = set(str(attrs.get("class") or "").split())
        return "single-score-card" in classes and "nba" in classes

    def _blocked(self) -> bool:
        return any(tag in _BLOCKED_CONTEXT_TAGS for tag, _ in self.stack)

    def _current_side(self, attrs: dict[str, str]) -> str:
        side = str(attrs.get("data-side") or "").strip().lower()
        if side in {"away", "home"}:
            return side
        if self.card_stack_index is None:
            return ""
        for _tag, ancestor in reversed(self.stack[self.card_stack_index:]):
            side = str(ancestor.get("data-side") or "").strip().lower()
            if side in {"away", "home"}:
                return side
        return ""

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {key: str(value or "") for key, value in attrs_list}
        if self.card is None and not self._blocked() and self._is_card(tag, attrs):
            self.card_stack_index = len(self.stack)
            self.card = {
                "root_tag": tag,
                "root_attrs": attrs,
                "teams": [],
                "time_text": [],
                "datetime_text": "",
                "status_text": [],
                "venue_text": [],
                "all_text": [],
            }

        if self.card is not None:
            href = attrs.get("href", "")
            team_match = _TEAM_URL_RE.search(href)
            if team_match is not None:
                self.card["teams"].append(
                    {
                        "provider_code": team_match.group(1).upper(),
                        "slug": team_match.group(2),
                        "side": self._current_side(attrs),
                    }
                )
            if tag == "time":
                self._time_depth += 1
                if attrs.get("datetime"):
                    self.card["datetime_text"] = attrs["datetime"]
            if attrs.get("data-role") == "status":
                self._status_depth += 1
            if attrs.get("data-role") == "venue":
                self._venue_depth += 1

        if tag not in _VOID_TAGS:
            self.stack.append((tag, attrs))

    def handle_startendtag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs_list)
        if tag not in _VOID_TAGS:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.card is None:
            return
        text = _clean_text(data)
        if not text:
            return
        self.card["all_text"].append(text)
        if self._time_depth:
            self.card["time_text"].append(text)
        if self._status_depth:
            self.card["status_text"].append(text)
        if self._venue_depth:
            self.card["venue_text"].append(text)

    def handle_endtag(self, tag: str) -> None:
        if self.card is not None:
            if tag == "time" and self._time_depth:
                self._time_depth -= 1
            if self._status_depth and self.stack and self.stack[-1][1].get("data-role") == "status":
                self._status_depth -= 1
            if self._venue_depth and self.stack and self.stack[-1][1].get("data-role") == "venue":
                self._venue_depth -= 1

        match_index: int | None = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                match_index = index
                break

        if (
            self.card is not None
            and self.card_stack_index is not None
            and match_index == self.card_stack_index
            and tag == self.card["root_tag"]
        ):
            self.cards.append(self.card)
            self.card = None
            self.card_stack_index = None
            self._time_depth = 0
            self._status_depth = 0
            self._venue_depth = 0

        if match_index is not None:
            self.stack = self.stack[:match_index]


def _unique_team_nodes(nodes: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for node in nodes:
        key = str(node.get("provider_code") or "").upper()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(node)
    return output


def _card_identity(card: dict[str, Any]) -> tuple[dict[str, str] | None, str | None, list[str]]:
    root = card.get("root_attrs") or {}
    root_match = _ROOT_MATCHUP_RE.match(str(root.get("data-abbrev") or "").strip())
    team_nodes = _unique_team_nodes(list(card.get("teams") or []))
    unknown: list[str] = []

    normalized_nodes: list[dict[str, str]] = []
    for node in team_nodes:
        raw = str(node.get("provider_code") or "").upper()
        canonical = normalize_cbs_team_code(raw)
        if canonical is None:
            unknown.append(raw)
            continue
        normalized_nodes.append({**node, "canonical": canonical})

    if unknown:
        return None, "unknown_identity", unknown

    by_side = {node.get("side"): node for node in normalized_nodes if node.get("side") in {"away", "home"}}
    away: dict[str, str] | None = by_side.get("away")
    home: dict[str, str] | None = by_side.get("home")

    if root_match is not None:
        away_raw, home_raw = root_match.groups()
        away_code = normalize_cbs_team_code(away_raw)
        home_code = normalize_cbs_team_code(home_raw)
        if away_code is None:
            unknown.append(away_raw.upper())
        if home_code is None:
            unknown.append(home_raw.upper())
        if unknown:
            return None, "unknown_identity", unknown
        by_canonical = {node["canonical"]: node for node in normalized_nodes}
        away = by_canonical.get(str(away_code)) or {
            "provider_code": away_raw.upper(), "slug": "", "side": "away", "canonical": str(away_code)
        }
        home = by_canonical.get(str(home_code)) or {
            "provider_code": home_raw.upper(), "slug": "", "side": "home", "canonical": str(home_code)
        }

    if away is None or home is None:
        if len(normalized_nodes) != 2:
            return None, "participant_count", []
        away, home = normalized_nodes[0], normalized_nodes[1]

    if away["canonical"] == home["canonical"]:
        return None, "participant_count", []

    return {
        "away_provider_code": away["provider_code"],
        "away_tricode": away["canonical"],
        "away_name": _slug_name(away.get("slug", ""), away["canonical"]),
        "home_provider_code": home["provider_code"],
        "home_tricode": home["canonical"],
        "home_name": _slug_name(home.get("slug", ""), home["canonical"]),
    }, None, []


def parse_cbs_scoreboard_html(
    html: str,
    requested_date: str,
    source_timezone: str = CBS_SOURCE_TZ,
) -> dict[str, Any]:
    """Parse card-scoped CBS NBA scoreboard HTML into canonical schedule rows."""
    _requested_date(requested_date)
    parser = _CBSScoreboardParser()
    parser.feed(str(html or ""))
    parser.close()

    games: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    unknown_identities: list[str] = []
    missing_times: list[str] = []

    for index, card in enumerate(parser.cards, start=1):
        root = card.get("root_attrs") or {}
        raw_id = str(root.get("data-game-id") or root.get("id") or f"card-{index}").strip()
        source_game_id = raw_id.removeprefix("game-") if raw_id else f"card-{index}"
        identity, error_kind, unknown = _card_identity(card)
        if unknown:
            unknown_identities.extend(unknown)
        if identity is None:
            parse_errors.append(raw_id or source_game_id)
            continue

        all_text = " ".join(card.get("all_text") or [])
        time_text = " ".join(card.get("time_text") or [])
        if not time_text:
            clock_match = _CLOCK_RE.search(all_text)
            if clock_match is not None:
                time_text = clock_match.group(0)
        tip_utc = _parse_cbs_tip(
            requested_date=requested_date,
            time_text=time_text,
            datetime_text=str(card.get("datetime_text") or ""),
            source_timezone=source_timezone,
        )
        if tip_utc is None:
            missing_times.append(raw_id or source_game_id)
            continue

        phoenix = tip_utc.astimezone(PHOENIX_TZ)
        phoenix_date = phoenix.date().isoformat()
        root_classes = str(root.get("class") or "").lower()
        explicit_status = " ".join(card.get("status_text") or [])
        if explicit_status:
            status = frozen_schedule.normalize_game_status(explicit_status)
        elif "final" in root_classes:
            status = "FINAL"
        elif "live" in root_classes or "in-progress" in root_classes:
            status = "LIVE"
        else:
            status = "UPCOMING"

        games.append(
            {
                "source": "CBS Sports",
                "source_game_id": source_game_id,
                "game_key": f"{identity['away_tricode']}@{identity['home_tricode']}:{phoenix_date}",
                "away_tricode": identity["away_tricode"],
                "away_name": identity["away_name"],
                "home_tricode": identity["home_tricode"],
                "home_name": identity["home_name"],
                "tip_utc": tip_utc.isoformat().replace("+00:00", "Z"),
                "tip_iso_phoenix": phoenix.isoformat(),
                "tip_phoenix": phoenix.strftime("%-I:%M %p %Z"),
                "game_date_phoenix": phoenix_date,
                "status": status,
                "venue": " ".join(card.get("venue_text") or []),
                "provider_team_codes": {
                    "away": identity["away_provider_code"],
                    "home": identity["home_provider_code"],
                },
            }
        )

    games.sort(key=lambda item: (item["tip_utc"], item["game_key"]))
    return {
        "games": games,
        "parse_errors": sorted(set(parse_errors)),
        "unknown_identities": sorted(set(unknown_identities)),
        "missing_times": sorted(set(missing_times)),
    }


def _parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _pair_agrees(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if str(left.get("game_key") or "") != str(right.get("game_key") or ""):
        return False
    left_tip = _parse_utc(left.get("tip_utc"))
    right_tip = _parse_utc(right.get("tip_utc"))
    if left_tip is None or right_tip is None:
        return False
    return abs((left_tip - right_tip).total_seconds()) <= TIP_TOLERANCE_SECONDS


def reconcile_resilient_schedule(
    provider_games: dict[str, list[dict[str, Any]]],
    window_dates: Iterable[str],
    *,
    provider_errors: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Certify each matchup with any agreeing pair of independent providers."""
    dates = tuple(window_dates)
    by_provider: dict[str, dict[str, dict[str, Any]]] = {
        provider: {
            str(item.get("game_key") or ""): item
            for item in provider_games.get(provider, [])
            if str(item.get("game_key") or "")
        }
        for provider in SCHEDULE_PROVIDERS
    }
    keys = sorted(set().union(*(set(rows) for rows in by_provider.values())))
    certified: list[dict[str, Any]] = []
    unverified_keys: list[str] = []
    conflict_keys: list[str] = []

    pair_priority = (
        ("NBA Official", "ESPN NBA"),
        ("NBA Official", "CBS Sports"),
        ("ESPN NBA", "CBS Sports"),
    )

    for key in keys:
        present = {
            provider: by_provider[provider][key]
            for provider in SCHEDULE_PROVIDERS
            if key in by_provider[provider]
        }
        agreeing_pairs = [
            pair
            for pair in pair_priority
            if pair[0] in present and pair[1] in present and _pair_agrees(present[pair[0]], present[pair[1]])
        ]
        if not agreeing_pairs:
            if len(present) >= 2:
                conflict_keys.append(key)
            else:
                unverified_keys.append(key)
            continue

        chosen_pair = agreeing_pairs[0]
        base = dict(present[chosen_pair[0]])
        confirming = list(chosen_pair)
        for provider in SCHEDULE_PROVIDERS:
            if provider in confirming or provider not in present:
                continue
            if _pair_agrees(base, present[provider]):
                confirming.append(provider)
        rejected = [provider for provider in SCHEDULE_PROVIDERS if provider in present and provider not in confirming]
        base["confirming_sources"] = confirming
        base["source_agreement"] = len(confirming)
        base["source_game_ids"] = {
            provider: present[provider].get("source_game_id") for provider in confirming
        }
        base["rejected_sources"] = rejected
        certified.append(base)

    errors = dict(provider_errors or {})
    nonempty_providers = [provider for provider in SCHEDULE_PROVIDERS if by_provider[provider]]
    if conflict_keys:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "PROVIDER_CONFLICT",
            "games": [],
            "source_agreement": 0,
            "window_dates": dates,
            "provider_errors": errors,
            "conflict_game_keys": conflict_keys,
            "unverified_game_keys": unverified_keys,
        }
    if not certified:
        state = "PROVIDER_CONFLICT" if len(nonempty_providers) >= 2 else "INSUFFICIENT_PROVIDER_QUORUM"
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": state,
            "games": [],
            "source_agreement": 0,
            "window_dates": dates,
            "provider_errors": errors,
            "conflict_game_keys": [],
            "unverified_game_keys": unverified_keys,
        }

    certified.sort(key=lambda item: (item["tip_utc"], item["game_key"]))
    return {
        "verification": "VERIFIED",
        "diagnostic_state": "SOURCE_CONSENSUS",
        "games": certified,
        "source_agreement": min(int(item.get("source_agreement") or 0) for item in certified),
        "window_dates": dates,
        "provider_errors": errors,
        "conflict_game_keys": [],
        "unverified_game_keys": unverified_keys,
    }


def _fetch_cbs_daily(session: Any, date_text: str, *, timeout: float) -> str:
    url = CBS_SCOREBOARD_URL.format(date=date_text.replace("-", ""))
    response = session.get(url, headers=CBS_HEADERS, timeout=timeout)
    response.raise_for_status()
    text = getattr(response, "text", None)
    if text is None:
        content = getattr(response, "content", b"")
        text = content.decode("utf-8", "replace") if isinstance(content, (bytes, bytearray)) else str(content or "")
    if not str(text or "").strip():
        raise ValueError("CBS scoreboard returned empty HTML")
    return str(text)


def load_verified_nba_schedule(
    *,
    now_utc: datetime | None = None,
    days: int = frozen_schedule.ROLLING_DAYS,
    session: Any | None = None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Fetch all three schedule providers independently and apply 2-of-3 quorum."""
    window = frozen_schedule.rolling_phoenix_dates(now_utc=now_utc, days=days)
    delegate = session if session is not None else requests.Session()
    repaired = step1._NbaProviderTransportRepairSession(
        delegate,
        season_start_year=step1._season_start_year(now_utc),
    )

    provider_games: dict[str, list[dict[str, Any]]] = {provider: [] for provider in SCHEDULE_PROVIDERS}
    provider_errors: dict[str, str] = {}
    cbs_parse_errors: list[str] = []
    cbs_unknown_identities: list[str] = []
    cbs_missing_times: list[str] = []

    try:
        official_payload = frozen_schedule._fetch_official(repaired, timeout=timeout)
        provider_games["NBA Official"] = frozen_schedule.parse_nba_official(official_payload, window)
    except Exception as exc:
        provider_errors["NBA Official"] = type(exc).__name__

    try:
        espn_payload = frozen_schedule._fetch_espn(repaired, window, timeout=timeout)
        provider_games["ESPN NBA"] = frozen_schedule.parse_espn(espn_payload, window)
    except Exception as exc:
        provider_errors["ESPN NBA"] = type(exc).__name__

    for phoenix_date in window:
        try:
            html = _fetch_cbs_daily(delegate, phoenix_date, timeout=timeout)
            parsed = parse_cbs_scoreboard_html(html, phoenix_date)
            provider_games["CBS Sports"].extend(parsed["games"])
            cbs_parse_errors.extend(f"{phoenix_date}:{value}" for value in parsed["parse_errors"])
            cbs_unknown_identities.extend(f"{phoenix_date}:{value}" for value in parsed["unknown_identities"])
            cbs_missing_times.extend(f"{phoenix_date}:{value}" for value in parsed["missing_times"])
        except Exception as exc:
            provider_errors.setdefault("CBS Sports", type(exc).__name__)

    result = reconcile_resilient_schedule(
        provider_games,
        window,
        provider_errors=provider_errors,
    )
    generated = now_utc or datetime.now(timezone.utc)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    result["generated_at_phoenix"] = generated.astimezone(PHOENIX_TZ).isoformat()
    result["provider_game_counts"] = {
        provider: len(provider_games[provider]) for provider in SCHEDULE_PROVIDERS
    }
    result["provider_game_keys"] = {
        provider: sorted(str(item.get("game_key") or "") for item in provider_games[provider])
        for provider in SCHEDULE_PROVIDERS
    }
    result["cbs_parse_errors"] = sorted(set(cbs_parse_errors))
    result["cbs_unknown_identities"] = sorted(set(cbs_unknown_identities))
    result["cbs_missing_times"] = sorted(set(cbs_missing_times))
    return result


__all__ = [
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_STEP1",
    "MAY_MODIFY_PRODUCTION_ROUTER",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_SOURCE_OWNERSHIP",
    "NETWORK_PROVIDER_COUNT_ADDED",
    "SCHEDULE_PROVIDERS",
    "TIP_TOLERANCE_SECONDS",
    "CBS_TO_NBA_TRICODE",
    "CBS_SCOREBOARD_URL",
    "normalize_cbs_team_code",
    "parse_cbs_scoreboard_html",
    "reconcile_resilient_schedule",
    "load_verified_nba_schedule",
]
