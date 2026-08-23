"""MLB 1+ Hit UI V13.14 — Step 11 home-plate umpire + strike-zone context.

Presentation/context-only wrapper around verified V13.13. Hit Model V13 probability
math, Monte Carlo, candidate pool, lineup handling, ranking, calibration and
persistence remain unchanged.

Step 11 adds official MLB home-plate umpire context for each Top-5 card:
1) the current game's posted home-plate umpire from the official MLB game feed,
   with schedule/officials hydration as a fail-closed fallback,
2) date-cut recent games in which that same official worked home plate,
3) transparent box-score strikeout/walk environment over that sample,
4) called-strike share on taken pitches derived from official MLB pitch-by-pitch
   call descriptions/codes when available, and
5) a descriptive zone lean using explicit display-only thresholds.

The zone label is not an official umpire grade and does not enter Hit Model V13.
If MLB has not posted a plate umpire or the historical sample cannot be verified,
Step 11 says so rather than inventing data.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import math

import requests
import streamlit as st

import engine as hit_engine
import mlb_hit_hub_v1313 as prior

active = prior.active
core = prior.core
visual = prior.visual

UI_VERSION = "V13.14"
MLB_API = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "Mozilla/5.0 KyreSportsAI/1.0"}

# Cache-safe boundary: preserve verified Steps 1-10 exactly by function name.
_BASE_PICK_HTML = prior._pick_html_v1313


def _safe_id(value):
    try:
        return prior._safe_id(value)
    except Exception:
        try:
            x = int(float(value))
            return x if x > 0 else None
        except Exception:
            return None


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
            return int(hit_engine.season())
        except Exception:
            return 2026


def _official_record(entry):
    entry = entry or {}
    official = entry.get("official") or entry.get("person") or {}
    kind = str(entry.get("officialType") or entry.get("type") or "").strip()
    oid = _safe_id(official.get("id") or entry.get("id"))
    name = str(official.get("fullName") or official.get("name") or entry.get("fullName") or "").strip()
    return {"id": oid, "name": name, "type": kind}


def _is_home_plate(kind):
    text = str(kind or "").strip().lower().replace("-", " ")
    return "home plate" in text or text in {"home", "hp", "plate"}


@st.cache_data(ttl=600, show_spinner=False)
def _plate_umpire_for_game(game_pk):
    pk = _safe_id(game_pk)
    if pk is None:
        return {"available": False, "source": "NONE"}

    # Primary: official MLB live/game feed already used elsewhere by Hit V13.
    try:
        feed = hit_engine.game_feed(pk) or {}
        officials = (((feed.get("liveData") or {}).get("boxscore") or {}).get("officials") or [])
        for item in officials:
            row = _official_record(item)
            if row.get("id") and _is_home_plate(row.get("type")):
                return {"available": True, **row, "source": "MLB game feed"}
    except Exception:
        pass

    # Fallback: official schedule hydration. Never infer an umpire from crew order.
    try:
        r = requests.get(
            f"{MLB_API}/schedule",
            params={"sportId": 1, "gamePk": int(pk), "hydrate": "officials"},
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        for block in r.json().get("dates") or []:
            for game in block.get("games") or []:
                for item in game.get("officials") or []:
                    row = _official_record(item)
                    if row.get("id") and _is_home_plate(row.get("type")):
                        return {"available": True, **row, "source": "MLB schedule officials"}
    except Exception:
        pass

    return {"available": False, "source": "MLB official data"}


@st.cache_data(ttl=1800, show_spinner=False)
def _umpire_plate_game_pks(umpire_id, season_year, slate_day, max_games=5):
    uid = _safe_id(umpire_id)
    try:
        slate = datetime.strptime(str(slate_day)[:10], "%Y-%m-%d").date()
    except Exception:
        return []
    if uid is None:
        return []

    try:
        r = requests.get(
            f"{MLB_API}/jobs/umpires/games/{uid}",
            params={"season": int(season_year), "hydrate": "officials"},
            headers=_HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        payload = r.json() or {}
    except Exception:
        return []

    verified = []
    candidates = []
    for block in payload.get("dates") or []:
        block_day = str(block.get("date") or "")[:10]
        for game in block.get("games") or []:
            pk = _safe_id(game.get("gamePk"))
            day_text = str(game.get("gameDate") or block_day or "")[:10]
            try:
                gday = datetime.strptime(day_text, "%Y-%m-%d").date()
            except Exception:
                continue
            if pk is None or gday >= slate:
                continue
            candidates.append((gday, pk))
            for item in game.get("officials") or []:
                row = _official_record(item)
                if row.get("id") == uid and _is_home_plate(row.get("type")):
                    verified.append((gday, pk))
                    break

    # Some MLB schedule responses omit hydrated officials. In that case, verify
    # recent associated games through the official game feed, bounded to 16 checks.
    if len(verified) < max_games:
        seen = {pk for _, pk in verified}
        for gday, pk in sorted(candidates, reverse=True)[:16]:
            if pk in seen:
                continue
            current = _plate_umpire_for_game(pk)
            if current.get("available") and _safe_id(current.get("id")) == uid:
                verified.append((gday, pk))
                seen.add(pk)
            if len(verified) >= max_games:
                break

    verified = sorted(set(verified), reverse=True)
    return [int(pk) for _, pk in verified[:max_games]]


def _team_batting_stat(box, side, key):
    try:
        stats = (((box.get("teams") or {}).get(side) or {}).get("teamStats") or {}).get("batting") or {}
        return _num(stats.get(key), 0.0) or 0.0
    except Exception:
        return 0.0


def _pitch_call_counts(feed):
    called = balls = swings = total_pitches = 0
    plays = (((feed.get("liveData") or {}).get("plays") or {}).get("allPlays") or [])
    for play in plays:
        for event in (play or {}).get("playEvents") or []:
            if not (event or {}).get("isPitch"):
                continue
            total_pitches += 1
            details = (event or {}).get("details") or {}
            call = details.get("call") or {}
            code = str(call.get("code") or "").upper().strip()
            desc = str(call.get("description") or details.get("description") or "").lower().strip()

            if code == "C" or "called strike" in desc:
                called += 1
            elif code in {"B", "*B", "I", "P"} or desc in {"ball", "blocked ball", "automatic ball", "pitchout", "intentional ball"}:
                balls += 1
            elif code in {"S", "W", "T"} or "swinging strike" in desc or "missed bunt" in desc:
                swings += 1
    return {"called": called, "balls": balls, "swings": swings, "total": total_pitches}


@st.cache_data(ttl=1800, show_spinner=False)
def _umpire_tendency(umpire_id, season_year, slate_day):
    uid = _safe_id(umpire_id)
    if uid is None:
        return {"available": False}

    pks = _umpire_plate_game_pks(uid, int(season_year), str(slate_day), 5)
    if not pks:
        return {"available": False, "games": 0}

    games = 0
    strikeouts = walks = called = balls = swings = total_pitches = 0.0
    used_pks = []
    for pk in pks:
        try:
            feed = hit_engine.game_feed(int(pk)) or {}
            box = ((feed.get("liveData") or {}).get("boxscore") or {})
            if not box:
                continue
            games += 1
            used_pks.append(int(pk))
            strikeouts += _team_batting_stat(box, "away", "strikeOuts") + _team_batting_stat(box, "home", "strikeOuts")
            walks += _team_batting_stat(box, "away", "baseOnBalls") + _team_batting_stat(box, "home", "baseOnBalls")
            calls = _pitch_call_counts(feed)
            called += calls.get("called", 0)
            balls += calls.get("balls", 0)
            swings += calls.get("swings", 0)
            total_pitches += calls.get("total", 0)
        except Exception:
            continue

    if games <= 0:
        return {"available": False, "games": 0}

    taken = called + balls
    called_share = (called / taken) if taken > 0 else None
    k_per_game = strikeouts / games
    bb_per_game = walks / games

    # Display-only, explicit heuristic. It is intentionally not a proprietary or
    # official umpire grade and does not claim causal strike-zone impact.
    if games < 3 or taken < 250:
        lean = "SAMPLE LIMITED"
    elif called_share is not None and called_share >= 0.325:
        lean = "PITCHER-LEAN WATCH"
    elif called_share is not None and called_share <= 0.285:
        lean = "HITTER-LEAN WATCH"
    else:
        lean = "NEAR NEUTRAL"

    return {
        "available": True,
        "games": games,
        "game_pks": used_pks,
        "strikeouts": strikeouts,
        "walks": walks,
        "k_per_game": k_per_game,
        "bb_per_game": bb_per_game,
        "called_strikes": int(called),
        "balls": int(balls),
        "swings": int(swings),
        "taken_pitches": int(taken),
        "total_pitches": int(total_pitches),
        "called_strike_share": called_share,
        "lean": lean,
    }


def _umpire_strip(result):
    pk = _safe_id((result or {}).get("game_pk"))
    ump = _plate_umpire_for_game(pk)
    if not ump.get("available"):
        return (
            '<div class="hit1314-context">'
            '<div class="hit1314-head">STEP 11 • HOME-PLATE UMPIRE + STRIKE-ZONE CONTEXT</div>'
            '<div class="hit1314-note">MLB has not posted a verifiable home-plate umpire for this game yet. No umpire or zone tendency was inferred; Hit Model V13 is unchanged.</div>'
            '</div>'
        )

    uid = _safe_id(ump.get("id"))
    name = str(ump.get("name") or "Home-plate umpire")
    tendency = _umpire_tendency(uid, _season_from_day(), _selected_day())

    if not tendency.get("available"):
        return (
            '<div class="hit1314-context">'
            '<div class="hit1314-head">STEP 11 • HOME-PLATE UMPIRE + STRIKE-ZONE CONTEXT</div>'
            f'<div class="hit1314-main"><b>{escape(name)}</b> • Home Plate • {escape(str(ump.get("source") or "MLB official data"))}</div>'
            '<div class="hit1314-note">Official date-cut plate-game tendency sample unavailable. No K/BB or called-strike tendency was invented; Hit Model V13 is unchanged.</div>'
            '</div>'
        )

    games = int(_num(tendency.get("games"), 0) or 0)
    called_share = _num(tendency.get("called_strike_share"), None)
    taken = int(_num(tendency.get("taken_pitches"), 0) or 0)
    kpg = _num(tendency.get("k_per_game"), None)
    bbpg = _num(tendency.get("bb_per_game"), None)
    lean = str(tendency.get("lean") or "UNAVAILABLE")

    called_text = "—" if called_share is None else f"{called_share * 100.0:.1f}%"
    k_text = "—" if kpg is None else f"{kpg:.1f} K/game"
    bb_text = "—" if bbpg is None else f"{bbpg:.1f} BB/game"

    return (
        '<div class="hit1314-context">'
        '<div class="hit1314-head">STEP 11 • HOME-PLATE UMPIRE + STRIKE-ZONE CONTEXT</div>'
        f'<div class="hit1314-main"><b>{escape(name)}</b> • Home Plate • {escape(str(ump.get("source") or "MLB official data"))}</div>'
        f'<div class="hit1314-sub"><b>Date-cut plate sample</b> • L{games} home-plate game(s) • {escape(k_text)} • {escape(bb_text)}</div>'
        f'<div class="hit1314-zone"><b>{escape(lean)}</b> • Called-strike share on taken pitches {escape(called_text)} • {taken:,} taken-pitch calls</div>'
        '<div class="hit1314-note">Called-strike share is derived from official MLB pitch-by-pitch calls in verified prior home-plate games. Zone lean uses explicit display-only thresholds (≥32.5% pitcher-lean, ≤28.5% hitter-lean; otherwise neutral) and is not an official umpire grade or a V13 model input.</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hit1314-context{margin:7px 0 5px;padding:9px 10px;border:1px solid #51606f;background:linear-gradient(145deg,#111820,#0a1018);border-radius:12px}
.hit1314-head{font-size:.44rem;letter-spacing:.08em;color:#9fd8ff;font-weight:950;text-transform:uppercase}
.hit1314-main{font-size:.53rem;color:#edf4fa;line-height:1.48;margin-top:3px}.hit1314-main b{color:#ffffff}
.hit1314-sub{font-size:.49rem;color:#c4d0da;line-height:1.46;margin-top:3px}.hit1314-sub b{color:#d9ecfa}
.hit1314-zone{font-size:.50rem;color:#cbd6df;line-height:1.46;margin-top:4px}.hit1314-zone b{color:#ffd36a}
.hit1314-note{font-size:.40rem;color:#7d8994;line-height:1.4;margin-top:4px}
</style>
"""

if "hit1314-context" not in core.HIT_CSS:
    core.HIT_CSS = core.HIT_CSS + _EXTRA_CSS


def _pick_html_v1314(result, rank):
    html = _BASE_PICK_HTML(result, rank)
    if not isinstance(html, str):
        html = str(html or "")
    try:
        strip = _umpire_strip(result if isinstance(result, dict) else {})
    except Exception:
        strip = (
            '<div class="hit1314-context">'
            '<div class="hit1314-head">STEP 11 • HOME-PLATE UMPIRE + STRIKE-ZONE CONTEXT</div>'
            '<div class="hit1314-note">Step-11 umpire context unavailable for this card. V13 projection and ranking remain unaffected.</div>'
            '</div>'
        )
    marker = '<div class="hit-pick-prob">'
    if marker in html:
        return html.replace(marker, strip + marker, 1)
    return html + strip


active._pick_html = _pick_html_v1314


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.caption(
        "🧑‍⚖️ Hit UI V13.14 • Step 11 official home-plate umpire + date-cut strike-zone context ACTIVE • "
        "display/context only • Hit Model V13 unchanged"
    )
    return active.render_hit_hub(games_df, section_header, status_info, team_logo, h)
