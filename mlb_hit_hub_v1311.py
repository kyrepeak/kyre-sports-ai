"""MLB 1+ Hit UI V13.11 — Step 8 opponent run-prevention + fielding context.

Presentation/context-only wrapper around verified cache-safe V13.10.2. Hit Model V13
probability math, Monte Carlo, candidate pool, lineup handling, ranking, calibration
and persistence remain unchanged.

Step 8 adds official MLB opponent-team season context for each Top-5 hitter:
1) team pitching ERA / WHIP / H/9 / opponent batting average,
2) a transparent team BABIP-allowed value derived only when official MLB pitching
   totals provide every required input,
3) team fielding percentage,
4) errors per game and double plays per game when official fielding totals exist.

This layer is descriptive only. It never changes the V13 probability, confidence,
Monte Carlo distribution, ranking or candidate selection. Missing fields are labeled
unavailable rather than estimated.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import math

import requests
import streamlit as st

import engine as hit_engine
import mlb_hit_hub_v13102 as prior

active = prior.active
core = prior.core
visual = prior.visual

UI_VERSION = "V13.11"
MLB_API = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "Mozilla/5.0 KyreSportsAI/1.0"}

# Cache-safe boundary: bind directly to the verified V13.10.2 renderer.
_BASE_PICK_HTML = prior._pick_html_v13102


def _safe_id(value):
    return prior._safe_id(value)


def _num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _selected_day():
    try:
        return str(prior._selected_day() or "")[:10]
    except Exception:
        return ""


def _season_from_day():
    day = _selected_day()
    try:
        return datetime.strptime(day, "%Y-%m-%d").year
    except Exception:
        try:
            return hit_engine.season()
        except Exception:
            return 2026


def _fmt(value, digits=2):
    x = _num(value, None)
    return "—" if x is None else f"{x:.{digits}f}"


def _avg(value):
    x = _num(value, None)
    return "—" if x is None else f"{x:.3f}".lstrip("0")


def _pct(value, digits=3):
    x = _num(value, None)
    return "—" if x is None else f"{x * 100.0:.{digits}f}%"


def _opponent_team_id(result):
    """Resolve the opposing MLB team from the exact modeled game."""
    pk = _safe_id((result or {}).get("game_pk"))
    own = _safe_id((result or {}).get("team_id"))
    if pk is None or own is None:
        return None
    try:
        feed = hit_engine.game_feed(pk) or {}
        teams = ((feed.get("gameData") or {}).get("teams") or {})
        away = _safe_id((teams.get("away") or {}).get("id"))
        home = _safe_id((teams.get("home") or {}).get("id"))
        if own == away:
            return home
        if own == home:
            return away
    except Exception:
        pass
    return None


def _first_stat(payload):
    try:
        groups = payload.get("stats") or []
        split = ((groups[0].get("splits") or [None])[0] if groups else None) or {}
        stat = split.get("stat") or {}
        return stat if isinstance(stat, dict) else {}
    except Exception:
        return {}


@st.cache_data(ttl=900, show_spinner=False)
def _opponent_team_context(team_id, season):
    tid = _safe_id(team_id)
    if tid is None:
        return {"available": False}

    pitching = {}
    fielding = {}
    try:
        r = requests.get(
            f"{MLB_API}/teams/{tid}/stats",
            params={"stats": "season", "group": "pitching", "season": int(season)},
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        pitching = _first_stat(r.json())
    except Exception:
        pitching = {}

    try:
        r = requests.get(
            f"{MLB_API}/teams/{tid}/stats",
            params={"stats": "season", "group": "fielding", "season": int(season)},
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        fielding = _first_stat(r.json())
    except Exception:
        fielding = {}

    if not pitching and not fielding:
        return {"available": False}

    innings = None
    try:
        innings = hit_engine.ipfloat(pitching.get("inningsPitched")) if pitching else None
    except Exception:
        innings = None

    hits = _num(pitching.get("hits"), None)
    home_runs = _num(pitching.get("homeRuns"), None)
    strikeouts = _num(pitching.get("strikeOuts"), None)
    at_bats = _num(pitching.get("atBats"), None)
    sac_flies = _num(pitching.get("sacFlies"), None)

    h9 = (hits * 9.0 / innings) if hits is not None and innings and innings > 0 else None

    babip = None
    if None not in (hits, home_runs, strikeouts, at_bats, sac_flies):
        denom = at_bats - strikeouts - home_runs + sac_flies
        if denom > 0:
            babip = (hits - home_runs) / denom
            if not math.isfinite(babip) or babip < 0 or babip > 1:
                babip = None

    games = _num(pitching.get("gamesPlayed"), None)
    if games is None or games <= 0:
        games = _num(fielding.get("gamesPlayed"), None)

    errors = _num(fielding.get("errors"), None)
    double_plays = _num(fielding.get("doublePlays"), None)
    errors_pg = (errors / games) if errors is not None and games and games > 0 else None
    dp_pg = (double_plays / games) if double_plays is not None and games and games > 0 else None

    field_pct = _num(fielding.get("fielding"), None)
    if field_pct is None:
        field_pct = _num(fielding.get("fieldingPercentage"), None)

    return {
        "available": True,
        "era": _num(pitching.get("era"), None),
        "whip": _num(pitching.get("whip"), None),
        "opp_avg": _num(pitching.get("avg"), None),
        "h9": h9,
        "babip_allowed": babip,
        "fielding_pct": field_pct,
        "errors_pg": errors_pg,
        "double_plays_pg": dp_pg,
        "games": int(games) if games and games > 0 else None,
    }


def _opponent_strip(result):
    opponent_id = _opponent_team_id(result)
    ctx = _opponent_team_context(opponent_id, _season_from_day())
    opponent = str((result or {}).get("opponent") or "Opponent")

    if not ctx.get("available"):
        return (
            '<div class="hit1311-context">'
            '<div class="hit1311-head">STEP 8 • OPPONENT RUN PREVENTION + FIELDING</div>'
            f'<div class="hit1311-note">Official MLB team context unavailable for {escape(opponent)}. '
            'No defensive value was estimated; V13 ranking is unaffected.</div>'
            '</div>'
        )

    pitching_bits = []
    if _num(ctx.get("era"), None) is not None:
        pitching_bits.append(f"ERA {_fmt(ctx.get('era'), 2)}")
    if _num(ctx.get("whip"), None) is not None:
        pitching_bits.append(f"WHIP {_fmt(ctx.get('whip'), 2)}")
    if _num(ctx.get("h9"), None) is not None:
        pitching_bits.append(f"H/9 {_fmt(ctx.get('h9'), 2)}")
    if _num(ctx.get("opp_avg"), None) is not None:
        pitching_bits.append(f"Opp AVG {_avg(ctx.get('opp_avg'))}")

    bip_bits = []
    if _num(ctx.get("babip_allowed"), None) is not None:
        bip_bits.append(f"BABIP allowed {_avg(ctx.get('babip_allowed'))}")
    if _num(ctx.get("fielding_pct"), None) is not None:
        bip_bits.append(f"Fielding {_pct(ctx.get('fielding_pct'), 3)}")
    if _num(ctx.get("errors_pg"), None) is not None:
        bip_bits.append(f"Errors/game {_fmt(ctx.get('errors_pg'), 2)}")
    if _num(ctx.get("double_plays_pg"), None) is not None:
        bip_bits.append(f"DP/game {_fmt(ctx.get('double_plays_pg'), 2)}")

    pitching_text = " • ".join(pitching_bits) if pitching_bits else "Official team pitching context unavailable"
    bip_text = " • ".join(bip_bits) if bip_bits else "Official fielding / ball-in-play context unavailable"

    return (
        '<div class="hit1311-context">'
        '<div class="hit1311-head">STEP 8 • OPPONENT RUN PREVENTION + FIELDING</div>'
        f'<div class="hit1311-main"><b>{escape(opponent)}</b> • {escape(pitching_text)}</div>'
        f'<div class="hit1311-sub"><b>Ball-in-play / fielding</b> • {escape(bip_text)}</div>'
        '<div class="hit1311-note">BABIP allowed is derived only from official MLB team pitching totals when all inputs exist. '
        'This entire Step-8 layer is descriptive and does not change Hit Model V13.</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hit1311-context{margin:7px 0 5px;padding:9px 10px;border:1px solid #5a4c34;background:linear-gradient(145deg,#17150f,#0d1318);border-radius:12px}
.hit1311-head{font-size:.44rem;letter-spacing:.08em;color:#e8c778;font-weight:950;text-transform:uppercase}
.hit1311-main{font-size:.53rem;color:#e8edf2;line-height:1.5;margin-top:3px}.hit1311-main b{color:#fff1c4}
.hit1311-sub{font-size:.50rem;color:#c8d0d8;line-height:1.48;margin-top:3px}.hit1311-sub b{color:#e8d9ad}
.hit1311-note{font-size:.42rem;color:#7f8994;line-height:1.4;margin-top:4px}
</style>
"""

if "hit1311-context" not in core.HIT_CSS:
    core.HIT_CSS = core.HIT_CSS + _EXTRA_CSS


def _pick_html_v1311(result, rank):
    html = _BASE_PICK_HTML(result, rank)
    if not isinstance(html, str):
        html = str(html or "")
    try:
        strip = _opponent_strip(result if isinstance(result, dict) else {})
    except Exception:
        strip = (
            '<div class="hit1311-context">'
            '<div class="hit1311-head">STEP 8 • OPPONENT RUN PREVENTION + FIELDING</div>'
            '<div class="hit1311-note">Step-8 context unavailable for this card. V13 projection and ranking remain unaffected.</div>'
            '</div>'
        )
    marker = '<div class="hit-pick-prob">'
    if marker in html:
        return html.replace(marker, strip + marker, 1)
    return html + strip


active._pick_html = _pick_html_v1311


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.caption(
        "🛡️ Hit UI V13.11 • Step 8 official opponent run-prevention + fielding context ACTIVE • "
        "MLB team pitching/fielding • display/context only • Hit Model V13 unchanged"
    )
    return active.render_hit_hub(games_df, section_header, status_info, team_logo, h)
