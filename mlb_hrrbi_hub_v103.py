"""MLB H+R+RBI V1.0.3 — Step 2 opposing probable starter context.

Presentation/context-only wrapper around verified H+R+RBI V1.0.2. The Strongest
2+ cards keep Step 1 batter/team visual identity and add the opposing probable
starter photo plus official MLB season ERA, WHIP, handedness, K% and K/9.

No H/R/RBI component rate, candidate pool, lineup rule, finalist selection,
Monte Carlo simulation, threshold probability, ranking, confidence or fair-odds
math is changed. Missing display stats fail gracefully and are never invented.
"""
from __future__ import annotations

from html import escape

import requests
import streamlit as st

import mlb_hrrbi_hub_v102 as prior

MODEL_VERSION = "H+R+RBI V1.0.3"
base = prior.base
MLB_API = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "KyreSportsAI/1.0"}


def _safe_id(value):
    return prior._safe_id(value)


def _selected_season():
    try:
        day = str(base.schedule.current_selected_date())
        year = int(day[:4])
        if 2000 <= year <= 2100:
            return year
    except Exception:
        pass
    return 2026


@st.cache_data(ttl=600, show_spinner=False)
def _official_pitcher_stats(player_id, season_year):
    """Official MLB season line for display only; never a model input."""
    pid = _safe_id(player_id)
    if pid is None:
        return {}
    try:
        r = requests.get(
            f"{MLB_API}/people/{pid}/stats",
            params={"stats": "season", "group": "pitching", "season": int(season_year)},
            headers=_HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        groups = r.json().get("stats") or []
        splits = groups[0].get("splits") or [] if groups else []
        stat = (splits[0].get("stat") or {}) if splits else {}
        if not stat:
            return {}
        strikeouts = base.sf(stat.get("strikeOuts"), 0) or 0
        batters_faced = base.sf(stat.get("battersFaced"), 0) or 0
        k_pct = (100.0 * strikeouts / batters_faced) if batters_faced else None
        return {
            "era": stat.get("era"),
            "whip": stat.get("whip"),
            "k_pct": k_pct,
            "k9": base.sf(stat.get("strikeoutsPer9Inn")),
            "innings": stat.get("inningsPitched"),
            "games_started": stat.get("gamesStarted"),
        }
    except Exception:
        return {}


def _pitcher_profile(result):
    pid = _safe_id(result.get("starter_id"))
    fallback = result.get("pitcher") or {}
    official = _official_pitcher_stats(pid, _selected_season()) if pid else {}
    return {
        "id": pid,
        "name": result.get("starter_name") or fallback.get("name") or "TBD",
        "hand": fallback.get("hand") or "?",
        "era": official.get("era") or fallback.get("era"),
        "whip": official.get("whip") or fallback.get("whip"),
        "k_pct": official.get("k_pct"),
        "k9": official.get("k9") if official.get("k9") is not None else fallback.get("k9"),
    }


def _fmt_num(value, digits=2):
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        text = str(value or "").strip()
        return text if text and text.upper() not in {"N/A", "NONE"} else "—"


def _pitcher_strip(result):
    p = _pitcher_profile(result)
    hand = str(p.get("hand") or "?").upper()
    hand_label = f"{hand}HP" if hand in {"R", "L"} else "Hand —"
    photo = prior._img(
        prior.mlb_player_headshot_url(p.get("id"), width=140),
        "hrr103-pitcher-photo",
        p.get("name"),
    )
    pieces = [
        f"ERA {_fmt_num(p.get('era'))}",
        f"WHIP {_fmt_num(p.get('whip'))}",
    ]
    if p.get("k_pct") is not None:
        pieces.append(f"K% {_fmt_num(p.get('k_pct'), 1)}%")
    if p.get("k9") is not None:
        pieces.append(f"K/9 {_fmt_num(p.get('k9'), 1)}")
    stats = " • ".join(pieces)
    return (
        '<div class="hrr103-pitcher">'
        f'{photo}'
        '<div class="hrr103-pitcher-copy">'
        '<div class="hrr103-eyebrow">STEP 2 • OPPOSING PROBABLE STARTER • MLB</div>'
        f'<div class="hrr103-pitcher-name">{prior._e(p.get("name"))} <span>{escape(hand_label)}</span></div>'
        f'<div class="hrr103-pitcher-stats">{escape(stats)}</div>'
        '</div></div>'
    )


_EXTRA_CSS = r"""
<style>
.hrr103-pitcher{display:grid;grid-template-columns:50px minmax(0,1fr);align-items:center;gap:10px;margin:8px 0 5px;padding:8px 9px;border:1px solid #1d405a;background:#081725;border-radius:13px}
.hrr103-pitcher-photo{width:48px;height:48px;border-radius:50%;object-fit:cover;object-position:center top;background:#0a1928;border:1px solid #315a79}
.hrr103-pitcher-copy{min-width:0}.hrr103-eyebrow{font-size:.43rem;letter-spacing:.08em;color:#5f8eac;font-weight:900;text-transform:uppercase}
.hrr103-pitcher-name{font-size:.70rem;color:#eef7ff;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}.hrr103-pitcher-name span{font-size:.49rem;color:#7bd4ff;margin-left:3px}
.hrr103-pitcher-stats{font-size:.52rem;color:#9bb0c1;line-height:1.45;margin-top:2px}
.hrr103-step-badge{display:inline-flex;align-items:center;gap:5px;border:1px solid #2a6078;background:#071d2b;color:#79dfff;border-radius:999px;padding:5px 8px;font-size:.52rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin:0 0 9px}
@media(max-width:700px){.hrr103-pitcher{grid-template-columns:44px minmax(0,1fr)}.hrr103-pitcher-photo{width:42px;height:42px}.hrr103-pitcher-stats{font-size:.49rem}}
</style>
"""

if "hrr103-pitcher" not in base.CSS:
    base.CSS = base.CSS + _EXTRA_CSS


def _card_v103(r, rank, threshold):
    """Reuse verified V1.0.2 card, inserting display-only starter context."""
    html = prior._card_v102(r, rank, threshold)
    marker = '<div class="hrr-prob">'
    strip = _pitcher_strip(r)
    if marker in html:
        return html.replace(marker, strip + marker, 1)
    return html


# Card-render seam only. Candidate building, simulation and sorting remain V1.0.
base._card = _card_v103


def render_hrrbi_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(
        '<div class="hrr103-step-badge">🧢 H+R+RBI V1.0.3 • Steps 1–2 active • batter identity + opposing starter</div>',
        unsafe_allow_html=True,
    )
    # Skip V1.0.2's extra Step-1 badge while retaining its card/CSS layer.
    return prior.prior.render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
