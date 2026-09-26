"""NFL Prop Analytics Page 3 Step 5 — game-by-game historical chart.

Renders the frozen Step 3 exact-ID game sample against the frozen Step 4 manual
analysis line. The chart is descriptive only: it does not fetch or infer a
sportsbook line, odds, projections, recommendations, rankings, or wager actions.
"""
from __future__ import annotations

from datetime import datetime
import html as html_lib
import math
from typing import Any

import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 STEP 5 • GAME-BY-GAME CHART V1"
PAGE3_CHART_STEP = 5
PAGE3_CHART_VERSION = "v1"
SPORTSBOOK_LINE_SOURCE = False
SPORTSBOOK_ODDS_LOGIC = False
PROJECTION_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
WAGER_ACTIONS = False
MAX_CHART_GAMES = 20


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _number(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _week_or_date(row: dict[str, Any]) -> str:
    for key in ("week_label", "week", "week_number"):
        raw = _text(row.get(key))
        if raw:
            upper = raw.upper()
            if "WEEK" in upper or upper.startswith("W"):
                return upper
            if raw.isdigit():
                return f"WEEK {int(raw)}"
            return upper
    raw_date = _text(row.get("date"))
    if raw_date:
        try:
            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            return dt.strftime("%m/%d")
        except ValueError:
            if len(raw_date) >= 10:
                return raw_date[5:10].replace("-", "/")
    return "GAME"


def _format_value(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.1f}"


def build_game_chart_spec(
    games: Any,
    *,
    line: Any,
) -> dict[str, Any]:
    """Normalize exact-ID history rows into a deterministic chart contract."""
    line_value = _number(line)
    if line_value is None:
        return {
            "ready": False,
            "reason": "manual Step 4 analysis line is required",
            "line": None,
            "games": [],
        }

    normalized: list[dict[str, Any]] = []
    for row in list(games or [])[:MAX_CHART_GAMES]:
        if not isinstance(row, dict):
            continue
        value = _number(row.get("value"))
        event_id = _text(row.get("official_event_id") or row.get("event_id"))
        if value is None or not event_id.isdigit():
            continue
        opponent = _text(row.get("opponent_abbr") or "OPP").upper()
        outcome = "over" if value > line_value else "under" if value < line_value else "push"
        normalized.append({
            "official_event_id": event_id,
            "opponent_abbr": opponent,
            "week_or_date": _week_or_date(row),
            "date": _text(row.get("date")),
            "season": int(row.get("season") or 0),
            "value": value,
            "outcome": outcome,
        })

    if not normalized:
        return {
            "ready": False,
            "reason": "verified historical games are required",
            "line": line_value,
            "games": [],
        }

    axis_high = max(max(row["value"] for row in normalized), line_value, 1.0)
    axis_high = max(1.0, math.ceil(axis_high * 1.12))
    line_pct = max(0.0, min(100.0, (line_value / axis_high) * 100.0))
    for row in normalized:
        row["height_pct"] = max(1.5, min(100.0, (row["value"] / axis_high) * 100.0))

    return {
        "ready": True,
        "line": line_value,
        "line_pct": line_pct,
        "axis_high": float(axis_high),
        "sample_size": len(normalized),
        "over_count": sum(1 for row in normalized if row["outcome"] == "over"),
        "under_count": sum(1 for row in normalized if row["outcome"] == "under"),
        "push_count": sum(1 for row in normalized if row["outcome"] == "push"),
        "games": normalized,
    }


def render_game_chart(
    *,
    games: Any,
    line: Any,
    market_key: Any,
    market_label: Any,
    history_key: Any,
    history_label: Any,
) -> dict[str, Any]:
    """Render a compact responsive game-by-game bar chart against Step 4 line."""
    market = _text(market_key)
    market_name = _text(market_label) or market or "Selected prop"
    history = _text(history_key)
    history_name = _text(history_label) or history or "Selected window"
    spec = build_game_chart_spec(games, line=line)

    if not spec.get("ready"):
        st.markdown(
            f"""
<section class="ks-pa5-chart ks-pa5-chart-unavailable"
         data-prop-page3-step5-chart="{PAGE3_CHART_VERSION}"
         data-prop-page3-step5-state="unavailable"
         data-prop-page3-step5-market="{html_lib.escape(market)}"
         data-prop-page3-step5-history="{html_lib.escape(history)}">
  <div class="ks-pa5-head">
    <div><span>GAME-BY-GAME</span><strong>Chart unavailable</strong></div>
    <em>STEP 5</em>
  </div>
  <p>{html_lib.escape(str(spec.get("reason") or "Verified history and analysis line are required."))}</p>
</section>
""",
            unsafe_allow_html=True,
        )
        return spec

    chart_games = list(reversed(spec["games"]))
    bar_html: list[str] = []
    for game in chart_games:
        bar_html.append(
            f"""
<div class="ks-pa5-game"
     data-prop-page3-step5-game="{html_lib.escape(game['official_event_id'])}"
     data-prop-page3-step5-opponent="{html_lib.escape(game['opponent_abbr'])}"
     data-prop-page3-step5-value="{game['value']:.1f}"
     data-prop-page3-step5-outcome="{game['outcome']}">
  <div class="ks-pa5-value">{html_lib.escape(_format_value(game['value']))}</div>
  <div class="ks-pa5-bar-slot">
    <div class="ks-pa5-bar ks-pa5-{game['outcome']}" style="height:{game['height_pct']:.2f}%"></div>
  </div>
  <div class="ks-pa5-opp">vs {html_lib.escape(game['opponent_abbr'])}</div>
  <div class="ks-pa5-week">{html_lib.escape(game['week_or_date'])}</div>
</div>
"""
        )

    st.markdown(
        f"""
<section class="ks-pa5-chart"
         data-prop-page3-step5-chart="{PAGE3_CHART_VERSION}"
         data-prop-page3-step5-state="ready"
         data-prop-page3-step5-market="{html_lib.escape(market)}"
         data-prop-page3-step5-history="{html_lib.escape(history)}"
         data-prop-page3-step5-line="{spec['line']:.1f}"
         data-prop-page3-step5-line-source="manual-step4"
         data-prop-page3-step5-sample="{spec['sample_size']}"
         data-prop-page3-step5-over-count="{spec['over_count']}"
         data-prop-page3-step5-under-count="{spec['under_count']}"
         data-prop-page3-step5-push-count="{spec['push_count']}">
  <div class="ks-pa5-head">
    <div>
      <span>GAME-BY-GAME • STEP 5</span>
      <strong>{html_lib.escape(market_name)} • {html_lib.escape(history_name)}</strong>
    </div>
    <em>OPPONENT • WEEK/DATE</em>
  </div>

  <div class="ks-pa5-legend">
    <span><i class="ks-pa5-dot ks-pa5-dot-over"></i>OVER</span>
    <span><i class="ks-pa5-dot ks-pa5-dot-under"></i>UNDER</span>
    <span><i class="ks-pa5-line-swatch"></i>LINE {spec['line']:.1f}</span>
  </div>

  <div class="ks-pa5-scroll">
    <div class="ks-pa5-plot" style="--ks-pa5-games:{spec['sample_size']};">
      <div class="ks-pa5-line" style="bottom:{spec['line_pct']:.3f}%"
           data-prop-page3-step5-selected-line="{spec['line']:.1f}">
        <span>{spec['line']:.1f}</span>
      </div>
      {''.join(bar_html)}
    </div>
  </div>

  <div class="ks-pa5-foot">
    <span>{spec['over_count']} OVER</span>
    <span>{spec['under_count']} UNDER</span>
    <span>{spec['push_count']} PUSH</span>
    <em>HISTORICAL ONLY • MANUAL ANALYSIS LINE</em>
  </div>
</section>

<style data-prop-page3-step5-css="{PAGE3_CHART_VERSION}">
.ks-pa5-chart{{
  width:100%;max-width:100%;min-width:0;margin:10px 0 14px;padding:13px;
  border:1px solid rgba(56,189,248,.18);border-radius:16px;
  background:
    radial-gradient(circle at 88% -10%,rgba(14,165,233,.10),transparent 18rem),
    linear-gradient(180deg,rgba(6,16,28,.98),rgba(3,10,18,.99));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.025);
  overflow:hidden;
}}
.ks-pa5-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:12px}}
.ks-pa5-head>div{{display:flex;flex-direction:column;gap:2px;min-width:0}}
.ks-pa5-head span{{color:#38bdf8;font-size:.51rem;font-weight:950;letter-spacing:.12em}}
.ks-pa5-head strong{{color:#edf8ff;font-size:.84rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa5-head em{{color:#64748b;font-size:.48rem;font-style:normal;font-weight:850;text-align:right}}
.ks-pa5-legend{{display:flex;align-items:center;gap:12px;margin:9px 0 4px;color:#7890a8;font-size:.48rem;font-weight:900}}
.ks-pa5-legend span{{display:flex;align-items:center;gap:4px}}
.ks-pa5-dot{{display:inline-block;width:7px;height:7px;border-radius:999px}}
.ks-pa5-dot-over{{background:#38bdf8;box-shadow:0 0 9px rgba(56,189,248,.45)}}
.ks-pa5-dot-under{{background:#64748b}}
.ks-pa5-line-swatch{{display:inline-block;width:14px;height:2px;background:#f8fafc;box-shadow:0 0 7px rgba(248,250,252,.32)}}
.ks-pa5-scroll{{width:100%;max-width:100%;overflow-x:auto;overscroll-behavior-inline:contain;padding-bottom:2px}}
.ks-pa5-plot{{
  --ks-pa5-games:10;
  position:relative;isolation:isolate;
  min-width:max(100%,calc(var(--ks-pa5-games) * 44px));
  height:238px;padding:14px 8px 0;
  display:grid;grid-template-columns:repeat(var(--ks-pa5-games),minmax(30px,1fr));
  align-items:end;gap:5px;
  border-top:1px solid rgba(148,163,184,.06);
  border-bottom:1px solid rgba(148,163,184,.08);
  background:
    repeating-linear-gradient(to top,transparent 0,transparent 49px,rgba(148,163,184,.05) 50px);
}}
.ks-pa5-line{{
  position:absolute;left:6px;right:6px;z-index:5;height:1px;
  background:rgba(248,250,252,.82);box-shadow:0 0 8px rgba(248,250,252,.22);
  pointer-events:none;
}}
.ks-pa5-line span{{
  position:absolute;right:0;bottom:3px;padding:2px 5px;border-radius:6px;
  color:#f8fafc;background:#111827;font-size:.44rem;font-weight:950;
  border:1px solid rgba(248,250,252,.12);
}}
.ks-pa5-game{{height:100%;min-width:0;display:grid;grid-template-rows:18px 1fr 20px 16px;align-items:end;text-align:center}}
.ks-pa5-value{{align-self:end;color:#cbd5e1;font-size:.53rem;font-weight:900}}
.ks-pa5-bar-slot{{height:100%;min-height:0;display:flex;align-items:flex-end;justify-content:center}}
.ks-pa5-bar{{width:min(74%,25px);min-height:2px;border-radius:5px 5px 2px 2px}}
.ks-pa5-over{{background:linear-gradient(180deg,#7dd3fc,#0284c7);box-shadow:0 0 12px rgba(56,189,248,.16)}}
.ks-pa5-under{{background:linear-gradient(180deg,#94a3b8,#475569)}}
.ks-pa5-push{{background:linear-gradient(180deg,#fbbf24,#b45309)}}
.ks-pa5-opp{{align-self:center;color:#d8e8f6;font-size:.48rem;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa5-week{{align-self:start;color:#60758d;font-size:.43rem;font-weight:800;white-space:nowrap}}
.ks-pa5-foot{{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-top:8px}}
.ks-pa5-foot span{{padding:3px 6px;border:1px solid rgba(125,211,252,.10);border-radius:999px;color:#7890a8;font-size:.46rem;font-weight:900}}
.ks-pa5-foot em{{margin-left:auto;color:#586d84;font-size:.44rem;font-style:normal;font-weight:800}}
.ks-pa5-chart-unavailable{{border-color:rgba(248,113,113,.16)}}
.ks-pa5-chart-unavailable p{{margin:7px 0 0;color:#8295aa;font-size:.62rem}}
@media(max-width:560px){{
  .ks-pa5-head{{align-items:flex-start;flex-direction:column;gap:3px}}
  .ks-pa5-head em{{text-align:left}}
  .ks-pa5-plot{{height:220px;min-width:max(100%,calc(var(--ks-pa5-games) * 42px))}}
  .ks-pa5-foot em{{width:100%;margin-left:0}}
}}
</style>
""",
        unsafe_allow_html=True,
    )
    return spec


__all__ = [
    "MAX_CHART_GAMES",
    "MODEL_VERSION",
    "PAGE3_CHART_STEP",
    "PAGE3_CHART_VERSION",
    "PROJECTION_LOGIC",
    "SPORTSBOOK_LINE_SOURCE",
    "SPORTSBOOK_ODDS_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "WAGER_ACTIONS",
    "build_game_chart_spec",
    "render_game_chart",
]
