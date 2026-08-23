"""MLB H+R+RBI V1.0.13 — Step 10 starter workload + times-through-order exposure.

Presentation/audit wrapper around verified H+R+RBI V1.0.12 Steps 1-9.
Strongest-threshold cards retain every verified layer and add a fail-safe starter
workload panel built from official MLB season pitching stats, official game logs,
and the already-existing V1.0 starter/bullpen exposure estimate:
- season IP/start, BF/start and pitches/start when MLB publishes them,
- recent-start L5 IP/BF/pitches averages,
- expected starter IP today from the existing V1.0 exposure layer,
- projected hitter PA versus the starter,
- clearly labeled times-through-order exposure estimate,
- quick-hook / normal-hook / long-leash classification,
- recent workload trend,
- transparent FAVORABLE / NEUTRAL / TOUGH starter-exposure grade.

Important: this does NOT claim exact first/second/third-time-through performance
splits when MLB does not publish a reliable split. TTO shown here is exposure only,
not a new performance input. Step 10 is audit/context only and does not change any
H/R/RBI rate, Monte Carlo probability, ranking, confidence or fair odds.
"""
from __future__ import annotations

from html import escape

import requests
import streamlit as st

import mlb_hrrbi_hub_v112 as prior
import mlb_hrrbi_hub_v107 as env_step

MODEL_VERSION = "H+R+RBI V1.0.13"
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


def _ipfloat(value):
    text = str(value or "0.0")
    try:
        whole, frac = (text.split(".", 1) + ["0"])[:2]
        outs = int(frac[:1]) if frac[:1].isdigit() else 0
        outs = max(0, min(outs, 2))
        return float(whole) + outs / 3.0
    except Exception:
        return _sf(value, 0.0) or 0.0


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


def _fmt(value, digits=1):
    x = _sf(value, None)
    return f"{x:.{digits}f}" if x is not None else "—"


@st.cache_data(ttl=900, show_spinner=False)
def _official_pitching_season(pid, season_year):
    player_id = _safe_id(pid)
    if player_id is None:
        return {}
    try:
        r = requests.get(
            f"{MLB_API}/people/{player_id}/stats",
            params={"stats": "season", "group": "pitching", "season": int(season_year)},
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        groups = r.json().get("stats") or []
        split = ((groups[0].get("splits") or [None])[0] if groups else None) or {}
        stat = split.get("stat") or {}
        starts = int(_sf(stat.get("gamesStarted"), 0) or 0)
        ip = _ipfloat(stat.get("inningsPitched"))
        bf = _sf(stat.get("battersFaced"), None)
        pitches = _sf(stat.get("numberOfPitches"), None)
        if pitches is None:
            pitches = _sf(stat.get("pitchesThrown"), None)
        return {
            "available": bool(stat),
            "starts": starts,
            "ip": ip,
            "bf": bf,
            "pitches": pitches,
            "ip_start": (ip / starts) if starts > 0 else None,
            "bf_start": (bf / starts) if bf is not None and starts > 0 else None,
            "pitches_start": (pitches / starts) if pitches is not None and starts > 0 else None,
            "era": _sf(stat.get("era"), None),
            "whip": _sf(stat.get("whip"), None),
        }
    except Exception:
        return {}


@st.cache_data(ttl=900, show_spinner=False)
def _official_recent_starts(pid, season_year, limit=5):
    player_id = _safe_id(pid)
    if player_id is None:
        return {"available": False, "starts": []}
    try:
        r = requests.get(
            f"{MLB_API}/people/{player_id}/stats",
            params={"stats": "gameLog", "group": "pitching", "season": int(season_year)},
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        groups = r.json().get("stats") or []
        splits = groups[0].get("splits") or [] if groups else []
        rows = []
        for sp in splits:
            stat = sp.get("stat") or {}
            if int(_sf(stat.get("gamesStarted"), 0) or 0) <= 0:
                continue
            ip = _ipfloat(stat.get("inningsPitched"))
            bf = _sf(stat.get("battersFaced"), None)
            pitches = _sf(stat.get("numberOfPitches"), None)
            if pitches is None:
                pitches = _sf(stat.get("pitchesThrown"), None)
            rows.append({
                "date": str(sp.get("date") or ""),
                "ip": ip,
                "bf": bf,
                "pitches": pitches,
            })
        rows = rows[-max(1, int(limit)):]
        if not rows:
            return {"available": False, "starts": []}

        def avg(key):
            vals = [_sf(x.get(key), None) for x in rows]
            vals = [x for x in vals if x is not None]
            return (sum(vals) / len(vals)) if vals else None

        return {
            "available": True,
            "starts": rows,
            "games": len(rows),
            "ip_start": avg("ip"),
            "bf_start": avg("bf"),
            "pitches_start": avg("pitches"),
        }
    except Exception:
        return {"available": False, "starts": []}


def _existing_exposure(result):
    try:
        _bp, _quality, exposure, _workload = env_step._bullpen_profile(result)
        return exposure or {}
    except Exception:
        return {}


def _hook_label(season_ctx, recent_ctx):
    ip = _sf(recent_ctx.get("ip_start"), None)
    if ip is None:
        ip = _sf(season_ctx.get("ip_start"), None)
    pitches = _sf(recent_ctx.get("pitches_start"), None)
    if pitches is None:
        pitches = _sf(season_ctx.get("pitches_start"), None)
    bf = _sf(recent_ctx.get("bf_start"), None)
    if bf is None:
        bf = _sf(season_ctx.get("bf_start"), None)

    if ip is None and pitches is None and bf is None:
        return "DATA LIMITED", "limited"
    if (ip is not None and ip < 4.9) or (pitches is not None and pitches < 78) or (bf is not None and bf < 20.5):
        return "QUICK HOOK", "good"
    if ((ip is not None and ip >= 5.8) and ((pitches is not None and pitches >= 90) or (bf is not None and bf >= 24))):
        return "LONG LEASH", "tough"
    return "NORMAL HOOK", "neutral"


def _workload_trend(season_ctx, recent_ctx):
    if not recent_ctx.get("available"):
        return "RECENT START SAMPLE LIMITED", "limited"
    deltas = []
    for key in ("ip_start", "bf_start", "pitches_start"):
        s = _sf(season_ctx.get(key), None)
        r = _sf(recent_ctx.get(key), None)
        if s is not None and r is not None:
            if key == "ip_start":
                deltas.append((r - s) / 0.45)
            elif key == "bf_start":
                deltas.append((r - s) / 2.0)
            else:
                deltas.append((r - s) / 7.0)
    if not deltas:
        return "RECENT WORKLOAD COMPARISON LIMITED", "limited"
    score = sum(deltas) / len(deltas)
    if score >= 0.8:
        return "DEEPER RECENT LEASH", "tough"
    if score <= -0.8:
        return "SHORTER RECENT LEASH", "good"
    return "STABLE WORKLOAD", "neutral"


def _tto_exposure(projected_pa_vs_sp):
    pa = _sf(projected_pa_vs_sp, None)
    if pa is None:
        return "TTO exposure unavailable"
    if pa >= 3.45:
        return "Likely 1st + 2nd + 3rd pass; 4th-pass chance"
    if pa >= 2.45:
        return "Likely 1st + 2nd + 3rd pass"
    if pa >= 1.45:
        return "Likely 1st + 2nd pass; 3rd-pass chance limited"
    return "Mostly 1st-pass exposure; early bullpen path likely"


def _starter_grade(result, season_ctx, recent_ctx, exposure, hook_label):
    observed = 0
    toughness = 0
    era = _sf(season_ctx.get("era"), None)
    whip = _sf(season_ctx.get("whip"), None)
    if era is None:
        try:
            era = _sf((result.get("pitcher") or {}).get("era"), None)
        except Exception:
            era = None
    if whip is None:
        try:
            whip = _sf((result.get("pitcher") or {}).get("whip"), None)
        except Exception:
            whip = None

    if era is not None:
        observed += 1
        if era <= 3.45:
            toughness += 2
        elif era <= 3.95:
            toughness += 1
        elif era >= 4.90:
            toughness -= 2
        elif era >= 4.45:
            toughness -= 1
    if whip is not None:
        observed += 1
        if whip <= 1.18:
            toughness += 1
        elif whip >= 1.38:
            toughness -= 1

    projected_pa = _sf(result.get("projected_pa"), None)
    starter_share = _sf(exposure.get("starter_share"), None)
    pa_vs_sp = projected_pa * starter_share if projected_pa is not None and starter_share is not None else None
    if pa_vs_sp is not None:
        observed += 1
        if pa_vs_sp >= 2.8:
            toughness += 1
        elif pa_vs_sp <= 1.7:
            toughness -= 1

    if hook_label == "LONG LEASH":
        observed += 1
        toughness += 1
    elif hook_label == "QUICK HOOK":
        observed += 1
        toughness -= 1

    if observed < 2:
        return "DATA LIMITED", "limited", "NEUTRAL"
    if toughness >= 3:
        return "TOUGH", "tough", "HURTS HITTER"
    if toughness <= -2:
        return "FAVORABLE", "good", "SUPPORTS HITTER"
    return "NEUTRAL", "neutral", "NEUTRAL"


def _workload_strip(result):
    starter_id = _safe_id(result.get("starter_id"))
    season_year = _season_year()
    season_ctx = _official_pitching_season(starter_id, season_year)
    recent_ctx = _official_recent_starts(starter_id, season_year, 5)
    exposure = _existing_exposure(result)

    hook, hook_cls = _hook_label(season_ctx, recent_ctx)
    trend, trend_cls = _workload_trend(season_ctx, recent_ctx)
    grade, grade_cls, hitter_context = _starter_grade(result, season_ctx, recent_ctx, exposure, hook)

    starter_name = str(result.get("starter_name") or result.get("opposing_pitcher") or "")
    if not starter_name:
        starter_name = str((result.get("pitcher") or {}).get("name") or "Opposing starter")

    season_bits = []
    if season_ctx.get("starts") is not None:
        season_bits.append(f"{int(season_ctx.get('starts') or 0)} GS")
    if season_ctx.get("ip_start") is not None:
        season_bits.append(f"{_fmt(season_ctx.get('ip_start'),1)} IP/start")
    if season_ctx.get("bf_start") is not None:
        season_bits.append(f"{_fmt(season_ctx.get('bf_start'),1)} BF/start")
    if season_ctx.get("pitches_start") is not None:
        season_bits.append(f"{_fmt(season_ctx.get('pitches_start'),0)} pitches/start")
    season_text = " • ".join(season_bits) if season_bits else "Official season starter workload unavailable"

    recent_bits = []
    if recent_ctx.get("available"):
        recent_bits.append(f"L{int(recent_ctx.get('games') or 0)} starts")
        if recent_ctx.get("ip_start") is not None:
            recent_bits.append(f"{_fmt(recent_ctx.get('ip_start'),1)} IP/start")
        if recent_ctx.get("bf_start") is not None:
            recent_bits.append(f"{_fmt(recent_ctx.get('bf_start'),1)} BF/start")
        if recent_ctx.get("pitches_start") is not None:
            recent_bits.append(f"{_fmt(recent_ctx.get('pitches_start'),0)} pitches/start")
    recent_text = " • ".join(recent_bits) if recent_bits else "Recent official start workload unavailable"

    starter_ip = _sf(exposure.get("starter_ip"), None)
    starter_share = _sf(exposure.get("starter_share"), None)
    projected_pa = _sf(result.get("projected_pa"), None)
    pa_vs_sp = projected_pa * starter_share if projected_pa is not None and starter_share is not None else None

    expected_bits = []
    if starter_ip is not None:
        expected_bits.append(f"Expected SP IP {_fmt(starter_ip,1)}")
    if starter_share is not None:
        expected_bits.append(f"Starter share {starter_share*100:.1f}%")
    if pa_vs_sp is not None:
        expected_bits.append(f"~{pa_vs_sp:.1f} hitter PA vs SP")
    expected_text = " • ".join(expected_bits) if expected_bits else "Existing starter-exposure estimate unavailable"

    tto_text = _tto_exposure(pa_vs_sp)
    impact_cls = "support" if hitter_context == "SUPPORTS HITTER" else "hurt" if hitter_context == "HURTS HITTER" else "neutral"

    return (
        '<div class="hrr113-sp">'
        '<div class="hrr113-head">'
        '<span>STEP 10 • STARTER WORKLOAD + TIMES-THROUGH-ORDER EXPOSURE</span>'
        f'<b class="{grade_cls}">{escape(grade)}</b>'
        '</div>'
        f'<div class="hrr113-main"><strong>{escape(starter_name)}</strong> • {escape(season_text)}</div>'
        f'<div class="hrr113-row"><strong>Recent starts</strong> • {escape(recent_text)}</div>'
        f'<div class="hrr113-row"><strong>Existing game exposure</strong> • {escape(expected_text)}</div>'
        '<div class="hrr113-divider"></div>'
        f'<div class="hrr113-row"><strong>TTO exposure estimate</strong> • {escape(tto_text)}</div>'
        f'<div class="hrr113-row"><strong>Hook profile</strong> • <span class="tag-{hook_cls}">{escape(hook)}</span></div>'
        f'<div class="hrr113-row"><strong>Workload trend</strong> • <span class="tag-{trend_cls}">{escape(trend)}</span></div>'
        f'<div class="hrr113-impact {impact_cls}"><strong>2+ starter context:</strong> {escape(hitter_context)}</div>'
        '<div class="hrr113-note">Audit/context only • TTO is an exposure estimate derived from verified starter workload and the existing V1.0 starter-share projection. It is not an invented TTO performance split and adds no new probability adjustment.</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hrr113-sp{margin:7px 0 5px;padding:9px 10px;border:1px solid #42547b;background:linear-gradient(145deg,#101827,#08131d);border-radius:12px}
.hrr113-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.hrr113-head span{font-size:.43rem;letter-spacing:.08em;color:#9bb9ff;font-weight:950;text-transform:uppercase}.hrr113-head b{border:1px solid #4c5e81;border-radius:999px;padding:3px 7px;font-size:.43rem;white-space:nowrap}.hrr113-head b.good{border-color:#1f6b4f;background:#0a3326;color:#79edb7}.hrr113-head b.neutral{border-color:#6d5a18;background:#382f0d;color:#f1d36c}.hrr113-head b.tough{border-color:#7a3b38;background:#351514;color:#ff9d98}.hrr113-head b.limited{border-color:#465564;background:#16202a;color:#a6b3bf}
.hrr113-main{font-size:.54rem;color:#e7edff;line-height:1.5;margin-top:5px}.hrr113-main strong,.hrr113-row strong{color:#f4f7ff}.hrr113-row{font-size:.50rem;color:#b5c1d8;line-height:1.48;margin-top:4px}.hrr113-divider{height:1px;background:#33405e;margin:7px 0 4px}.hrr113-impact{font-size:.52rem;font-weight:850;line-height:1.45;margin-top:5px}.hrr113-impact.support{color:#82e9af}.hrr113-impact.hurt{color:#f3a29d}.hrr113-impact.neutral{color:#e4d28e}.hrr113-note{font-size:.43rem;color:#7d899f;line-height:1.4;margin-top:5px}.tag-good{color:#83eab1}.tag-neutral{color:#e4d28e}.tag-tough{color:#f3a29d}.tag-limited{color:#a1acb8}
.hrr113-step-badge{display:inline-flex;align-items:center;gap:5px;border:1px solid #4c5e81;background:#101827;color:#aec6ff;border-radius:999px;padding:5px 8px;font-size:.52rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin:0 0 9px}
@media(max-width:700px){.hrr113-head{align-items:flex-start}.hrr113-head b{font-size:.40rem}.hrr113-row{font-size:.49rem}}
</style>
"""

if "hrr113-sp" not in base.CSS:
    base.CSS = base.CSS + _EXTRA_CSS


def _card_v113(result, rank, threshold):
    """Verified Steps 1-9 first; Step 10 can never crash or suppress the card."""
    html = _BASE_CARD(result, rank, threshold)
    try:
        strip = _workload_strip(result)
        marker = '<div class="hrr-prob">'
        if marker in html and strip:
            return html.replace(marker, strip + marker, 1)
    except Exception:
        pass
    return html


base._card = _card_v113


def render_hrrbi_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(
        '<div class="hrr113-step-badge">🧭 H+R+RBI V1.0.13 • Steps 1–10 active • starter workload + TTO exposure</div>',
        unsafe_allow_html=True,
    )
    return prior.render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
