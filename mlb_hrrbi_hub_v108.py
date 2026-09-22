"""MLB H+R+RBI V1.0.8 — Step 6 plate-appearance + batting-order opportunity.

Presentation/audit wrapper around verified H+R+RBI V1.0.7. Strongest 2+ cards
retain Steps 1-5 and add a fail-safe opportunity layer:
- confirmed/projected batting-order slot and home/away side,
- the EXISTING V1.0 projected PA already used by the H+R+RBI model,
- official MLB team PA/game and runs/game,
- the EXISTING V1.0 batting-order Run and RBI role factors,
- starter-vs-bullpen projected PA exposure,
- official MLB opposing starter BF/start and IP/start,
- structural bottom-9 availability context,
- transparent lineup/substitution watch.

Model firewall: Step 6 does not add or re-apply any adjustment. It exposes values
already used by H+R+RBI V1.0 plus official MLB opportunity context. Candidate
selection, H/R/RBI rates, Monte Carlo, threshold probabilities, ranking,
confidence and fair odds are unchanged. Every optional display lookup is fail-safe.
"""
from __future__ import annotations

from datetime import datetime
from html import escape

import requests
import streamlit as st

import engine as hit_engine
import mlb_hrrbi_hub_v107 as prior

MODEL_VERSION = "H+R+RBI V1.0.8"
base = prior.base
core = prior.core
MLB_API = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "Mozilla/5.0 KyreSportsAI/1.0"}


def _safe_id(value):
    return prior._safe_id(value)


def _sf(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _selected_day():
    try:
        return str(base.schedule.current_selected_date())[:10]
    except Exception:
        return ""


def _season_year():
    try:
        return datetime.strptime(_selected_day(), "%Y-%m-%d").year
    except Exception:
        try:
            return int(hit_engine.season())
        except Exception:
            return 2026


def _fmt(value, digits=1):
    x = _sf(value, None)
    return f"{x:.{digits}f}" if x is not None else "—"


def _signed_pct(multiplier):
    x = _sf(multiplier, None)
    if x is None:
        return "—"
    delta = (x - 1.0) * 100.0
    if abs(delta) < 0.05:
        return "0.0%"
    return f"{delta:+.1f}%"


@st.cache_data(ttl=900, show_spinner=False)
def _team_opportunity(team_id, season_year):
    """Official MLB team season hitting totals converted to per-game context."""
    tid = _safe_id(team_id)
    if tid is None:
        return {"available": False}
    try:
        r = requests.get(
            f"{MLB_API}/teams/{tid}/stats",
            params={"stats": "season", "group": "hitting", "season": int(season_year)},
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        groups = r.json().get("stats") or []
        split = ((groups[0].get("splits") or [None])[0] if groups else None) or {}
        stat = split.get("stat") or {}
        games = _sf(stat.get("gamesPlayed"), 0) or 0
        if games <= 0:
            return {"available": False}
        pa = _sf(stat.get("plateAppearances"), None)
        runs = _sf(stat.get("runs"), None)
        return {
            "available": True,
            "games": int(games),
            "pa_per_game": pa / games if pa is not None else None,
            "runs_per_game": runs / games if runs is not None else None,
        }
    except Exception:
        return {"available": False}


@st.cache_data(ttl=900, show_spinner=False)
def _starter_opportunity(starter_id, season_year):
    """Official MLB opposing-starter BF/start and IP/start; display only."""
    pid = _safe_id(starter_id)
    if pid is None:
        return {"available": False}
    try:
        r = requests.get(
            f"{MLB_API}/people/{pid}/stats",
            params={"stats": "season", "group": "pitching", "season": int(season_year)},
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        groups = r.json().get("stats") or []
        split = ((groups[0].get("splits") or [None])[0] if groups else None) or {}
        stat = split.get("stat") or {}
        starts = _sf(stat.get("gamesStarted"), 0) or 0
        if starts <= 0:
            return {"available": False}
        bf = _sf(stat.get("battersFaced"), None)
        innings = hit_engine.ipfloat(stat.get("inningsPitched"))
        return {
            "available": True,
            "starts": int(starts),
            "bf_per_start": bf / starts if bf is not None else None,
            "ip_per_start": innings / starts if innings is not None else None,
        }
    except Exception:
        return {"available": False}


def _model_role_factors(spot):
    """Exact V1.0 batting-order factors already used by the model."""
    try:
        run_mult, rbi_mult = base._lineup_component_factors(int(spot or 4))
        return float(run_mult), float(rbi_mult)
    except Exception:
        return None, None


def _starter_exposure(result):
    pitcher = result.get("pitcher") if isinstance(result.get("pitcher"), dict) else {}
    if not pitcher:
        sid = _safe_id(result.get("starter_id"))
        if sid is not None:
            try:
                pitcher = hit_engine.pitcher_stats(sid) or {}
            except Exception:
                pitcher = {}
    try:
        expected_ab = float(hit_engine.ab_for_spot(result.get("position") or 4))
        return hit_engine.starter_exposure(pitcher, expected_ab) or {}
    except Exception:
        return {}


def _bottom_ninth_note(result):
    side = str(result.get("team_side") or "").lower()
    if side == "home":
        return "HOME • bottom 9th can disappear when the home club already leads"
    if side == "away":
        return "AWAY • top 9th remains structurally available in regulation"
    return "HOME/AWAY unavailable • no ninth-inning assumption made"


def _lineup_watch(result):
    confirmed = bool(result.get("lineup_confirmed"))
    spot = int(_sf(result.get("position"), 0) or 0)
    if not confirmed:
        return "PROJECTED • opportunity confidence reduced until today's lineup is official"
    if 1 <= spot <= 6:
        return "CONFIRMED TOP-6 • lower substitution watch; no penalty inferred"
    if 7 <= spot <= 9:
        return "CONFIRMED LOWER ORDER • substitution/PA watch shown qualitatively only"
    return "CONFIRMED • batting slot unavailable"


def _opportunity_grade(projected_pa, spot, confirmed):
    pa = _sf(projected_pa, None)
    if pa is None:
        return "DATA LIMITED", "limited"
    score = 0
    if pa >= 4.65:
        score += 2
    elif pa >= 4.30:
        score += 1
    elif pa < 3.85:
        score -= 1
    if 1 <= int(spot or 0) <= 5:
        score += 1
    elif 8 <= int(spot or 0) <= 9:
        score -= 1
    if confirmed:
        score += 1
    if score >= 3:
        return "ELITE OPPORTUNITY", "good"
    if score >= 1:
        return "STRONG OPPORTUNITY", "good"
    if score <= -1:
        return "LIMITED OPPORTUNITY", "tough"
    return "NORMAL OPPORTUNITY", "neutral"


def _opportunity_strip(result):
    season_year = _season_year()
    spot = int(_sf(result.get("position"), 0) or 0)
    side = str(result.get("team_side") or "Unknown").upper()
    confirmed = bool(result.get("lineup_confirmed"))
    lineup = "CONFIRMED" if confirmed else "PROJECTED"
    projected_pa = _sf(result.get("projected_pa"), None)

    team_ctx = _team_opportunity(result.get("team_id"), season_year)
    starter_ctx = _starter_opportunity(result.get("starter_id"), season_year)
    exposure = _starter_exposure(result)
    run_mult, rbi_mult = _model_role_factors(spot)
    grade, grade_cls = _opportunity_grade(projected_pa, spot, confirmed)

    headline = [f"Bat #{spot if spot else '—'}", side, lineup]
    if projected_pa is not None:
        headline.append(f"Model projected PA {_fmt(projected_pa, 2)}")

    team_bits = []
    if team_ctx.get("available"):
        if team_ctx.get("pa_per_game") is not None:
            team_bits.append(f"{_fmt(team_ctx.get('pa_per_game'), 1)} team PA/game")
        if team_ctx.get("runs_per_game") is not None:
            team_bits.append(f"{_fmt(team_ctx.get('runs_per_game'), 2)} team R/game")
    team_text = " • ".join(team_bits) if team_bits else "Official team PA/run context unavailable"

    role_bits = ["Hit: PA-volume driven"]
    if run_mult is not None:
        role_bits.append(f"Run slot factor {_signed_pct(run_mult)}")
    if rbi_mult is not None:
        role_bits.append(f"RBI slot factor {_signed_pct(rbi_mult)}")
    role_text = " • ".join(role_bits)

    starter_share = _sf(exposure.get("starter_share"), None)
    exposure_bits = []
    if starter_share is not None:
        bullpen_share = max(0.0, 1.0 - starter_share)
        exposure_bits.extend([
            f"Starter {starter_share * 100.0:.1f}%",
            f"Bullpen {bullpen_share * 100.0:.1f}%",
        ])
        if projected_pa is not None:
            exposure_bits.append(f"~{projected_pa * starter_share:.1f} PA vs SP")
            exposure_bits.append(f"~{projected_pa * bullpen_share:.1f} PA vs BP")
    exposure_text = " • ".join(exposure_bits) if exposure_bits else "Starter/bullpen PA exposure unavailable"

    starter_bits = []
    if starter_ctx.get("available"):
        if starter_ctx.get("bf_per_start") is not None:
            starter_bits.append(f"{_fmt(starter_ctx.get('bf_per_start'), 1)} BF/start")
        if starter_ctx.get("ip_per_start") is not None:
            starter_bits.append(f"{_fmt(starter_ctx.get('ip_per_start'), 1)} IP/start")
    starter_text = " • ".join(starter_bits) if starter_bits else "Official starter workload context unavailable"

    return (
        '<div class="hrr108-opp">'
        '<div class="hrr108-head">'
        '<span>STEP 6 • PLATE APPEARANCE + BATTING-ORDER OPPORTUNITY</span>'
        f'<b class="{grade_cls}">{escape(grade)}</b>'
        '</div>'
        f'<div class="hrr108-main">{escape(" • ".join(headline))}</div>'
        f'<div class="hrr108-row"><strong>Team opportunity</strong> • {escape(team_text)}</div>'
        f'<div class="hrr108-row"><strong>Existing V1.0 lineup role</strong> • {escape(role_text)}</div>'
        f'<div class="hrr108-row"><strong>Projected matchup exposure</strong> • {escape(exposure_text)}</div>'
        f'<div class="hrr108-row"><strong>Opposing starter workload</strong> • {escape(starter_text)}</div>'
        '<div class="hrr108-divider"></div>'
        f'<div class="hrr108-risk"><strong>9th-inning context:</strong> {escape(_bottom_ninth_note(result))}</div>'
        f'<div class="hrr108-risk"><strong>Lineup watch:</strong> {escape(_lineup_watch(result))}</div>'
        '<div class="hrr108-note">Audit/context only • projected PA and Run/RBI slot factors shown here are the existing H+R+RBI V1.0 model values; Step 6 adds no new adjustment.</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hrr108-opp{margin:7px 0 5px;padding:9px 10px;border:1px solid #45516b;background:linear-gradient(145deg,#0d1624,#08131d);border-radius:12px}
.hrr108-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.hrr108-head span{font-size:.43rem;letter-spacing:.08em;color:#9cc7ff;font-weight:950;text-transform:uppercase}.hrr108-head b{border:1px solid #465a75;border-radius:999px;padding:3px 7px;font-size:.44rem;white-space:nowrap;color:#c5d7ee}.hrr108-head b.good{border-color:#1f6b4f;background:#0a3326;color:#79edb7}.hrr108-head b.neutral{border-color:#6d5a18;background:#382f0d;color:#f1d36c}.hrr108-head b.tough{border-color:#7a3b38;background:#351514;color:#ff9d98}.hrr108-head b.limited{border-color:#465564;background:#16202a;color:#a6b3bf}
.hrr108-main{font-size:.59rem;color:#eef6ff;line-height:1.5;margin-top:5px;font-weight:850}.hrr108-row{font-size:.51rem;color:#aebfd3;line-height:1.48;margin-top:4px}.hrr108-row strong{color:#dbeaff}.hrr108-risk{font-size:.49rem;color:#d7cf9b;line-height:1.45;margin-top:3px}.hrr108-risk strong{color:#f1e6ad}.hrr108-note{font-size:.43rem;color:#74879e;line-height:1.4;margin-top:5px}.hrr108-divider{height:1px;background:#26364b;margin:7px 0 4px}
.hrr108-step-badge{display:inline-flex;align-items:center;gap:5px;border:1px solid #465a75;background:#101b2a;color:#b7d8ff;border-radius:999px;padding:5px 8px;font-size:.52rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin:0 0 9px}
@media(max-width:700px){.hrr108-head{align-items:flex-start}.hrr108-head b{font-size:.40rem}.hrr108-main{font-size:.54rem}}
</style>
"""

if "hrr108-opp" not in base.CSS:
    base.CSS = base.CSS + _EXTRA_CSS


def _card_v108(r, rank, threshold):
    """Verified Steps 1-5 first; Step 6 can never crash or suppress the card."""
    html = prior._card_v107(r, rank, threshold)
    try:
        strip = _opportunity_strip(r)
        marker = '<div class="hrr-prob">'
        if marker in html and strip:
            return html.replace(marker, strip + marker, 1)
    except Exception:
        pass
    return html


base._card = _card_v108


def render_hrrbi_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(
        '<div class="hrr108-step-badge">🎯 H+R+RBI V1.0.8 • Steps 1–6 active • PA + batting-order opportunity</div>',
        unsafe_allow_html=True,
    )
    return core.render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
