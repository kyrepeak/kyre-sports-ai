"""MLB H+R+RBI V1.0.7 — Step 5 park/weather + bullpen environment.

Presentation/audit wrapper around verified H+R+RBI V1.0.6. Strongest 2+ cards
retain Steps 1-4 and add a fail-safe environment layer:
- verified MLB venue/weather/roof context,
- the EXISTING V1.0 park/weather adjustment already used by the H+R+RBI model,
- opponent active-reliever aggregate (ERA/WHIP/K9/hand mix when available),
- expected starter-vs-bullpen plate-appearance exposure,
- recent 3-day bullpen workload from completed MLB box scores.

Important model firewall: Step 5 does not add a new adjustment to the model. It
only exposes the environment adjustment already present in H+R+RBI V1.0 plus
read-only bullpen context. Candidate selection, H/R/RBI component rates, Monte
Carlo, threshold probabilities, ranking, confidence and fair odds are unchanged.
Every optional display lookup is fail-safe and cannot suppress the Top-5 card.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from html import escape

import requests
import streamlit as st

import engine as hit_engine
import mlb_hrrbi_hub_v106 as prior

MODEL_VERSION = "H+R+RBI V1.0.7"
base = prior.base
core = prior.core
MLB_API = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "Mozilla/5.0 KyreSportsAI/1.0"}


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


def _fmt(value, digits=2):
    x = _sf(value, None)
    return f"{x:.{digits}f}" if x is not None else "—"


def _pct(value, digits=1, signed=False):
    x = _sf(value, None)
    if x is None:
        return "—"
    n = x * 100.0
    return f"{n:+.{digits}f}%" if signed else f"{n:.{digits}f}%"


def _environment_grade(model_env):
    explicit = str((model_env or {}).get("grade") or "").strip()
    if explicit and explicit.lower() not in {"unknown", "unavailable", "none"}:
        return explicit.upper()
    adj = _sf((model_env or {}).get("total_adjustment"), None)
    if adj is None:
        return "DATA LIMITED"
    if adj >= 0.025:
        return "HITTER FRIENDLY"
    if adj <= -0.025:
        return "PITCHER FRIENDLY"
    return "NEUTRAL"


@st.cache_data(ttl=600, show_spinner=False)
def _recent_bullpen_workload(team_id, slate_day, lookback_days=3):
    """Completed-game relief workload before the selected slate; display only."""
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

        bullpen_ip = 0.0
        bullpen_pitches = 0
        relief_apps = 0
        relief_games = 0

        for game in games:
            status = game.get("status") or {}
            detailed = str(status.get("detailedState") or "").lower()
            abstract = str(status.get("abstractGameState") or "").lower()
            if abstract != "final" and not any(x in detailed for x in ("final", "game over", "completed")):
                continue

            away_id = _safe_id((((game.get("teams") or {}).get("away") or {}).get("team") or {}).get("id"))
            home_id = _safe_id((((game.get("teams") or {}).get("home") or {}).get("team") or {}).get("id"))
            side = "away" if away_id == tid else "home" if home_id == tid else None
            game_pk = _safe_id(game.get("gamePk"))
            if side is None or game_pk is None:
                continue

            try:
                feed = hit_engine.game_feed(game_pk)
                team_box = (((feed.get("liveData") or {}).get("boxscore") or {}).get("teams") or {}).get(side) or {}
                pitcher_ids = [_safe_id(x) for x in (team_box.get("pitchers") or [])]
                pitcher_ids = [x for x in pitcher_ids if x is not None]
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
                    starter_id = pitcher_ids[0]

                used_relief = False
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
                    used_relief = True
                if used_relief:
                    relief_games += 1
            except Exception:
                continue

        if bullpen_pitches >= 160 or bullpen_ip >= 6.0:
            flag = "HEAVY"
        elif bullpen_pitches >= 100 or bullpen_ip >= 4.0:
            flag = "ELEVATED"
        elif relief_games > 0:
            flag = "LIGHT"
        else:
            flag = "RESTED / NO RECENT RELIEF SAMPLE"

        return {
            "available": True,
            "innings": bullpen_ip,
            "pitches": bullpen_pitches,
            "appearances": relief_apps,
            "games": relief_games,
            "flag": flag,
        }
    except Exception:
        return {"available": False}


def _environment_profile(result):
    model_env = result.get("environment_model")
    model_env = model_env if isinstance(model_env, dict) else {}
    raw_env = {}
    try:
        raw_env = hit_engine.environment(int(result.get("game_pk"))) or {}
    except Exception:
        raw_env = {}

    # Prefer the exact environment adjustment already computed by H+R+RBI V1.0.
    if not model_env:
        try:
            model_env = hit_engine.env_adj(raw_env, result.get("venue_name") or "Unknown") or {}
        except Exception:
            model_env = {}
    return raw_env, model_env


def _opponent_team_id(result):
    for key in ("opponent_team_id", "opponent_id", "opp_team_id"):
        value = _safe_id(result.get(key))
        if value is not None:
            return value
    return None


def _bullpen_profile(result):
    team_id = _opponent_team_id(result)
    starter_id = _safe_id(result.get("starter_id"))
    try:
        bullpen = hit_engine.bullpen(team_id, starter_id) or {} if team_id else {}
    except Exception:
        bullpen = {}
    try:
        quality = hit_engine.quality(bullpen, True) or {} if bullpen else {}
    except Exception:
        quality = {}
    try:
        exposure = hit_engine.starter_exposure(
            result.get("pitcher") if isinstance(result.get("pitcher"), dict) else {},
            hit_engine.ab_for_spot(result.get("position")),
        ) or {}
    except Exception:
        exposure = {}
    workload = _recent_bullpen_workload(team_id, _selected_day(), 3)
    return bullpen, quality, exposure, workload


def _environment_strip(result):
    raw_env, model_env = _environment_profile(result)
    bullpen, quality, exposure, workload = _bullpen_profile(result)

    venue = (
        model_env.get("venue_name")
        or raw_env.get("venue_name")
        or result.get("venue_name")
        or "Venue unavailable"
    )
    temperature = model_env.get("temperature")
    if temperature is None:
        temperature = raw_env.get("temperature")
    condition = str(model_env.get("condition") or raw_env.get("condition") or "Unknown")
    wind = str(model_env.get("wind") or raw_env.get("wind") or "Unknown")
    roof = str(model_env.get("roof_type") or raw_env.get("roof_type") or "Unknown")
    grade = _environment_grade(model_env)

    env_bits = [str(venue)]
    if temperature is not None:
        env_bits.append(f"{_fmt(temperature, 0)}°F")
    if condition.lower() not in {"unknown", "none", ""}:
        env_bits.append(condition)
    if wind.lower() not in {"unknown", "none", ""}:
        env_bits.append(wind)
    if roof.lower() not in {"unknown", "none", ""}:
        env_bits.append(f"Roof {roof}")

    adj_bits = []
    for key, label in (
        ("park_adjustment", "park"),
        ("temperature_adjustment", "temp"),
        ("wind_adjustment", "wind"),
        ("total_adjustment", "combined"),
    ):
        if model_env.get(key) is not None:
            adj_bits.append(f"{label} {_pct(model_env.get(key), 1, True)}")
    adjustment = " • ".join(adj_bits) if adj_bits else "Existing H+R+RBI environment adjustment unavailable"

    if bullpen:
        bp_bits = [f"ERA {_fmt(bullpen.get('era'))}", f"WHIP {_fmt(bullpen.get('whip'))}"]
        if bullpen.get("k9") is not None:
            bp_bits.append(f"K/9 {_fmt(bullpen.get('k9'), 1)}")
        if bullpen.get("reliever_count") is not None:
            bp_bits.append(f"{int(bullpen.get('reliever_count') or 0)} active RP")
        if quality.get("difficulty"):
            bp_bits.append(f"difficulty {quality.get('difficulty')}")
        bullpen_text = " • ".join(bp_bits)
    else:
        bullpen_text = "Active-reliever aggregate unavailable — nothing inferred"

    exposure_bits = []
    starter_share = _sf(exposure.get("starter_share"), None)
    if starter_share is not None:
        exposure_bits.append(f"Starter {_pct(starter_share)}")
        exposure_bits.append(f"Bullpen {_pct(max(0.0, 1.0 - starter_share))}")
    if exposure.get("starter_ip") is not None:
        exposure_bits.append(f"SP expected IP {_fmt(exposure.get('starter_ip'), 1)}")
    exposure_text = " • ".join(exposure_bits) if exposure_bits else "Starter/bullpen exposure unavailable"

    if workload.get("available"):
        workload_text = (
            f"3-day bullpen workload: {int(workload.get('pitches') or 0)} pitches • "
            f"{_fmt(workload.get('innings'), 1)} IP • "
            f"{int(workload.get('appearances') or 0)} relief apps • {workload.get('flag') or '—'}"
        )
    else:
        workload_text = "3-day bullpen workload unavailable — fatigue not inferred"

    return (
        '<div class="hrr107-env">'
        '<div class="hrr107-head">'
        '<span>STEP 5 • PARK / WEATHER + RUN ENVIRONMENT</span>'
        f'<b>{escape(str(grade))}</b>'
        '</div>'
        f'<div class="hrr107-main">{escape(" • ".join(env_bits))}</div>'
        f'<div class="hrr107-sub">Existing model environment: {escape(adjustment)}</div>'
        '<div class="hrr107-divider"></div>'
        f'<div class="hrr107-main"><strong>Opponent bullpen</strong> • {escape(bullpen_text)}</div>'
        f'<div class="hrr107-sub">{escape(exposure_text)}</div>'
        f'<div class="hrr107-work">{escape(workload_text)}</div>'
        '<div class="hrr107-note">Audit/context only • Step 5 adds no new probability adjustment. The displayed park/weather adjustment is the one already used by H+R+RBI V1.0.</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hrr107-env{margin:7px 0 5px;padding:9px 10px;border:1px solid #355442;background:linear-gradient(145deg,#0a1a17,#08151c);border-radius:12px}
.hrr107-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.hrr107-head span{font-size:.43rem;letter-spacing:.08em;color:#8de59c;font-weight:950;text-transform:uppercase}.hrr107-head b{border:1px solid #326546;background:#0b3124;color:#94efaf;border-radius:999px;padding:3px 7px;font-size:.46rem;white-space:nowrap}
.hrr107-main{font-size:.57rem;color:#edf8ef;line-height:1.5;margin-top:5px}.hrr107-main strong{color:#d9f6df}.hrr107-sub{font-size:.49rem;color:#94aa9b;line-height:1.45;margin-top:2px}.hrr107-work{font-size:.50rem;color:#d7c98e;line-height:1.45;margin-top:4px}.hrr107-note{font-size:.43rem;color:#70847a;line-height:1.4;margin-top:5px}.hrr107-divider{height:1px;background:#244034;margin:7px 0 4px}
.hrr107-step-badge{display:inline-flex;align-items:center;gap:5px;border:1px solid #3b6847;background:#0b2419;color:#9af0aa;border-radius:999px;padding:5px 8px;font-size:.52rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin:0 0 9px}
@media(max-width:700px){.hrr107-head{align-items:flex-start}.hrr107-head b{font-size:.42rem}.hrr107-main{font-size:.54rem}}
</style>
"""

if "hrr107-env" not in base.CSS:
    base.CSS = base.CSS + _EXTRA_CSS


def _card_v107(r, rank, threshold):
    """Verified Steps 1-4 first; Step 5 can never crash or suppress the card."""
    html = prior._card_v106(r, rank, threshold)
    try:
        strip = _environment_strip(r)
        marker = '<div class="hrr-prob">'
        if marker in html and strip:
            return html.replace(marker, strip + marker, 1)
    except Exception:
        pass
    return html


base._card = _card_v107


def render_hrrbi_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(
        '<div class="hrr107-step-badge">🌦️ H+R+RBI V1.0.7 • Steps 1–5 active • park/weather + bullpen context</div>',
        unsafe_allow_html=True,
    )
    return core.render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
