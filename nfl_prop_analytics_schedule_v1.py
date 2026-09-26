"""NFL Prop Analytics V1 — Step 2 Schedule Truth Layer.

Page 1 only. This module discovers the upcoming Sunday NFL slate from
independent public schedule sources, reconciles the fields, and renders a
fail-closed schedule board. It intentionally does not own player props,
sportsbook odds, projections, or any Passing Yards behavior.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time as dt_time, timedelta, timezone
import html as html_lib
from io import StringIO
import re
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 2 SCHEDULE TRUTH"
STEP = 2
PAGE = 1
SCHEDULE_ONLY = True
PLAYER_PROP_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PASSING_YARDS = False
MAY_MODIFY_EXISTING_NFL_MARKETS = False

NFLVERSE_GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
NFL_SCHEDULE_URL = "https://www.nfl.com/schedules/{season}/by-week/week-{week}"

AZ = ZoneInfo("America/Phoenix")
ET = ZoneInfo("America/New_York")

TEAM_ALIASES = {
    "ARI": "ARI", "ARIZONA": "ARI", "CARDINALS": "ARI",
    "ATL": "ATL", "ATLANTA": "ATL", "FALCONS": "ATL",
    "BAL": "BAL", "BALTIMORE": "BAL", "RAVENS": "BAL",
    "BUF": "BUF", "BUFFALO": "BUF", "BILLS": "BUF",
    "CAR": "CAR", "CAROLINA": "CAR", "PANTHERS": "CAR",
    "CHI": "CHI", "CHICAGO": "CHI", "BEARS": "CHI",
    "CIN": "CIN", "CINCINNATI": "CIN", "BENGALS": "CIN",
    "CLE": "CLE", "CLEVELAND": "CLE", "BROWNS": "CLE",
    "DAL": "DAL", "DALLAS": "DAL", "COWBOYS": "DAL",
    "DEN": "DEN", "DENVER": "DEN", "BRONCOS": "DEN",
    "DET": "DET", "DETROIT": "DET", "LIONS": "DET",
    "GB": "GB", "GNB": "GB", "GREEN BAY": "GB", "PACKERS": "GB",
    "HOU": "HOU", "HOUSTON": "HOU", "TEXANS": "HOU",
    "IND": "IND", "INDIANAPOLIS": "IND", "COLTS": "IND",
    "JAX": "JAX", "JAC": "JAX", "JACKSONVILLE": "JAX", "JAGUARS": "JAX",
    "KC": "KC", "KAN": "KC", "KANSAS CITY": "KC", "CHIEFS": "KC",
    "LAC": "LAC", "LA CHARGERS": "LAC", "CHARGERS": "LAC",
    "LAR": "LAR", "LA": "LAR", "LA RAMS": "LAR", "RAMS": "LAR",
    "LV": "LV", "OAK": "LV", "LAS VEGAS": "LV", "RAIDERS": "LV",
    "MIA": "MIA", "MIAMI": "MIA", "DOLPHINS": "MIA",
    "MIN": "MIN", "MINNESOTA": "MIN", "VIKINGS": "MIN",
    "NE": "NE", "NWE": "NE", "NEW ENGLAND": "NE", "PATRIOTS": "NE",
    "NO": "NO", "NOR": "NO", "NEW ORLEANS": "NO", "SAINTS": "NO",
    "NYG": "NYG", "GIANTS": "NYG",
    "NYJ": "NYJ", "JETS": "NYJ",
    "PHI": "PHI", "PHILADELPHIA": "PHI", "EAGLES": "PHI",
    "PIT": "PIT", "PITTSBURGH": "PIT", "STEELERS": "PIT",
    "SEA": "SEA", "SEATTLE": "SEA", "SEAHAWKS": "SEA",
    "SF": "SF", "SFO": "SF", "SAN FRANCISCO": "SF", "49ERS": "SF",
    "TB": "TB", "TAM": "TB", "TAMPA BAY": "TB", "BUCCANEERS": "TB",
    "TEN": "TEN", "TENNESSEE": "TEN", "TITANS": "TEN",
    "WAS": "WAS", "WSH": "WAS", "WASHINGTON": "WAS", "COMMANDERS": "WAS",
}

TEAM_NAMES = {
    "ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills",
    "CAR": "Panthers", "CHI": "Bears", "CIN": "Bengals", "CLE": "Browns",
    "DAL": "Cowboys", "DEN": "Broncos", "DET": "Lions", "GB": "Packers",
    "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars", "KC": "Chiefs",
    "LAC": "Chargers", "LAR": "Rams", "LV": "Raiders", "MIA": "Dolphins",
    "MIN": "Vikings", "NE": "Patriots", "NO": "Saints", "NYG": "Giants",
    "NYJ": "Jets", "PHI": "Eagles", "PIT": "Steelers", "SEA": "Seahawks",
    "SF": "49ers", "TB": "Buccaneers", "TEN": "Titans", "WAS": "Commanders",
}

SOURCE_PRIORITY = ("NFL", "NFLVERSE", "ESPN")
REQUEST_HEADERS = {
    "User-Agent": "KyreSportsAI/1.0 schedule-truth-layer (+https://kyre-sports-ai.streamlit.app)"
}


def _canon_team(value: Any) -> str:
    token = str(value or "").strip().upper()
    return TEAM_ALIASES.get(token, token)


def _target_sunday(today: date | None = None) -> date:
    base = today or datetime.now(AZ).date()
    return base + timedelta(days=(6 - base.weekday()) % 7)


def _kickoff_et(target: date, clock: str) -> datetime | None:
    raw = str(clock or "").strip()
    if not raw or raw.lower() in {"nan", "none"}:
        return None
    for fmt in ("%H:%M", "%I:%M %p"):
        try:
            parsed = datetime.strptime(raw, fmt).time()
            return datetime.combine(target, parsed, ET).astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _safe_iso(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _game(
    *,
    away: Any,
    home: Any,
    kickoff_utc: datetime | None,
    source: str,
    season: int,
    week: int | None = None,
    network: str = "",
    status: str = "",
    venue: str = "",
    game_id: str = "",
) -> dict[str, Any] | None:
    away_abbr = _canon_team(away)
    home_abbr = _canon_team(home)
    if away_abbr not in TEAM_NAMES or home_abbr not in TEAM_NAMES or away_abbr == home_abbr:
        return None
    return {
        "away": away_abbr,
        "home": home_abbr,
        "kickoff_utc": kickoff_utc,
        "source": source,
        "season": int(season),
        "week": int(week) if week not in (None, "", "nan") else None,
        "network": str(network or "").strip(),
        "status": str(status or "").strip(),
        "venue": str(venue or "").strip(),
        "game_id": str(game_id or "").strip(),
    }


def _from_nflverse(target: date) -> list[dict[str, Any]]:
    response = requests.get(
        NFLVERSE_GAMES_URL,
        headers=REQUEST_HEADERS,
        timeout=6,
    )
    response.raise_for_status()
    frame = pd.read_csv(StringIO(response.text), low_memory=False)
    if "gameday" not in frame.columns:
        raise RuntimeError("NFLVERSE_GAMEDAY_MISSING")
    rows = frame[frame["gameday"].astype(str) == target.isoformat()]
    games: list[dict[str, Any]] = []
    for _, row in rows.iterrows():
        kickoff = _kickoff_et(target, row.get("gametime", ""))
        item = _game(
            away=row.get("away_team"),
            home=row.get("home_team"),
            kickoff_utc=kickoff,
            source="NFLVERSE",
            season=int(row.get("season", target.year)),
            week=row.get("week"),
            network=row.get("network", ""),
            status="scheduled",
            venue=row.get("stadium", ""),
            game_id=row.get("game_id", ""),
        )
        if item:
            games.append(item)
    return games


def _from_espn(target: date) -> list[dict[str, Any]]:
    response = requests.get(
        ESPN_SCOREBOARD_URL,
        params={"dates": target.strftime("%Y%m%d"), "limit": 100},
        headers=REQUEST_HEADERS,
        timeout=6,
    )
    response.raise_for_status()
    payload = response.json()
    games: list[dict[str, Any]] = []
    for event in payload.get("events", []):
        competition = (event.get("competitions") or [{}])[0]
        sides = {}
        for competitor in competition.get("competitors", []):
            sides[competitor.get("homeAway")] = (
                competitor.get("team", {}).get("abbreviation")
            )
        broadcasts = []
        for broadcast in competition.get("broadcasts", []):
            broadcasts.extend(broadcast.get("names") or [])
        week = (
            event.get("week", {}).get("number")
            or competition.get("week", {}).get("number")
            or payload.get("week", {}).get("number")
        )
        season = event.get("season", {}).get("year") or target.year
        status = (
            event.get("status", {}).get("type", {}).get("description")
            or event.get("status", {}).get("type", {}).get("name")
            or "scheduled"
        )
        venue = competition.get("venue", {}).get("fullName", "")
        item = _game(
            away=sides.get("away"),
            home=sides.get("home"),
            kickoff_utc=_safe_iso(event.get("date")),
            source="ESPN",
            season=int(season),
            week=week,
            network=" / ".join(dict.fromkeys(broadcasts)),
            status=status,
            venue=venue,
            game_id=event.get("id", ""),
        )
        if item:
            games.append(item)
    return games


_OFFICIAL_GAME_RE = re.compile(
    r"\b([A-Za-z0-9]+)\s+at\s+([A-Za-z0-9]+),\s+Sunday,\s+"
    r"([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th),\s+"
    r"(\d{1,2}:\d{2}\s+[AP]M)(?:,\s+([A-Z][A-Z0-9+/.]*))?",
    re.IGNORECASE,
)


def _from_nfl_official(target: date, season: int, week: int | None) -> list[dict[str, Any]]:
    if not week:
        return []
    url = NFL_SCHEDULE_URL.format(season=season, week=week)
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=6)
    response.raise_for_status()
    clean = html_lib.unescape(re.sub(r"<[^>]+>", " ", response.text))
    clean = re.sub(r"\s+", " ", clean)

    games: list[dict[str, Any]] = []
    for match in _OFFICIAL_GAME_RE.finditer(clean):
        away, home, month, day_text, clock, network = match.groups()
        try:
            game_date = datetime.strptime(
                f"{month} {int(day_text)} {season}", "%B %d %Y"
            ).date()
        except ValueError:
            continue
        if game_date != target:
            continue
        kickoff = _kickoff_et(target, clock)
        item = _game(
            away=away,
            home=home,
            kickoff_utc=kickoff,
            source="NFL",
            season=season,
            week=week,
            network=network or "",
            status="scheduled",
        )
        if item:
            games.append(item)
    return games


def _week_hint(*collections: list[dict[str, Any]]) -> int | None:
    for games in collections:
        for game in games:
            if game.get("week"):
                return int(game["week"])
    return None


def _field_from_sources(
    bundle: dict[str, dict[str, Any]],
    field: str,
    order: tuple[str, ...],
    default: Any = "",
) -> Any:
    for source in order:
        value = bundle.get(source, {}).get(field)
        if value not in (None, ""):
            return value
    return default


def _reconcile_schedule(
    source_games: dict[str, list[dict[str, Any]]],
    target: date,
) -> list[dict[str, Any]]:
    bundles: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for source, games in source_games.items():
        for game in games:
            kickoff = game.get("kickoff_utc")
            if kickoff is not None:
                event_date = kickoff.astimezone(ET).date()
                if event_date != target:
                    continue
            key = (game["away"], game["home"])
            bundles.setdefault(key, {})[source] = game

    reconciled: list[dict[str, Any]] = []
    for (away, home), bundle in bundles.items():
        sources = tuple(source for source in SOURCE_PRIORITY if source in bundle)
        kickoff = _field_from_sources(
            bundle, "kickoff_utc", ("NFL", "ESPN", "NFLVERSE"), None
        )
        week = _field_from_sources(bundle, "week", ("NFL", "NFLVERSE", "ESPN"), None)
        network = _field_from_sources(bundle, "network", ("NFL", "ESPN", "NFLVERSE"), "")
        status = _field_from_sources(bundle, "status", ("ESPN", "NFL", "NFLVERSE"), "scheduled")
        venue = _field_from_sources(bundle, "venue", ("NFLVERSE", "ESPN", "NFL"), "")
        game_id = _field_from_sources(bundle, "game_id", ("NFLVERSE", "ESPN", "NFL"), "")

        kickoff_votes = [
            game.get("kickoff_utc")
            for game in bundle.values()
            if game.get("kickoff_utc") is not None
        ]
        kickoff_consensus = True
        if len(kickoff_votes) >= 2:
            anchor = kickoff_votes[0]
            kickoff_consensus = all(
                abs((vote - anchor).total_seconds()) <= 600
                for vote in kickoff_votes[1:]
            )

        reconciled.append(
            {
                "away": away,
                "home": home,
                "away_name": TEAM_NAMES[away],
                "home_name": TEAM_NAMES[home],
                "kickoff_utc": kickoff,
                "week": week,
                "network": network,
                "status": status,
                "venue": venue,
                "game_id": game_id,
                "sources": sources,
                "source_count": len(sources),
                "verified": len(sources) >= 2 and kickoff_consensus,
                "kickoff_consensus": kickoff_consensus,
            }
        )

    def sort_key(game: dict[str, Any]) -> tuple[int, str, str]:
        kickoff = game.get("kickoff_utc")
        stamp = int(kickoff.timestamp()) if kickoff else 2**62
        return stamp, game["away"], game["home"]

    return sorted(reconciled, key=sort_key)


def _load_schedule_truth_uncached(target: date) -> dict[str, Any]:
    errors: dict[str, str] = {}

    def safe(label: str, loader):
        try:
            return loader()
        except Exception as exc:
            errors[label] = f"{type(exc).__name__}:{exc}"
            return []

    with ThreadPoolExecutor(max_workers=2) as pool:
        nflverse_future = pool.submit(safe, "NFLVERSE", lambda: _from_nflverse(target))
        espn_future = pool.submit(safe, "ESPN", lambda: _from_espn(target))
        nflverse_games = nflverse_future.result()
        espn_games = espn_future.result()

    week = _week_hint(nflverse_games, espn_games)
    season = target.year
    official_games = safe(
        "NFL",
        lambda: _from_nfl_official(target, season=season, week=week),
    )

    source_games = {
        "NFL": official_games,
        "NFLVERSE": nflverse_games,
        "ESPN": espn_games,
    }
    games = _reconcile_schedule(source_games, target)
    available = tuple(
        source for source in SOURCE_PRIORITY if source_games.get(source)
    )
    verified_count = sum(1 for game in games if game["verified"])

    return {
        "target_date": target.isoformat(),
        "season": season,
        "week": week,
        "games": games,
        "game_count": len(games),
        "verified_count": verified_count,
        "sources_available": available,
        "source_errors": errors,
        "fail_closed": not bool(games),
    }


@st.cache_data(ttl=600, show_spinner=False)
def _cached_schedule_truth(target_iso: str) -> dict[str, Any]:
    return _load_schedule_truth_uncached(date.fromisoformat(target_iso))


def load_schedule_truth(target_date: date | None = None) -> dict[str, Any]:
    target = target_date or _target_sunday()
    return _cached_schedule_truth(target.isoformat())


def _kickoff_label(kickoff: datetime | None) -> str:
    if kickoff is None:
        return "Time TBD"
    local = kickoff.astimezone(ET)
    return local.strftime("%-I:%M %p ET")


def render_schedule_truth_layer() -> None:
    truth = load_schedule_truth()
    games = truth["games"]
    target = date.fromisoformat(truth["target_date"])
    date_label = target.strftime("%A • %B %-d, %Y")
    source_label = " + ".join(truth["sources_available"]) or "No source"
    verified_count = int(truth["verified_count"])

    if truth["fail_closed"]:
        st.markdown(
            f"""
<section data-nfl-prop-analytics-step2-schedule="v1"
         data-prop-schedule-state="fail-closed"
         data-prop-schedule-date="{html_lib.escape(truth['target_date'])}"
         data-prop-schedule-count="0"
         data-prop-schedule-verified-count="0">
  <div class="ks-pa2-empty">
    <strong>Schedule truth is temporarily unavailable.</strong>
    <span>No unverified or fabricated games are being displayed.</span>
  </div>
</section>
""",
            unsafe_allow_html=True,
        )
        return

    cards = []
    for game in games:
        badge = "VERIFIED" if game["verified"] else "SOURCE CONFIRMED"
        sources = " • ".join(game["sources"])
        network = game["network"] or "Network TBD"
        cards.append(
            f"""
<article class="ks-pa2-game" data-prop-game="{game['away']}-{game['home']}"
         data-prop-game-source-count="{game['source_count']}"
         data-prop-game-verified="{'true' if game['verified'] else 'false'}">
  <div class="ks-pa2-cardtop">
    <span>{html_lib.escape(_kickoff_label(game['kickoff_utc']))}</span>
    <span>{html_lib.escape(network)}</span>
  </div>
  <div class="ks-pa2-matchup">
    <div class="ks-pa2-team">
      <b>{html_lib.escape(game['away'])}</b>
      <span>{html_lib.escape(game['away_name'])}</span>
    </div>
    <div class="ks-pa2-at">@</div>
    <div class="ks-pa2-team ks-pa2-home">
      <b>{html_lib.escape(game['home'])}</b>
      <span>{html_lib.escape(game['home_name'])}</span>
    </div>
  </div>
  <div class="ks-pa2-proof">
    <span class="ks-pa2-badge">{badge}</span>
    <span>{html_lib.escape(sources)}</span>
  </div>
</article>
"""
        )

    st.markdown(
        f"""
<section class="ks-pa2-board"
         data-nfl-prop-analytics-step2-schedule="v1"
         data-prop-schedule-state="live"
         data-prop-schedule-date="{html_lib.escape(truth['target_date'])}"
         data-prop-schedule-count="{len(games)}"
         data-prop-schedule-verified-count="{verified_count}"
         data-prop-schedule-sources="{html_lib.escape(','.join(truth['sources_available']))}">
  <div class="ks-pa2-head">
    <div>
      <div class="ks-pa2-eyebrow">STEP 2 • SCHEDULE TRUTH</div>
      <h2>Sunday NFL Games</h2>
      <p>{html_lib.escape(date_label)}</p>
    </div>
    <div class="ks-pa2-truth">
      <strong>{verified_count}/{len(games)} verified</strong>
      <span>{html_lib.escape(source_label)}</span>
    </div>
  </div>
  <div class="ks-pa2-grid">
    {''.join(cards)}
  </div>
</section>
<style data-nfl-prop-analytics-step2-css="v1">
.ks-pa2-board{{width:100%;min-width:0;margin:10px 0 24px}}
.ks-pa2-head{{display:flex;justify-content:space-between;align-items:flex-end;gap:14px;margin:0 0 14px}}
.ks-pa2-eyebrow{{font-size:.7rem;font-weight:900;letter-spacing:.14em;color:#7dd3fc}}
.ks-pa2-head h2{{margin:.28rem 0 .18rem;color:#f8fafc;font-size:clamp(1.35rem,4vw,2rem);letter-spacing:-.035em}}
.ks-pa2-head p{{margin:0;color:#8fa4bd;font-size:.84rem}}
.ks-pa2-truth{{display:flex;flex-direction:column;align-items:flex-end;gap:3px;padding:9px 11px;border:1px solid rgba(125,211,252,.18);border-radius:12px;background:rgba(14,165,233,.055)}}
.ks-pa2-truth strong{{color:#e0f2fe;font-size:.78rem}}
.ks-pa2-truth span{{color:#7890ab;font-size:.65rem}}
.ks-pa2-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}
.ks-pa2-game{{min-width:0;border:1px solid rgba(125,211,252,.16);border-radius:15px;background:linear-gradient(145deg,rgba(7,14,24,.98),rgba(10,22,38,.94));padding:13px;overflow:hidden}}
.ks-pa2-cardtop,.ks-pa2-proof{{display:flex;justify-content:space-between;gap:8px;align-items:center;color:#7890ab;font-size:.66rem;font-weight:800}}
.ks-pa2-matchup{{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:8px;margin:14px 0}}
.ks-pa2-team{{display:flex;flex-direction:column;min-width:0}}
.ks-pa2-team b{{color:#f8fafc;font-size:1.05rem;line-height:1}}
.ks-pa2-team span{{margin-top:4px;color:#a8bad0;font-size:.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa2-home{{text-align:right;align-items:flex-end}}
.ks-pa2-at{{color:#38bdf8;font-size:.72rem;font-weight:900}}
.ks-pa2-proof{{padding-top:10px;border-top:1px solid rgba(148,163,184,.10)}}
.ks-pa2-badge{{color:#bae6fd!important;font-size:.61rem;letter-spacing:.07em}}
.ks-pa2-empty{{padding:16px;border:1px solid rgba(248,113,113,.3);border-radius:14px;background:rgba(127,29,29,.12);display:flex;flex-direction:column;gap:4px}}
.ks-pa2-empty strong{{color:#fecaca}}.ks-pa2-empty span{{color:#cbd5e1;font-size:.8rem}}
@media(max-width:680px){{
  .ks-pa2-head{{align-items:stretch;flex-direction:column}}
  .ks-pa2-truth{{align-items:flex-start}}
  .ks-pa2-grid{{grid-template-columns:1fr}}
}}
</style>
""",
        unsafe_allow_html=True,
    )


__all__ = [
    "MODEL_VERSION",
    "STEP",
    "PAGE",
    "SCHEDULE_ONLY",
    "PLAYER_PROP_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_PASSING_YARDS",
    "MAY_MODIFY_EXISTING_NFL_MARKETS",
    "load_schedule_truth",
    "render_schedule_truth_layer",
]
