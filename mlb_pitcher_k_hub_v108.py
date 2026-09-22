"""MLB Pitcher Strikeouts O/U V1.0.8 — Step 1 verified pitcher slate.

Additive Step-1 presentation/verification layer on top of the proven V1.0.7
Pitcher K stack. Projection math, workload model, opponent-K model, sportsbook
parsing, line grading, Monte Carlo and rankings remain unchanged.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import streamlit as st

import mlb_pitcher_k_hub_v107 as v107

engine = v107.engine
MODEL_VERSION = "Pitcher K V1.0.8"

_STEP1_CSS = r"""
<style>
.pk-step1{border:1px solid #2a4f69;background:linear-gradient(145deg,#0c1a29,#08131f);border-radius:18px;padding:15px 16px;margin:12px 0 14px}
.pk-step1-title{color:#fff;font-size:1.05rem;font-weight:1000}
.pk-step1-sub{color:#8fa4b8;font-size:.69rem;line-height:1.55;margin-top:4px}
</style>
"""


def _int_or_none(value):
    try:
        value = int(value)
        return value if value > 0 else None
    except Exception:
        return None


def _starter_slots(games_df):
    rows = []
    if games_df is None or games_df.empty:
        return rows
    for _, game in games_df.iterrows():
        try:
            game_pk = int(game.get("game_pk"))
        except Exception:
            game_pk = None
        for side in ("away", "home"):
            other = "home" if side == "away" else "away"
            pid = _int_or_none(game.get(f"{side}_pitcher_id"))
            name = str(game.get(f"{side}_pitcher") or "").strip()
            rows.append({
                "game_pk": game_pk,
                "player_id": pid,
                "player_name": name or "TBD",
                "team": str(game.get(f"{side}_team") or "").strip(),
                "opponent": str(game.get(f"{other}_team") or "").strip(),
                "first_pitch": game.get("first_pitch_et"),
                "game_status": str(game.get("status") or ""),
                "starter_state": "MLB PROBABLE" if pid else ("NAME ONLY" if name else "TBD"),
            })
    return rows


def _enrich(slots):
    out = [dict(x) for x in slots]
    ids = sorted({int(x["player_id"]) for x in out if x.get("player_id")})
    profiles, errors = {}, {}
    if ids:
        with ThreadPoolExecutor(max_workers=min(8, len(ids))) as pool:
            futs = {pool.submit(engine._pitcher_profile, pid): pid for pid in ids}
            for fut in as_completed(futs):
                pid = futs[fut]
                try:
                    profiles[pid] = fut.result() or {}
                except Exception as exc:
                    errors[pid] = str(exc)
    for row in out:
        p = profiles.get(row.get("player_id")) or {}
        row.update({
            "hand": p.get("hand"),
            "era": p.get("era"),
            "whip": p.get("whip"),
            "k9": p.get("k9"),
            "season_k": p.get("k"),
            "starts": p.get("starts"),
            "profile_ok": bool(p),
            "profile_error": errors.get(row.get("player_id")),
        })
    return out


def _render_step1(games_df, selected):
    st.markdown(_STEP1_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="pk-step1"><div class="pk-step1-title">✅ Step 1 — Verified Pitcher Slate</div>'
        '<div class="pk-step1-sub">Official MLB probable-starter slots for the selected date. '
        'Pitcher identity comes from the MLB schedule feed; ERA, WHIP, K/9, season strikeouts, '
        'starts and handedness come from the same MLB pitcher profile used by the production K engine. '
        'Missing starters remain TBD and are never invented.</div></div>',
        unsafe_allow_html=True,
    )

    rows = _enrich(_starter_slots(games_df))
    total = len(rows)
    listed = sum(1 for x in rows if x.get("player_id"))
    profiles = sum(1 for x in rows if x.get("player_id") and x.get("profile_ok"))
    by_game = {}
    for row in rows:
        by_game.setdefault(row.get("game_pk"), []).append(row)
    complete = sum(
        1 for game_rows in by_game.values()
        if len(game_rows) >= 2 and all(x.get("player_id") for x in game_rows[:2])
    )
    missing = max(total - listed, 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Games", len(by_game))
    c2.metric("Starters listed", f"{listed}/{total}")
    c3.metric("Complete games", f"{complete}/{len(by_game)}")
    c4.metric("Profiles loaded", f"{profiles}/{listed}" if listed else "0/0")

    ready = bool(total and missing == 0 and profiles == listed)
    if ready:
        st.success(f"✅ STEP 1 PASSED • {listed} official probable starters verified for {selected} with season profiles loaded.")
    elif total:
        st.warning(
            f"⚠️ STEP 1 CHECK • {listed}/{total} starter slots currently have an official MLB probable pitcher; "
            f"{missing} slot(s) remain TBD. Existing verified starters stay usable, but missing pitchers are not modeled."
        )
    else:
        st.error("Step 1 could not build starter slots from the verified MLB slate.")
        return

    table = []
    for row in rows:
        hand = str(row.get("hand") or "").upper()
        table.append({
            "Pitcher": row.get("player_name") or "TBD",
            "Team": row.get("team") or "—",
            "Opponent": row.get("opponent") or "—",
            "Hand": f"{hand}HP" if hand in {"R", "L"} else "—",
            "Starter status": row.get("starter_state") or "TBD",
            "First pitch": row.get("first_pitch") or "—",
            "ERA": round(float(row["era"]), 2) if row.get("era") is not None else None,
            "WHIP": round(float(row["whip"]), 2) if row.get("whip") is not None else None,
            "K/9": round(float(row["k9"]), 1) if row.get("k9") is not None else None,
            "Season K": int(round(float(row["season_k"]))) if row.get("season_k") is not None else None,
            "Starts": int(row["starts"]) if row.get("starts") is not None else None,
        })
    st.dataframe(pd.DataFrame(table), hide_index=True, use_container_width=True)
    st.caption(
        "Starter status uses MLB's probable-pitcher feed. Pregame probable starters are not mislabeled as confirmed official starts."
    )
    st.session_state["pk108_step1_rows"] = rows
    st.session_state["pk108_step1_ready"] = ready


def render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h):
    # Preload the same verified date-scope slate so Step 1 can be injected directly
    # beneath the existing hero without replacing any V1.0.7 renderer/model behavior.
    selected = engine.schedule.current_selected_date()
    try:
        fresh, _diag = engine.schedule.games_for_date_with_diagnostics(selected)
    except Exception:
        fresh = games_df
    step_games = fresh if fresh is not None and not fresh.empty else games_df

    original_markdown = st.markdown
    injected = {"done": False}

    def _markdown_with_step1(body, *args, **kwargs):
        text = str(body or "")
        if "pk-hero" in text and "Pitcher Strikeouts O/U" in text:
            text = text.replace("Pitcher Strikeouts O/U — V1.0.1", "Pitcher Strikeouts O/U — V1.0.8")
            result = original_markdown(text, *args, **kwargs)
            if not injected["done"]:
                injected["done"] = True
                _render_step1(step_games, selected)
            return result
        return original_markdown(body, *args, **kwargs)

    st.markdown = _markdown_with_step1
    try:
        return v107.render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        st.markdown = original_markdown
