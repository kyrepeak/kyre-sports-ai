"""MLB H+R+RBI V1.0.11 — Step 8 opponent run prevention + team defense.

Presentation/audit wrapper around verified H+R+RBI V1.0.10 Steps 1-7.
Strongest-threshold cards retain every verified layer and add a fail-safe opponent
run-prevention panel built from official MLB team season pitching/fielding stats
plus completed recent games before the selected slate date:
- season runs allowed/game and hits allowed/game,
- team ERA / WHIP / HR allowed per game,
- official fielding percentage and errors/game,
- L5/L10 runs allowed/game,
- transparent VERY WEAK / WEAK / AVERAGE / STRONG / ELITE prevention grade,
- explicit hitter-facing SUPPORTS / NEUTRAL / HURTS context label.

Model firewall: Step 8 is descriptive/audit only. No opponent-defense field is fed
back into H+R+RBI V1.0 component rates, candidate selection, Monte Carlo,
threshold probability, ranking, confidence or fair odds. Missing official data is
labeled unavailable rather than inferred.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from html import escape

import requests
import streamlit as st

import mlb_hrrbi_hub_v110 as prior

MODEL_VERSION = "H+R+RBI V1.0.11"
base = prior.base
core = prior.core
MLB_API = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "Mozilla/5.0 KyreSportsAI/1.0"}

# Preserve verified Steps 1-7 exactly, including V1.0.9 pitch-share validation.
_BASE_CARD = base._card


def _safe_id(value):
    try:
        if value is None:
            return None
        number = int(float(value))
        return number if number > 0 else None
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
        return datetime.strptime(_selected_day(), "%Y-%m-%d").year
    except Exception:
        return 2026


def _fmt(value, digits=2):
    x = _sf(value, None)
    return f"{x:.{digits}f}" if x is not None else "—"


@st.cache_data(ttl=900, show_spinner=False)
def _team_group_stats(team_id, season_year, group):
    """Official MLB team season stats for one group; display-only."""
    tid = _safe_id(team_id)
    if tid is None:
        return {}
    try:
        r = requests.get(
            f"{MLB_API}/teams/{tid}/stats",
            params={"stats": "season", "group": str(group), "season": int(season_year)},
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        groups = r.json().get("stats") or []
        split = ((groups[0].get("splits") or [None])[0] if groups else None) or {}
        return split.get("stat") or {}
    except Exception:
        return {}


@st.cache_data(ttl=600, show_spinner=False)
def _recent_team_prevention(team_id, slate_day):
    """Runs allowed in the most recent completed games before the selected slate."""
    tid = _safe_id(team_id)
    if tid is None:
        return {"available": False}
    try:
        day = datetime.strptime(str(slate_day)[:10], "%Y-%m-%d").date()
    except Exception:
        return {"available": False}

    start = day - timedelta(days=35)
    end = day - timedelta(days=1)
    if end < start:
        return {"available": False}

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
        rows = []
        for block in r.json().get("dates") or []:
            date_text = str(block.get("date") or "")
            for game in block.get("games") or []:
                status = game.get("status") or {}
                abstract = str(status.get("abstractGameState") or "").lower()
                detailed = str(status.get("detailedState") or "").lower()
                if abstract != "final" and not any(x in detailed for x in ("final", "game over", "completed")):
                    continue

                teams = game.get("teams") or {}
                away = teams.get("away") or {}
                home = teams.get("home") or {}
                away_id = _safe_id((away.get("team") or {}).get("id"))
                home_id = _safe_id((home.get("team") or {}).get("id"))
                away_score = _sf(away.get("score"), None)
                home_score = _sf(home.get("score"), None)
                if away_score is None or home_score is None:
                    continue

                if away_id == tid:
                    ra = home_score
                elif home_id == tid:
                    ra = away_score
                else:
                    continue
                rows.append((date_text, _safe_id(game.get("gamePk")) or 0, float(ra)))

        rows.sort(key=lambda x: (x[0], x[1]))
        runs_allowed = [x[2] for x in rows]
        if not runs_allowed:
            return {"available": False}

        def window(n):
            sample = runs_allowed[-int(n):]
            if not sample:
                return None
            return {
                "games": len(sample),
                "ra_per_game": sum(sample) / len(sample),
                "shutouts": sum(1 for x in sample if x <= 0.0),
            }

        return {
            "available": True,
            "games": len(runs_allowed),
            "l5": window(5),
            "l10": window(10),
        }
    except Exception:
        return {"available": False}


def _season_profile(team_id):
    year = _season_year()
    pitching = _team_group_stats(team_id, year, "pitching")
    fielding = _team_group_stats(team_id, year, "fielding")

    games = _sf(pitching.get("gamesPlayed"), None)
    if games is None or games <= 0:
        games = _sf(fielding.get("gamesPlayed"), None)

    runs = _sf(pitching.get("runs"), None)
    hits = _sf(pitching.get("hits"), None)
    hr = _sf(pitching.get("homeRuns"), None)
    errors = _sf(fielding.get("errors"), None)
    field_pct = _sf(fielding.get("fielding"), None)
    if field_pct is None:
        field_pct = _sf(fielding.get("fieldingPercentage"), None)

    return {
        "available": bool(pitching or fielding),
        "games": games,
        "ra_per_game": (runs / games) if runs is not None and games and games > 0 else None,
        "hits_allowed_per_game": (hits / games) if hits is not None and games and games > 0 else None,
        "hr_allowed_per_game": (hr / games) if hr is not None and games and games > 0 else None,
        "era": _sf(pitching.get("era"), None),
        "whip": _sf(pitching.get("whip"), None),
        "field_pct": field_pct,
        "errors_per_game": (errors / games) if errors is not None and games and games > 0 else None,
    }


def _prevention_grade(season_ctx, recent_ctx):
    """Transparent descriptive grade; never a model input."""
    if not season_ctx.get("available"):
        return "DATA LIMITED", "limited", "NEUTRAL"

    score = 0
    observed = 0

    ra = _sf(season_ctx.get("ra_per_game"), None)
    if ra is not None:
        observed += 1
        if ra <= 3.70:
            score += 2
        elif ra <= 4.15:
            score += 1
        elif ra >= 5.00:
            score -= 2
        elif ra >= 4.65:
            score -= 1

    era = _sf(season_ctx.get("era"), None)
    if era is not None:
        observed += 1
        if era <= 3.60:
            score += 2
        elif era <= 4.05:
            score += 1
        elif era >= 4.90:
            score -= 2
        elif era >= 4.50:
            score -= 1

    whip = _sf(season_ctx.get("whip"), None)
    if whip is not None:
        observed += 1
        if whip <= 1.20:
            score += 1
        elif whip >= 1.38:
            score -= 1

    fld = _sf(season_ctx.get("field_pct"), None)
    if fld is not None:
        observed += 1
        if fld >= 0.987:
            score += 1
        elif fld <= 0.981:
            score -= 1

    l5 = (recent_ctx or {}).get("l5") or {}
    l5_ra = _sf(l5.get("ra_per_game"), None)
    if l5_ra is not None and int(l5.get("games") or 0) >= 3:
        observed += 1
        if l5_ra <= 3.50:
            score += 1
        elif l5_ra >= 5.30:
            score -= 1

    if observed < 2:
        return "DATA LIMITED", "limited", "NEUTRAL"
    if score >= 5:
        return "ELITE", "elite", "HURTS HITTER"
    if score >= 2:
        return "STRONG", "strong", "HURTS HITTER"
    if score <= -5:
        return "VERY WEAK", "veryweak", "SUPPORTS HITTER"
    if score <= -2:
        return "WEAK", "weak", "SUPPORTS HITTER"
    return "AVERAGE", "average", "NEUTRAL"


def _defense_strip(result):
    opponent_id = _safe_id(result.get("opponent_team_id"))
    opponent_name = str(result.get("opponent") or "Opponent")
    season_ctx = _season_profile(opponent_id)
    recent_ctx = _recent_team_prevention(opponent_id, _selected_day())
    grade, grade_cls, hitter_context = _prevention_grade(season_ctx, recent_ctx)

    season_bits = []
    if season_ctx.get("ra_per_game") is not None:
        season_bits.append(f"RA/G {_fmt(season_ctx.get('ra_per_game'), 2)}")
    if season_ctx.get("hits_allowed_per_game") is not None:
        season_bits.append(f"H allowed/G {_fmt(season_ctx.get('hits_allowed_per_game'), 2)}")
    if season_ctx.get("era") is not None:
        season_bits.append(f"ERA {_fmt(season_ctx.get('era'), 2)}")
    if season_ctx.get("whip") is not None:
        season_bits.append(f"WHIP {_fmt(season_ctx.get('whip'), 2)}")
    if season_ctx.get("hr_allowed_per_game") is not None:
        season_bits.append(f"HR allowed/G {_fmt(season_ctx.get('hr_allowed_per_game'), 2)}")
    season_text = " • ".join(season_bits) if season_bits else "Official season run-prevention stats unavailable"

    field_bits = []
    if season_ctx.get("field_pct") is not None:
        field_bits.append(f"Fielding % {float(season_ctx.get('field_pct')):.3f}")
    if season_ctx.get("errors_per_game") is not None:
        field_bits.append(f"Errors/G {_fmt(season_ctx.get('errors_per_game'), 2)}")
    field_text = " • ".join(field_bits) if field_bits else "Official fielding context unavailable"

    recent_bits = []
    for key, label in (("l5", "L5"), ("l10", "L10")):
        row = (recent_ctx or {}).get(key) or {}
        if row.get("ra_per_game") is not None:
            recent_bits.append(
                f"{label} RA/G {_fmt(row.get('ra_per_game'), 2)} ({int(row.get('games') or 0)} G)"
            )
    recent_text = " • ".join(recent_bits) if recent_bits else "Recent completed-game run prevention unavailable"

    context_cls = "support" if hitter_context == "SUPPORTS HITTER" else "hurt" if hitter_context == "HURTS HITTER" else "neutral"

    return (
        '<div class="hrr111-defense">'
        '<div class="hrr111-head">'
        '<span>STEP 8 • OPPONENT RUN PREVENTION + TEAM DEFENSE</span>'
        f'<b class="grade-{grade_cls}">{escape(grade)}</b>'
        '</div>'
        f'<div class="hrr111-main"><strong>{escape(opponent_name)}</strong> • {escape(season_text)}</div>'
        f'<div class="hrr111-row"><strong>Team defense</strong> • {escape(field_text)}</div>'
        f'<div class="hrr111-row"><strong>Recent prevention</strong> • {escape(recent_text)}</div>'
        '<div class="hrr111-divider"></div>'
        f'<div class="hrr111-impact {context_cls}"><strong>2+ context:</strong> {escape(hitter_context)}</div>'
        '<div class="hrr111-note">Audit/context only • grade uses official season pitching/fielding plus recent runs allowed. Step 8 does not feed this grade back into the H+R+RBI probability or ranking.</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hrr111-defense{margin:7px 0 5px;padding:9px 10px;border:1px solid #5a4936;background:linear-gradient(145deg,#1a1510,#0a131b);border-radius:12px}
.hrr111-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.hrr111-head span{font-size:.43rem;letter-spacing:.08em;color:#f0bd78;font-weight:950;text-transform:uppercase}.hrr111-head b{border:1px solid #665445;border-radius:999px;padding:3px 7px;font-size:.43rem;white-space:nowrap}.hrr111-head b.grade-elite,.hrr111-head b.grade-strong{border-color:#1f6b4f;background:#0a3326;color:#79edb7}.hrr111-head b.grade-average{border-color:#6d5a18;background:#382f0d;color:#f1d36c}.hrr111-head b.grade-weak,.hrr111-head b.grade-veryweak{border-color:#7a3b38;background:#351514;color:#ff9d98}.hrr111-head b.grade-limited{border-color:#465564;background:#16202a;color:#a6b3bf}
.hrr111-main{font-size:.55rem;color:#f3eadf;line-height:1.5;margin-top:5px}.hrr111-main strong,.hrr111-row strong{color:#fff1df}.hrr111-row{font-size:.50rem;color:#c6b9aa;line-height:1.48;margin-top:4px}.hrr111-divider{height:1px;background:#403429;margin:7px 0 4px}.hrr111-impact{font-size:.52rem;line-height:1.45;font-weight:800}.hrr111-impact.support{color:#81e8ae}.hrr111-impact.hurt{color:#f2a29d}.hrr111-impact.neutral{color:#e5d18c}.hrr111-note{font-size:.43rem;color:#847a70;line-height:1.4;margin-top:5px}
.hrr111-step-badge{display:inline-flex;align-items:center;gap:5px;border:1px solid #665445;background:#1a1510;color:#f0c58f;border-radius:999px;padding:5px 8px;font-size:.52rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin:0 0 9px}
@media(max-width:700px){.hrr111-head{align-items:flex-start}.hrr111-head b{font-size:.40rem}.hrr111-main{font-size:.52rem}}
</style>
"""

if "hrr111-defense" not in base.CSS:
    base.CSS = base.CSS + _EXTRA_CSS


def _card_v111(result, rank, threshold):
    """Verified Steps 1-7 first; Step 8 can never crash or suppress the card."""
    html = _BASE_CARD(result, rank, threshold)
    try:
        strip = _defense_strip(result)
        marker = '<div class="hrr-prob">'
        if marker in html and strip:
            return html.replace(marker, strip + marker, 1)
    except Exception:
        pass
    return html


base._card = _card_v111


def render_hrrbi_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(
        '<div class="hrr111-step-badge">🛡️ H+R+RBI V1.0.11 • Steps 1–8 active • opponent run prevention + defense</div>',
        unsafe_allow_html=True,
    )
    return prior.render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
