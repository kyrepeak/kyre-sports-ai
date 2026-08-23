"""MLB H+R+RBI V1.0.12 — Step 9 bullpen matchup + handedness path.

Presentation/audit wrapper around verified H+R+RBI V1.0.11 Steps 1-8.
Strongest-threshold cards retain every verified layer and add a fail-safe relief-path panel:
- active opponent relief-core roster,
- RHP/LHP relief-innings mix,
- batter season split versus the dominant bullpen hand,
- strongest active relievers by current-season relief workload/quality,
- projected bullpen PA exposure already used by H+R+RBI V1.0,
- the same recent aggregate bullpen workload/fatigue signal shown in Step 5,
- transparent FAVORABLE / NEUTRAL / TOUGH / DATA LIMITED bullpen grade.

This is not a prediction of exact reliever sequence. The listed names are an active-roster
likely relief pool only. Step 9 is display/audit context and does not feed any new value
into H/R/RBI rates, Monte Carlo, threshold probability, ranking, confidence or fair odds.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape

import requests
import streamlit as st

import mlb_hrrbi_hub_v111 as prior
import mlb_hrrbi_hub_v107 as env_step

MODEL_VERSION = "H+R+RBI V1.0.12"
base = prior.base
core = prior.core
MLB_API = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "Mozilla/5.0 KyreSportsAI/1.0"}

_BASE_CARD = base._card


def _safe_id(value):
    try:
        if value is None:
            return None
        x = int(float(value))
        return x if x > 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


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
        return int((_selected_day() or "2026")[:4])
    except Exception:
        return 2026


@st.cache_data(ttl=900, show_spinner=False)
def _active_pitcher_ids(team_id, season_year):
    tid = _safe_id(team_id)
    if tid is None:
        return []
    try:
        r = requests.get(
            f"{MLB_API}/teams/{tid}/roster",
            params={"rosterType": "active", "season": int(season_year)},
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        out = []
        for row in r.json().get("roster") or []:
            pos = row.get("position") or {}
            if str(pos.get("abbreviation") or "").upper() != "P":
                continue
            person = row.get("person") or {}
            pid = _safe_id(person.get("id"))
            if pid is not None:
                out.append({"id": pid, "name": person.get("fullName") or f"Player {pid}"})
        return out
    except Exception:
        return []


def _pitcher_profile(pid):
    try:
        p = base.pitcher_stats(pid) or {}
    except Exception:
        p = {}
    if not p:
        return None
    games = int(_sf(p.get("games"), 0) or 0)
    starts = int(_sf(p.get("games_started"), 0) or 0)
    ip = _sf(p.get("true_innings"), 0.0) or 0.0
    if games <= 0 or ip <= 0:
        return None
    if starts > max(5, int(round(games * 0.40))):
        return None
    relief_weight = max(games - starts, 0) + max(ip - starts * 3.0, 0.0) * 0.35
    return {
        "id": _safe_id(p.get("id")) or _safe_id(pid),
        "name": str(p.get("name") or f"Player {pid}"),
        "hand": str(p.get("hand") or "?").upper(),
        "games": games,
        "starts": starts,
        "ip": ip,
        "era": _sf(p.get("era"), None),
        "whip": _sf(p.get("whip"), None),
        "k9": _sf(p.get("k9"), None),
        "relief_weight": relief_weight,
    }


@st.cache_data(ttl=900, show_spinner=False)
def _active_relief_core(team_id, starter_id, season_year):
    starter = _safe_id(starter_id)
    roster = _active_pitcher_ids(team_id, season_year)
    ids = [x["id"] for x in roster if x.get("id") and x.get("id") != starter]
    if not ids:
        return []
    out = []
    with ThreadPoolExecutor(max_workers=min(6, len(ids))) as pool:
        futures = {pool.submit(_pitcher_profile, pid): pid for pid in ids}
        for fut in as_completed(futures):
            try:
                row = fut.result()
            except Exception:
                row = None
            if row:
                out.append(row)
    out.sort(key=lambda x: (x.get("relief_weight", 0.0), x.get("ip", 0.0)), reverse=True)
    return out


def _hand_mix(relievers):
    weights = {"R": 0.0, "L": 0.0}
    for p in relievers or []:
        hand = str(p.get("hand") or "").upper()
        if hand not in weights:
            continue
        weights[hand] += max(_sf(p.get("ip"), 0.0) or 0.0, 0.0)
    total = weights["R"] + weights["L"]
    if total <= 0:
        return {"available": False}
    dominant = "R" if weights["R"] >= weights["L"] else "L"
    return {"available": True, "R": weights["R"] / total, "L": weights["L"] / total, "dominant": dominant}


def _batter_split(result, hand):
    if hand not in {"R", "L"}:
        return {}
    pid = _safe_id(result.get("player_id"))
    if pid is None:
        return {}
    try:
        return base.hand_split(pid, hand) or {}
    except Exception:
        return {}


def _bullpen_context(result):
    team_id = _safe_id(result.get("opponent_team_id"))
    starter_id = _safe_id(result.get("starter_id"))
    season_year = _season_year()
    relievers = _active_relief_core(team_id, starter_id, season_year)
    mix = _hand_mix(relievers)
    dominant = mix.get("dominant") if mix.get("available") else None
    split = _batter_split(result, dominant)
    try:
        bullpen, quality, exposure, workload = env_step._bullpen_profile(result)
    except Exception:
        bullpen, quality, exposure, workload = {}, {}, {}, {}
    return relievers, mix, split, bullpen or {}, quality or {}, exposure or {}, workload or {}


def _grade(mix, split, bullpen, workload):
    observed = 0
    toughness = 0.0
    era = _sf(bullpen.get("era"), None)
    whip = _sf(bullpen.get("whip"), None)
    k9 = _sf(bullpen.get("k9"), None)
    if era is not None:
        observed += 1
        if era <= 3.55:
            toughness += 2
        elif era <= 4.00:
            toughness += 1
        elif era >= 4.80:
            toughness -= 2
        elif era >= 4.40:
            toughness -= 1
    if whip is not None:
        observed += 1
        if whip <= 1.18:
            toughness += 1
        elif whip >= 1.38:
            toughness -= 1
    if k9 is not None:
        observed += 1
        if k9 >= 9.8:
            toughness += 1
        elif k9 <= 7.5:
            toughness -= 1
    ab = _sf(split.get("at_bats"), 0) or 0
    ops = _sf(split.get("ops"), None)
    if ab >= 40 and ops is not None:
        observed += 1
        if ops <= 0.700:
            toughness += 1
        elif ops >= 0.850:
            toughness -= 1
    flag = str(workload.get("flag") or "").upper()
    if "HEAVY" in flag:
        observed += 1
        toughness -= 1
    elif "ELEVATED" in flag:
        observed += 1
        toughness -= 0.5
    if observed < 2:
        return "DATA LIMITED", "limited", "NEUTRAL"
    if toughness >= 3:
        return "TOUGH", "tough", "HURTS HITTER"
    if toughness <= -2:
        return "FAVORABLE", "good", "SUPPORTS HITTER"
    return "NEUTRAL", "neutral", "NEUTRAL"


def _fmt(value, digits=2):
    x = _sf(value, None)
    return f"{x:.{digits}f}" if x is not None else "—"


def _reliever_line(p):
    hand = str(p.get("hand") or "?")
    parts = [f"{escape(str(p.get('name') or 'Reliever'))} {escape(hand)}HP"]
    if p.get("era") is not None:
        parts.append(f"ERA {_fmt(p.get('era'),2)}")
    if p.get("whip") is not None:
        parts.append(f"WHIP {_fmt(p.get('whip'),2)}")
    if p.get("k9") is not None:
        parts.append(f"K/9 {_fmt(p.get('k9'),1)}")
    parts.append(f"{_fmt(p.get('ip'),1)} IP")
    return " • ".join(parts)


def _bullpen_strip(result):
    relievers, mix, split, bullpen, quality, exposure, workload = _bullpen_context(result)
    grade, grade_cls, hitter_context = _grade(mix, split, bullpen, workload)

    if mix.get("available"):
        mix_text = f"RHP {mix.get('R',0)*100:.0f}% • LHP {mix.get('L',0)*100:.0f}% • dominant {mix.get('dominant')}HP"
    else:
        mix_text = "Active relief-core handedness mix unavailable"

    dominant = mix.get("dominant")
    if split:
        split_text = (
            f"Batter vs {dominant}HP • {int(_sf(split.get('at_bats'),0) or 0)} AB "
            f"• AVG {split.get('avg','—')} • OPS {split.get('ops','—')}"
        )
    else:
        split_text = "Batter split vs dominant bullpen hand unavailable"

    bp_bits = []
    if bullpen.get("era") is not None:
        bp_bits.append(f"ERA {_fmt(bullpen.get('era'),2)}")
    if bullpen.get("whip") is not None:
        bp_bits.append(f"WHIP {_fmt(bullpen.get('whip'),2)}")
    if bullpen.get("k9") is not None:
        bp_bits.append(f"K/9 {_fmt(bullpen.get('k9'),1)}")
    if quality.get("difficulty"):
        bp_bits.append(f"difficulty {quality.get('difficulty')}")
    bp_text = " • ".join(bp_bits) if bp_bits else "Aggregate bullpen quality unavailable"

    starter_share = _sf(exposure.get("starter_share"), None)
    projected_pa = _sf(result.get("projected_pa"), None)
    if starter_share is not None:
        bp_share = max(0.0, 1.0 - starter_share)
        exp_text = f"Bullpen exposure {bp_share*100:.1f}%"
        if projected_pa is not None:
            exp_text += f" • ~{projected_pa*bp_share:.1f} projected PA vs relief"
    else:
        exp_text = "Projected bullpen PA exposure unavailable"

    if workload.get("available"):
        workload_text = (
            f"{int(workload.get('pitches') or 0)} pitches • "
            f"{_fmt(workload.get('innings'),1)} IP • "
            f"{int(workload.get('appearances') or 0)} relief apps • "
            f"{workload.get('flag') or '—'}"
        )
    else:
        workload_text = "Recent bullpen workload unavailable"

    core = list(relievers or [])[:3]
    if core:
        core_html = "".join(f'<div class="hrr112-rel">{_reliever_line(p)}</div>' for p in core)
    else:
        core_html = '<div class="hrr112-rel">Active relief-core detail unavailable — no reliever sequence inferred</div>'

    impact_cls = "support" if hitter_context == "SUPPORTS HITTER" else "hurt" if hitter_context == "HURTS HITTER" else "neutral"
    return (
        '<div class="hrr112-bp">'
        '<div class="hrr112-head">'
        '<span>STEP 9 • BULLPEN MATCHUP + HANDEDNESS PATH</span>'
        f'<b class="{grade_cls}">{escape(grade)}</b>'
        '</div>'
        f'<div class="hrr112-row"><strong>Active relief-core hand mix</strong> • {escape(mix_text)}</div>'
        f'<div class="hrr112-row"><strong>Hitter split</strong> • {escape(split_text)}</div>'
        f'<div class="hrr112-row"><strong>Aggregate bullpen</strong> • {escape(bp_text)}</div>'
        f'<div class="hrr112-row"><strong>Projected relief exposure</strong> • {escape(exp_text)}</div>'
        f'<div class="hrr112-row"><strong>Recent bullpen workload</strong> • {escape(workload_text)}</div>'
        '<div class="hrr112-divider"></div>'
        '<div class="hrr112-subhead">ACTIVE-ROSTER LIKELY RELIEF POOL • NOT A GUARANTEED SEQUENCE</div>'
        f'{core_html}'
        f'<div class="hrr112-impact {impact_cls}"><strong>2+ context:</strong> {escape(hitter_context)}</div>'
        '<div class="hrr112-note">Audit/context only • reliever names are an active-roster relief pool ranked by season relief workload/quality. Actual usage depends on score, leverage, rest and manager decisions. Step 9 adds no probability adjustment.</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hrr112-bp{margin:7px 0 5px;padding:9px 10px;border:1px solid #315a63;background:linear-gradient(145deg,#0b191d,#08131b);border-radius:12px}
.hrr112-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.hrr112-head span{font-size:.43rem;letter-spacing:.08em;color:#79d9e4;font-weight:950;text-transform:uppercase}.hrr112-head b{border:1px solid #365d66;border-radius:999px;padding:3px 7px;font-size:.43rem;white-space:nowrap}.hrr112-head b.good{border-color:#1f6b4f;background:#0a3326;color:#79edb7}.hrr112-head b.neutral{border-color:#6d5a18;background:#382f0d;color:#f1d36c}.hrr112-head b.tough{border-color:#7a3b38;background:#351514;color:#ff9d98}.hrr112-head b.limited{border-color:#465564;background:#16202a;color:#a6b3bf}
.hrr112-row{font-size:.50rem;color:#b6cbd0;line-height:1.48;margin-top:4px}.hrr112-row strong{color:#e3f8fb}.hrr112-divider{height:1px;background:#27434a;margin:7px 0 5px}.hrr112-subhead{font-size:.42rem;letter-spacing:.06em;color:#7a9ca3;font-weight:900;margin-bottom:4px}.hrr112-rel{font-size:.49rem;color:#d4e6e9;line-height:1.45;padding:3px 0;border-bottom:1px solid rgba(74,112,120,.22)}.hrr112-impact{font-size:.52rem;font-weight:850;margin-top:6px}.hrr112-impact.support{color:#81e8ae}.hrr112-impact.hurt{color:#f2a29d}.hrr112-impact.neutral{color:#e5d18c}.hrr112-note{font-size:.43rem;color:#748a8f;line-height:1.4;margin-top:5px}
.hrr112-step-badge{display:inline-flex;align-items:center;gap:5px;border:1px solid #315a63;background:#0b191d;color:#8de5ee;border-radius:999px;padding:5px 8px;font-size:.52rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin:0 0 9px}
@media(max-width:700px){.hrr112-head{align-items:flex-start}.hrr112-head b{font-size:.40rem}.hrr112-row,.hrr112-rel{font-size:.48rem}}
</style>
"""

if "hrr112-bp" not in base.CSS:
    base.CSS = base.CSS + _EXTRA_CSS


def _card_v112(result, rank, threshold):
    html = _BASE_CARD(result, rank, threshold)
    try:
        strip = _bullpen_strip(result)
        marker = '<div class="hrr-prob">'
        if marker in html and strip:
            return html.replace(marker, strip + marker, 1)
    except Exception:
        pass
    return html


base._card = _card_v112


def render_hrrbi_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(
        '<div class="hrr112-step-badge">🧯 H+R+RBI V1.0.12 • Steps 1–9 active • bullpen handedness + relief path</div>',
        unsafe_allow_html=True,
    )
    return prior.render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
