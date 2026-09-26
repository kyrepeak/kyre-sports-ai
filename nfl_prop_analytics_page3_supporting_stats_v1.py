"""NFL Prop Analytics Page 3 Step 6 — supporting stats.

Builds prop-relevant supporting metrics from the exact event IDs already
certified by Page 3 Step 3. The UI can toggle Average/Median. Data is descriptive
historical box-score context only: no sportsbook lines, odds, projections,
recommendations, rankings, staking, or wager actions.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import html as html_lib
import math
import re
from statistics import mean, median
from typing import Any

import requests
import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 STEP 6 • SUPPORTING STATS V1"
PAGE3_SUPPORT_STEP = 6
PAGE3_SUPPORT_VERSION = "v1"
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
REQUEST_TIMEOUT_SECONDS = 8
MAX_WORKERS = 6
MAX_SUPPORT_GAMES = 20
SPORTSBOOK_LINE_SOURCE = False
SPORTSBOOK_ODDS_LOGIC = False
PROJECTION_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
WAGER_ACTIONS = False

REQUEST_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "User-Agent": "KyreSportsAI-PropAnalytics-SupportingStats/1.0",
}

METRIC_META = {
    "attempts": ("ATTEMPTS", "ATT"),
    "completions": ("COMPLETIONS", "CMP"),
    "completion_pct": ("COMPLETION %", "%"),
    "passing_yards": ("PASS YARDS", "YDS"),
    "yards_per_attempt": ("YARDS / ATT", "YPA"),
    "passing_tds": ("PASS TD", "TD"),
    "interceptions": ("INTERCEPTIONS", "INT"),
    "carries": ("CARRIES", "CAR"),
    "rushing_yards": ("RUSH YARDS", "YDS"),
    "yards_per_carry": ("YARDS / CARRY", "YPC"),
    "receptions": ("RECEPTIONS", "REC"),
    "targets": ("TARGETS", "TGT"),
    "catch_pct": ("CATCH %", "%"),
    "receiving_yards": ("REC YARDS", "YDS"),
    "yards_per_reception": ("YARDS / REC", "YPR"),
    "longest_reception": ("LONG REC", "YDS"),
    "receiving_tds": ("REC TD", "TD"),
    "scrimmage_yards": ("SCRIMMAGE", "YDS"),
    "touches": ("TOUCHES", "TOT"),
    "skill_tds": ("RUSH + REC TD", "TD"),
}

MARKET_METRICS = {
    "passing_yards": ("attempts", "completions", "completion_pct", "yards_per_attempt", "passing_tds", "interceptions"),
    "passing_touchdowns": ("attempts", "completions", "passing_yards", "yards_per_attempt", "interceptions", "rushing_yards"),
    "interceptions": ("attempts", "completion_pct", "passing_yards", "yards_per_attempt", "passing_tds", "rushing_yards"),
    "completions": ("attempts", "completion_pct", "passing_yards", "yards_per_attempt", "passing_tds", "interceptions"),
    "attempts": ("completions", "completion_pct", "passing_yards", "yards_per_attempt", "passing_tds", "interceptions"),
    "rushing_yards": ("carries", "yards_per_carry", "receptions", "receiving_yards", "scrimmage_yards", "skill_tds"),
    "carries": ("rushing_yards", "yards_per_carry", "receptions", "receiving_yards", "touches", "skill_tds"),
    "receptions": ("targets", "catch_pct", "receiving_yards", "yards_per_reception", "longest_reception", "receiving_tds"),
    "receiving_yards": ("targets", "receptions", "catch_pct", "yards_per_reception", "longest_reception", "receiving_tds"),
    "longest_reception": ("targets", "receptions", "receiving_yards", "yards_per_reception", "catch_pct", "receiving_tds"),
    "anytime_touchdown": ("carries", "rushing_yards", "receptions", "receiving_yards", "touches", "skill_tds"),
}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _number(value: Any) -> float | None:
    raw = _text(value).replace(",", "")
    if not raw or raw in {"--", "-"}:
        return None
    match = re.match(r"^-?\d+(?:\.\d+)?", raw)
    if not match:
        return None
    try:
        out = float(match.group(0))
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _value(values: dict[str, float | None], *labels: str) -> float | None:
    for label in labels:
        if label in values and values[label] is not None:
            return values[label]
    return None


@lru_cache(maxsize=256)
def _summary(event_id: str) -> dict[str, Any]:
    try:
        response = requests.get(
            ESPN_SUMMARY,
            params={"event": event_id},
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(f"supporting stats summary read failed: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("supporting stats summary response was not an object")
    return payload


def _athlete_categories(summary: dict[str, Any], athlete_id: str) -> dict[str, tuple[list[str], list[Any]]]:
    found: dict[str, tuple[list[str], list[Any]]] = {}
    for team_block in ((summary.get("boxscore") or {}).get("players") or []):
        if not isinstance(team_block, dict):
            continue
        for category in team_block.get("statistics") or []:
            if not isinstance(category, dict):
                continue
            name = _text(category.get("name")).lower()
            if name not in {"passing", "rushing", "receiving"}:
                continue
            labels = [str(x).upper() for x in (category.get("labels") or [])]
            for row in category.get("athletes") or []:
                if not isinstance(row, dict):
                    continue
                athlete = row.get("athlete") or {}
                if _text(athlete.get("id")) != athlete_id:
                    continue
                stats = row.get("stats") or []
                if isinstance(stats, list):
                    found[name] = (labels, stats)
                    break
    return found


def _labeled(row: tuple[list[str], list[Any]] | None) -> dict[str, float | None]:
    if row is None:
        return {}
    labels, stats = row
    return {label: _number(stats[i]) if i < len(stats) else None for i, label in enumerate(labels)}


def extract_event_metrics(summary: dict[str, Any], athlete_id: str) -> dict[str, float]:
    categories = _athlete_categories(summary, athlete_id)
    passing_row = categories.get("passing")
    rushing = _labeled(categories.get("rushing"))
    receiving = _labeled(categories.get("receiving"))
    out: dict[str, float] = {}

    if passing_row is not None:
        labels, stats = passing_row
        passing = _labeled(passing_row)
        completions = _value(passing, "CMP", "COMP")
        attempts = _value(passing, "ATT")
        catt_index = next((i for i, label in enumerate(labels) if label in {"C/ATT", "CMP/ATT", "COMP/ATT"}), None)
        if catt_index is not None and catt_index < len(stats):
            match = re.match(r"^(\d+)\s*/\s*(\d+)$", _text(stats[catt_index]))
            if match:
                completions = float(match.group(1))
                attempts = float(match.group(2))
        yards = _value(passing, "YDS", "PASS YDS", "PASSYDS")
        passing_tds = _value(passing, "TD", "TDS")
        interceptions = _value(passing, "INT", "INTS")
        if completions is not None: out["completions"] = completions
        if attempts is not None:
            out["attempts"] = attempts
            if completions is not None and attempts > 0:
                out["completion_pct"] = completions / attempts * 100.0
        if yards is not None:
            out["passing_yards"] = yards
            if attempts is not None and attempts > 0:
                out["yards_per_attempt"] = yards / attempts
        if passing_tds is not None: out["passing_tds"] = passing_tds
        if interceptions is not None: out["interceptions"] = interceptions

    carries = _value(rushing, "CAR", "ATT")
    rush_yards = _value(rushing, "YDS", "RUSH YDS", "RUSHYDS")
    rush_tds = _value(rushing, "TD", "TDS")
    if carries is not None: out["carries"] = carries
    if rush_yards is not None:
        out["rushing_yards"] = rush_yards
        if carries is not None and carries > 0:
            out["yards_per_carry"] = rush_yards / carries

    receptions = _value(receiving, "REC")
    targets = _value(receiving, "TGTS", "TGT", "TARGETS", "TAR")
    rec_yards = _value(receiving, "YDS", "REC YDS", "RECYDS")
    rec_tds = _value(receiving, "TD", "TDS")
    longest = _value(receiving, "LONG", "LG")
    if receptions is not None: out["receptions"] = receptions
    if targets is not None:
        out["targets"] = targets
        if receptions is not None and targets > 0:
            out["catch_pct"] = receptions / targets * 100.0
    if rec_yards is not None:
        out["receiving_yards"] = rec_yards
        if receptions is not None and receptions > 0:
            out["yards_per_reception"] = rec_yards / receptions
    if longest is not None: out["longest_reception"] = longest
    if rec_tds is not None: out["receiving_tds"] = rec_tds

    if rush_yards is not None or rec_yards is not None:
        out["scrimmage_yards"] = float(rush_yards or 0.0) + float(rec_yards or 0.0)
    if carries is not None or receptions is not None:
        out["touches"] = float(carries or 0.0) + float(receptions or 0.0)
    if rush_tds is not None or rec_tds is not None:
        out["skill_tds"] = float(rush_tds or 0.0) + float(rec_tds or 0.0)
    return out


def _history_row_metrics(row: dict[str, Any]) -> dict[str, float]:
    """Reuse certified Step 3 game-log fields before making any extra network read."""
    out: dict[str, float] = {}
    for source, target in (
        ("completions", "completions"),
        ("attempts", "attempts"),
        ("passing_yards", "passing_yards"),
        ("passing_tds", "passing_tds"),
        ("interceptions", "interceptions"),
    ):
        value = _number(row.get(source))
        if value is not None:
            out[target] = value

    completions = out.get("completions")
    attempts = out.get("attempts")
    passing_yards = out.get("passing_yards")
    if completions is not None and attempts is not None and attempts > 0:
        out["completion_pct"] = completions / attempts * 100.0
    if passing_yards is not None and attempts is not None and attempts > 0:
        out["yards_per_attempt"] = passing_yards / attempts
    return out


def _event_support(
    row: dict[str, Any],
    athlete_id: str,
    required_metrics: tuple[str, ...],
) -> dict[str, Any] | None:
    event_id = _text(row.get("official_event_id") or row.get("event_id"))
    if not event_id.isdigit():
        return None

    metrics = _history_row_metrics(row)
    if required_metrics and all(key in metrics for key in required_metrics):
        return {
            "official_event_id": event_id,
            "metrics": metrics,
            "source": "certified-step3-gamelog",
        }

    try:
        boxscore_metrics = extract_event_metrics(_summary(event_id), athlete_id)
    except RuntimeError:
        boxscore_metrics = {}
    metrics.update(boxscore_metrics)
    if not metrics:
        return None
    return {
        "official_event_id": event_id,
        "metrics": metrics,
        "source": "exact-id-boxscore" if boxscore_metrics else "certified-step3-gamelog",
    }


def load_supporting_stats(
    *,
    games: Any,
    athlete_id: Any,
    market_key: Any,
    mode: str = "average",
) -> dict[str, Any]:
    athlete = _text(athlete_id)
    market = _text(market_key)
    mode_key = _text(mode).lower()
    if mode_key not in {"average", "median"}:
        mode_key = "average"
    if not athlete.isdigit():
        return {"ready": False, "reason": "exact athlete id is required", "metrics": []}

    selected = [row for row in list(games or [])[:MAX_SUPPORT_GAMES] if isinstance(row, dict)]
    if not selected:
        return {"ready": False, "reason": "verified historical games are required", "metrics": []}

    profile = MARKET_METRICS.get(market, ())
    event_rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, max(1, len(selected)))) as pool:
        futures = [
            pool.submit(_event_support, row, athlete, tuple(profile))
            for row in selected
        ]
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                event_rows.append(result)

    cards: list[dict[str, Any]] = []
    for key in profile:
        values = [
            float(row["metrics"][key])
            for row in event_rows
            if key in row.get("metrics", {}) and _number(row["metrics"][key]) is not None
        ]
        if not values:
            continue
        value = mean(values) if mode_key == "average" else median(values)
        label, unit = METRIC_META[key]
        cards.append({
            "key": key,
            "label": label,
            "unit": unit,
            "value": float(value),
            "sample_size": len(values),
        })

    return {
        "ready": bool(cards),
        "reason": "" if cards else "no verified supporting metrics for selected sample",
        "mode": mode_key,
        "market_key": market,
        "event_count": len(event_rows),
        "requested_game_count": len(selected),
        "metrics": cards[:6],
        "source": (
            "Certified Step 3 athlete game log + ESPN exact-ID box scores"
            if any(row.get("source") == "exact-id-boxscore" for row in event_rows)
            else "Certified Step 3 exact-ID athlete game log"
        ),
        "sportsbook_line": False,
    }


def _format_metric(key: str, value: float) -> str:
    if key in {"completion_pct", "catch_pct"}:
        return f"{value:.1f}%"
    if key in {"yards_per_attempt", "yards_per_carry", "yards_per_reception"}:
        return f"{value:.1f}"
    if abs(value - round(value)) < 0.05:
        return str(int(round(value)))
    return f"{value:.1f}"


def render_supporting_stats(
    *,
    games: Any,
    athlete_id: Any,
    market_key: Any,
    market_label: Any,
    history_key: Any,
    history_label: Any,
) -> dict[str, Any]:
    mode_label = st.segmented_control(
        "Supporting stat summary",
        options=["AVERAGE", "MEDIAN"],
        default="AVERAGE",
        selection_mode="single",
        key="nfl_prop_analytics_page3_step6_support_mode_v1_"
        + "_".join((_text(athlete_id) or "player", _text(market_key) or "market", _text(history_key) or "window")),
    )
    mode = "median" if mode_label == "MEDIAN" else "average"
    payload = load_supporting_stats(
        games=games,
        athlete_id=athlete_id,
        market_key=market_key,
        mode=mode,
    )
    market_name = _text(market_label) or _text(market_key) or "Selected prop"
    history_name = _text(history_label) or _text(history_key) or "Selected window"

    if not payload.get("ready"):
        st.markdown(
            f"""
<section class="ks-pa6-support ks-pa6-support-unavailable"
         data-prop-page3-step6-supporting-stats="{PAGE3_SUPPORT_VERSION}"
         data-prop-page3-step6-state="unavailable"
         data-prop-page3-step6-mode="{mode}">
  <div class="ks-pa6-head"><div><span>SUPPORTING STATS • STEP 6</span><strong>Verified box-score context unavailable</strong></div><em>FAIL CLOSED</em></div>
  <p>{html_lib.escape(str(payload.get("reason") or "Supporting metrics unavailable."))}</p>
</section>
<style data-prop-page3-step6-unavailable-css="{PAGE3_SUPPORT_VERSION}">
.ks-pa6-support{{width:100%;max-width:100%;min-width:0;margin:10px 0 14px;padding:13px;border:1px solid rgba(248,113,113,.16);border-radius:16px;background:linear-gradient(180deg,rgba(6,16,28,.98),rgba(3,10,18,.99));overflow:hidden}}
.ks-pa6-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:10px;margin-bottom:10px}}
.ks-pa6-head>div{{display:flex;flex-direction:column;gap:2px;min-width:0}}
.ks-pa6-head span{{color:#38bdf8;font-size:.51rem;font-weight:950;letter-spacing:.12em}}
.ks-pa6-head strong{{color:#edf8ff;font-size:.84rem}}
.ks-pa6-head em{{color:#64748b;font-size:.48rem;font-style:normal;font-weight:850}}
.ks-pa6-support-unavailable p{{margin:6px 0 0;color:#8295aa;font-size:.62rem}}
@media(max-width:560px){{.ks-pa6-head{{align-items:flex-start;flex-direction:column}}}}
</style>
""",
            unsafe_allow_html=True,
        )
        return payload

    cards = []
    for metric in payload["metrics"]:
        cards.append(
            f"""
<article data-prop-page3-step6-metric="{html_lib.escape(metric['key'])}"
         data-prop-page3-step6-metric-sample="{metric['sample_size']}">
  <span>{html_lib.escape(metric['label'])}</span>
  <strong>{html_lib.escape(_format_metric(metric['key'], metric['value']))}</strong>
  <small>{metric['sample_size']} VERIFIED GAMES</small>
</article>
"""
        )

    st.markdown(
        f"""
<section class="ks-pa6-support"
         data-prop-page3-step6-supporting-stats="{PAGE3_SUPPORT_VERSION}"
         data-prop-page3-step6-state="ready"
         data-prop-page3-step6-mode="{payload['mode']}"
         data-prop-page3-step6-market="{html_lib.escape(_text(market_key))}"
         data-prop-page3-step6-history="{html_lib.escape(_text(history_key))}"
         data-prop-page3-step6-event-count="{payload['event_count']}"
         data-prop-page3-step6-metric-count="{len(payload['metrics'])}"
         data-prop-page3-step6-source="espn-exact-id-boxscores">
  <div class="ks-pa6-head">
    <div>
      <span>SUPPORTING STATS • STEP 6</span>
      <strong>{html_lib.escape(market_name)} • {html_lib.escape(history_name)}</strong>
    </div>
    <em>{payload['mode'].upper()} • PROP-RELEVANT CONTEXT</em>
  </div>
  <div class="ks-pa6-grid">{''.join(cards)}</div>
  <p class="ks-pa6-note">Historical box-score context only • exact ESPN event + athlete IDs • no sportsbook or projection influence</p>
</section>
<style data-prop-page3-step6-css="{PAGE3_SUPPORT_VERSION}">
.ks-pa6-support{{width:100%;max-width:100%;min-width:0;margin:10px 0 14px;padding:13px;border:1px solid rgba(56,189,248,.17);border-radius:16px;background:linear-gradient(180deg,rgba(6,16,28,.98),rgba(3,10,18,.99));overflow:hidden}}
.ks-pa6-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:10px;margin-bottom:10px}}
.ks-pa6-head>div{{display:flex;flex-direction:column;gap:2px;min-width:0}}
.ks-pa6-head span{{color:#38bdf8;font-size:.51rem;font-weight:950;letter-spacing:.12em}}
.ks-pa6-head strong{{color:#edf8ff;font-size:.84rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa6-head em{{color:#64748b;font-size:.48rem;font-style:normal;font-weight:850;text-align:right}}
.ks-pa6-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}}
.ks-pa6-grid article{{min-width:0;padding:11px 10px;border:1px solid rgba(148,163,184,.10);border-radius:11px;background:rgba(15,23,42,.45);display:flex;flex-direction:column;gap:3px}}
.ks-pa6-grid article span{{color:#71859d;font-size:.48rem;font-weight:900;letter-spacing:.07em}}
.ks-pa6-grid article strong{{color:#f8fafc;font-size:1.2rem;line-height:1}}
.ks-pa6-grid article small{{color:#60758d;font-size:.43rem;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa6-note{{margin:9px 0 0;color:#60758d;font-size:.52rem;line-height:1.4}}
.ks-pa6-support-unavailable{{border-color:rgba(248,113,113,.16)}}
.ks-pa6-support-unavailable p{{margin:6px 0 0;color:#8295aa;font-size:.62rem}}
@media(max-width:560px){{.ks-pa6-head{{align-items:flex-start;flex-direction:column}}.ks-pa6-head em{{text-align:left}}.ks-pa6-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
</style>
""",
        unsafe_allow_html=True,
    )
    return payload


__all__ = [
    "MAX_SUPPORT_GAMES",
    "METRIC_META",
    "MODEL_VERSION",
    "PAGE3_SUPPORT_STEP",
    "PAGE3_SUPPORT_VERSION",
    "PROJECTION_LOGIC",
    "SPORTSBOOK_LINE_SOURCE",
    "SPORTSBOOK_ODDS_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "WAGER_ACTIONS",
    "extract_event_metrics",
    "load_supporting_stats",
    "render_supporting_stats",
]
