"""CFB Over/Under Clean Page V18 — live market-connected threshold page.

Additive Step 4 wrapper over permanently frozen Clean Page V17.

Frozen V17 rendering helpers and frozen Steps 3-12 model engines are reused
unchanged. This page only:
- reads the production Step 3 CFB odds endpoint through Market Adapter V1;
- attaches lines by official ESPN event ID;
- auto-fills the current FanDuel game total as the analysis threshold;
- shows timestamped sportsbook context;
- gives each full-slate row its own current market total.

Market data never changes the frozen projection formula. Projection weight stays
0%; the market total is a comparison/selection threshold only.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_over_under_clean_page_v17 as frozen_page
import cfb_over_under_market_adapter_v1 as market_adapter
import cfb_schedule_v6_runtime_snapshot as schedule_v6

MODEL_VERSION = "CFB O/U CLEAN PAGE V18 • LIVE ODDS THRESHOLD"
MARKET = "Over/Under"
FROZEN_PAGE = "cfb_over_under_clean_page_v17"
FROZEN_RUNTIME_SLATE = "cfb_over_under_slate_v14_runtime"
ACTIVE_SCHEDULE = "cfb_schedule_v6_runtime_snapshot"
_ET = ZoneInfo("America/New_York")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _market_caption(
    game: Mapping[str, Any],
    market_diag: Mapping[str, Any],
) -> str:
    line = market_adapter.market_line(game)
    if line is None:
        error = _clean(market_diag.get("error"))
        detail = f" • {escape(error)}" if error else ""
        return (
            "🟡 LIVE MARKET LINE UNAVAILABLE — manual analysis threshold remains "
            "available; frozen projection math is unchanged."
            + detail
        )
    sportsbook = _clean(game.get("market_sportsbook")) or "Sportsbook"
    status = _clean(game.get("market_status")) or "active"
    updated = _clean(game.get("market_updated_at_utc")) or "timestamp unavailable"
    return (
        f"🟢 LIVE {escape(sportsbook.upper())} GAME TOTAL: "
        f"<b>{line:.1f}</b> • {escape(status)} • updated {escape(updated)} "
        "• market projection weight <b>0%</b>"
    )


def _line_board(
    games: list[Mapping[str, Any]],
    selected_identity: str,
    selected_line: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for game in games:
        identity = _clean(game.get("identity_key") or game.get("game_id"))
        live_line = market_adapter.market_line(game)
        analysis_line: float | None
        if identity == selected_identity:
            analysis_line = float(selected_line)
        else:
            analysis_line = float(live_line) if live_line is not None else None

        rows.append(
            {
                "Use": identity == selected_identity and analysis_line is not None,
                "Matchup": f"{game.get('away_team')} @ {game.get('home_team')}",
                "Kickoff ET": game.get("kickoff_et"),
                "Sportsbook": _clean(game.get("market_sportsbook")) or "—",
                "Live Total": live_line,
                "Analysis Line": analysis_line,
                "Market": (
                    "LIVE"
                    if game.get("market_line_available") is True
                    else "UNAVAILABLE"
                ),
                "Identity": identity,
            }
        )
    return rows


def render_over_under_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    st.caption(
        "🟢 CFB O/U • CLEAN PAGE V18 ACTIVE • LIVE ODDS CONNECTED • "
        "FROZEN PROJECTION MATH PRESERVED"
    )
    st.markdown(frozen_page._CSS, unsafe_allow_html=True)

    selected = st.date_input(
        "📅 CFB Over/Under slate date",
        value=datetime.now(_ET).date(),
        key="cfb_ou_v18_date",
    )
    day = selected.isoformat()

    games, schedule_diag = schedule_v6.load_with_diagnostics(day)
    if not games:
        st.warning("No verified College Football games were returned for this date.")
        return

    odds_payload, market_diag = market_adapter.load_odds_for_date(day, "FanDuel")
    games, attach_diag = market_adapter.attach_market_lines(games, odds_payload)

    if _clean(market_diag.get("status")) == "GREEN":
        st.success(
            "🟢 LIVE CFB ODDS API CONNECTED — "
            f"{int(attach_diag.get('market_lines_attached') or 0)} of "
            f"{len(games)} schedule games received an identity-verified "
            "FanDuel total line."
        )
    else:
        st.warning(
            "🟡 Live CFB odds API is unavailable for this date. "
            "Manual threshold entry remains available and no market data will "
            "enter the frozen projection formula."
        )

    st.caption(
        f"Schedule: {len(games)} games • "
        f"{int(schedule_diag.get('espn_matches') or 0)} enriched matches • "
        f"{int(attach_diag.get('market_lines_attached') or 0)} live totals • "
        f"{int(schedule_diag.get('venue_missing') or 0)} venue missing • "
        f"{int(schedule_diag.get('broadcast_missing') or 0)} broadcast missing"
    )

    index = st.selectbox(
        "🏟️ Over/Under matchup",
        options=list(range(len(games))),
        format_func=lambda i: (
            f"{games[int(i)].get('away_team')} @ "
            f"{games[int(i)].get('home_team')} "
            f"• {games[int(i)].get('kickoff_et') or 'TBD'} "
            + (
                f"• O/U {market_adapter.market_line(games[int(i)]):.1f}"
                if market_adapter.market_line(games[int(i)]) is not None
                else "• O/U unavailable"
            )
        ),
        key=f"cfb_ou_v18_matchup_{day}",
    )
    selected_game = dict(games[int(index)])
    identity = _clean(
        selected_game.get("identity_key")
        or selected_game.get("game_id")
        or index
    )

    live_line = market_adapter.market_line(selected_game)
    default_line = float(live_line) if live_line is not None else 50.5

    st.markdown(
        _market_caption(selected_game, market_diag),
        unsafe_allow_html=True,
    )

    line = st.number_input(
        (
            "🎯 Analysis total line — live market threshold only "
            "(0% projection weight)"
            if live_line is not None
            else "🎯 Manual analysis total line — threshold only (0% projection weight)"
        ),
        min_value=20.0,
        max_value=100.0,
        value=default_line,
        step=0.5,
        key=f"cfb_ou_v18_line_{day}_{identity}",
    )

    if live_line is not None and abs(float(line) - float(live_line)) > 0.001:
        st.caption(
            f"✏️ Manual override active: {float(line):.1f} "
            f"(live {selected_game.get('market_sportsbook') or 'market'} "
            f"total {float(live_line):.1f})."
        )

    try:
        result = frozen_page.runtime_slate.analyze_game(
            selected_game,
            day,
            float(line),
        )
    except Exception as exc:
        st.error(
            "Current runtime analysis failed visibly: "
            f"{type(exc).__name__}: {exc}"
        )
        return

    game = dict(result.get("game") or selected_game)
    away = dict(result.get("away") or {})
    home = dict(result.get("home") or {})
    diag = result.get("team_diag") or {}

    runtime_status = _clean(diag.get("runtime_status")) or "CHECK"
    if runtime_status == "GREEN":
        st.success(
            "🟢 CURRENT TEAM DATA PATH GREEN — no record/venue/broadcast "
            "contradictions detected."
        )
    else:
        st.warning(
            "🟡 Current team data path is not fully green: "
            + " • ".join(
                str(x) for x in (diag.get("runtime_issues") or [])[:4]
            )
        )

    st.markdown(frozen_page._step1(game, away, home), unsafe_allow_html=True)
    st.markdown(frozen_page._step2(away, home), unsafe_allow_html=True)

    try:
        readable_matchup = frozen_page.readable_step3.build_matchup_step3(
            game,
            away,
            home,
        )
    except Exception as exc:
        readable_matchup = {
            "ready": True,
            "display_ready": False,
            "reason": (
                "Readable Step 3 data failed visibly: "
                f"{type(exc).__name__}: {exc}"
            ),
        }

    st.markdown(
        frozen_page._step3_readable(
            readable_matchup,
            result.get("matchup_engine") or {},
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        frozen_page._model_step(
            4,
            "PACE / EXPECTED POSSESSIONS",
            result.get("pace_engine") or {},
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        frozen_page._model_step(
            5,
            "EXPLOSIVE PLAY PROFILE",
            result.get("explosive_engine") or {},
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        frozen_page._model_step(
            6,
            "RED ZONE",
            result.get("red_zone_engine") or {},
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        frozen_page._model_step(
            7,
            "THIRD DOWN",
            result.get("third_down_engine") or {},
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        frozen_page._model_step(
            8,
            "TURNOVER VOLATILITY",
            result.get("turnover_engine") or {},
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        frozen_page._model_step(
            9,
            "GAME-DAY ENVIRONMENT",
            result.get("environment_engine") or {},
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        frozen_page._model_step(
            10,
            "HISTORICAL MATCHUP CONTEXT",
            result.get("history_engine") or {},
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        frozen_page._model_step(
            11,
            "CURRENT FORM + SCHEDULE STRENGTH",
            result.get("form_strength_engine") or {},
        ),
        unsafe_allow_html=True,
    )
    st.markdown(frozen_page._cert_step(result), unsafe_allow_html=True)
    st.markdown(frozen_page._final(result), unsafe_allow_html=True)

    st.markdown("### Full-slate scan")
    st.caption(
        "Each game now starts with its own live FanDuel total when available. "
        "You may edit the Analysis Line manually before scanning."
    )
    editor = st.data_editor(
        _line_board(games, identity, float(line)),
        use_container_width=True,
        hide_index=True,
        key=f"cfb_ou_v18_board_{day}",
    )
    try:
        records = editor.to_dict("records")
    except Exception:
        records = list(editor) if isinstance(editor, list) else []

    selected_lines: dict[str, float] = {}
    for row in records:
        if not bool(row.get("Use")):
            continue
        row_identity = _clean(row.get("Identity"))
        try:
            row_line = float(row.get("Analysis Line"))
        except Exception:
            continue
        if row_identity and 20.0 <= row_line <= 100.0:
            selected_lines[row_identity] = row_line

    if st.button(
        f"Run clean-page O/U scan for {len(selected_lines)} selected game(s)",
        key=f"cfb_ou_v18_scan_{day}",
        type="primary",
        disabled=not bool(selected_lines),
    ):
        rows, scan_diag = frozen_page.runtime_slate.scan_slate(
            games,
            day,
            selected_lines,
        )
        ranked = frozen_page.final_model.rank_slate(rows, limit=5)
        st.session_state[f"cfb_ou_v18_top5_{day}"] = ranked
        st.session_state[f"cfb_ou_v18_scan_diag_{day}"] = scan_diag

    top5 = st.session_state.get(f"cfb_ou_v18_top5_{day}") or []
    scan_diag = st.session_state.get(f"cfb_ou_v18_scan_diag_{day}") or {}
    if scan_diag:
        st.caption(
            f"{int(scan_diag.get('games_analyzed') or 0)} analyzed • "
            f"{int(scan_diag.get('step12_certified_games') or 0)} "
            "Step-12 certified • "
            f"{len(scan_diag.get('errors') or [])} errors"
        )
    for rank, row in enumerate(top5, start=1):
        game_row = row.get("game") or {}
        final_row = row.get("final") or {}
        raw_row = row.get("raw") or {}
        st.markdown(
            f"**#{rank} {game_row.get('away_team')} @ "
            f"{game_row.get('home_team')} — "
            f"{final_row.get('selection') or raw_row.get('model_lean') or 'PASS'}** "
            f"• projected total "
            f"{frozen_page._num(raw_row.get('projected_total'),1)} "
            f"• analysis line {frozen_page._num(row.get('analysis_line'),1)}"
        )


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(
            f"Clean O/U Page V18 received unsupported market: {market}"
        )
    return render_over_under_hub(
        section_header,
        status_info,
        team_logo,
        h,
    )


__all__ = [
    "FROZEN_PAGE",
    "ACTIVE_SCHEDULE",
    "FROZEN_RUNTIME_SLATE",
    "MARKET",
    "MODEL_VERSION",
    "_line_board",
    "_market_caption",
    "render_cfb_hub",
    "render_over_under_hub",
]
