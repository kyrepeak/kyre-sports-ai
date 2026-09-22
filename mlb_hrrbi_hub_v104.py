"""MLB H+R+RBI V1.0.4 — Step 2 opposing starter renderer repair.

Presentation/context-only wrapper around verified H+R+RBI V1.0.2. This replaces
broken V1.0.3 Step 2 rendering while preserving the working Step 1 batter/team
identity layer.

Repair details:
- uses the real V1.0.1 escape helper through V1.0.2's parent binding,
- normalizes optional pitcher fallback payloads before reading display fields,
- official MLB starter stats remain display-only and fail closed,
- the entire Step 2 strip is card-level fail-safe: if any optional starter context
  cannot render, the verified V1.0.2 card is returned unchanged instead of taking
  down the Strongest 2+ Top-5 board.

No H/R/RBI component rate, candidate pool, lineup rule, finalist selection,
Monte Carlo simulation, threshold probability, ranking, confidence or fair-odds
math is changed.
"""
from __future__ import annotations

from html import escape

import requests
import streamlit as st

import mlb_hrrbi_hub_v102 as prior

MODEL_VERSION = "H+R+RBI V1.0.4"
base = prior.base
core = prior.prior  # V1.0.1 null-safe bridge; owns _e / _fmt_recent.
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
        splits = (groups[0].get("splits") or []) if groups else []
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


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _pitcher_profile(result):
    result = _as_dict(result)
    pid = _safe_id(result.get("starter_id"))
    fallback = _as_dict(result.get("pitcher"))
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
    except (TypeError, ValueError, OverflowError):
        text = str(value or "").strip()
        return text if text and text.upper() not in {"N/A", "NONE", "NAN"} else "—"


def _pitcher_strip(result):
    """Build Step 2 display strip. Never allowed to affect model payload."""
    p = _pitcher_profile(result)
    hand = str(p.get("hand") or "?").upper()
    hand_label = f"{hand}HP" if hand in {"R", "L"} else "Hand —"
    photo = prior._img(
        prior.mlb_player_headshot_url(p.get("id"), width=140),
        "hrr104-pitcher-photo",
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
        '<div class="hrr104-pitcher">'
        f'{photo}'
        '<div class="hrr104-pitcher-copy">'
        '<div class="hrr104-eyebrow">STEP 2 • OPPOSING PROBABLE STARTER • MLB</div>'
        f'<div class="hrr104-pitcher-name">{core._e(p.get("name"))} <span>{escape(hand_label)}</span></div>'
        f'<div class="hrr104-pitcher-stats">{escape(stats)}</div>'
        '</div></div>'
    )


_EXTRA_CSS = r"""
<style>
.hrr104-pitcher{display:grid;grid-template-columns:50px minmax(0,1fr);align-items:center;gap:10px;margin:8px 0 5px;padding:8px 9px;border:1px solid #1d405a;background:#081725;border-radius:13px}
.hrr104-pitcher-photo{width:48px;height:48px;border-radius:50%;object-fit:cover;object-position:center top;background:#0a1928;border:1px solid #315a79}
.hrr104-pitcher-copy{min-width:0}.hrr104-eyebrow{font-size:.43rem;letter-spacing:.08em;color:#5f8eac;font-weight:900;text-transform:uppercase}
.hrr104-pitcher-name{font-size:.70rem;color:#eef7ff;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}.hrr104-pitcher-name span{font-size:.49rem;color:#7bd4ff;margin-left:3px}
.hrr104-pitcher-stats{font-size:.52rem;color:#9bb0c1;line-height:1.45;margin-top:2px}
.hrr104-step-badge{display:inline-flex;align-items:center;gap:5px;border:1px solid #2a6078;background:#071d2b;color:#79dfff;border-radius:999px;padding:5px 8px;font-size:.52rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin:0 0 9px}
@media(max-width:700px){.hrr104-pitcher{grid-template-columns:44px minmax(0,1fr)}.hrr104-pitcher-photo{width:42px;height:42px}.hrr104-pitcher-stats{font-size:.49rem}}
</style>
"""

if "hrr104-pitcher" not in base.CSS:
    base.CSS = base.CSS + _EXTRA_CSS


def _card_v104(r, rank, threshold):
    """Verified Step-1 card first; optional Step-2 enrichment can never crash it."""
    html = prior._card_v102(r, rank, threshold)
    try:
        strip = _pitcher_strip(r)
        marker = '<div class="hrr-prob">'
        if marker in html and strip:
            return html.replace(marker, strip + marker, 1)
    except Exception:
        # Presentation-only starter context must never take down the Top-5 board.
        pass
    return html


# Card-render seam only. Candidate building, simulation and sorting remain V1.0.
base._card = _card_v104


def render_hrrbi_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(
        '<div class="hrr104-step-badge">🧢 H+R+RBI V1.0.4 • Steps 1–2 active • fail-safe starter context</div>',
        unsafe_allow_html=True,
    )
    # Call V1.0.1 directly to avoid duplicate wrapper captions while retaining
    # V1.0.2 identity CSS/card behavior through the patched base._card seam.
    return core.render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
