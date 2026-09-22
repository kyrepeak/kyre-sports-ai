"""MLB Matchup Explorer V2 — Step 1 Player + Opportunity Foundation.

This layer starts the redesigned single-player Matchup Intelligence card. Step 1
verifies identity, game context, lineup readiness, opposing starter context and
season sample completeness before later V2 steps are allowed to reason about a
hit probability.

IMPORTANT: Step 1 is data-quality / gating only. It does not change projection,
probability, simulation, calibration, ranking, selection or fair-odds math.
The complete V1 Matchup Explorer remains frozen and accessible as a legacy audit.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_hub_v14 as v14
import mlb_matchup_player_v20 as frozen_detail
import mlb_matchup_player_v22 as clean

VERSION = "MLB Matchup Intelligence V2 Step 1"
V2_INTELLIGENCE_LABEL = "🧠 Matchup Intelligence V2 — new steps"
LEGACY_AUDIT_LABEL = "🧊 Legacy V1 Matchup audit — frozen"
PROBABILITY_IMPACT = "NONE"


def _safe_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except Exception:
        return None


def _present(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return bool(text and text not in {"—", "TBD", "None", "nan"})


def _known_hand(value: Any) -> bool:
    text = str(value or "").strip().upper()
    return text.startswith("L") or text.startswith("R") or text.startswith("S")


def _lineup_points(source: str, valid_slot: bool) -> int:
    text = str(source or "").upper()
    if "CONFIRMED" in text:
        source_points = 15
    elif "PROJECTED" in text:
        source_points = 10
    elif "BENCH" in text or "ACTIVE ROSTER" in text:
        source_points = 2
    else:
        source_points = 0
    return source_points + (10 if valid_slot else 0)


def _quality_score(fields: dict[str, Any]) -> tuple[int, dict[str, tuple[int, int]]]:
    """Return transparent input-completeness score; never a hit probability."""
    identity = 0
    identity += 4 if fields.get("player_id") else 0
    identity += 2 if _present(fields.get("player_name")) else 0
    identity += 2 if _present(fields.get("team")) else 0
    identity += 2 if _present(fields.get("opponent")) else 0

    game = 0
    game += 3 if fields.get("game_pk") else 0
    game += 3 if _present(fields.get("game_date")) else 0
    game += 3 if _present(fields.get("first_pitch")) else 0
    game += 3 if _present(fields.get("venue")) else 0
    game += 3 if _present(fields.get("game_status")) else 0

    slot = _safe_int(fields.get("slot"))
    valid_slot = bool(fields.get("lineup_role")) and slot is not None and 1 <= slot <= 9
    lineup = _lineup_points(str(fields.get("lineup_source") or ""), valid_slot)

    starter = 0
    starter += 6 if _present(fields.get("starter_name")) else 0
    starter += 6 if fields.get("starter_id") else 0
    starter += 4 if _known_hand(fields.get("starter_hand")) else 0
    starter += 4 if _known_hand(fields.get("batter_hand")) else 0

    stat = fields.get("season_stat") or {}
    season = 0
    season += 4 if bool(stat) else 0
    season += 8 if (_safe_int(stat.get("plateAppearances")) or 0) > 0 else 0
    season += 3 if (_safe_int(stat.get("atBats")) or 0) > 0 else 0
    season += 3 if _present(stat.get("avg")) else 0
    season += 2 if (_safe_int(stat.get("gamesPlayed")) or 0) > 0 else 0

    feed = 0
    feed += 3 if bool(fields.get("player_person")) else 0
    feed += 3 if bool(fields.get("starter_person")) else 0
    feed += 2 if _present(fields.get("lineup_source")) else 0
    feed += 2 if str(fields.get("side") or "").lower() in {"home", "away"} else 0

    components = {
        "Identity": (identity, 10),
        "Game context": (game, 15),
        "Lineup readiness": (lineup, 25),
        "Starter + handedness": (starter, 20),
        "Season sample": (season, 20),
        "Official feed completeness": (feed, 10),
    }
    score = sum(v[0] for v in components.values())
    return max(0, min(100, int(score))), components


def _quality_label(score: int) -> str:
    if score >= 90:
        return "ELITE DATA"
    if score >= 80:
        return "STRONG DATA"
    if score >= 65:
        return "USABLE DATA"
    if score >= 50:
        return "PARTIAL DATA"
    return "LOW DATA"


def _build_foundation(games_df) -> dict[str, Any] | None:
    player, row = frozen_detail._selected_player(games_df)
    if not player or row is None:
        return None

    player_id = v14._safe_int(player.get("id"))
    starter_id = v14._safe_int(player.get("opponent_pitcher_id"))
    day = ui._date_str(row)
    try:
        season = int(day[:4])
    except Exception:
        return None

    player_person = ui._person(player_id) if player_id else {}
    starter_person = ui._person(starter_id) if starter_id else {}
    season_stat = ui._season_hitting(player_id, season) if player_id else {}

    batter_hand = str((player_person.get("batSide") or {}).get("code") or (player_person.get("batSide") or {}).get("description") or "—")
    starter_hand = str((starter_person.get("pitchHand") or {}).get("code") or (starter_person.get("pitchHand") or {}).get("description") or "—")

    slot = _safe_int(player.get("slot"))
    lineup_role = bool(player.get("lineup_role"))
    valid_slot = lineup_role and slot is not None and 1 <= slot <= 9
    source = str(player.get("source") or "UNKNOWN")
    source_upper = source.upper()
    confirmed = "CONFIRMED" in source_upper
    projected = "PROJECTED" in source_upper

    fields = {
        "player_id": player_id,
        "player_name": str(player.get("name") or "Hitter"),
        "team": str(player.get("team") or "—"),
        "opponent": str(player.get("opponent") or "—"),
        "game_pk": v14._safe_int(row.get("game_pk")),
        "game_date": day,
        "first_pitch": str(row.get("first_pitch_et") or "—"),
        "venue": str(row.get("venue_name") or "—"),
        "game_status": str(row.get("status") or "—"),
        "lineup_source": source,
        "lineup_role": lineup_role,
        "slot": slot,
        "side": str(player.get("side") or "—"),
        "starter_name": str(player.get("opponent_pitcher") or "TBD"),
        "starter_id": starter_id,
        "starter_hand": starter_hand,
        "batter_hand": batter_hand,
        "season_stat": season_stat,
        "player_person": player_person,
        "starter_person": starter_person,
    }
    score, components = _quality_score(fields)

    pa = _safe_int(season_stat.get("plateAppearances")) or 0
    ab = _safe_int(season_stat.get("atBats")) or 0
    hits = _safe_int(season_stat.get("hits")) or 0
    games = _safe_int(season_stat.get("gamesPlayed")) or 0
    avg = str(season_stat.get("avg") or "—")

    starter_ready = _present(fields["starter_name"]) and bool(starter_id)
    foundation_ready = bool(valid_slot and starter_ready and pa > 0 and score >= 65)
    if confirmed:
        lineup_note = "Confirmed batting order"
    elif projected:
        lineup_note = "Projected batting order • uncertainty stays elevated until official"
    elif lineup_role:
        lineup_note = "Batting-order role present • source status unresolved"
    else:
        lineup_note = "No batting-order slot • later probability steps remain gated"

    pa_basis = "Ready for Step 9 PA model" if valid_slot else "GATED until batting-order slot is available"
    snapshot = datetime.now(ui.ET).isoformat(timespec="seconds")

    return {
        **fields,
        "season": season,
        "confirmed": confirmed,
        "projected": projected,
        "valid_slot": valid_slot,
        "score": score,
        "quality_label": _quality_label(score),
        "components": components,
        "foundation_ready": foundation_ready,
        "lineup_note": lineup_note,
        "pa_basis": pa_basis,
        "season_pa": pa,
        "season_ab": ab,
        "season_hits": hits,
        "season_games": games,
        "season_avg": avg,
        "snapshot": snapshot,
    }


def _esc(value: Any) -> str:
    return ui._esc(value)


def _gate_icon(condition: bool) -> str:
    return "✅" if condition else "⏳"


def _render_step1(games_df) -> None:
    d = _build_foundation(games_df)
    if not d:
        st.warning("Step 1 foundation is waiting for a verified game and player selection.")
        return

    slot_text = f"#{d['slot']}" if d.get("valid_slot") else "—"
    side = str(d.get("side") or "—").upper()
    starter = f"{d['starter_name']} ({d['starter_hand']})"
    ready_badge = "READY" if d.get("foundation_ready") else "PARTIAL"
    comp_text = " • ".join(
        f"{name} {earned}/{maximum}"
        for name, (earned, maximum) in d["components"].items()
    )

    st.markdown(
        f'''<div class="mxv2-step mxv2-step1">
          <div class="mxv2-top">
            <div class="mxv2-kicker">STEP 1 • PLAYER + OPPORTUNITY FOUNDATION</div>
            <div class="mxv2-badge">{d['quality_label']} • {d['score']}/100</div>
          </div>
          <div class="mxv2-lead"><b>{_esc(d['player_name'])}</b> • {_esc(d['team'])} vs {_esc(d['opponent'])}</div>
          <div class="mxv2-status">{_esc(d['lineup_source'])} • batting {slot_text} • {side} • {_esc(ready_badge)}</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row"><b>Identity / game</b> • MLB player {d['player_id'] or '—'} • game {d['game_pk'] or '—'} • {_esc(d['game_date'])} {_esc(d['first_pitch'])} ET • {_esc(d['venue'])} • {_esc(d['game_status'])}</div>
          <div class="mxv2-row"><b>Lineup / opportunity</b> • {_esc(d['lineup_note'])} • {_esc(d['pa_basis'])}</div>
          <div class="mxv2-row"><b>Starter context</b> • {_esc(starter)} • MLB pitcher {d['starter_id'] or '—'} • batter hand {_esc(d['batter_hand'])}</div>
          <div class="mxv2-row"><b>Season sample</b> • {d['season_games']} G • {d['season_pa']} PA • {d['season_ab']} AB • {d['season_hits']} H • AVG {_esc(d['season_avg'])}</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row mxv2-muted"><b>Input completeness</b> • {_esc(comp_text)}</div>
          <div class="mxv2-row mxv2-muted"><b>Snapshot</b> • {_esc(d['snapshot'])} • official MLB-backed fields • probability impact: NONE</div>
        </div>''',
        unsafe_allow_html=True,
    )

    if not d.get("valid_slot"):
        st.warning("Step 1 gate: this player is not currently in a confirmed/projected batting-order slot. Later V2 probability steps must not manufacture a PA expectation.")
    elif d.get("projected"):
        st.info("Step 1 gate: projected lineup is usable for research, but later V2 steps should widen uncertainty until the lineup becomes official.")
    if not d.get("starter_id"):
        st.warning("Step 1 gate: opposing starter identity is incomplete. Starter-specific matchup steps must remain pending.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    """Render V2 Step 1 while preserving the complete V1 model as rollback/audit."""
    snapshot_slot = st.empty()

    with st.expander(V2_INTELLIGENCE_LABEL, expanded=True):
        st.caption("V2 rebuild • new steps will accumulate together in this single-player intelligence panel.")
        _render_step1(games_df)

    original_caption = st.caption
    st.caption = clean._filtered_caption(original_caption)
    try:
        with st.expander(LEGACY_AUDIT_LABEL, expanded=False):
            st.caption("Frozen V1 calculations remain available here while V2 is rebuilt step-by-step.")
            frozen_detail.render_player_layer(
                games_df,
                section_header,
                status_info,
                team_logo,
                h,
            )
    finally:
        st.caption = original_caption

    # Preserve the already-certified V1 summary while V2 steps are developed.
    clean._render_snapshot(snapshot_slot, games_df)


__all__ = [
    "LEGACY_AUDIT_LABEL",
    "PROBABILITY_IMPACT",
    "V2_INTELLIGENCE_LABEL",
    "VERSION",
    "_build_foundation",
    "_quality_score",
    "render_player_layer",
]
