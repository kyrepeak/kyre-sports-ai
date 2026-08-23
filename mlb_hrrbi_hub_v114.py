"""MLB H+R+RBI V1.0.14 — Step 11 verified umpire + strike-zone context.

Presentation/audit wrapper around verified H+R+RBI V1.0.13 Steps 1-10.
Strongest-threshold cards retain every verified layer and add a fail-safe umpire panel:
- official MLB home-plate umpire assignment when published,
- assignment status (CONFIRMED / NOT YET PUBLISHED),
- available umpiring crew context,
- explicit historical-zone data availability state,
- no hitter/pitcher-friendly grade unless verified historical zone data exists.

Important model firewall: MLB's official game feed publishes game officials but does
not provide a complete historical umpire strike-zone tendency dataset through the
existing Kyre Sports AI pipeline. Therefore Step 11 does not invent called-strike,
walk, strikeout, run-environment or zone-width numbers. Until a verified historical
umpire source is connected, zone grade is DATA LIMITED and hitter impact is NEUTRAL
/ NO ADJUSTMENT. No H/R/RBI rate, Monte Carlo probability, ranking, confidence or
fair odds is changed.
"""
from __future__ import annotations

from html import escape

import streamlit as st

import engine as hit_engine
import mlb_hrrbi_hub_v113 as prior

MODEL_VERSION = "H+R+RBI V1.0.14"
base = prior.base
core = prior.core
_BASE_CARD = base._card


def _safe_id(value):
    try:
        if value is None:
            return None
        x = int(float(value))
        return x if x > 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _official_type(row):
    return str((row or {}).get("officialType") or (row or {}).get("type") or "").strip()


def _official_person(row):
    row = row or {}
    official = row.get("official") or row.get("person") or {}
    return {
        "id": _safe_id(official.get("id")),
        "name": str(official.get("fullName") or official.get("name") or "").strip(),
    }


@st.cache_data(ttl=180, show_spinner=False)
def _officials_for_game(game_pk):
    """Read officials from the official MLB live game feed; never infer assignments."""
    pk = _safe_id(game_pk)
    if pk is None:
        return {"available": False, "home_plate": None, "crew": []}
    try:
        feed = hit_engine.game_feed(pk) or {}
    except Exception:
        return {"available": False, "home_plate": None, "crew": []}

    officials = []
    try:
        officials = (((feed.get("liveData") or {}).get("boxscore") or {}).get("officials") or [])
    except Exception:
        officials = []

    if not officials:
        try:
            officials = ((feed.get("gameData") or {}).get("officials") or [])
        except Exception:
            officials = []

    crew = []
    home_plate = None
    for row in officials or []:
        typ = _official_type(row)
        person = _official_person(row)
        if not person.get("name"):
            continue
        item = {"type": typ or "Official", **person}
        crew.append(item)
        key = typ.lower().replace("-", " ")
        if "home" in key and "plate" in key:
            home_plate = item

    return {
        "available": bool(crew),
        "home_plate": home_plate,
        "crew": crew,
    }


def _crew_text(crew):
    items = []
    for row in list(crew or [])[:4]:
        typ = str(row.get("type") or "Official")
        name = str(row.get("name") or "")
        if name:
            items.append(f"{typ}: {name}")
    return " • ".join(items) if items else "Official MLB crew not yet published"


def _umpire_strip(result):
    officials = _officials_for_game(result.get("game_pk"))
    hp = officials.get("home_plate") or {}
    hp_name = str(hp.get("name") or "").strip()

    if hp_name:
        assignment = "CONFIRMED"
        assignment_cls = "confirmed"
        primary = hp_name
        source_line = "Official MLB game feed"
    else:
        assignment = "NOT YET PUBLISHED"
        assignment_cls = "pending"
        primary = "Home-plate umpire unavailable"
        source_line = "MLB has not published a home-plate assignment in the game feed"

    crew_text = _crew_text(officials.get("crew") or [])

    # No verified historical zone source is wired into this production path yet.
    zone_grade = "DATA LIMITED"
    hitter_context = "NEUTRAL • NO ADJUSTMENT"
    zone_line = (
        "Historical called-strike / BB / K / zone-width tendencies are not scored "
        "until a verified umpire-history source is connected"
    )

    return (
        '<div class="hrr114-ump">'
        '<div class="hrr114-head">'
        '<span>STEP 11 • UMPIRE + STRIKE-ZONE CONTEXT</span>'
        f'<b class="{assignment_cls}">{escape(assignment)}</b>'
        '</div>'
        f'<div class="hrr114-main"><strong>Home plate</strong> • {escape(primary)}</div>'
        f'<div class="hrr114-row"><strong>Assignment source</strong> • {escape(source_line)}</div>'
        f'<div class="hrr114-row"><strong>Crew</strong> • {escape(crew_text)}</div>'
        '<div class="hrr114-divider"></div>'
        f'<div class="hrr114-row"><strong>Zone grade</strong> • {escape(zone_grade)}</div>'
        f'<div class="hrr114-row"><strong>Historical tendency status</strong> • {escape(zone_line)}</div>'
        f'<div class="hrr114-impact"><strong>2+ context:</strong> {escape(hitter_context)}</div>'
        '<div class="hrr114-note">Audit/context only • no umpire tendency is inferred from name, reputation or a tiny sample. Step 11 adds no probability adjustment.</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hrr114-ump{margin:7px 0 5px;padding:9px 10px;border:1px solid #4b536a;background:linear-gradient(145deg,#111722,#08131b);border-radius:12px}
.hrr114-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.hrr114-head span{font-size:.43rem;letter-spacing:.08em;color:#b8c7ff;font-weight:950;text-transform:uppercase}.hrr114-head b{border:1px solid #4f5a72;border-radius:999px;padding:3px 7px;font-size:.43rem;white-space:nowrap}.hrr114-head b.confirmed{border-color:#1f6b4f;background:#0a3326;color:#79edb7}.hrr114-head b.pending{border-color:#6d5a18;background:#382f0d;color:#f1d36c}
.hrr114-main{font-size:.55rem;color:#eef2ff;line-height:1.5;margin-top:5px}.hrr114-main strong,.hrr114-row strong{color:#ffffff}.hrr114-row{font-size:.50rem;color:#b6c0d3;line-height:1.48;margin-top:4px}.hrr114-divider{height:1px;background:#30394c;margin:7px 0 4px}.hrr114-impact{font-size:.52rem;color:#e5d18c;line-height:1.45;font-weight:800;margin-top:5px}.hrr114-note{font-size:.43rem;color:#7d879a;line-height:1.4;margin-top:5px}
.hrr114-step-badge{display:inline-flex;align-items:center;gap:5px;border:1px solid #4f5a72;background:#111722;color:#c6d2ff;border-radius:999px;padding:5px 8px;font-size:.52rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin:0 0 9px}
@media(max-width:700px){.hrr114-head{align-items:flex-start}.hrr114-head b{font-size:.40rem}.hrr114-row{font-size:.49rem}}
</style>
"""

if "hrr114-ump" not in base.CSS:
    base.CSS = base.CSS + _EXTRA_CSS


def _card_v114(result, rank, threshold):
    """Verified Steps 1-10 first; Step 11 can never crash or suppress the card."""
    html = _BASE_CARD(result, rank, threshold)
    try:
        strip = _umpire_strip(result)
        marker = '<div class="hrr-prob">'
        if marker in html and strip:
            return html.replace(marker, strip + marker, 1)
    except Exception:
        pass
    return html


base._card = _card_v114


def render_hrrbi_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(
        '<div class="hrr114-step-badge">🧑‍⚖️ H+R+RBI V1.0.14 • Steps 1–11 active • verified umpire assignment context</div>',
        unsafe_allow_html=True,
    )
    return prior.render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
