"""MLB Moneyline V16.8 — Step 3 starter vs opposing lineup matchup.

Presentation/evidence wrapper over permanently frozen V16.7. Step 3 evaluates each
posted opposing lineup against the probable starter using official MLB handedness
splits. It is descriptive evidence only: no Moneyline probability, simulation,
fair-odds, candidate selection, ranking, or market math changes.

Fail-closed: both official batting orders must be posted and the starter/lineup split
sample must be sufficient before a matchup grade is emitted.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape
import json
import math
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import streamlit as st
import mlb_moneyline_hub_v167 as prior

MODEL_VERSION = "V16.8 • MONEYLINE STEP 3 • STARTER VS OPPOSING LINEUP"
FROZEN_MONEYLINE_PRESENTATION = "mlb_moneyline_hub_v167"
FROZEN_MODEL_CHAIN = prior.FROZEN_MODEL_CHAIN
SEASON = prior.SEASON

MIN_LINEUP_HITTERS = 7
MIN_LINEUP_SPLIT_PA = 350
MIN_STARTER_SIDE_COVERAGE = 0.75

_STEP3_CSS = r"""
<style>
.ml168-step3{grid-area:identity;margin-top:7px;padding:10px 11px;border:1px solid rgba(226,149,58,.30);border-radius:13px;background:linear-gradient(145deg,rgba(31,21,8,.94),rgba(12,18,26,.97));box-shadow:inset 3px 0 #f0a24d}
.ml168-step3-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.ml168-step3-title{font-size:.58rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;color:#ffc77f}
.ml168-grade{display:inline-flex;align-items:center;border-radius:999px;padding:5px 8px;font-size:.50rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;border:1px solid #6c5c42;background:#2c2417;color:#f4d8ad}
.ml168-grade.home{border-color:#356f55;background:#0d2d22;color:#96e5bb}.ml168-grade.away{border-color:#4e64a1;background:#111d3c;color:#abc2ff}.ml168-grade.neutral{border-color:#75621e;background:#31290d;color:#f4dc78}.ml168-grade.limited{border-color:#5a626a;background:#22292f;color:#d2dbe1}
.ml168-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:8px}.ml168-side{border:1px solid rgba(226,149,58,.20);border-radius:10px;background:rgba(9,16,23,.78);padding:8px}.ml168-side h4{margin:0 0 4px;color:#f4f7f9;font-size:.63rem;line-height:1.25}.ml168-side small{color:#7e909b;font-size:.44rem}.ml168-side-grade{display:inline-flex;margin-top:5px;border-radius:999px;padding:4px 6px;border:1px solid #5a6570;background:#17212a;color:#d5dde2;font-size:.44rem;font-weight:900}.ml168-side-grade.hitter{border-color:#6d6330;background:#30290e;color:#f4df84}.ml168-side-grade.pitcher{border-color:#4e64a1;background:#111d3c;color:#b1c8ff}.ml168-side-grade.neutral{border-color:#4d6255;background:#15251d;color:#b8dec9}.ml168-side-grade.limited{border-color:#555e65;background:#20272c;color:#c8d0d5}
.ml168-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:7px}.ml168-stat{border:1px solid rgba(91,140,166,.18);border-radius:8px;padding:6px 4px;background:#091722;text-align:center}.ml168-stat b{display:block;color:#e8f0f4;font-size:.57rem}.ml168-stat span{display:block;color:#718592;font-size:.40rem;margin-top:2px;text-transform:uppercase}
.ml168-pills{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.ml168-pill{display:inline-flex;border-radius:999px;padding:4px 7px;border:1px solid rgba(226,149,58,.23);background:#221b10;color:#ecc994;font-size:.46rem;font-weight:850}.ml168-source{margin-top:6px;color:#708696;font-size:.43rem;line-height:1.4}
@media(max-width:640px){.ml168-grid{grid-template-columns:1fr}.ml168-step3{padding:9px}.ml168-stats{grid-template-columns:repeat(3,minmax(0,1fr))}}
</style>
"""


def _f(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _i(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None


def _rate(value: Any) -> float | None:
    val = _f(value)
    if val is None:
        return None
    if abs(val) > 1.0:
        val /= 100.0
    return max(0.0, min(1.0, val))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _json(url: str) -> dict[str, Any] | None:
    try:
        req = Request(url, headers={"User-Agent": "KyreSportsAI/16.8"})
        with urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False)
def _stat_split(player_id: int, group: str, sit_code: str) -> dict[str, Any]:
    if group not in {"hitting", "pitching"} or sit_code not in {"vl", "vr"}:
        return {"status": "PENDING", "stat": {}}
    query = urlencode({
        "stats": "statSplits",
        "group": group,
        "season": SEASON,
        "sitCodes": sit_code,
        "gameType": "R",
    })
    data = _json(f"https://statsapi.mlb.com/api/v1/people/{int(player_id)}/stats?{query}")
    if not data:
        return {"status": "PENDING", "stat": {}}
    try:
        blocks = data.get("stats") or []
        splits = (blocks[0].get("splits") or []) if blocks else []
        if not splits:
            return {"status": "VERIFIED_NO_SPLIT", "stat": {}}
        stat = splits[0].get("stat") or {}
        return {"status": "VERIFIED", "stat": stat if isinstance(stat, dict) else {}}
    except Exception:
        return {"status": "PENDING", "stat": {}}


def _split_code_for_pitcher_hand(hand: Any) -> str | None:
    text = str(hand or "").strip().upper()
    if text.startswith("L"):
        return "vl"
    if text.startswith("R"):
        return "vr"
    return None


def _effective_batter_side(bat_side: Any, starter_hand: Any) -> str | None:
    batter = str(bat_side or "").strip().upper()[:1]
    starter = str(starter_hand or "").strip().upper()[:1]
    if batter in {"L", "R"}:
        return batter
    if batter == "S" and starter == "R":
        return "L"
    if batter == "S" and starter == "L":
        return "R"
    return None


def _player_meta(feed: Mapping[str, Any], player_id: int) -> dict[str, Any]:
    players = ((feed.get("gameData") or {}).get("players") or {})
    item = players.get(f"ID{int(player_id)}") or {}
    return {
        "name": str(item.get("fullName") or f"Player {player_id}"),
        "bat_side": str((item.get("batSide") or {}).get("code") or ""),
        "pitch_hand": str((item.get("pitchHand") or {}).get("code") or ""),
    }


def _official_lineup(feed: Mapping[str, Any], side: str) -> list[int]:
    teams = (((feed.get("liveData") or {}).get("boxscore") or {}).get("teams") or {})
    raw = (teams.get(side) or {}).get("battingOrder") or []
    out: list[int] = []
    for value in raw:
        pid = _i(value)
        if pid:
            out.append(pid)
    return out[:9]


def _probable(feed: Mapping[str, Any], side: str) -> dict[str, Any]:
    probable = (((feed.get("gameData") or {}).get("probablePitchers") or {}).get(side) or {})
    pid = _i(probable.get("id"))
    if not pid:
        return {}
    meta = _player_meta(feed, pid)
    return {
        "id": pid,
        "name": str(probable.get("fullName") or meta.get("name") or "TBD"),
        "hand": meta.get("pitch_hand") or "",
    }


def _hitter_payload(response: Mapping[str, Any]) -> dict[str, Any]:
    stat = response.get("stat") or {}
    pa = _i(stat.get("plateAppearances")) or 0
    ab = _i(stat.get("atBats")) or 0
    hits = _i(stat.get("hits")) or 0
    strikeouts = _i(stat.get("strikeOuts")) or 0
    walks = _i(stat.get("baseOnBalls")) or 0
    avg = _rate(stat.get("avg"))
    if avg is None and ab > 0:
        avg = hits / ab
    ops = _f(stat.get("ops"))
    return {
        "status": response.get("status") or "PENDING",
        "pa": pa,
        "ab": ab,
        "hits": hits,
        "avg": avg,
        "ops": ops,
        "k_pct": strikeouts / pa if pa > 0 else None,
        "bb_pct": walks / pa if pa > 0 else None,
    }


def _pitcher_payload(response: Mapping[str, Any]) -> dict[str, Any]:
    stat = response.get("stat") or {}
    bf = _i(stat.get("battersFaced")) or 0
    hits = _i(stat.get("hits")) or 0
    strikeouts = _i(stat.get("strikeOuts")) or 0
    walks = _i(stat.get("baseOnBalls")) or 0
    avg = _rate(stat.get("avg"))
    ops = _f(stat.get("ops"))
    return {
        "status": response.get("status") or "PENDING",
        "bf": bf,
        "hits": hits,
        "avg": avg,
        "ops": ops,
        "k_pct": strikeouts / bf if bf > 0 else None,
        "bb_pct": walks / bf if bf > 0 else None,
    }


def _fetch_hitter_splits(player_ids: list[int], sit_code: str) -> dict[int, dict[str, Any]]:
    ids = [int(x) for x in player_ids if _i(x)]
    if not ids:
        return {}
    out: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(9, len(ids))) as pool:
        futures = {pool.submit(_stat_split, pid, "hitting", sit_code): pid for pid in ids}
        for future in as_completed(futures):
            pid = futures[future]
            try:
                out[pid] = _hitter_payload(future.result())
            except Exception:
                out[pid] = _hitter_payload({"status": "PENDING", "stat": {}})
    return out


def _aggregate_lineup(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [row for row in rows if (row.get("pa") or 0) > 0 and row.get("avg") is not None]
    total_pa = sum(int(row.get("pa") or 0) for row in usable)
    total_ab = sum(int(row.get("ab") or 0) for row in usable)
    hits = sum(int(row.get("hits") or 0) for row in usable)
    if not usable or total_pa <= 0:
        return {"hitters": 0, "pa": 0, "ab": 0, "avg": None, "ops": None, "k_pct": None, "bb_pct": None}

    def weighted(metric: str) -> float | None:
        pairs = [(float(row[metric]), int(row.get("pa") or 0)) for row in usable if row.get(metric) is not None]
        denom = sum(weight for _, weight in pairs)
        return sum(value * weight for value, weight in pairs) / denom if denom > 0 else None

    return {
        "hitters": len(usable),
        "pa": total_pa,
        "ab": total_ab,
        "avg": hits / total_ab if total_ab > 0 else weighted("avg"),
        "ops": weighted("ops"),
        "k_pct": weighted("k_pct"),
        "bb_pct": weighted("bb_pct"),
    }


def _aggregate_starter_sides(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    batter_sides: list[str],
) -> dict[str, Any]:
    known = [side for side in batter_sides if side in {"L", "R"}]
    if not known:
        return {"coverage": 0.0, "avg": None, "ops": None, "k_pct": None, "bb_pct": None, "bf": 0}

    counts = {"L": known.count("L"), "R": known.count("R")}
    payloads = {"L": left, "R": right}
    represented = 0
    weighted_rows: list[tuple[dict[str, Any], int]] = []
    for side, count in counts.items():
        if count <= 0:
            continue
        row = dict(payloads[side] or {})
        if row.get("avg") is not None and (row.get("bf") or 0) > 0:
            represented += count
            weighted_rows.append((row, count))

    coverage = represented / len(known) if known else 0.0
    if not weighted_rows:
        return {"coverage": coverage, "avg": None, "ops": None, "k_pct": None, "bb_pct": None, "bf": 0}

    def weighted(metric: str) -> float | None:
        pairs = [(float(row[metric]), count) for row, count in weighted_rows if row.get(metric) is not None]
        denom = sum(weight for _, weight in pairs)
        return sum(value * weight for value, weight in pairs) / denom if denom > 0 else None

    return {
        "coverage": coverage,
        "avg": weighted("avg"),
        "ops": weighted("ops"),
        "k_pct": weighted("k_pct"),
        "bb_pct": weighted("bb_pct"),
        "bf": sum(int(row.get("bf") or 0) for row, _ in weighted_rows),
    }


def _signal(value: float | None, center: float, scale: float, high_good: bool = True) -> float | None:
    if value is None:
        return None
    raw = (float(value) - center) / scale
    if not high_good:
        raw *= -1.0
    return _clamp(raw, -1.0, 1.0)


def _matchup_score(lineup: Mapping[str, Any], starter: Mapping[str, Any]) -> dict[str, Any]:
    lineup_signals = [
        (_signal(lineup.get("avg"), 0.245, 0.050, True), 0.35),
        (_signal(lineup.get("ops"), 0.720, 0.180, True), 0.35),
        (_signal(lineup.get("k_pct"), 0.225, 0.100, False), 0.20),
        (_signal(lineup.get("bb_pct"), 0.085, 0.060, True), 0.10),
    ]
    starter_signals = [
        (_signal(starter.get("avg"), 0.245, 0.050, True), 0.35),
        (_signal(starter.get("ops"), 0.720, 0.180, True), 0.35),
        (_signal(starter.get("k_pct"), 0.225, 0.100, False), 0.20),
        (_signal(starter.get("bb_pct"), 0.085, 0.060, True), 0.10),
    ]

    def combine(rows: list[tuple[float | None, float]]) -> tuple[float | None, float]:
        usable = [(float(value), weight) for value, weight in rows if value is not None]
        denom = sum(weight for _, weight in usable)
        if denom <= 0:
            return None, 0.0
        return sum(value * weight for value, weight in usable) / denom, denom

    lineup_signal, lineup_coverage = combine(lineup_signals)
    starter_signal, starter_coverage = combine(starter_signals)
    if lineup_signal is None or starter_signal is None:
        return {"score": None, "label": "DATA LIMITED / PENDING", "label_cls": "limited", "coverage": 0.0}

    combined = 0.55 * lineup_signal + 0.45 * starter_signal
    score = int(round(_clamp(50.0 + 25.0 * combined, 25.0, 75.0)))
    if score >= 65:
        label, cls = "STRONG LINEUP EDGE", "hitter"
    elif score >= 57:
        label, cls = "LINEUP EDGE", "hitter"
    elif score <= 35:
        label, cls = "STRONG STARTER EDGE", "pitcher"
    elif score <= 43:
        label, cls = "STARTER EDGE", "pitcher"
    else:
        label, cls = "NEUTRAL", "neutral"
    return {
        "score": score,
        "label": label,
        "label_cls": cls,
        "coverage": min(lineup_coverage, starter_coverage),
    }


def _side_matchup(feed: Mapping[str, Any], offense_side: str, starter_side: str) -> dict[str, Any]:
    lineup_ids = _official_lineup(feed, offense_side)
    starter = _probable(feed, starter_side)
    if len(lineup_ids) < 9:
        return {
            "status": "PENDING",
            "lineup_confirmed": False,
            "lineup_count": len(lineup_ids),
            "starter": starter,
            "score": None,
            "label": "LINEUP NOT CONFIRMED",
            "label_cls": "limited",
            "reason": "Official MLB batting order has fewer than nine hitters.",
        }
    if not starter.get("id") or starter.get("hand") not in {"L", "R"}:
        return {
            "status": "PENDING",
            "lineup_confirmed": True,
            "lineup_count": len(lineup_ids),
            "starter": starter,
            "score": None,
            "label": "STARTER HAND PENDING",
            "label_cls": "limited",
            "reason": "Probable starter identity/handedness is incomplete.",
        }

    split_code = _split_code_for_pitcher_hand(starter.get("hand"))
    hitter_splits = _fetch_hitter_splits(lineup_ids, split_code or "vr")
    hitter_rows: list[dict[str, Any]] = []
    effective_sides: list[str] = []
    for pid in lineup_ids:
        meta = _player_meta(feed, pid)
        row = dict(hitter_splits.get(pid) or {})
        row["player_id"] = pid
        row["name"] = meta.get("name")
        hitter_rows.append(row)
        side = _effective_batter_side(meta.get("bat_side"), starter.get("hand"))
        if side:
            effective_sides.append(side)

    lineup = _aggregate_lineup(hitter_rows)
    left = _pitcher_payload(_stat_split(int(starter["id"]), "pitching", "vl"))
    right = _pitcher_payload(_stat_split(int(starter["id"]), "pitching", "vr"))
    starter_splits = _aggregate_starter_sides(left, right, effective_sides)

    sufficient = (
        lineup.get("hitters", 0) >= MIN_LINEUP_HITTERS
        and lineup.get("pa", 0) >= MIN_LINEUP_SPLIT_PA
        and starter_splits.get("coverage", 0.0) >= MIN_STARTER_SIDE_COVERAGE
        and starter_splits.get("avg") is not None
    )
    quality_score = 0
    quality_score += 30
    quality_score += 20 if starter.get("id") and starter.get("hand") in {"L", "R"} else 0
    quality_score += 30 if lineup.get("hitters", 0) >= MIN_LINEUP_HITTERS and lineup.get("pa", 0) >= MIN_LINEUP_SPLIT_PA else 15 if lineup.get("hitters", 0) >= 5 else 0
    quality_score += 20 if starter_splits.get("coverage", 0.0) >= MIN_STARTER_SIDE_COVERAGE else int(round(20 * starter_splits.get("coverage", 0.0)))

    grade = _matchup_score(lineup, starter_splits) if sufficient else {
        "score": None,
        "label": "DATA LIMITED / PENDING",
        "label_cls": "limited",
        "coverage": 0.0,
    }
    return {
        "status": "VERIFIED" if sufficient else "PENDING",
        "lineup_confirmed": True,
        "lineup_count": len(lineup_ids),
        "starter": starter,
        "lineup": lineup,
        "starter_splits": starter_splits,
        "score": grade.get("score"),
        "label": grade.get("label"),
        "label_cls": grade.get("label_cls"),
        "quality_score": quality_score,
        "reason": "" if sufficient else "Official lineup is posted, but handedness-split evidence is below the fail-closed threshold.",
    }


def _overall_grade(away: Mapping[str, Any], home: Mapping[str, Any]) -> tuple[str, str, float | None]:
    away_score = _f(away.get("score"))
    home_score = _f(home.get("score"))
    if away_score is None or home_score is None:
        return "DATA LIMITED / PENDING", "limited", None
    edge = home_score - away_score
    if edge >= 10:
        return "STRONG HOME MATCHUP EDGE", "home", edge
    if edge >= 4:
        return "HOME MATCHUP EDGE", "home", edge
    if edge <= -10:
        return "STRONG AWAY MATCHUP EDGE", "away", edge
    if edge <= -4:
        return "AWAY MATCHUP EDGE", "away", edge
    return "BALANCED MATCHUPS", "neutral", edge


def _ctx(result: Mapping[str, Any]) -> dict[str, Any]:
    game_pk = _i(result.get("game_pk"))
    if not game_pk:
        return {
            "grade": "DATA LIMITED / PENDING",
            "grade_cls": "limited",
            "edge": None,
            "reason": "No verified MLB game PK available.",
            "away": {},
            "home": {},
        }
    feed = prior._game_feed(game_pk)
    if not feed:
        return {
            "grade": "DATA LIMITED / PENDING",
            "grade_cls": "limited",
            "edge": None,
            "reason": "Official MLB live game feed unavailable.",
            "away": {},
            "home": {},
        }

    away = _side_matchup(feed, "away", "home")
    home = _side_matchup(feed, "home", "away")
    grade, grade_cls, edge = _overall_grade(away, home)
    return {
        "grade": grade,
        "grade_cls": grade_cls,
        "edge": edge,
        "away": away,
        "home": home,
        "reason": "" if edge is not None else "Both starter-vs-lineup matchup sides must clear the evidence threshold.",
    }


def _fmt(value: Any, digits: int = 3, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.{digits}f}{suffix}"


def _side_html(title: str, side: Mapping[str, Any]) -> str:
    starter = side.get("starter") or {}
    lineup = side.get("lineup") or {}
    pitcher = side.get("starter_splits") or {}
    score = side.get("score")
    score_text = "N/A" if score is None else f"{int(score)}/100"
    label = escape(str(side.get("label") or "DATA LIMITED / PENDING"))
    cls = escape(str(side.get("label_cls") or "limited"))
    hand = escape(str(starter.get("hand") or "?"))
    starter_name = escape(str(starter.get("name") or "TBD"))
    sample = f'{int(lineup.get("hitters") or 0)} hitters • {int(lineup.get("pa") or 0)} split PA'
    return (
        '<div class="ml168-side">'
        f'<h4>{escape(title)}</h4>'
        f'<small>{starter_name} • {hand}HP • {escape(sample)}</small>'
        f'<div class="ml168-side-grade {cls}">{label} • {escape(score_text)}</div>'
        '<div class="ml168-stats">'
        f'<div class="ml168-stat"><b>{_fmt(lineup.get("avg"))}</b><span>Lineup AVG split</span></div>'
        f'<div class="ml168-stat"><b>{_fmt(lineup.get("ops"))}</b><span>Lineup OPS split</span></div>'
        f'<div class="ml168-stat"><b>{_fmt((lineup.get("k_pct") * 100) if lineup.get("k_pct") is not None else None,1,"%")}</b><span>Lineup K%</span></div>'
        '</div>'
        '<div class="ml168-stats">'
        f'<div class="ml168-stat"><b>{_fmt(pitcher.get("avg"))}</b><span>Starter AVG allowed</span></div>'
        f'<div class="ml168-stat"><b>{_fmt(pitcher.get("ops"))}</b><span>Starter OPS allowed</span></div>'
        f'<div class="ml168-stat"><b>{_fmt((pitcher.get("k_pct") * 100) if pitcher.get("k_pct") is not None else None,1,"%")}</b><span>Starter K%</span></div>'
        '</div>'
        f'<div class="ml168-source">Data quality {int(side.get("quality_score") or 0)}/100. {escape(str(side.get("reason") or ""))}</div>'
        '</div>'
    )


def _html(context: Mapping[str, Any]) -> str:
    edge = context.get("edge")
    edge_text = "N/A" if edge is None else f"{abs(float(edge)):.1f} pts"
    return (
        '<div class="ml168-step3">'
        '<div class="ml168-step3-head">'
        '<span class="ml168-step3-title">STEP 3 • STARTER VS OPPOSING LINEUP MATCHUP</span>'
        f'<span class="ml168-grade {escape(str(context.get("grade_cls") or "limited"))}">{escape(str(context.get("grade") or "DATA LIMITED / PENDING"))}</span>'
        '</div>'
        '<div class="ml168-grid">'
        f'{_side_html("Away lineup vs home starter", context.get("away") or {})}'
        f'{_side_html("Home lineup vs away starter", context.get("home") or {})}'
        '</div>'
        '<div class="ml168-pills">'
        f'<span class="ml168-pill">MATCHUP DIFFERENTIAL • {escape(edge_text)}</span>'
        '<span class="ml168-pill">OFFICIAL LINEUPS ONLY</span>'
        '<span class="ml168-pill">NO PROBABILITY ADJUSTMENT</span>'
        '</div>'
        f'<div class="ml168-source">Official MLB Stats API statSplits + official game feed • fail-closed below lineup/sample thresholds. {escape(str(context.get("reason") or ""))}</div>'
        '</div>'
    )


def _inject(card: str, html: str) -> str:
    text = str(card or "")
    if not html or "ks-pick-card" not in text or "ml168-step3" in text:
        return text
    return text[:-6] + html + "</div>" if text.endswith("</div>") else text + html


_FROZEN_STEP2_RENDERER = prior._renderer


def _renderer(original, rows, lineups):
    step2 = _FROZEN_STEP2_RENDERER(original, rows, lineups)

    def wrapped(results, status_info, team_logo, h):
        ordered = list(results or [])[:5]
        cursor = {"i": 0}
        original_markdown = st.markdown

        def capture(body: Any, *args: Any, **kwargs: Any):
            text = str(body or "")
            if "ks-pick-card" in text and cursor["i"] < len(ordered):
                text = _inject(text, _html(_ctx(ordered[cursor["i"]])))
                cursor["i"] += 1
            return original_markdown(text, *args, **kwargs)

        st.markdown = capture
        try:
            return step2(results, status_info, team_logo, h)
        finally:
            st.markdown = original_markdown

    return wrapped


def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
    """Render frozen V16.7 plus presentation-only Step 3 starter-vs-lineup evidence."""
    st.markdown(_STEP3_CSS, unsafe_allow_html=True)
    original_renderer = prior._renderer
    prior._renderer = _renderer
    try:
        return prior.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        prior._renderer = original_renderer


__all__ = [
    "FROZEN_MODEL_CHAIN",
    "FROZEN_MONEYLINE_PRESENTATION",
    "MIN_LINEUP_HITTERS",
    "MIN_LINEUP_SPLIT_PA",
    "MODEL_VERSION",
    "_aggregate_lineup",
    "_aggregate_starter_sides",
    "_effective_batter_side",
    "_matchup_score",
    "_overall_grade",
    "_side_matchup",
    "render_moneyline_hub",
]
