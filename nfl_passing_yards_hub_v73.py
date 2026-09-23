"""NFL Passing Yards V73 — Live Market + Line Movement Step 4.

Additive presentation-only wrapper over frozen V72. It reads the already-
certified Step 10 market card after the frozen model is complete and maintains a
bounded per-session history of exact live market snapshots for the selected
matchup/QB slot.

Important truth boundary:
- the current certified FanDuel line/prices come from the existing exact-ID Kyre
  Sports API bridge;
- the "first seen" line is the first certified snapshot observed in this active
  Streamlit session, NOT a claim about the sportsbook's true historical opener;
- if no prior certified snapshot exists, movement is explicitly NOT YET
  PROVABLE;
- only currently certified books participate in the "best available" readout;
  today that contract is FanDuel only;
- no sportsbook input feeds projection/model/context/probability math.

Sportsbook projection influence remains exactly 0.0%. Stake sizing stays OFF.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import math
import re
from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v72 as prior

_FROZEN_SELECTED_ANALYSIS = prior._selected_analysis_v72

MODEL_VERSION = "NFL PASSING YARDS V73 • LIVE MARKET + LINE MOVEMENT STEP 4"
FROZEN_PRIOR = "nfl_passing_yards_hub_v72"
LIVE_MARKET_VERSION = "v73"
NEW_PHASE_STEP = 4
PRESENTATION_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_DATA_PROVIDER = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
HISTORY_LIMIT = 12
_CERTIFIED_SOURCE = "Kyre Sports API"
_CERTIFIED_BOOK = "FanDuel"
_HISTORY_KEY = "_kpy73_certified_market_history"

_LIVE_MARKET_CSS = r"""
<style data-passing-yards-live-market-css="v73">
.ks-py73-market,.ks-py73-market *{box-sizing:border-box}
.ks-py73-market{
  margin:9px 0 12px;padding:12px;border:1px solid var(--kyre-sem-border-medium);
  border-radius:14px;background:linear-gradient(145deg,var(--kyre-sem-surface-panel),var(--kyre-sem-surface-panel-alt));
}
.ks-py73-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:10px}
.ks-py73-kicker{font-size:.54rem;font-weight:950;letter-spacing:.1em;text-transform:uppercase;color:var(--kyre-sem-text-accent-soft)}
.ks-py73-title{margin-top:3px;font-size:.96rem;font-weight:950;color:var(--kyre-sem-text-primary)}
.ks-py73-state{flex:0 0 auto;border:1px solid var(--kyre-sem-border-medium);border-radius:999px;padding:5px 8px;font-size:.52rem;font-weight:950;color:var(--kyre-sem-text-accent-soft)}
.ks-py73-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
.ks-py73-cell{min-width:0;padding:9px;border:1px solid var(--kyre-sem-border-soft);border-radius:10px;background:rgba(255,255,255,.014)}
.ks-py73-cell b{display:block;font-size:.82rem;line-height:1.2;color:var(--kyre-sem-text-primary);overflow-wrap:anywhere}
.ks-py73-cell span{display:block;margin-top:4px;font-size:.46rem;font-weight:900;text-transform:uppercase;color:var(--kyre-sem-text-muted)}
.ks-py73-move{margin-top:9px;padding:9px 10px;border:1px solid var(--kyre-sem-border-soft);border-radius:10px;font-size:.57rem;line-height:1.5;color:var(--kyre-sem-text-muted)}
.ks-py73-move strong{color:var(--kyre-sem-text-primary)}
.ks-py73-foot{margin-top:8px;padding-top:8px;border-top:1px solid var(--kyre-sem-border-soft);font-size:.52rem;line-height:1.5;color:var(--kyre-sem-text-muted)}
@media(max-width:760px){.ks-py73-head{flex-direction:column}.ks-py73-state{align-self:flex-start}.ks-py73-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:420px){.ks-py73-market{padding:10px}.ks-py73-grid{grid-template-columns:1fr}}
</style>
"""


def _plain(value: Any, fallback: str = "") -> str:
    text = re.sub(r"<[^>]+>", "", str(value if value is not None else ""), flags=re.S)
    text = text.replace("&nbsp;", " ").strip()
    return text or fallback


def _num(value: Any) -> float:
    try:
        out = float(str(value).replace(",", "").replace("+", "").strip())
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _finite(value: Any) -> bool:
    return math.isfinite(_num(value))


def _market_field(body: str, kind: str, fallback: str = "—") -> str:
    pattern = (
        rf'data-market-field="{re.escape(kind)}"[^>]*>\s*'
        rf'<b[^>]*>(.*?)</b>'
    )
    match = re.search(pattern, str(body or ""), flags=re.S | re.I)
    return _plain(match.group(1), fallback) if match else fallback


def _market_source(body: str) -> str:
    match = re.search(
        r'class="ks-py63-market-source"[^>]*>\s*<strong>Source:</strong>\s*(.*?)\s*•\s*sportsbook projection influence',
        str(body or ""),
        flags=re.S | re.I,
    )
    return _plain(match.group(1), "Verified market source unavailable") if match else "Verified market source unavailable"


def _odds_pair(body: str) -> tuple[str, str]:
    text = _market_field(body, "offered-odds", "— / —")
    parts = [part.strip() for part in text.split("/", 1)]
    return (parts[0] if parts else "—", parts[1] if len(parts) > 1 else "—")


def _session_timestamp(slot: int) -> str:
    index = max(0, int(slot) - 1)
    pattern = re.compile(rf"^kpy10_{index}_.*_timestamp$")
    for key in sorted(st.session_state.keys()):
        if pattern.match(str(key)):
            value = str(st.session_state.get(key) or "").strip()
            if value:
                return value
    return ""


def _snapshot_key(slot: int, source: str) -> str:
    try:
        date = str(st.query_params.get("ks_py_date") or "").strip()
        matchup = str(st.query_params.get("ks_py_matchup") or "").strip()
    except Exception:
        date = ""
        matchup = ""
    return "|".join((date, matchup, str(int(slot)), str(source or "").strip()))


def build_snapshot(body: str, slot: int, *, timestamp: str = "") -> dict:
    line_text = _market_field(body, "line", "")
    over_text, under_text = _odds_pair(body)
    source = _market_source(body)
    certified = _CERTIFIED_SOURCE.casefold() in source.casefold() and _CERTIFIED_BOOK.casefold() in source.casefold()
    ready = bool(
        certified
        and _finite(line_text)
        and _finite(over_text)
        and _finite(under_text)
        and abs(_num(over_text)) >= 100
        and abs(_num(under_text)) >= 100
    )
    return {
        "ready": ready,
        "certified": certified,
        "slot": int(slot),
        "source": source,
        "sportsbook": _CERTIFIED_BOOK if certified else "",
        "line": _num(line_text) if _finite(line_text) else math.nan,
        "over_odds": int(_num(over_text)) if _finite(over_text) else None,
        "under_odds": int(_num(under_text)) if _finite(under_text) else None,
        "captured_at_utc": str(timestamp or "").strip(),
        "projection_weight": 0.0,
    }


def update_history(history: list[dict], snapshot: dict, *, limit: int = HISTORY_LIMIT) -> list[dict]:
    rows = [dict(row) for row in (history or []) if isinstance(row, dict) and row.get("ready")]
    if not snapshot.get("ready"):
        return rows[-max(1, int(limit)):]
    signature = (
        snapshot.get("line"),
        snapshot.get("over_odds"),
        snapshot.get("under_odds"),
    )
    if not rows or (
        rows[-1].get("line"),
        rows[-1].get("over_odds"),
        rows[-1].get("under_odds"),
    ) != signature:
        rows.append(dict(snapshot))
    elif snapshot.get("captured_at_utc"):
        rows[-1]["captured_at_utc"] = snapshot.get("captured_at_utc")
    return rows[-max(1, int(limit)):]


def movement_summary(history: list[dict]) -> dict:
    rows = [row for row in (history or []) if isinstance(row, dict) and row.get("ready")]
    if not rows:
        return {
            "ready": False,
            "state": "MARKET UNAVAILABLE",
            "first_line": math.nan,
            "current_line": math.nan,
            "line_delta": math.nan,
            "price_state": "—",
            "observation_count": 0,
        }
    first, current = rows[0], rows[-1]
    first_line = _num(first.get("line"))
    current_line = _num(current.get("line"))
    delta = current_line - first_line if _finite(first_line) and _finite(current_line) else math.nan
    if len(rows) < 2:
        state = "NO PRIOR CERTIFIED SNAPSHOT"
    elif abs(delta) > 1e-9:
        state = f"LINE {'UP' if delta > 0 else 'DOWN'} {abs(delta):g}"
    elif (
        current.get("over_odds") != first.get("over_odds")
        or current.get("under_odds") != first.get("under_odds")
    ):
        state = "PRICE MOVE • LINE FLAT"
    else:
        state = "FLAT"
    price_state = (
        f"O {current.get('over_odds'):+d} / U {current.get('under_odds'):+d}"
        if isinstance(current.get("over_odds"), int) and isinstance(current.get("under_odds"), int)
        else "—"
    )
    return {
        "ready": True,
        "state": state,
        "first_line": first_line,
        "current_line": current_line,
        "line_delta": delta,
        "price_state": price_state,
        "observation_count": len(rows),
    }


def _fmt_line(value: Any) -> str:
    return f"{_num(value):g}" if _finite(value) else "—"


def build_live_market_panel(snapshot: dict, history: list[dict]) -> str:
    move = movement_summary(history)
    if not snapshot.get("ready"):
        return (
            '<section class="ks-py73-market" data-passing-yards-live-market="v73" '
            'data-passing-yards-live-market-ready="false">'
            '<div class="ks-py73-head"><div><div class="ks-py73-kicker">Live market intelligence</div>'
            '<div class="ks-py73-title">Certified market unavailable</div></div>'
            '<div class="ks-py73-state">FAIL CLOSED</div></div>'
            '<div class="ks-py73-foot">No live line, opening-line claim, or movement value is fabricated. '
            'The frozen model remains independent of sportsbook input.</div></section>'
        )

    current_line = _fmt_line(snapshot.get("line"))
    first_line = _fmt_line(move.get("first_line"))
    timestamp = snapshot.get("captured_at_utc") or "Freshness validated upstream • timestamp unavailable in rendered state"
    delta = move.get("line_delta")
    delta_text = f"{delta:+g}" if _finite(delta) and move.get("observation_count", 0) >= 2 else "NOT YET PROVABLE"
    over = snapshot.get("over_odds")
    under = snapshot.get("under_odds")
    offered = f"O {over:+d} / U {under:+d}" if isinstance(over, int) and isinstance(under, int) else "—"

    return (
        '<section class="ks-py73-market" data-passing-yards-live-market="v73" '
        'data-passing-yards-live-market-ready="true" '
        'data-passing-yards-v224-runtime="live-market-step4">'
        '<div class="ks-py73-head"><div>'
        '<div class="ks-py73-kicker">Live market + line movement • post-model only</div>'
        '<div class="ks-py73-title">Certified Market Tape</div>'
        f'</div><div class="ks-py73-state">{escape(str(move.get("state") or "CHECK"))}</div></div>'
        '<div class="ks-py73-grid">'
        f'<div class="ks-py73-cell" data-live-market-field="current-line"><b>{escape(current_line)}</b><span>Current FanDuel Line</span></div>'
        f'<div class="ks-py73-cell" data-live-market-field="prices"><b>{escape(offered)}</b><span>Current O / U Price</span></div>'
        f'<div class="ks-py73-cell" data-live-market-field="first-line"><b>{escape(first_line)}</b><span>First Certified Session Line</span></div>'
        f'<div class="ks-py73-cell" data-live-market-field="movement"><b>{escape(delta_text)}</b><span>Line Move vs First Seen</span></div>'
        '</div>'
        '<div class="ks-py73-move" data-live-market-movement="v73">'
        f'<strong>Movement state:</strong> {escape(str(move.get("state") or "CHECK"))} • '
        f'<strong>observations:</strong> {int(move.get("observation_count") or 0)} • '
        f'<strong>current price:</strong> {escape(move.get("price_state") or "—")}.<br>'
        '<strong>Book coverage:</strong> 1 certified book • FanDuel. '
        f'<strong>Best available among certified books:</strong> {escape(offered)} at {escape(current_line)}.'
        '</div>'
        '<div class="ks-py73-foot">'
        f'<strong>Captured:</strong> {escape(str(timestamp))} • source: {escape(str(snapshot.get("source") or ""))}. '
        '“First Certified Session Line” is the first exact-ID snapshot observed in this active Streamlit session; '
        'it is not represented as the sportsbook’s historical opening line. If there is no prior snapshot, movement stays NOT YET PROVABLE. '
        'Sportsbook projection influence 0.0% • stake sizing OFF.'
        '</div></section>'
    )


def _insert_after_market_detail(body: str, panel: str) -> str:
    text = str(body or "")
    start = text.find('<section class="ks-py63-market-detail"')
    if start < 0:
        return text
    end = text.find("</section>", start)
    if end < 0:
        return text
    end += len("</section>")
    return text[:end] + panel + text[end:]


def _inject_live_market(body: str, slot: int) -> str:
    text = str(body or "")
    if (
        'data-passing-yards-qb-detail="v59"' not in text
        or 'data-passing-yards-market-detail="v63"' not in text
        or 'data-passing-yards-matchup-intelligence="v72"' not in text
        or 'data-passing-yards-live-market="v73"' in text
    ):
        return text

    snapshot = build_snapshot(text, slot, timestamp=_session_timestamp(slot))
    history_map = st.session_state.setdefault(_HISTORY_KEY, {})
    if not isinstance(history_map, dict):
        history_map = {}
        st.session_state[_HISTORY_KEY] = history_map
    key = _snapshot_key(slot, snapshot.get("source") or "")
    history = update_history(history_map.get(key) or [], snapshot)
    history_map[key] = history

    panel = build_live_market_panel(snapshot, history)
    text = _insert_after_market_detail(text, panel)
    ready = 'data-passing-yards-matchup-intelligence-ready="v72"'
    if ready in text and 'data-passing-yards-live-market-ready="v73"' not in text:
        text = text.replace(
            ready,
            ready + ' data-passing-yards-live-market-ready="v73"',
            1,
        )
    return _LIVE_MARKET_CSS + text


def _selected_analysis_v73(captured: dict[str, list[str]], slot: int) -> str:
    return _inject_live_market(
        _FROZEN_SELECTED_ANALYSIS(captured, slot),
        slot,
    )


def render_nfl_passing_yards_hub() -> None:
    original = prior._selected_analysis_v72
    prior._selected_analysis_v72 = _selected_analysis_v73
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._selected_analysis_v72 = original


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V73 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "HISTORY_LIMIT",
    "LIVE_MARKET_VERSION",
    "MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_DATA_PROVIDER",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "NEW_PHASE_STEP",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_inject_live_market",
    "_selected_analysis_v73",
    "build_live_market_panel",
    "build_snapshot",
    "movement_summary",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
    "update_history",
]
