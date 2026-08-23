"""MLB 1+ Hit UI V13.12 — Step 9 bullpen-arm workload + handedness context.

Presentation/context-only wrapper around verified V13.11. Hit Model V13 probability
math, Monte Carlo, candidate pool, lineup handling, ranking, calibration and
persistence remain unchanged.

Step 9 adds official MLB opponent-bullpen context behind the verified starter:
1) current active-roster relief staff using the same reliever eligibility boundary as
   the frozen V13 bullpen helper,
2) individual high-use reliever hand / ERA / WHIP / K9 season context,
3) official box-score pitch counts and appearances over the three days before the
   selected slate, with a transparent workload-watch heuristic,
4) active bullpen right/left-handed innings mix, and
5) the batter's official MLB season OPS split vs RHP/LHP, summarized against that
   bullpen hand mix as a descriptive platoon lean.

No reliever is declared officially available/unavailable. Workload labels are
presentation heuristics only, and missing data are never invented. No Step-9 field
is passed into prescreen, deep_scan, model_inputs, Monte Carlo, confidence,
calibration or ranking.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from html import escape
import math

import requests
import streamlit as st

import engine as hit_engine
import mlb_hit_hub_v1311 as prior

active = prior.active
core = prior.core
visual = prior.visual

UI_VERSION = "V13.12"
MLB_API = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "Mozilla/5.0 KyreSportsAI/1.0"}

# Cache-safe boundary: preserve verified Steps 1-8 exactly.
_BASE_PICK_HTML = prior._pick_html_v1311


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
    try:
        return int(prior._season_from_day())
    except Exception:
        day = _selected_day()
        try:
            return datetime.strptime(day, "%Y-%m-%d").year
        except Exception:
            return 2026


def _fmt(value, digits=2):
    x = _num(value, None)
    return "—" if x is None else f"{x:.{digits}f}"


def _avg(value):
    x = _num(value, None)
    return "—" if x is None else f"{x:.3f}".lstrip("0")


def _pct(value, digits=1):
    x = _num(value, None)
    return "—" if x is None else f"{x * 100.0:.{digits}f}%"


@st.cache_data(ttl=1200, show_spinner=False)
def _person_bat_side(player_id):
    pid = _safe_id(player_id)
    if pid is None:
        return "?"
    try:
        r = requests.get(f"{MLB_API}/people/{pid}", headers=_HEADERS, timeout=10)
        r.raise_for_status()
        person = (r.json().get("people") or [{}])[0]
        return str(((person.get("batSide") or {}).get("code") or "?")).upper()
    except Exception:
        return "?"


@st.cache_data(ttl=1200, show_spinner=False)
def _hitting_split(player_id, pitcher_hand, season_year):
    pid = _safe_id(player_id)
    hand = str(pitcher_hand or "").upper()
    if pid is None or hand not in {"R", "L"}:
        return {}
    sit = "vr" if hand == "R" else "vl"
    try:
        r = requests.get(
            f"{MLB_API}/people/{pid}/stats",
            params={
                "stats": "statSplits",
                "group": "hitting",
                "gameType": "R",
                "sitCodes": sit,
                "season": int(season_year),
            },
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        for group in r.json().get("stats") or []:
            for split in group.get("splits") or []:
                stat = (split or {}).get("stat") or {}
                if stat:
                    return {
                        "ab": int(_num(stat.get("atBats"), 0) or 0),
                        "avg": _num(stat.get("avg"), None),
                        "ops": _num(stat.get("ops"), None),
                    }
    except Exception:
        pass
    return {}


def _game_day(game):
    text = str((game or {}).get("gameDate") or "")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except Exception:
            return None


@st.cache_data(ttl=600, show_spinner=False)
def _active_relief_staff(team_id, starter_id, slate_day):
    """Active relief staff + date-cut individual workload, display only."""
    tid = _safe_id(team_id)
    sid = _safe_id(starter_id)
    try:
        slate = datetime.strptime(str(slate_day)[:10], "%Y-%m-%d").date()
    except Exception:
        return {"available": False}
    if tid is None:
        return {"available": False}

    try:
        r = requests.get(
            f"{MLB_API}/teams/{tid}/roster",
            params={"rosterType": "active"},
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        roster = r.json().get("roster") or []
    except Exception:
        return {"available": False}

    staff = []
    for entry in roster:
        pos = str(((entry.get("position") or {}).get("abbreviation") or "")).upper()
        pid = _safe_id(((entry.get("person") or {}).get("id")))
        if pos != "P" or pid is None or pid == sid:
            continue
        try:
            p = hit_engine.pitcher_stats(pid) or {}
        except Exception:
            continue
        innings = _num(p.get("true_innings"), 0) or 0
        games = int(_num(p.get("games"), 0) or 0)
        starts = int(_num(p.get("games_started"), 0) or 0)
        if innings <= 0 or games <= 0:
            continue
        # Match the native V13 bullpen reliever eligibility contract.
        if not (starts <= 3 or starts / max(games, 1) <= 0.35):
            continue
        staff.append({
            "id": pid,
            "name": str(p.get("name") or (entry.get("person") or {}).get("fullName") or f"Pitcher {pid}"),
            "hand": str(p.get("hand") or "?").upper(),
            "era": _num(p.get("era"), None),
            "whip": _num(p.get("whip"), None),
            "k9": _num(p.get("k9"), None),
            "games": games,
            "innings": innings,
            "p1": 0,
            "p2": 0,
            "p3": 0,
            "apps1": 0,
            "apps2": 0,
            "apps3": 0,
            "ip3": 0.0,
        })

    if not staff:
        return {"available": False}

    by_id = {p["id"]: p for p in staff}
    start = slate - timedelta(days=3)
    end = slate - timedelta(days=1)
    try:
        r = requests.get(
            f"{MLB_API}/schedule",
            params={
                "sportId": 1,
                "teamId": tid,
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
            },
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        games = []
        for block in r.json().get("dates") or []:
            games.extend(block.get("games") or [])
    except Exception:
        games = []

    for game in games:
        status = game.get("status") or {}
        detailed = str(status.get("detailedState") or "").lower()
        abstract = str(status.get("abstractGameState") or "").lower()
        if abstract != "final" and not any(x in detailed for x in ("final", "game over", "completed")):
            continue
        gday = _game_day(game)
        if gday is None:
            continue
        days_back = (slate - gday).days
        if days_back < 1 or days_back > 3:
            continue
        away_id = _safe_id((((game.get("teams") or {}).get("away") or {}).get("team") or {}).get("id"))
        home_id = _safe_id((((game.get("teams") or {}).get("home") or {}).get("team") or {}).get("id"))
        side = "away" if away_id == tid else "home" if home_id == tid else None
        pk = _safe_id(game.get("gamePk"))
        if side is None or pk is None:
            continue
        try:
            feed = hit_engine.game_feed(pk) or {}
            team_box = (((feed.get("liveData") or {}).get("boxscore") or {}).get("teams") or {}).get(side) or {}
            players = team_box.get("players") or {}
            for pid, profile in by_id.items():
                stat = (((players.get(f"ID{pid}") or {}).get("stats") or {}).get("pitching") or {})
                pitches = int(_num(stat.get("pitchesThrown"), 0) or 0)
                ip = 0.0
                try:
                    ip = float(hit_engine.ipfloat(stat.get("inningsPitched")))
                except Exception:
                    ip = 0.0
                if pitches <= 0 and ip <= 0:
                    continue
                profile["p3"] += pitches
                profile["apps3"] += 1
                profile["ip3"] += ip
                if days_back <= 2:
                    profile["p2"] += pitches
                    profile["apps2"] += 1
                if days_back == 1:
                    profile["p1"] += pitches
                    profile["apps1"] += 1
        except Exception:
            continue

    right_ip = sum(p["innings"] for p in staff if p["hand"] == "R")
    left_ip = sum(p["innings"] for p in staff if p["hand"] == "L")
    known_ip = right_ip + left_ip
    right_share = right_ip / known_ip if known_ip > 0 else None
    left_share = left_ip / known_ip if known_ip > 0 else None

    for p in staff:
        if p["p1"] >= 30 or p["p2"] >= 45 or p["apps2"] >= 2:
            p["workload"] = "WORKLOAD WATCH"
        elif p["p1"] > 0:
            p["workload"] = "USED YESTERDAY"
        elif p["p2"] > 0:
            p["workload"] = "USED LAST 2D"
        else:
            p["workload"] = "RESTED 3D"

    # "High-use" is intentionally based on season appearances, not a claim about
    # manager intent or official game availability.
    staff.sort(key=lambda p: (p.get("games", 0), p.get("innings", 0.0)), reverse=True)
    shown = staff[:4]

    return {
        "available": True,
        "count": len(staff),
        "right_count": sum(1 for p in staff if p["hand"] == "R"),
        "left_count": sum(1 for p in staff if p["hand"] == "L"),
        "right_share": right_share,
        "left_share": left_share,
        "clear_count": sum(1 for p in staff if p.get("workload") != "WORKLOAD WATCH"),
        "watch_count": sum(1 for p in staff if p.get("workload") == "WORKLOAD WATCH"),
        "shown": shown,
        "window": f"{start.isoformat()} to {end.isoformat()}",
    }


def _platoon_lean(result, staff):
    pid = _safe_id((result or {}).get("player_id"))
    if pid is None or not staff.get("available"):
        return {"label": "UNAVAILABLE"}

    year = _season_from_day()
    side = _person_bat_side(pid)
    vr = _hitting_split(pid, "R", year)
    vl = _hitting_split(pid, "L", year)
    rshare = _num(staff.get("right_share"), None)
    lshare = _num(staff.get("left_share"), None)

    overall_ops = None
    try:
        overall_ops = _num((hit_engine.hitter_stats(pid) or {}).get("ops"), None)
    except Exception:
        overall_ops = None

    rops = _num(vr.get("ops"), None)
    lops = _num(vl.get("ops"), None)
    rab = int(_num(vr.get("ab"), 0) or 0)
    lab = int(_num(vl.get("ab"), 0) or 0)

    mix_ops = None
    if None not in (rshare, lshare, rops, lops):
        mix_ops = rshare * rops + lshare * lops

    sample_limited = rab < 20 or lab < 20
    if mix_ops is None or overall_ops is None:
        label = "SAMPLE / MIX LIMITED"
    else:
        delta = mix_ops - overall_ops
        if sample_limited:
            label = "SAMPLE LIMITED"
        elif delta >= 0.050:
            label = "FAVORABLE LEAN"
        elif delta <= -0.050:
            label = "TOUGH LEAN"
        else:
            label = "NEAR NEUTRAL"

    return {
        "label": label,
        "bat_side": side,
        "r_ops": rops,
        "l_ops": lops,
        "r_ab": rab,
        "l_ab": lab,
        "mix_ops": mix_ops,
        "overall_ops": overall_ops,
        "sample_limited": sample_limited,
    }


def _bullpen_arm_strip(result):
    team_id = _safe_id((result or {}).get("opponent_team_id"))
    starter_id = _safe_id((result or {}).get("starter_id"))
    staff = _active_relief_staff(team_id, starter_id, _selected_day())
    opponent = str((result or {}).get("opponent") or "Opponent")

    if not staff.get("available"):
        return (
            '<div class="hit1312-context">'
            '<div class="hit1312-head">STEP 9 • BULLPEN ARMS + HANDEDNESS PRESSURE</div>'
            f'<div class="hit1312-note">Active relief-arm detail unavailable for {escape(opponent)}. '
            'No availability or platoon value was inferred; V13 ranking is unaffected.</div>'
            '</div>'
        )

    lean = _platoon_lean(result, staff)
    mix_bits = [
        f"{int(staff.get('count') or 0)} active relief arms",
        f"RHP {int(staff.get('right_count') or 0)}",
        f"LHP {int(staff.get('left_count') or 0)}",
    ]
    if _num(staff.get("right_share"), None) is not None:
        mix_bits.append(f"R-IP share {_pct(staff.get('right_share'))}")
    if _num(staff.get("left_share"), None) is not None:
        mix_bits.append(f"L-IP share {_pct(staff.get('left_share'))}")
    mix_text = " • ".join(mix_bits)

    workload_text = (
        f"Workload screen: {int(staff.get('clear_count') or 0)} clear • "
        f"{int(staff.get('watch_count') or 0)} watch"
    )

    split_bits = [f"Batter {escape(str(lean.get('bat_side') or '?'))}"]
    if _num(lean.get("r_ops"), None) is not None:
        split_bits.append(f"vs RHP OPS {_avg(lean.get('r_ops'))} ({int(lean.get('r_ab') or 0)} AB)")
    if _num(lean.get("l_ops"), None) is not None:
        split_bits.append(f"vs LHP OPS {_avg(lean.get('l_ops'))} ({int(lean.get('l_ab') or 0)} AB)")
    if _num(lean.get("mix_ops"), None) is not None:
        split_bits.append(f"hand-mix OPS {_avg(lean.get('mix_ops'))}")
    split_text = " • ".join(split_bits)

    arms = []
    for p in staff.get("shown") or []:
        stat_bits = [escape(str(p.get("hand") or "?")) + "HP"]
        if _num(p.get("era"), None) is not None:
            stat_bits.append(f"ERA {_fmt(p.get('era'), 2)}")
        if _num(p.get("whip"), None) is not None:
            stat_bits.append(f"WHIP {_fmt(p.get('whip'), 2)}")
        if _num(p.get("k9"), None) is not None:
            stat_bits.append(f"K/9 {_fmt(p.get('k9'), 1)}")
        stat_bits.append(f"3D {int(p.get('p3') or 0)} pitches/{int(p.get('apps3') or 0)} app")
        arms.append(
            '<div class="hit1312-arm">'
            f'<b>{escape(str(p.get("name") or "Reliever"))}</b> • {" • ".join(stat_bits)} '
            f'<span>{escape(str(p.get("workload") or "—"))}</span>'
            '</div>'
        )

    arms_html = "".join(arms) if arms else '<div class="hit1312-note">No high-use relief arms could be displayed.</div>'
    label = escape(str(lean.get("label") or "UNAVAILABLE"))

    return (
        '<div class="hit1312-context">'
        '<div class="hit1312-head">STEP 9 • BULLPEN ARMS + HANDEDNESS PRESSURE</div>'
        f'<div class="hit1312-main"><b>{escape(opponent)}</b> • {escape(mix_text)}</div>'
        f'<div class="hit1312-work">{escape(workload_text)}</div>'
        f'<div class="hit1312-split"><b>{label}</b> • {split_text}</div>'
        '<div class="hit1312-divider"></div>'
        '<div class="hit1312-label">HIGH-USE ACTIVE RELIEVERS • OFFICIAL MLB ROSTER + 3-DAY BOX-SCORE WORKLOAD</div>'
        f'{arms_html}'
        '<div class="hit1312-note">Workload labels are transparent heuristics, not official availability declarations. '
        'The platoon lean compares official batter OPS splits with the active bullpen hand mix only; it does not change Hit Model V13.</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hit1312-context{margin:7px 0 5px;padding:9px 10px;border:1px solid #48586d;background:linear-gradient(145deg,#101720,#09131b);border-radius:12px}
.hit1312-head{font-size:.44rem;letter-spacing:.08em;color:#9ec8f3;font-weight:950;text-transform:uppercase}
.hit1312-main{font-size:.54rem;color:#e7eef6;line-height:1.5;margin-top:3px}.hit1312-main b{color:#d7eaff}
.hit1312-work{font-size:.49rem;color:#c9d4df;line-height:1.45;margin-top:2px}
.hit1312-split{font-size:.50rem;color:#d9e4ee;line-height:1.5;margin-top:3px}.hit1312-split b{color:#8fd4ff}
.hit1312-divider{height:1px;background:#253a4c;margin:6px 0 4px}
.hit1312-label{font-size:.40rem;color:#6fa3cf;letter-spacing:.06em;font-weight:900;margin-bottom:2px}
.hit1312-arm{font-size:.47rem;color:#cbd7e2;line-height:1.45;padding:3px 0;border-top:1px solid #1d2d3b}.hit1312-arm b{color:#edf6ff}.hit1312-arm span{color:#d9c67d;font-weight:800}
.hit1312-note{font-size:.41rem;color:#738391;line-height:1.4;margin-top:4px}
</style>
"""

if "hit1312-context" not in core.HIT_CSS:
    core.HIT_CSS = core.HIT_CSS + _EXTRA_CSS


def _pick_html_v1312(result, rank):
    html = _BASE_PICK_HTML(result, rank)
    if not isinstance(html, str):
        html = str(html or "")
    try:
        strip = _bullpen_arm_strip(result if isinstance(result, dict) else {})
    except Exception:
        strip = (
            '<div class="hit1312-context">'
            '<div class="hit1312-head">STEP 9 • BULLPEN ARMS + HANDEDNESS PRESSURE</div>'
            '<div class="hit1312-note">Step-9 context unavailable for this card. V13 projection and ranking remain unaffected.</div>'
            '</div>'
        )
    marker = '<div class="hit-pick-prob">'
    if marker in html:
        return html.replace(marker, strip + marker, 1)
    return html + strip


active._pick_html = _pick_html_v1312


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.caption(
        "🧩 Hit UI V13.12 • Step 9 active bullpen arms + 3-day workload + handedness pressure ACTIVE • "
        "official MLB roster/box scores • display/context only • Hit Model V13 unchanged"
    )
    return active.render_hit_hub(games_df, section_header, status_info, team_logo, h)
