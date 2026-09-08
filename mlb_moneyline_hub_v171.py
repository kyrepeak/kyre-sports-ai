"""MLB Moneyline V17.1 — Step 5L live-game compatibility bridge.

This additive wrapper keeps permanently frozen pregame Moneyline V17.0 intact
and adds an in-game route for official MLB games that are actively playing.

Pregame mode:
- delegates unchanged to frozen mlb_moneyline_hub_v170.

Live mode:
- exact official MLB gamePk matching only,
- fresh MLB schedule status detection,
- API-first live-state and live-market bridges when available,
- existing state-aware V19 live simulation for current score/inning/outs/bases,
  current batter/pitcher, walk-off logic and extra-inning handling.

Final games are never presented as live betting opportunities. No frozen Step 1-5
files or pregame Moneyline probability math are modified.
"""
from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st

MODEL_VERSION = "V17.1 • MONEYLINE STEP 5L • LIVE IN-GAME SUPPORT"
FROZEN_MONEYLINE_PRESENTATION = "mlb_moneyline_hub_v170"
FROZEN_ROUTER_TARGET = "streamlit_memory_lazy_router_v8"
MLB_API = "https://statsapi.mlb.com/api/v1"

_LIVE_CSS = r"""
<style>
.ml171-livebadge{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;border:1px solid rgba(255,76,76,.35);border-radius:13px;padding:9px 11px;margin:0 0 10px;background:linear-gradient(145deg,rgba(46,9,12,.93),rgba(10,18,28,.96))}
.ml171-livebadge b{color:#ff9f9f;font-size:.61rem;letter-spacing:.07em;text-transform:uppercase}
.ml171-livebadge span{color:#aebbc4;font-size:.48rem;font-weight:800}
.ml171-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#ff3d3d;box-shadow:0 0 0 4px rgba(255,61,61,.12);margin-right:5px}
.ml171-health{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:8px}.ml171-pill{display:inline-flex;border:1px solid #3d4c58;border-radius:999px;padding:4px 7px;background:#121c24;color:#c4d0d8;font-size:.46rem;font-weight:850}.ml171-pill.live{border-color:#7a3638;background:#311517;color:#ffaaa7}.ml171-pill.final{border-color:#555f65;background:#20272c;color:#ccd5da}.ml171-pill.pre{border-color:#5a6135;background:#242711;color:#e3e78d}
</style>
"""


def _safe_int(value: Any) -> int | None:
    try:
        out = int(float(value))
        return out if out > 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _json(url: str) -> dict[str, Any] | None:
    try:
        req = Request(url, headers={"User-Agent": "KyreSportsAI/17.1"})
        with urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _state_label(status: Any) -> str:
    text = str(status or "").strip().lower()
    if any(x in text for x in ("final", "game over", "completed")):
        return "FINAL"
    if any(x in text for x in ("delayed", "suspended")):
        return "DELAYED"
    if any(x in text for x in (
        "in progress",
        "manager challenge",
        "review",
        "warmup",
        "mid ",
        "top ",
        "bottom ",
    )):
        return "LIVE"
    return "PREGAME"


def _day_from_games(games_df) -> str:
    if games_df is not None and not getattr(games_df, "empty", True):
        try:
            value = str(games_df.iloc[0].get("game_date") or "")[:10]
            if len(value) == 10:
                return value
        except Exception:
            pass
    return datetime.now().date().isoformat()


@st.cache_data(ttl=10, show_spinner=False)
def _official_status_snapshot(day: str, game_pks: tuple[int, ...]) -> dict[int, dict[str, Any]]:
    """One-call official MLB status snapshot keyed only by exact gamePk."""
    allowed = {int(pk) for pk in game_pks if _safe_int(pk)}
    if not allowed:
        return {}
    query = urlencode({
        "sportId": 1,
        "date": str(day)[:10],
        "hydrate": "linescore",
    })
    data = _json(f"{MLB_API}/schedule?{query}")
    if not data:
        return {}

    out: dict[int, dict[str, Any]] = {}
    for date_block in data.get("dates") or []:
        for game in date_block.get("games") or []:
            pk = _safe_int(game.get("gamePk"))
            if pk is None or pk not in allowed:
                continue
            status = game.get("status") or {}
            teams = game.get("teams") or {}
            away = teams.get("away") or {}
            home = teams.get("home") or {}
            linescore = game.get("linescore") or {}
            out[pk] = {
                "game_pk": pk,
                "status": str(status.get("detailedState") or status.get("abstractGameState") or "Unknown"),
                "state": _state_label(status.get("detailedState") or status.get("abstractGameState")),
                "away_runs": int(away.get("score") or 0),
                "home_runs": int(home.get("score") or 0),
                "inning": linescore.get("currentInningOrdinal") or linescore.get("currentInning"),
                "inning_state": linescore.get("inningState") or "",
            }
    return out


def _game_pks(games_df) -> tuple[int, ...]:
    if games_df is None or getattr(games_df, "empty", True) or "game_pk" not in games_df.columns:
        return ()
    out: list[int] = []
    for value in games_df["game_pk"].tolist():
        pk = _safe_int(value)
        if pk is not None:
            out.append(pk)
    return tuple(sorted(set(out)))


def _live_subset(games_df, snapshot: Mapping[int, Mapping[str, Any]]):
    """Return exact-ID rows that are LIVE or DELAYED; finals are excluded."""
    if games_df is None or getattr(games_df, "empty", True):
        return pd.DataFrame(columns=getattr(games_df, "columns", []))
    live_ids = {
        int(pk)
        for pk, item in snapshot.items()
        if str((item or {}).get("state")) in {"LIVE", "DELAYED"}
    }
    if not live_ids or "game_pk" not in games_df.columns:
        return games_df.iloc[0:0].copy()

    ids = pd.to_numeric(games_df["game_pk"], errors="coerce")
    frame = games_df[ids.isin(live_ids)].copy()
    if frame.empty:
        return frame

    for idx, row in frame.iterrows():
        pk = _safe_int(row.get("game_pk"))
        item = dict(snapshot.get(pk) or {})
        if not item:
            continue
        frame.at[idx, "status"] = item.get("status")
    return frame.reset_index(drop=True)


def _counts(snapshot: Mapping[int, Mapping[str, Any]]) -> dict[str, int]:
    counts = {"LIVE": 0, "DELAYED": 0, "PREGAME": 0, "FINAL": 0}
    for item in snapshot.values():
        state = str((item or {}).get("state") or "PREGAME")
        if state not in counts:
            state = "PREGAME"
        counts[state] += 1
    return counts


def _install_live_bridges() -> dict[str, bool]:
    result = {"state_bridge": False, "market_bridge": False}
    try:
        import mlb_step9c_live_state_consumer_v1 as state_bridge
        state_bridge.install_step9c_live_state_consumer()
        result["state_bridge"] = True
    except Exception:
        pass
    try:
        import mlb_step9e_live_market_consumer_v1 as market_bridge
        market_bridge.install_step9e_live_market_consumer()
        result["market_bridge"] = True
    except Exception:
        pass
    return result


def _render_health(counts: Mapping[str, int]) -> None:
    st.markdown(
        '<div class="ml171-health">'
        f'<span class="ml171-pill live">🔴 {int(counts.get("LIVE",0))} LIVE</span>'
        f'<span class="ml171-pill live">⚠️ {int(counts.get("DELAYED",0))} DELAYED</span>'
        f'<span class="ml171-pill pre">⏳ {int(counts.get("PREGAME",0))} PREGAME</span>'
        f'<span class="ml171-pill final">🏁 {int(counts.get("FINAL",0))} FINAL</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def _render_pregame(games_df, section_header, status_info, team_logo, h):
    import mlb_moneyline_hub_v170 as pregame
    return pregame.render_moneyline_hub(
        games_df,
        section_header,
        status_info,
        team_logo,
        h,
    )


def _render_live(live_games, section_header, status_info, team_logo, h):
    bridges = _install_live_bridges()
    if not bridges["state_bridge"]:
        st.caption("Live state API bridge unavailable; falling back to the existing direct official MLB live feed.")
    if not bridges["market_bridge"]:
        st.caption("Live market API bridge unavailable; sportsbook pricing may require the existing fallback connection.")

    # V19.2.2 owns the current state-aware live simulation and market dashboard.
    # Step 9C/9E patch its transport layers before render.
    import live_game_hub_v1921 as live
    return live.render_live_hub(
        live_games,
        section_header,
        status_info,
        team_logo,
        h,
    )


def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
    """Render pregame V17.0 or exact-ID in-game Moneyline mode."""
    st.markdown(_LIVE_CSS, unsafe_allow_html=True)

    pks = _game_pks(games_df)
    day = _day_from_games(games_df)
    snapshot = _official_status_snapshot(day, pks)
    counts = _counts(snapshot)
    active = int(counts["LIVE"]) + int(counts["DELAYED"])

    st.markdown(
        '<div class="ml171-livebadge">'
        '<b><span class="ml171-dot"></span>Moneyline Step 5L • Live Game Support</b>'
        '<span>Pregame V17.0 remains frozen • live mode uses exact official MLB game IDs</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    _render_health(counts)

    if active <= 0:
        st.caption("No active MLB games on this selected slate — Moneyline stays in frozen pregame mode.")
        return _render_pregame(games_df, section_header, status_info, team_logo, h)

    mode = st.radio(
        "Moneyline mode",
        ["🔴 LIVE IN-GAME", "⏳ PREGAME"],
        index=0,
        horizontal=True,
        key="ml171_moneyline_mode",
    )

    if mode == "⏳ PREGAME":
        return _render_pregame(games_df, section_header, status_info, team_logo, h)

    live_games = _live_subset(games_df, snapshot)
    if live_games.empty:
        st.warning("Official live status was detected, but exact gamePk rows could not be matched. Live mode failed closed.")
        return

    st.caption(
        "Live mode refreshes the current score, inning, outs, bases, batter and pitcher, "
        "then uses the existing V19 state-aware simulation for in-game Moneyline probabilities."
    )
    return _render_live(live_games, section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_MONEYLINE_PRESENTATION",
    "FROZEN_ROUTER_TARGET",
    "MLB_API",
    "MODEL_VERSION",
    "_counts",
    "_game_pks",
    "_live_subset",
    "_official_status_snapshot",
    "_state_label",
    "render_moneyline_hub",
]
