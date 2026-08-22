"""MLB 1+ Hit UI V13.8 — Step 5 park/weather + bullpen exposure context.

Presentation/context-only wrapper around the verified V13.7 Top-5 scanner. Hit
Model V13 probability math, Monte Carlo, candidate pool, lineup handling, ranking,
calibration and persistence remain unchanged.

Step 5 adds display-only context already represented by, or consistent with, the
existing V13 model inputs:
1) MLB game-feed venue/weather/roof conditions,
2) the frozen V13 park/weather adjustment and environment grade,
3) current active-reliever bullpen aggregate (ERA/WHIP/K9/hand mix) from the same
   MLB Stats based helper used by V13,
4) V13 starter-vs-bullpen expected plate-appearance exposure, and
5) a read-only recent bullpen workload snapshot from official MLB box scores for
   the three days before the selected slate.

The workload label is a display heuristic only. Missing data are labeled unavailable;
AVG/OPS allowed are never synthesized from incomplete relief aggregates. No Step-5
field is passed into prescreen, deep_scan, model_inputs, Monte Carlo, confidence,
calibration or ranking.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from html import escape

import requests
import streamlit as st

import engine as hit_engine
import mlb_hit_hub_v137 as prior

active = prior.active
core = prior.core
visual = prior.visual

UI_VERSION = "V13.8"
MLB_API = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "Mozilla/5.0 KyreSportsAI/1.0"}

# Capture the verified V13.7 card renderer before replacing only the active HTML
# function. This preserves Steps 1-4 byte-for-byte in the rendered card.
_BASE_PICK_HTML = active._pick_html


def _safe_id(value):
    try:
        if value is None:
            return None
        number = int(float(value))
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def _sf(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _selected_day():
    try:
        return str(active.schedule.current_selected_date())[:10]
    except Exception:
        return ""


def _fmt(value, digits=2):
    x = _sf(value, None)
    if x is None:
        return "—"
    return f"{x:.{digits}f}"


def _pct(value, digits=1, signed=False):
    x = _sf(value, None)
    if x is None:
        return "—"
    n = x * 100.0
    return f"{n:+.{digits}f}%" if signed else f"{n:.{digits}f}%"


@st.cache_data(ttl=600, show_spinner=False)
def _recent_bullpen_workload(team_id, slate_day, lookback_days=3):
    """Official MLB box-score relief workload before the selected slate.

    This is display-only. It intentionally excludes the selected slate date so no
    live/in-progress workload can leak into the pregame card.
    """
    tid = _safe_id(team_id)
    try:
        day = datetime.strptime(str(slate_day)[:10], "%Y-%m-%d").date()
    except Exception:
        return {"available": False}
    if tid is None:
        return {"available": False}

    start = day - timedelta(days=max(1, int(lookback_days)))
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
        games = []
        for block in r.json().get("dates") or []:
            games.extend(block.get("games") or [])

        final_games = 0
        bullpen_ip = 0.0
        bullpen_pitches = 0
        relief_apps = 0

        for game in games:
            status = game.get("status") or {}
            detailed = str(status.get("detailedState") or "").lower()
            abstract = str(status.get("abstractGameState") or "").lower()
            if abstract != "final" and not any(x in detailed for x in ("final", "game over", "completed")):
                continue

            away_id = _safe_id((((game.get("teams") or {}).get("away") or {}).get("team") or {}).get("id"))
            home_id = _safe_id((((game.get("teams") or {}).get("home") or {}).get("team") or {}).get("id"))
            side = "away" if away_id == tid else "home" if home_id == tid else None
            pk = _safe_id(game.get("gamePk"))
            if side is None or pk is None:
                continue

            try:
                feed = hit_engine.game_feed(pk)
                team_box = (((feed.get("liveData") or {}).get("boxscore") or {}).get("teams") or {}).get(side) or {}
                pitcher_ids = [
                    _safe_id(x) for x in (team_box.get("pitchers") or []) if _safe_id(x) is not None
                ]
                players = team_box.get("players") or {}
                if not pitcher_ids:
                    continue

                starter_id = None
                for pid in pitcher_ids:
                    stat = (((players.get(f"ID{pid}") or {}).get("stats") or {}).get("pitching") or {})
                    if (_sf(stat.get("gamesStarted"), 0) or 0) > 0:
                        starter_id = pid
                        break
                if starter_id is None:
                    # MLB box-score pitcher arrays are chronological; first pitcher
                    # is the safe fallback only when gamesStarted is absent.
                    starter_id = pitcher_ids[0]

                game_had_relief = False
                for pid in pitcher_ids:
                    if pid == starter_id:
                        continue
                    stat = (((players.get(f"ID{pid}") or {}).get("stats") or {}).get("pitching") or {})
                    ip = hit_engine.ipfloat(stat.get("inningsPitched"))
                    pitches = int(_sf(stat.get("pitchesThrown"), 0) or 0)
                    if ip <= 0 and pitches <= 0:
                        continue
                    bullpen_ip += float(ip)
                    bullpen_pitches += pitches
                    relief_apps += 1
                    game_had_relief = True
                if game_had_relief:
                    final_games += 1
            except Exception:
                continue

        if bullpen_pitches >= 160 or bullpen_ip >= 6.0:
            flag = "HEAVY"
        elif bullpen_pitches >= 100 or bullpen_ip >= 4.0:
            flag = "ELEVATED"
        elif final_games > 0:
            flag = "LIGHT"
        else:
            flag = "RESTED / NO RECENT RELIEF SAMPLE"

        return {
            "available": True,
            "games": final_games,
            "innings": bullpen_ip,
            "pitches": bullpen_pitches,
            "appearances": relief_apps,
            "flag": flag,
            "window": f"{start.isoformat()} to {end.isoformat()}",
        }
    except Exception:
        return {"available": False}


def _environment_profile(result):
    env = result.get("environment") or {}
    if not env:
        try:
            env = hit_engine.environment(result.get("game_pk")) or {}
        except Exception:
            env = {}
    try:
        model_env = hit_engine.env_adj(env, result.get("venue_name") or "Unknown") or {}
    except Exception:
        model_env = {}
    return env, model_env


def _bullpen_profile(result):
    team_id = _safe_id(result.get("opponent_team_id"))
    starter_id = _safe_id(result.get("starter_id"))
    try:
        bp = hit_engine.bullpen(team_id, starter_id) or {}
    except Exception:
        bp = {}
    try:
        quality = hit_engine.quality(bp, True) or {} if bp else {}
    except Exception:
        quality = {}

    pitcher = result.get("pitcher") or {}
    try:
        exposure = hit_engine.starter_exposure(
            pitcher,
            hit_engine.ab_for_spot(result.get("position")),
        ) or {}
    except Exception:
        exposure = {}

    workload = _recent_bullpen_workload(team_id, _selected_day(), 3)
    return bp, quality, exposure, workload


def _environment_bullpen_strip(result):
    env, model_env = _environment_profile(result)
    bp, bp_quality, exposure, workload = _bullpen_profile(result)

    venue = model_env.get("venue_name") or env.get("venue_name") or result.get("venue_name") or "Venue unavailable"
    temp = model_env.get("temperature")
    condition = str(model_env.get("condition") or env.get("condition") or "Unknown")
    wind = str(model_env.get("wind") or env.get("wind") or "Unknown")
    roof = str(model_env.get("roof_type") or env.get("roof_type") or "Unknown")
    grade = str(model_env.get("grade") or "Unavailable")

    env_bits = [escape(str(venue))]
    if temp is not None:
        env_bits.append(f"{_fmt(temp, 0)}°F")
    if condition and condition.lower() != "unknown":
        env_bits.append(escape(condition))
    if wind and wind.lower() != "unknown":
        env_bits.append(escape(wind))
    if roof and roof.lower() != "unknown":
        env_bits.append(f"Roof {escape(roof)}")

    adjustment_bits = []
    if model_env.get("park_adjustment") is not None:
        adjustment_bits.append(f"V13 park adj {_pct(model_env.get('park_adjustment'), 1, True)}")
    if model_env.get("temperature_adjustment") is not None:
        adjustment_bits.append(f"temp {_pct(model_env.get('temperature_adjustment'), 1, True)}")
    if model_env.get("wind_adjustment") is not None:
        adjustment_bits.append(f"wind {_pct(model_env.get('wind_adjustment'), 1, True)}")
    if model_env.get("total_adjustment") is not None:
        adjustment_bits.append(f"combined {_pct(model_env.get('total_adjustment'), 1, True)}")

    if bp:
        bp_bits = [
            f"ERA {_fmt(bp.get('era'))}",
            f"WHIP {_fmt(bp.get('whip'))}",
        ]
        if bp.get("k9") is not None:
            bp_bits.append(f"K/9 {_fmt(bp.get('k9'), 1)}")
        if bp.get("reliever_count") is not None:
            bp_bits.append(f"{int(bp.get('reliever_count') or 0)} active RP")
        difficulty = bp_quality.get("difficulty")
        if difficulty:
            bp_bits.append(f"V13 difficulty {escape(str(difficulty))}")
        bp_text = " • ".join(bp_bits)
    else:
        bp_text = "Active-reliever aggregate unavailable — no bullpen stats invented"

    exposure_bits = []
    if exposure.get("starter_share") is not None:
        exposure_bits.append(f"Starter {_pct(exposure.get('starter_share'))}")
        exposure_bits.append(f"Bullpen {_pct(1.0 - float(exposure.get('starter_share')))}")
    if exposure.get("starter_ip") is not None:
        exposure_bits.append(f"SP expected IP {_fmt(exposure.get('starter_ip'), 1)}")
    exposure_text = " • ".join(exposure_bits) if exposure_bits else "Starter/bullpen exposure unavailable"

    if workload.get("available"):
        workload_text = (
            f"3-day relief workload: {int(workload.get('pitches') or 0)} pitches • "
            f"{_fmt(workload.get('innings'), 1)} IP • {int(workload.get('appearances') or 0)} relief apps • "
            f"{escape(str(workload.get('flag') or '—'))}"
        )
    else:
        workload_text = "3-day relief workload unavailable — no fatigue value inferred"

    env_line = " • ".join(env_bits)
    adj_line = " • ".join(adjustment_bits) if adjustment_bits else "V13 environment adjustment unavailable"

    return (
        '<div class="hit138-context">'
        '<div class="hit138-head">STEP 5 • PARK / WEATHER + BULLPEN ENVIRONMENT</div>'
        f'<div class="hit138-env"><b>{escape(grade)}</b> • {env_line}</div>'
        f'<div class="hit138-sub">{adj_line}</div>'
        '<div class="hit138-divider"></div>'
        f'<div class="hit138-bp"><b>Opponent bullpen</b> • {bp_text}</div>'
        f'<div class="hit138-sub">{exposure_text}</div>'
        f'<div class="hit138-work">{workload_text}</div>'
        '<div class="hit138-note">AVG/OPS allowed are displayed only when a verified relief-only source supplies them; this layer never synthesizes them.</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hit138-context{margin:7px 0 5px;padding:9px 10px;border:1px solid #39523f;background:linear-gradient(145deg,#0c1a17,#08151b);border-radius:12px}
.hit138-head{font-size:.44rem;letter-spacing:.08em;color:#8de59c;font-weight:950;text-transform:uppercase}
.hit138-env,.hit138-bp{font-size:.58rem;color:#edf8ef;line-height:1.5;margin-top:3px}.hit138-env b{color:#9af0aa}.hit138-bp b{color:#d9f6df}
.hit138-sub{font-size:.49rem;color:#93aa9a;line-height:1.45;margin-top:2px}.hit138-work{font-size:.50rem;color:#d4c993;line-height:1.45;margin-top:3px}.hit138-note{font-size:.43rem;color:#70837a;line-height:1.4;margin-top:3px}
.hit138-divider{height:1px;background:#233a31;margin:6px 0 4px}
</style>
"""

if "hit138-context" not in core.HIT_CSS:
    core.HIT_CSS = core.HIT_CSS + _EXTRA_CSS


def _pick_html_v138(result, rank):
    """Inject Step 5 before the probability block; preserve V13.7 card otherwise."""
    html = _BASE_PICK_HTML(result, rank)
    marker = '<div class="hit-pick-prob">'
    strip = _environment_bullpen_strip(result)
    if marker in html:
        return html.replace(marker, strip + marker, 1)
    return html + strip


# Replace only the active V13.3 card renderer. All scanner/model functions remain native.
active._pick_html = _pick_html_v138


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.caption(
        "🌦️ Hit UI V13.8 • Step 5 park/weather + bullpen exposure/workload ACTIVE • "
        "context display only • Hit Model V13 unchanged"
    )
    return active.render_hit_hub(games_df, section_header, status_info, team_logo, h)
