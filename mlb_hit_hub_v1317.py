"""MLB 1+ Hit UI V13.17 — Step 2 compact mobile Top-5 cards.

Additive presentation-only wrapper over permanently frozen V13.16 Hits Step 1.

Step 2 makes the Top-5 board faster to scan on phone/tablet without changing:
- Hit Model V13 probability or Monte Carlo,
- the full-slate candidate pool,
- Top-5 ranking/order,
- confidence/data quality,
- calibration/history,
- any frozen Steps 1-11 evidence.

The frozen V13.16 card is rendered first. Step 2 reads the already-rendered
Step-1 summary labels from that card, promotes the most important values into a
compact hero, and moves the unchanged detailed Steps 1-11 evidence underneath a
collapsed disclosure. No evidence or result payload is recomputed.
"""
from __future__ import annotations

from html import escape
import re
from typing import Any

import streamlit as st
import mlb_hit_hub_v1316 as prior

active, core, visual = prior.active, prior.core, prior.visual
UI_VERSION = "V13.17"
_BASE_PICK_HTML = prior._pick_html_v1316


def _text(value: Any, default: str = "N/A") -> str:
    s = str(value or "").strip()
    return s if s else default


def _num(value: Any, default=None):
    try:
        x = float(value)
        return x if x == x and x not in (float("inf"), float("-inf")) else default
    except Exception:
        return default


def _summary_label(html: str, label: str, default: str = "DATA LIMITED") -> str:
    pattern = rf"{re.escape(label)}\s*•\s*([^<]+)"
    match = re.search(pattern, str(html or ""), flags=re.I)
    if not match:
        return default
    value = re.sub(r"\s+", " ", match.group(1)).strip()
    return value or default


def _evidence_score(html: str) -> str:
    match = re.search(r"EVIDENCE\s*•\s*(\d{1,3})\s*/\s*100", str(html or ""), flags=re.I)
    if not match:
        return "N/A"
    score = max(0, min(100, int(match.group(1))))
    return f"{score}/100"


def _pill_class(label: str) -> str:
    text = str(label or "").upper()
    if any(x in text for x in ("ELITE", "STRONG", "FAVORABLE", "HITTER FRIENDLY")):
        return "good"
    if any(x in text for x in ("LOW", "HARD", "TOUGH", "LIMITED")):
        return "warn"
    return "neutral"


def _official_headshot(player_id: Any) -> str:
    try:
        return str(visual.mlb_player_headshot_url(player_id, width=180) or "")
    except Exception:
        return ""


def _official_logo(team_id: Any) -> str:
    try:
        return str(visual.mlb_team_logo_url(team_id) or "")
    except Exception:
        return ""


def _img(url: str, css_class: str, alt: str) -> str:
    if not url:
        return ""
    return (
        f'<img class="{css_class}" src="{escape(url, quote=True)}" '
        f'alt="{escape(alt, quote=True)}" loading="lazy" referrerpolicy="no-referrer" '
        'onerror="this.style.display=\'none\'">'
    )


def _deep_inner(frozen_html: str) -> str:
    """Keep the exact frozen inner card evidence while hiding duplicated quick fields."""
    src = str(frozen_html or "").strip()
    if not src:
        return ""
    first = src.find(">")
    if first < 0:
        return src
    # Every certified V13.16 Top-5 card is one outer div. Remove only that shell.
    if src.endswith("</div>"):
        return src[first + 1:-6]
    return src[first + 1:]


def _pick_html_v1317(result, rank):
    """Build a compact shell around the already-rendered frozen V13.16 card."""
    frozen_html = str(_BASE_PICK_HTML(result, rank) or "")
    r = result or {}
    sim = r.get("sim") or {}

    p1 = _num(sim.get("p_one_plus"))
    p2 = _num(sim.get("p_two_plus"))
    xh = _num(sim.get("expected_hits"))
    lo = _num(sim.get("scenario_low"))
    hi = _num(sim.get("scenario_high"))

    pick = _summary_label(frozen_html, "PICK STRENGTH")
    matchup = _summary_label(frozen_html, "MATCHUP")
    opportunity = _summary_label(frozen_html, "OPPORTUNITY")
    evidence = _evidence_score(frozen_html)

    player = _text(r.get("player_name"), "Unknown hitter")
    team = _text(r.get("team"), "Team")
    opponent = _text(r.get("opponent"), "Opponent")
    starter = _text(r.get("starter_name"), "Starter TBD")
    spot = _text(r.get("position"), "—")
    pitch = _text(r.get("first_pitch"), "TBD")
    confidence = _text(r.get("confidence"), "N/A")
    lineup = "CONFIRMED" if bool(r.get("lineup_confirmed")) else "PROJECTED"
    lineup_cls = "confirmed" if bool(r.get("lineup_confirmed")) else "projected"

    headshot = _img(_official_headshot(r.get("player_id")), "hit1317-photo", player)
    logo = _img(_official_logo(r.get("team_id")), "hit1317-logo", team)
    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "•"
    rank_cls = " rank1" if rank == 1 else ""

    p1_text = "N/A" if p1 is None else f"{p1 * 100:.1f}%"
    p2_text = "N/A" if p2 is None else f"{p2 * 100:.1f}%"
    xh_text = "N/A" if xh is None else f"{xh:.2f}"
    range_text = "N/A" if lo is None or hi is None else f"{lo * 100:.1f}–{hi * 100:.1f}%"
    deep = _deep_inner(frozen_html)

    return (
        f'<div class="hit1317-card{rank_cls}">'
        '<div class="hit1317-top">'
        f'<div class="hit1317-rank">{medal} #{int(rank)} <span class="{lineup_cls}">{lineup}</span></div>'
        f'<span class="hit1317-pick {_pill_class(pick)}">PICK • {escape(pick)}</span>'
        '</div>'
        '<div class="hit1317-main">'
        '<div class="hit1317-person">'
        f'{headshot}'
        '<div class="hit1317-copy">'
        f'<div class="hit1317-name">{escape(player)}</div>'
        '<div class="hit1317-teamline">'
        f'{logo}<span>{escape(team)} vs {escape(opponent)}</span>'
        '</div>'
        f'<div class="hit1317-match">vs {escape(starter)} • Bat #{escape(spot)} • {escape(pitch)}</div>'
        '</div></div>'
        '<div class="hit1317-prob">'
        f'<b>{escape(p1_text)}</b><span>1+ HIT</span>'
        '</div>'
        '</div>'
        '<div class="hit1317-quick">'
        f'<div><b>{escape(p2_text)}</b><span>2+ Hits</span></div>'
        f'<div><b>{escape(xh_text)}</b><span>Expected Hits</span></div>'
        f'<div><b>{escape(matchup)}</b><span>Matchup</span></div>'
        f'<div><b>{escape(opportunity)}</b><span>Opportunity</span></div>'
        '</div>'
        '<div class="hit1317-foot">'
        f'<span>DATA {escape(confidence)}</span>'
        f'<span>EVIDENCE {escape(evidence)}</span>'
        f'<span>90% {escape(range_text)}</span>'
        '</div>'
        '<details class="hit1317-deep">'
        '<summary>＋ Full Steps 1–11 evidence + Step 1 final summary</summary>'
        f'<div class="hit1317-deepbody">{deep}</div>'
        '</details>'
        '</div>'
    )


active._pick_html = _pick_html_v1317

_CSS = r"""
<style>
.hit-top-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.hit1317-card{border:1px solid #294a61;background:linear-gradient(145deg,#0c1c2d,#07131f);border-radius:17px;padding:12px;min-width:0;box-shadow:0 7px 20px rgba(0,0,0,.14)}
.hit1317-card.rank1{grid-column:1/-1;border-color:#9a7d18;box-shadow:inset 3px 0 #d2ad20,0 8px 22px rgba(0,0,0,.16)}
.hit1317-top{display:flex;justify-content:space-between;align-items:center;gap:8px}.hit1317-rank{font-size:.57rem;color:#69dfff;font-weight:950;letter-spacing:.05em;text-transform:uppercase}.hit1317-rank span{display:inline-flex;margin-left:5px;padding:3px 6px;border-radius:999px;font-size:.41rem;border:1px solid #53616d;color:#b7c0c9;background:#18222b}.hit1317-rank span.confirmed{border-color:#1e6d4e;color:#7aedb7;background:#0a3023}.hit1317-rank span.projected{border-color:#7a631d;color:#f2d477;background:#30270c}
.hit1317-pick{display:inline-flex;border-radius:999px;padding:4px 7px;font-size:.43rem;font-weight:950;white-space:nowrap;border:1px solid #50606d;background:#17232d;color:#c9d4dc}.hit1317-pick.good{border-color:#1f6b4f;background:#0a3326;color:#79edb7}.hit1317-pick.warn{border-color:#785723;background:#30220e;color:#f6cf73}
.hit1317-main{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center;margin-top:9px}.hit1317-person{display:flex;align-items:center;gap:9px;min-width:0}.hit1317-photo{width:58px;height:58px;flex:0 0 58px;border-radius:50%;object-fit:cover;object-position:center top;background:#091725;border:1px solid #315a79}.hit1317-copy{min-width:0}.hit1317-name{font-size:1rem;font-weight:1000;color:#f8fbff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hit1317-teamline{display:flex;align-items:center;gap:5px;margin-top:3px;color:#a5b7c6;font-size:.62rem;font-weight:800}.hit1317-logo{width:20px;height:20px;object-fit:contain}.hit1317-match{color:#758da0;font-size:.57rem;line-height:1.4;margin-top:2px}
.hit1317-prob{text-align:right;border-left:1px solid #20394c;padding-left:10px}.hit1317-prob b{display:block;color:#fff;font-size:1.55rem;line-height:1;font-weight:1000;letter-spacing:-.04em}.hit1317-prob span{display:block;color:#72d8ff;font-size:.43rem;font-weight:950;margin-top:3px;letter-spacing:.08em}
.hit1317-quick{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:9px}.hit1317-quick>div{border:1px solid #203c50;background:#081722;border-radius:9px;padding:6px;text-align:center;min-width:0}.hit1317-quick b{display:block;color:#eef7ff;font-size:.57rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hit1317-quick span{display:block;color:#708696;font-size:.38rem;text-transform:uppercase;margin-top:2px}
.hit1317-foot{display:flex;flex-wrap:wrap;gap:5px;margin-top:7px}.hit1317-foot span{border:1px solid #263f50;background:#0d1a25;border-radius:999px;padding:4px 7px;color:#94a9b9;font-size:.42rem;font-weight:850}
.hit1317-deep{margin-top:8px;border-top:1px solid #1d3445;padding-top:7px}.hit1317-deep summary{cursor:pointer;color:#9db3c4;font-size:.51rem;font-weight:900;list-style:none}.hit1317-deep summary::-webkit-details-marker{display:none}.hit1317-deepbody{margin-top:8px}.hit1317-deepbody>.hit-rank,.hit1317-deepbody>.hit-pick-identity,.hit1317-deepbody>.hit-pick-name,.hit1317-deepbody>.hit-pick-meta,.hit1317-deepbody>.hit-pick-prob,.hit1317-deepbody>.hit-pick-sub,.hit1317-deepbody>.hit-conf{display:none!important}
.hit1317-deepbody .hit1316-final{margin-top:7px}
@media(max-width:700px){
  .hit-top-grid{grid-template-columns:1fr!important}.hit1317-card.rank1{grid-column:auto}.hit1317-card{padding:10px}
  .hit1317-photo{width:52px;height:52px;flex-basis:52px}.hit1317-name{font-size:.94rem}.hit1317-prob b{font-size:1.42rem}
  .hit1317-quick{grid-template-columns:repeat(2,minmax(0,1fr))}.hit1317-quick b{font-size:.55rem}
  .hit1317-top{align-items:flex-start}.hit1317-pick{font-size:.40rem}.hit1317-match{font-size:.54rem}
}
</style>
"""
if "hit1317-card" not in core.HIT_CSS:
    core.HIT_CSS += _CSS


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.caption(
        "📱 Hit UI V13.17 • Step 2 compact Top-5 cards ACTIVE • "
        "mobile quick scan + collapsed frozen evidence • Hit Model V13 unchanged"
    )
    return prior.render_hit_hub(games_df, section_header, status_info, team_logo, h)


__all__ = [
    "UI_VERSION",
    "_BASE_PICK_HTML",
    "_deep_inner",
    "_evidence_score",
    "_pick_html_v1317",
    "_summary_label",
    "render_hit_hub",
]
