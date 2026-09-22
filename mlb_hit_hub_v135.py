"""MLB 1+ Hit UI V13.5 — Step 2 opposing starter identity + official stats.

Presentation/context-only wrapper around the verified V13.4/V13.3 Top-5 scanner.
The existing V13 hit probability model, Monte Carlo, candidate pool, lineup logic,
ranking, calibration and persistence are unchanged.

Step 2 adds the verified opposing probable starter to each Top-5 card using the
starter_id/starter_name already carried by the modeled result. Pitcher headshots
use MLB's official image CDN. Season ERA/WHIP/hand/K%/K9 are read from MLB Stats;
when a display stat is unavailable the card falls back gracefully rather than
inventing a value.
"""
from __future__ import annotations

from html import escape

import requests
import streamlit as st

import mlb_hit_hub_v134 as prior

# prior.base is the real V13.3 module captured before app.py's compatibility alias.
active = prior.base
core = active.base

UI_VERSION = "V13.5"
MLB_API = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "KyreSportsAI/1.0"}


def _safe_id(value):
    return prior._safe_id(value)


def _selected_season():
    try:
        day = str(active.schedule.current_selected_date())
        year = int(day[:4])
        if 2000 <= year <= 2100:
            return year
    except Exception:
        pass
    return 2026


@st.cache_data(ttl=600, show_spinner=False)
def _official_pitcher_stats(player_id, season_year):
    """Display-only MLB season line. Never feeds the probability model."""
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
        strikeouts = core.sf(stat.get("strikeOuts"), 0) or 0
        batters_faced = core.sf(stat.get("battersFaced"), 0) or 0
        k_pct = (100.0 * strikeouts / batters_faced) if batters_faced else None
        return {
            "era": stat.get("era"),
            "whip": stat.get("whip"),
            "strikeouts": strikeouts,
            "batters_faced": batters_faced,
            "k_pct": k_pct,
            "k9": core.sf(stat.get("strikeoutsPer9Inn")),
            "innings": stat.get("inningsPitched"),
            "games_started": stat.get("gamesStarted"),
            # MLB Stats does not consistently expose FIP/xERA. Never synthesize it.
            "fip": stat.get("fip"),
            "xera": stat.get("xera") or stat.get("xEra"),
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
        "fip": official.get("fip"),
        "xera": official.get("xera"),
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
        "hit135-pitcher-photo",
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
    if p.get("xera") not in (None, "", "N/A"):
        pieces.append(f"xERA {_fmt_num(p.get('xera'))}")
    elif p.get("fip") not in (None, "", "N/A"):
        pieces.append(f"FIP {_fmt_num(p.get('fip'))}")
    stats = " • ".join(pieces)
    return (
        '<div class="hit135-pitcher">'
        f'{photo}'
        '<div class="hit135-pitcher-copy">'
        '<div class="hit135-eyebrow">OPPOSING PROBABLE STARTER • MLB</div>'
        f'<div class="hit135-pitcher-name">{core._e(p.get("name"))} <span>{escape(hand_label)}</span></div>'
        f'<div class="hit135-pitcher-stats">{escape(stats)}</div>'
        '</div></div>'
    )


_EXTRA_CSS = r"""
<style>
.hit135-pitcher{display:grid;grid-template-columns:48px minmax(0,1fr);align-items:center;gap:9px;margin:7px 0 4px;padding:7px 8px;border:1px solid #1d405a;background:#081725;border-radius:12px}
.hit135-pitcher-photo{width:46px;height:46px;border-radius:50%;object-fit:cover;object-position:center top;background:#0a1928;border:1px solid #315a79}
.hit135-pitcher-copy{min-width:0}.hit135-eyebrow{font-size:.43rem;letter-spacing:.08em;color:#5f8eac;font-weight:900}.hit135-pitcher-name{font-size:.68rem;color:#eef7ff;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}.hit135-pitcher-name span{font-size:.49rem;color:#7bd4ff;margin-left:3px}.hit135-pitcher-stats{font-size:.51rem;color:#9bb0c1;line-height:1.45;margin-top:2px}
@media(max-width:700px){.hit135-pitcher{grid-template-columns:44px minmax(0,1fr)}.hit135-pitcher-photo{width:42px;height:42px}}
</style>
"""

if "hit135-pitcher" not in core.HIT_CSS:
    core.HIT_CSS = core.HIT_CSS + _EXTRA_CSS


def _pick_html_v135(result, rank):
    sim = result["sim"]
    cls = "hit-pick rank1" if rank == 1 else "hit-pick"
    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "•"
    source = "✅ CONFIRMED" if result.get("lineup_confirmed") else "🕒 PROJECTED"
    player_name = result.get("player_name")
    team_name = result.get("team")
    player_img = prior._img(
        prior.mlb_player_headshot_url(result.get("player_id")),
        "hit134-photo",
        player_name,
    )
    team_img = prior._img(
        prior.mlb_team_logo_url(result.get("team_id")),
        "hit134-team-logo",
        team_name,
    )
    identity = (
        '<div class="hit134-identity">'
        f'{player_img}'
        '<div class="hit134-copy">'
        f'<div class="hit-pick-name">{core._e(player_name)}</div>'
        f'<div class="hit-pick-meta">{core._e(team_name)} vs {core._e(result.get("opponent"))}<br>'
        f'vs {core._e(result.get("starter_name"))} • Bat #{core._e(result.get("position"))} • {core._e(result.get("first_pitch"))}</div>'
        '<div class="hit134-source">MLB batter + team identity</div>'
        '</div>'
        f'{team_img}'
        '</div>'
    )
    return (
        f'<div class="{cls}">'
        f'<div class="hit-rank">{medal} Rank {rank} • {source}</div>'
        f'{identity}'
        f'{_pitcher_strip(result)}'
        f'<div class="hit-pick-prob">{sim["p_one_plus"]*100:.1f}%</div>'
        f'<div class="hit-pick-sub">2+ {sim["p_two_plus"]*100:.1f}% • xH {sim["expected_hits"]:.2f}<br>'
        f'90% {sim["scenario_low"]*100:.1f}–{sim["scenario_high"]*100:.1f}% • Data {int(result.get("data_score",0) or 0)}/8</div>'
        f'<div class="hit-conf">{core._e(result.get("confidence","—"))}</div>'
        '</div>'
    )


# Patch only the active V13.3 Top-5 HTML renderer. The scanner/model functions stay native.
active._pick_html = _pick_html_v135


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.caption(
        "🧢 Hit UI V13.5 • Step 2 opposing starter photo + official MLB season stats ACTIVE • "
        "presentation/context only • Hit Model V13 unchanged"
    )
    # Call V13.3 directly to avoid stacking old wrapper captions while preserving its scanner.
    return active.render_hit_hub(games_df, section_header, status_info, team_logo, h)
