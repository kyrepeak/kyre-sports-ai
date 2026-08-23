"""WNBA PRA V3.6.10 — Step-5 presentation performance audit/repair.

Presentation/performance-only wrapper over V3.6.9. Keeps the exact V2.8 Step-5
candidate logic, eligibility gate and PRA ranking while eliminating an avoidable
identity-side rebuild of the full Step-6 projection frame.

V3.6.9 resolved headshots through cards._identity_maps(), which calls the Step-6
visual _player_id_lookup(); that helper rebuilds base._projection_frame(day) and
therefore repeats role_projection_for_game across the slate only to recover player
IDs already present on the Step-5 rows. V3.6.10 carries those existing PLAYER_ID
and verified slate team IDs into the display payload and constructs image/logo URLs
from them directly. The existing verified Clark/Mitchell ESPN-ID fallback remains.

Defense and H2H remain board-level lookups, not per-card calls. Their provider work
continues to use the existing cached context/season schedule/game-summary helpers.
No projection, availability, minutes/usage math, sportsbook, qualification,
Monte Carlo, final-ready, ranking, selection or provider/cache TTL logic changes.
"""
from __future__ import annotations

from html import escape
import math

import streamlit as st

import wnba_pra_step5_layout_v369 as prior

v28 = prior.v28
role = v28.role
cards = prior.cards
defense_layer = prior.defense_layer
history_layer = prior.history_layer

MODEL_VERSION = "PRA V3.6.10 • STEP-5 PERFORMANCE REPAIR • MODEL PRESERVED"


def _int_id(value) -> int:
    try:
        x = int(float(value))
        return x if x > 0 else 0
    except Exception:
        return 0


def _adjusted_top5_v3610(schedule, stats):
    """Exact V3.6.8/V2.8 selection and sort, plus existing IDs for display only."""
    rows = []
    if schedule is None or schedule.empty:
        return rows

    for _, game in schedule.iterrows():
        result = role.role_projection_for_game(game, stats)
        away_id = _int_id(game.get("away_team_id"))
        home_id = _int_id(game.get("home_team_id"))

        for tid, frame in result.get("teams", {}).items():
            if frame is None or frame.empty:
                continue
            team_id = _int_id(tid)
            is_away = team_id == away_id
            opponent = game.get("home_team") if is_away else game.get("away_team")
            opponent_id = home_id if is_away else away_id
            team_tri = str(
                game.get("away_tricode") if is_away else game.get("home_tricode") or ""
            )
            opp_tri = str(
                game.get("home_tricode") if is_away else game.get("away_tricode") or ""
            )

            for _, p in frame.iterrows():
                status = str(p.get("DESIGNATION") or "NO DESIGNATION").upper()
                # Exact V2.8 eligibility gate.
                if status in role.OUT_STATUSES or float(p.get("PROJ_MIN") or 0) < 15:
                    continue

                rows.append(
                    {
                        "name": str(p.get("PLAYER_NAME") or "Player"),
                        "team": str(p.get("TEAM_ABBREVIATION") or p.get("TEAM_NAME") or ""),
                        "opponent": str(opponent or "—"),
                        "min": float(p.get("PROJ_MIN") or 0),
                        "usg": p.get("PROJ_USG"),
                        "p": float(p.get("PROJ_PTS") or 0),
                        "r": float(p.get("PROJ_REB") or 0),
                        "a": float(p.get("PROJ_AST") or 0),
                        "pra": float(p.get("PROJ_PRA") or 0),
                        "status": status,
                        "starter": bool(p.get("STARTER_CONFIRMED")),
                        # Existing V2.8 projection-path fields.
                        "source_pra": p.get("PRA"),
                        "base_min": p.get("BASE_MIN"),
                        "proj_min": p.get("PROJ_MIN"),
                        "min_delta": p.get("MIN_DELTA"),
                        "base_usg": p.get("BASE_USG"),
                        "proj_usg": p.get("PROJ_USG"),
                        "role_delta": p.get("ROLE_DELTA_PCT"),
                        # Existing identity fields carried only for rendering.
                        "player_id": p.get("PLAYER_ID"),
                        "player_id_source": p.get("PLAYER_ID_SOURCE"),
                        "team_id": team_id,
                        "opponent_id": opponent_id,
                        "team_tricode": team_tri,
                        "opponent_tricode": opp_tri,
                    }
                )

    # Exact V2.8 rank key/truncation.
    return sorted(rows, key=lambda x: x["pra"], reverse=True)[:5]


def _verified_fallback_id(name: str) -> int:
    """Reuse the already-approved V3.6.5 display-only ESPN fallbacks."""
    try:
        mapping = defense_layer.identity._VERIFIED_ESPN_PLAYER_IDS
        return _int_id(mapping.get(str(name or "")))
    except Exception:
        return 0


def _headshot_id(p: dict) -> int:
    pid = _int_id(p.get("player_id"))
    return pid or _verified_fallback_id(str(p.get("name") or ""))


def _logo_meta(team_id, label: str, tricode: str) -> dict:
    """Build display metadata from verified slate IDs; logo_url is a URL helper."""
    tid = _int_id(team_id)
    try:
        logo = cards.visual.schedule_v25.logo_url(tid) if tid else ""
    except Exception:
        logo = ""
    return {
        "team_id": tid,
        "name": str(label or ""),
        "tricode": str(tricode or label or "TEAM")[:4].upper(),
        "logo": str(logo or ""),
    }


def _render_top5_v3610(picks):
    """V3.6.9 compact cards with direct Step-5/slate identity reuse."""
    if not picks:
        st.markdown(
            '<div class="w2-empty">No eligible Step 5 projections are available.</div>',
            unsafe_allow_html=True,
        )
        return

    day = st.session_state.get("wnba_pra_v2_date")

    # PERFORMANCE GUARDRAIL: one defense build and one H2H build for the board.
    # No identity-map call here: that old path rebuilt the Step-6 projection frame.
    defenses = defense_layer._opponent_context_map(day)
    histories = history_layer._board_history_map(day, picks, defenses)
    rendered = []

    for i, p in enumerate(picks, 1):
        first = " first" if i == 1 else ""
        status = (
            "STARTER"
            if p["starter"]
            else p["status"]
            if p["status"] != "NO DESIGNATION"
            else "ACTIVE"
        )
        name = str(p.get("name") or "Player")
        team = str(p.get("team") or "")
        opponent = str(p.get("opponent") or "")

        pid = _headshot_id(p)
        tm = _logo_meta(p.get("team_id"), team, str(p.get("team_tricode") or team))
        om = _logo_meta(
            p.get("opponent_id"), opponent, str(p.get("opponent_tricode") or opponent)
        )
        defense = defenses.get(defense_layer._norm(opponent), {})
        history = histories.get(cards._player_key(name), {})

        headshot = cards._headshot_html(pid, name)
        team_logo = cards._logo_html(tm, team, f"{team} logo")
        opp_logo = cards._logo_html(om, opponent, f"{opponent} logo")

        rendered.append(
            f'<div class="w369-card{first}">'
            '<div class="w369-eyebrow">'
            f'<span>#{i} STEP-5 PRA</span>'
            '<div class="w369-layerchips">'
            '<span class="w369-chip">ID</span><span class="w369-chip">DEF</span>'
            '<span class="w369-chip">H2H</span><span class="w369-chip">PATH</span>'
            '</div></div>'
            '<div class="w369-hero">'
            f'{headshot}'
            '<div class="w369-hero-main">'
            f'<div class="w28-name" style="margin-top:0">{escape(name)}</div>'
            '<div class="w369-match">'
            f'{team_logo}<span style="color:#8da3b8;font-size:.45rem;font-weight:800">vs</span>{opp_logo}'
            '</div>'
            f'<div class="w369-meta">{escape(team)} vs {escape(opponent)} • {escape(status)} • {p["min"]:.1f} MIN</div>'
            '</div></div>'
            '<div class="w369-scoreline">'
            f'<div class="w369-pra">{p["pra"]:.1f}<span>Projected PRA</span></div>'
            '</div>'
            '<div class="w369-split">'
            f'<div><span>PTS</span><b>{p["p"]:.1f}</b></div>'
            f'<div><span>REB</span><b>{p["r"]:.1f}</b></div>'
            f'<div><span>AST</span><b>{p["a"]:.1f}</b></div>'
            f'<div><span>USG</span><b>{v28._fmt(p["usg"],1)}</b></div>'
            '</div>'
            f'{prior._compact_defense_box(defense, opponent)}'
            f'{prior._compact_history_box(history, opponent)}'
            f'{prior._compact_path_box(p)}'
            '</div>'
        )

    st.markdown(
        prior._LAYOUT_CSS
        + '<div class="w23-summary w369-board">'
        '<div class="w23-title">🏆 V2.8 Minutes + Role PRA — Top 5</div>'
        '<div class="w23-sub">Same Step-5 ranking/projections and compact layout. Identity now reuses existing Step-5/slate IDs instead of rebuilding the Step-6 projection frame. Defense, H2H and path remain presentation-only.</div>'
        f'<div class="w28-topgrid">{"".join(rendered)}</div>'
        '<div class="w369-boardnote">'
        '<b>⚡ Performance guardrail:</b> player/team identity is reused from the current Step-5/slate payload; no duplicate Step-6 projection rebuild is launched for headshots/logos. '
        'Defense is built once per board. H2H dedupes shared game IDs and reuses cached ESPN season/game-summary helpers. '
        '<b>Model guardrail:</b> projection, ranking, qualification and Monte Carlo math are unchanged.'
        '</div></div>',
        unsafe_allow_html=True,
    )


def _install_overrides():
    # V3.6.10 adds only display payload IDs + renderer; selection/rank behavior is identical.
    v28._adjusted_top5 = _adjusted_top5_v3610
    v28._render_top5 = _render_top5_v3610
    cards._render_top5 = _render_top5_v3610
    cards.v28._render_top5 = _render_top5_v3610
    defense_layer.cards._render_top5 = _render_top5_v3610
    defense_layer.cards.v28._render_top5 = _render_top5_v3610


def install():
    """Install V3.6.9 stack once, then apply performance-only overrides."""
    prior.install()
    _install_overrides()


def begin_render():
    """Install upstream presentation stack without repeating its install pass."""
    prior.begin_render()
    _install_overrides()


__all__ = ["MODEL_VERSION", "begin_render", "install"]
