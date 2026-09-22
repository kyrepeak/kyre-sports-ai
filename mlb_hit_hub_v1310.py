"""MLB 1+ Hit UI V13.10 — Step 7 recent hitting form + contact-quality context.

Presentation/context-only wrapper around verified V13.9. Hit Model V13 probability
math, Monte Carlo, candidate pool, lineup handling, ranking, calibration and
persistence remain unchanged.

Step 7 adds display-only context for each Top-5 hitter:
1) official MLB date-cut Last-5 and Last-10 game-log hitting form,
2) 1+ hit-game frequency and 2+ hit-game frequency,
3) recent AVG and strikeout rate from official game logs,
4) Baseball Savant season xBA/xSLG, average exit velocity, hard-hit rate and
   barrel rate when available, and
5) an explicit recent-vs-season strikeout comparison when both samples exist.

The recent game-log window excludes the selected slate date and later dates so a
current/live result cannot leak into the display. Savant contact metrics are labeled
as a season snapshot. No Step-7 field is passed into prescreen, deep_scan,
model_inputs, Monte Carlo, confidence, calibration or ranking.
"""
from __future__ import annotations

from html import escape

import requests
import streamlit as st

import engine as hit_engine
import mlb_hit_hub_v139 as prior

active = prior.active
core = prior.core
visual = prior.visual

UI_VERSION = "V13.10"
MLB_API = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "Mozilla/5.0 KyreSportsAI/1.0"}

# Preserve verified Steps 1-6 exactly; Step 7 injects one additional display block.
_BASE_PICK_HTML = active._pick_html


def _safe_id(value):
    return prior._safe_id(value)


def _sf(value, default=None):
    return prior._sf(value, default)


def _selected_day():
    return prior._selected_day()


def _fmt_avg(value):
    x = _sf(value, None)
    if x is None:
        return "—"
    return f"{x:.3f}".lstrip("0")


def _fmt_pct(value, digits=1):
    x = _sf(value, None)
    if x is None:
        return "—"
    return f"{x * 100.0:.{digits}f}%"


@st.cache_data(ttl=600, show_spinner=False)
def _official_recent_log(player_id, selected_day):
    """Official MLB hitting game log strictly before selected_day."""
    pid = _safe_id(player_id)
    day = str(selected_day or "")
    if pid is None or len(day) < 10:
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
        splits = (groups[0].get("splits") or []) if groups else []
        out = []
        for sp in splits:
            game_day = str(sp.get("date") or "")[:10]
            # Fail closed on undated rows and exclude the slate date itself so no
            # live/current-game result can enter the recent-form display.
            if not game_day or game_day >= day:
                continue
            stat = sp.get("stat") or {}
            pa = _sf(stat.get("plateAppearances"), None)
            ab = int(_sf(stat.get("atBats"), 0) or 0)
            hits = int(_sf(stat.get("hits"), 0) or 0)
            out.append(
                {
                    "date": game_day,
                    "pa": int(pa) if pa is not None else None,
                    "ab": ab,
                    "h": hits,
                    "hr": int(_sf(stat.get("homeRuns"), 0) or 0),
                    "bb": int(_sf(stat.get("baseOnBalls"), 0) or 0),
                    "so": int(_sf(stat.get("strikeOuts"), 0) or 0),
                    "tb": int(_sf(stat.get("totalBases"), 0) or 0),
                }
            )
        out.sort(key=lambda x: x.get("date") or "")
        return out
    except Exception:
        return []


def _window(rows, n):
    sample = list(rows or [])[-int(n):]
    if not sample:
        return {"available": False, "games": 0}
    games = len(sample)
    ab = sum(int(x.get("ab") or 0) for x in sample)
    hits = sum(int(x.get("h") or 0) for x in sample)
    so = sum(int(x.get("so") or 0) for x in sample)
    pa_values = [x.get("pa") for x in sample]
    pa = sum(int(x or 0) for x in sample if x is not None)
    pa_complete = all(x is not None for x in pa_values)
    return {
        "available": True,
        "games": games,
        "ab": ab,
        "hits": hits,
        "avg": (hits / ab) if ab else None,
        "hit_games": sum(1 for x in sample if int(x.get("h") or 0) >= 1),
        "multi_hit_games": sum(1 for x in sample if int(x.get("h") or 0) >= 2),
        "hr": sum(int(x.get("hr") or 0) for x in sample),
        "so": so,
        "pa": pa if pa_complete and pa > 0 else None,
        "k_rate": (so / pa) if pa_complete and pa > 0 else None,
        "start": sample[0].get("date"),
        "end": sample[-1].get("date"),
    }


def _season_contact(player_id):
    pid = _safe_id(player_id)
    if pid is None:
        return {"available": False}
    try:
        savant = hit_engine.statcast(pid) or {}
    except Exception:
        savant = {}
    try:
        season = hit_engine.hitter_stats(pid) or {}
    except Exception:
        season = {}

    pa = _sf(season.get("plate_appearances"), None)
    so = _sf(season.get("strikeouts"), None)
    season_k = (so / pa) if pa and so is not None else None
    available = bool(savant or season)
    return {
        "available": available,
        "avg": _sf(season.get("avg"), None),
        "season_k_rate": season_k,
        "xba": _sf(savant.get("xba"), None),
        "xslg": _sf(savant.get("xslg"), None),
        "avg_ev": _sf(savant.get("avg_ev"), None),
        "hard_hit_rate": _sf(savant.get("hard_hit_rate"), None),
        "barrel_rate": _sf(savant.get("barrel_rate"), None),
        "bbe": int(_sf(savant.get("bbe"), 0) or 0),
        "savant_pa": int(_sf(savant.get("pa"), 0) or 0),
    }


def _form_line(label, w):
    if not w.get("available"):
        return f"<b>{escape(label)}</b> • unavailable"
    games = int(w.get("games") or 0)
    bits = [
        f"{int(w.get('hits') or 0)}-for-{int(w.get('ab') or 0)} ({_fmt_avg(w.get('avg'))})",
        f"1+ hit {int(w.get('hit_games') or 0)}/{games} ({_fmt_pct((w.get('hit_games') or 0) / games if games else None)})",
        f"2+ hit {int(w.get('multi_hit_games') or 0)}/{games}",
    ]
    if w.get("k_rate") is not None:
        bits.append(f"K% {_fmt_pct(w.get('k_rate'))}")
    return f"<b>{escape(label)}</b> • " + " • ".join(bits)


def _contact_line(contact):
    if not contact.get("available"):
        return "Baseball Savant season contact snapshot unavailable"
    bits = []
    if contact.get("xba") is not None:
        bits.append(f"xBA {_fmt_avg(contact.get('xba'))}")
    if contact.get("xslg") is not None:
        bits.append(f"xSLG {_fmt_avg(contact.get('xslg'))}")
    if contact.get("avg_ev") is not None:
        bits.append(f"Avg EV {contact.get('avg_ev'):.1f} mph")
    if contact.get("hard_hit_rate") is not None:
        bits.append(f"Hard-Hit {_fmt_pct(contact.get('hard_hit_rate'))}")
    if contact.get("barrel_rate") is not None:
        bits.append(f"Barrel {_fmt_pct(contact.get('barrel_rate'))}")
    if contact.get("bbe"):
        bits.append(f"{contact.get('bbe')} BBE")
    return " • ".join(bits) if bits else "Baseball Savant season contact snapshot unavailable"


def _recent_form_strip(result):
    day = _selected_day()
    pid = _safe_id(result.get("player_id"))
    rows = _official_recent_log(pid, day)
    l5 = _window(rows, 5)
    l10 = _window(rows, 10)
    contact = _season_contact(pid)

    comparison = []
    if l10.get("k_rate") is not None:
        comparison.append(f"L10 K% {_fmt_pct(l10.get('k_rate'))}")
    if contact.get("season_k_rate") is not None:
        comparison.append(f"Season K% {_fmt_pct(contact.get('season_k_rate'))}")
    if contact.get("avg") is not None:
        comparison.append(f"Season AVG {_fmt_avg(contact.get('avg'))}")
    comparison_text = " • ".join(comparison) if comparison else "Recent-vs-season strikeout comparison unavailable"

    date_note = f"Official MLB game logs date-cut before {day}."
    if l10.get("available") and l10.get("start") and l10.get("end"):
        date_note += f" L10 window {l10.get('start')} to {l10.get('end')}."
    date_note += " Savant contact metrics are a season snapshot; display only."

    return (
        '<div class="hit1310-context">'
        '<div class="hit1310-head">STEP 7 • RECENT HITTING FORM + CONTACT QUALITY</div>'
        f'<div class="hit1310-form">{_form_line("Last 5", l5)}</div>'
        f'<div class="hit1310-form">{_form_line("Last 10", l10)}</div>'
        '<div class="hit1310-divider"></div>'
        '<div class="hit1310-kicker">CONTACT QUALITY • BASEBALL SAVANT</div>'
        f'<div class="hit1310-contact">{escape(_contact_line(contact))}</div>'
        f'<div class="hit1310-compare">{escape(comparison_text)}</div>'
        f'<div class="hit1310-note">{escape(date_note)}</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hit1310-context{margin:7px 0 5px;padding:9px 10px;border:1px solid #31566a;background:linear-gradient(145deg,#0b1920,#09131b);border-radius:12px}
.hit1310-head{font-size:.44rem;letter-spacing:.08em;color:#8ee8d6;font-weight:950;text-transform:uppercase}
.hit1310-form{font-size:.52rem;color:#d5e8ee;line-height:1.5;margin-top:3px}.hit1310-form b{color:#f3fbff}
.hit1310-divider{height:1px;background:#23434f;margin:6px 0 4px}
.hit1310-kicker{font-size:.42rem;letter-spacing:.07em;color:#7ec7f2;font-weight:900;text-transform:uppercase}
.hit1310-contact{font-size:.51rem;color:#c9d8e5;line-height:1.5;margin-top:3px}
.hit1310-compare{font-size:.48rem;color:#aac2d2;line-height:1.45;margin-top:3px}
.hit1310-note{font-size:.42rem;color:#728899;line-height:1.4;margin-top:4px}
</style>
"""

if "hit1310-context" not in core.HIT_CSS:
    core.HIT_CSS = core.HIT_CSS + _EXTRA_CSS


def _pick_html_v1310(result, rank):
    """Inject Step 7 after verified Steps 1-6 and before probability output."""
    html = _BASE_PICK_HTML(result, rank)
    marker = '<div class="hit-pick-prob">'
    strip = _recent_form_strip(result)
    if marker in html:
        return html.replace(marker, strip + marker, 1)
    return html + strip


active._pick_html = _pick_html_v1310


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.caption(
        "📈 Hit UI V13.10 • Step 7 official recent form + Savant contact-quality context ACTIVE • "
        "date-cut game logs • display/context only • Hit Model V13 unchanged"
    )
    return active.render_hit_hub(games_df, section_header, status_info, team_logo, h)
