"""WNBA Daily Picks V35 — certified Step-18A consumer presentation.

V35 replaces Daily Picks' on-page compute path with one GET of the already-
computed Step-18A in-memory snapshot. It never falls back to the legacy seven-
market Run-All controller when the consumer API is stale, unavailable, waking,
or empty. That prevents duplicate simulations and prevents old picks from being
recycled when the current production cycle has no board.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

from wnba_streamlit_consumer_v1 import load_latest_daily_picks

MODEL_VERSION = "WNBA DAILY PICKS V35 • STEP 18B CERTIFIED API CONSUMER"


_CSS = """
<style>
.k18b-shell{margin:2px 0 12px;padding:12px 14px;border:1px solid rgba(96,165,250,.22);border-radius:16px;background:rgba(30,41,59,.36)}
.k18b-kicker{font-size:.72rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:#93c5fd}
.k18b-title{font-size:1.15rem;font-weight:950;color:#f8fafc;margin-top:2px}
.k18b-sub{font-size:.77rem;color:#94a3b8;margin-top:3px}
.k18b-card{margin:10px 0;padding:14px 15px;border:1px solid rgba(148,163,184,.20);border-radius:17px;background:rgba(15,23,42,.62)}
.k18b-row{display:flex;gap:12px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap}
.k18b-rank{font-size:.72rem;font-weight:950;color:#93c5fd;letter-spacing:.06em;text-transform:uppercase}
.k18b-player{font-size:1.02rem;font-weight:950;color:#f8fafc;margin-top:2px}
.k18b-matchup{font-size:.73rem;color:#94a3b8;margin-top:2px}
.k18b-pick{font-size:1.00rem;font-weight:950;color:#e2e8f0;text-align:right}
.k18b-price{font-size:.73rem;color:#94a3b8;text-align:right;margin-top:2px}
.k18b-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:12px}
.k18b-metric{padding:8px 9px;border:1px solid rgba(148,163,184,.13);border-radius:11px;background:rgba(30,41,59,.34)}
.k18b-label{font-size:.62rem;font-weight:850;color:#94a3b8;text-transform:uppercase;letter-spacing:.045em}
.k18b-value{font-size:.88rem;font-weight:950;color:#f8fafc;margin-top:2px}
@media(max-width:700px){.k18b-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.k18b-pick,.k18b-price{text-align:left}}
</style>
"""


def _american(value: object) -> str:
    if value is None:
        return "—"
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "—"
    return f"+{number}" if number > 0 else str(number)


def _pct(value: object, *, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return "—"


def _card_html(card: Mapping[str, Any]) -> str:
    player = card.get("player") if isinstance(card.get("player"), Mapping) else {}
    prop = card.get("prop") if isinstance(card.get("prop"), Mapping) else {}
    market = card.get("market") if isinstance(card.get("market"), Mapping) else {}
    model = card.get("model") if isinstance(card.get("model"), Mapping) else {}
    consensus = card.get("consensus") if isinstance(card.get("consensus"), Mapping) else {}
    value = card.get("value") if isinstance(card.get("value"), Mapping) else {}
    team = str(player.get("team_key") or "—")
    opponent = str(player.get("opponent_team_key") or "—")
    player_name = escape(str(player.get("player_name") or "Unknown Player"))
    stat_label = escape(str(prop.get("stat_label") or str(prop.get("stat") or "").title()))
    pick = escape(str(prop.get("pick") or "—"))
    sportsbook = escape(str(market.get("sportsbook") or "—"))
    fair = model.get("fair_price") if isinstance(model.get("fair_price"), Mapping) else {}
    return f"""
<div class="k18b-card">
  <div class="k18b-row">
    <div>
      <div class="k18b-rank">Rank #{int(card.get('display_rank') or 0)} • {escape(stat_label)}</div>
      <div class="k18b-player">{player_name}</div>
      <div class="k18b-matchup">{escape(team)} vs {escape(opponent)}</div>
    </div>
    <div>
      <div class="k18b-pick">{pick}</div>
      <div class="k18b-price">{sportsbook} • {_american(market.get('american_odds'))}</div>
    </div>
  </div>
  <div class="k18b-grid">
    <div class="k18b-metric"><div class="k18b-label">Model Probability</div><div class="k18b-value">{_pct(model.get('resolved_fair_percentage'))}</div></div>
    <div class="k18b-metric"><div class="k18b-label">Fair Odds</div><div class="k18b-value">{_american(fair.get('american_odds'))}</div></div>
    <div class="k18b-metric"><div class="k18b-label">No-Vig Market</div><div class="k18b-value">{_pct(consensus.get('no_vig_percentage'))}</div></div>
    <div class="k18b-metric"><div class="k18b-label">Model Edge</div><div class="k18b-value">{_pct(consensus.get('edge_percentage_points'))}</div></div>
    <div class="k18b-metric"><div class="k18b-label">EV ROI</div><div class="k18b-value">{_pct(value.get('ev_roi_percentage'))}</div></div>
    <div class="k18b-metric"><div class="k18b-label">Push</div><div class="k18b-value">{_pct(model.get('push_percentage'))}</div></div>
    <div class="k18b-metric"><div class="k18b-label">Simulation</div><div class="k18b-value">5,000,000</div></div>
    <div class="k18b-metric"><div class="k18b-label">Convergence</div><div class="k18b-value">✓ Verified</div></div>
  </div>
</div>
"""


def _render_status(view: Mapping[str, Any]) -> None:
    state = str(view.get("state") or "error")
    reason = str(view.get("reason") or "unknown")
    snapshot = view.get("snapshot") if isinstance(view.get("snapshot"), Mapping) else {}
    runtime = view.get("runtime") if isinstance(view.get("runtime"), Mapping) else {}
    if state == "stale":
        st.warning(
            "The latest WNBA board snapshot is stale, so Daily Picks is hiding all cards until the always-on scheduler produces a fresh cycle."
        )
    elif state == "waiting":
        st.info("The WNBA consumer is online and waiting for its first successful scheduler cycle. No old picks are being reused.")
    elif state == "disabled":
        st.info("The WNBA Daily Picks consumer is currently disabled. No legacy model run was started.")
    elif state == "unavailable":
        st.info(f"No current qualified WNBA Daily Picks board is available. Production reason: {reason}.")
    else:
        error_type = str(view.get("error_type") or "APIReadError")
        st.error("The WNBA Daily Picks API could not be read safely. No cached or legacy picks are being shown.")
        st.caption(f"Read state: {error_type}")
    age = snapshot.get("age_seconds")
    due = runtime.get("next_refresh_due_at_utc")
    details = []
    if age is not None:
        try:
            details.append(f"snapshot age {float(age):.0f}s")
        except (TypeError, ValueError):
            pass
    if due:
        details.append(f"next refresh {due}")
    if details:
        st.caption(" • ".join(details))


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="k18b-shell"><div class="k18b-kicker">Step 18B • Certified API Consumer</div>'
        '<div class="k18b-title">WNBA Daily Picks</div>'
        '<div class="k18b-sub">Read-only latest scheduler snapshot • no on-page simulations • no stale-pick fallback</div></div>',
        unsafe_allow_html=True,
    )
    view = load_latest_daily_picks()
    if view.get("state") != "ready":
        _render_status(view)
        return view

    slate = str(view.get("slate_date") or "")
    cards = list(view.get("cards") or [])
    meta = view.get("board_meta") if isinstance(view.get("board_meta"), Mapping) else {}
    snapshot = view.get("snapshot") if isinstance(view.get("snapshot"), Mapping) else {}
    st.caption(
        f"Slate {slate} • {len(cards)} current qualified card(s) • "
        f"{int(meta.get('qualified_prop_count') or 0)} qualified props • "
        f"snapshot age {float(snapshot.get('age_seconds') or 0):.0f}s"
    )
    for card in cards:
        st.markdown(_card_html(card), unsafe_allow_html=True)
    if meta.get("full_requested_board_available") is not True:
        st.caption("The production board has fewer qualified cards than requested; rankings were not padded or forced.")
    return view


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
