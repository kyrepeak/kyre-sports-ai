"""MLB 1+ Hit UI V13.10.2 — Step 7 cache-safe recent form/contact repair.

Presentation/context-only wrapper around verified V13.9. This repair fixes a hot-
reload binding bug: Step 7 now binds directly to V13.9's verified card renderer by
function name instead of capturing the mutable active._pick_html pointer, which can
still reference a stale V13.10 renderer after Streamlit hot deploys. Step-7 numeric
conversions remain hardened and the Step-7 context itself fails closed. Hit Model
V13 probability math, Monte Carlo, candidate pool, lineup handling, ranking,
calibration and persistence remain unchanged.
"""
from __future__ import annotations

from html import escape
import math

import requests
import streamlit as st

import engine as hit_engine
import mlb_hit_hub_v139 as prior

active = prior.active
core = prior.core
visual = prior.visual

UI_VERSION = "V13.10.2"
MLB_API = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "Mozilla/5.0 KyreSportsAI/1.0"}

# CACHE-SAFE BOUNDARY: bind to the verified Step-6 renderer explicitly. Do not
# capture active._pick_html here; that mutable module-global can retain a stale
# Step-7 renderer across Streamlit hot deploys in a long-lived Python process.
_BASE_PICK_HTML = prior._pick_html_v139


def _safe_id(value):
    return prior._safe_id(value)


def _num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _int(value, default=0):
    x = _num(value, None)
    if x is None:
        return default
    try:
        return int(x)
    except (TypeError, ValueError, OverflowError):
        return default


def _selected_day():
    try:
        day = str(prior._selected_day() or "")[:10]
    except Exception:
        day = ""
    return day


def _avg(value):
    x = _num(value, None)
    return "—" if x is None else f"{x:.3f}".lstrip("0")


def _pct(value, digits=1):
    x = _num(value, None)
    return "—" if x is None else f"{x * 100.0:.{digits}f}%"


@st.cache_data(ttl=600, show_spinner=False)
def _official_recent_log(player_id, selected_day):
    """Return official MLB game-log rows strictly before selected_day."""
    pid = _safe_id(player_id)
    day = str(selected_day or "")[:10]
    if pid is None or len(day) != 10:
        return []
    try:
        season = int(day[:4])
        r = requests.get(
            f"{MLB_API}/people/{pid}/stats",
            params={"stats": "gameLog", "group": "hitting", "season": season},
            headers=_HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        groups = r.json().get("stats") or []
        splits = (groups[0].get("splits") or []) if groups and isinstance(groups[0], dict) else []
        out = []
        for sp in splits:
            if not isinstance(sp, dict):
                continue
            game_day = str(sp.get("date") or "")[:10]
            if len(game_day) != 10 or game_day >= day:
                continue
            stat = sp.get("stat") or {}
            if not isinstance(stat, dict):
                continue
            pa_raw = _num(stat.get("plateAppearances"), None)
            out.append({
                "date": game_day,
                "pa": _int(pa_raw, 0) if pa_raw is not None else None,
                "ab": _int(stat.get("atBats"), 0),
                "h": _int(stat.get("hits"), 0),
                "hr": _int(stat.get("homeRuns"), 0),
                "bb": _int(stat.get("baseOnBalls"), 0),
                "so": _int(stat.get("strikeOuts"), 0),
            })
        out.sort(key=lambda row: str(row.get("date") or ""))
        return out
    except Exception:
        return []


def _window(rows, n):
    sample = list(rows or [])[-max(1, int(n)):]
    if not sample:
        return {"available": False, "games": 0}
    games = len(sample)
    ab = sum(_int(row.get("ab"), 0) for row in sample if isinstance(row, dict))
    hits = sum(_int(row.get("h"), 0) for row in sample if isinstance(row, dict))
    so = sum(_int(row.get("so"), 0) for row in sample if isinstance(row, dict))
    pa_values = [row.get("pa") for row in sample if isinstance(row, dict)]
    pa_complete = len(pa_values) == games and all(_num(v, None) is not None for v in pa_values)
    pa = sum(_int(v, 0) for v in pa_values) if pa_complete else 0
    return {
        "available": True,
        "games": games,
        "ab": ab,
        "hits": hits,
        "avg": (hits / ab) if ab > 0 else None,
        "hit_games": sum(1 for row in sample if isinstance(row, dict) and _int(row.get("h"), 0) >= 1),
        "multi_hit_games": sum(1 for row in sample if isinstance(row, dict) and _int(row.get("h"), 0) >= 2),
        "so": so,
        "pa": pa if pa > 0 else None,
        "k_rate": (so / pa) if pa > 0 else None,
        "start": str(sample[0].get("date") or "") if isinstance(sample[0], dict) else "",
        "end": str(sample[-1].get("date") or "") if isinstance(sample[-1], dict) else "",
    }


def _season_contact(player_id):
    pid = _safe_id(player_id)
    if pid is None:
        return {"available": False}
    try:
        savant = hit_engine.statcast(pid) or {}
        if not isinstance(savant, dict):
            savant = {}
    except Exception:
        savant = {}
    try:
        season = hit_engine.hitter_stats(pid) or {}
        if not isinstance(season, dict):
            season = {}
    except Exception:
        season = {}

    pa = _num(season.get("plate_appearances"), None)
    so = _num(season.get("strikeouts"), None)
    season_k = (so / pa) if pa is not None and pa > 0 and so is not None else None
    return {
        "available": bool(savant or season),
        "avg": _num(season.get("avg"), None),
        "season_k_rate": season_k,
        "xba": _num(savant.get("xba"), None),
        "xslg": _num(savant.get("xslg"), None),
        "avg_ev": _num(savant.get("avg_ev"), None),
        "hard_hit_rate": _num(savant.get("hard_hit_rate"), None),
        "barrel_rate": _num(savant.get("barrel_rate"), None),
        "bbe": _int(savant.get("bbe"), 0),
    }


def _form_line(label, window):
    if not window.get("available"):
        return f"<b>{escape(str(label))}</b> • unavailable"
    games = max(0, _int(window.get("games"), 0))
    hit_games = max(0, _int(window.get("hit_games"), 0))
    multi = max(0, _int(window.get("multi_hit_games"), 0))
    frequency = (hit_games / games) if games > 0 else None
    bits = [
        f"{_int(window.get('hits'), 0)}-for-{_int(window.get('ab'), 0)} ({_avg(window.get('avg'))})",
        f"1+ hit {hit_games}/{games} ({_pct(frequency)})",
        f"2+ hit {multi}/{games}",
    ]
    if _num(window.get("k_rate"), None) is not None:
        bits.append(f"K% {_pct(window.get('k_rate'))}")
    return f"<b>{escape(str(label))}</b> • " + " • ".join(bits)


def _contact_line(contact):
    if not contact.get("available"):
        return "Baseball Savant season contact snapshot unavailable"
    bits = []
    xba = _num(contact.get("xba"), None)
    xslg = _num(contact.get("xslg"), None)
    avg_ev = _num(contact.get("avg_ev"), None)
    hard_hit = _num(contact.get("hard_hit_rate"), None)
    barrel = _num(contact.get("barrel_rate"), None)
    bbe = _int(contact.get("bbe"), 0)
    if xba is not None:
        bits.append(f"xBA {_avg(xba)}")
    if xslg is not None:
        bits.append(f"xSLG {_avg(xslg)}")
    if avg_ev is not None:
        bits.append(f"Avg EV {avg_ev:.1f} mph")
    if hard_hit is not None:
        bits.append(f"Hard-Hit {_pct(hard_hit)}")
    if barrel is not None:
        bits.append(f"Barrel {_pct(barrel)}")
    if bbe > 0:
        bits.append(f"{bbe} BBE")
    return " • ".join(bits) if bits else "Baseball Savant season contact snapshot unavailable"


def _recent_form_strip(result):
    day = _selected_day()
    pid = _safe_id((result or {}).get("player_id"))
    rows = _official_recent_log(pid, day)
    l5 = _window(rows, 5)
    l10 = _window(rows, 10)
    contact = _season_contact(pid)

    comparison = []
    if _num(l10.get("k_rate"), None) is not None:
        comparison.append(f"L10 K% {_pct(l10.get('k_rate'))}")
    if _num(contact.get("season_k_rate"), None) is not None:
        comparison.append(f"Season K% {_pct(contact.get('season_k_rate'))}")
    if _num(contact.get("avg"), None) is not None:
        comparison.append(f"Season AVG {_avg(contact.get('avg'))}")
    comparison_text = " • ".join(comparison) if comparison else "Recent-vs-season comparison unavailable"

    date_note = f"Official MLB game logs date-cut before {day or 'selected slate'}."
    if l10.get("available") and l10.get("start") and l10.get("end"):
        date_note += f" L10 window {l10.get('start')} to {l10.get('end')}."
    date_note += " Savant contact metrics are a season snapshot; display only."

    return (
        '<div class="hit13102-context">'
        '<div class="hit13102-head">STEP 7 • RECENT HITTING FORM + CONTACT QUALITY</div>'
        f'<div class="hit13102-form">{_form_line("Last 5", l5)}</div>'
        f'<div class="hit13102-form">{_form_line("Last 10", l10)}</div>'
        '<div class="hit13102-divider"></div>'
        '<div class="hit13102-kicker">CONTACT QUALITY • BASEBALL SAVANT</div>'
        f'<div class="hit13102-contact">{escape(str(_contact_line(contact)))}</div>'
        f'<div class="hit13102-compare">{escape(str(comparison_text))}</div>'
        f'<div class="hit13102-note">{escape(str(date_note))}</div>'
        '</div>'
    )


def _unavailable_strip():
    return (
        '<div class="hit13102-context">'
        '<div class="hit13102-head">STEP 7 • RECENT HITTING FORM + CONTACT QUALITY</div>'
        '<div class="hit13102-note">Recent-form/contact context unavailable for this card. '
        'The verified V13 projection and ranking remain unaffected.</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hit13102-context{margin:7px 0 5px;padding:9px 10px;border:1px solid #31566a;background:linear-gradient(145deg,#0b1920,#09131b);border-radius:12px}
.hit13102-head{font-size:.44rem;letter-spacing:.08em;color:#8ee8d6;font-weight:950;text-transform:uppercase}
.hit13102-form{font-size:.52rem;color:#d5e8ee;line-height:1.5;margin-top:3px}.hit13102-form b{color:#f3fbff}
.hit13102-divider{height:1px;background:#23434f;margin:6px 0 4px}
.hit13102-kicker{font-size:.42rem;letter-spacing:.07em;color:#7ec7f2;font-weight:900;text-transform:uppercase}
.hit13102-contact{font-size:.51rem;color:#c9d8e5;line-height:1.5;margin-top:3px}
.hit13102-compare{font-size:.48rem;color:#aac2d2;line-height:1.45;margin-top:3px}
.hit13102-note{font-size:.42rem;color:#728899;line-height:1.4;margin-top:4px}
</style>
"""

if "hit13102-context" not in core.HIT_CSS:
    core.HIT_CSS = core.HIT_CSS + _EXTRA_CSS


def _pick_html_v13102(result, rank):
    """Verified Step 6 + cache-safe, fail-closed Step 7 display injection."""
    html = _BASE_PICK_HTML(result, rank)
    if not isinstance(html, str):
        html = str(html or "")
    try:
        strip = _recent_form_strip(result if isinstance(result, dict) else {})
    except Exception:
        strip = _unavailable_strip()
    marker = '<div class="hit-pick-prob">'
    if marker in html:
        return html.replace(marker, strip + marker, 1)
    return html + strip


active._pick_html = _pick_html_v13102


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.caption(
        "🧰 Hit UI V13.10.2 • Step 7 cache-safe recent-form/contact repair ACTIVE • "
        "explicit V13.9 renderer binding • date-cut MLB logs • Savant season contact • Hit Model V13 unchanged"
    )
    return active.render_hit_hub(games_df, section_header, status_info, team_logo, h)
