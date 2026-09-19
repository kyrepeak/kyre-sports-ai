"""CFB Game Total Step 4 Matchup V2 — neon offense-vs-defense matchup board.

Presentation-only upgrade for the compact Game Total page. This module:
- reuses the already-certified NCAA offense/defense matchup engine,
- never changes projection/distribution/probability math,
- never uses sportsbook input to create the projection,
- keeps advanced fields blank when no verified source exists,
- renders Step 4 as the expanded, collapsible matchup board,
- forces the step stack into one full-width vertical column.

Frozen predecessor: cfb_game_total_step4_matchup_v1.
"""
from __future__ import annotations

from html import escape
import math
import re
from typing import Any, Mapping

import cfb_game_total_step4_matchup_v1 as legacy
import cfb_game_total_step4_multisource_v1 as multisource
import cfb_over_under_matchup_engine_v1 as matchup_engine

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
FROZEN_PREDECESSOR = "cfb_game_total_step4_matchup_v1"
STEP4_PRESENTATION_MARKER = "CFB_GAME_TOTAL_STEP4_MATCHUP_V2_NEON_STACK_ACTIVE"
STEP4_DATA_MARKER = "CFB_GAME_TOTAL_STEP4_VERIFIED_NCAA_MATCHUP_ENGINE_ACTIVE"
STEP4_DEPLOYMENT_MARKER = "CFB_GAME_TOTAL_STEP4_MULTISOURCE_FULL_COVERAGE_ACTIVE"

STEP4_CSS = r"""
<style>
/* V165: keep the existing page shell, but stack every analysis step vertically. */
.gt159-stepgrid{grid-template-columns:1fr!important;gap:8px!important}
.gt159-stepgrid>.gt159-step{grid-column:1/-1!important;width:100%!important}

/* Featured Step 4 shell */
.gt165-step4{grid-column:1/-1!important;position:relative;border:1px solid rgba(74,203,255,.68)!important;border-left:4px solid #ffd34f!important;border-radius:19px!important;background:linear-gradient(145deg,#061729 0%,#071a2b 54%,#111535 100%)!important;box-shadow:0 0 0 1px rgba(44,124,255,.22),0 0 34px rgba(0,217,255,.13),0 0 38px rgba(156,82,255,.08)!important;overflow:hidden}
.gt165-step4:before{content:"";position:absolute;inset:-1px;pointer-events:none;border-radius:19px;background:linear-gradient(90deg,rgba(34,219,255,.30),rgba(107,99,255,.19),rgba(190,68,255,.28));mix-blend-mode:screen}
.gt165-step4:after{content:"";position:absolute;left:0;right:0;top:0;height:3px;background:linear-gradient(90deg,#31e0ff 0%,#4b7dff 46%,#b758ff 100%);opacity:.90;pointer-events:none}
.gt165-step4 summary,.gt165-body{position:relative;z-index:1}
.gt165-step4 summary{min-height:76px!important;padding:12px 15px!important;grid-template-columns:52px minmax(0,1fr) auto!important;gap:13px!important;background:linear-gradient(90deg,rgba(5,31,55,.985),rgba(15,24,65,.965) 62%,rgba(33,18,78,.94))!important;border-bottom:1px solid rgba(69,184,255,.18)}
.gt165-step4 .gt159-num{width:50px!important;height:50px!important;border-radius:14px!important;background:linear-gradient(145deg,#19e1ff 0%,#4c7dff 55%,#9d59ff 100%)!important;color:#fff!important;box-shadow:0 0 22px rgba(45,190,255,.42),0 0 18px rgba(145,85,255,.25)!important;font-size:19px!important;font-weight:950!important}
.gt165-step4 .gt159-stepcopy b{font-size:18px!important;line-height:1.05!important;color:#fff!important;letter-spacing:-.01em}
.gt165-step4 .gt159-stepcopy span{font-size:9px!important;color:#a9c1d5!important;margin-top:5px!important;letter-spacing:.01em}
.gt165-headstatus{display:flex;align-items:center;justify-content:flex-end;gap:8px;min-width:0}
.gt165-coverage{display:inline-flex;align-items:center;gap:6px;padding:7px 10px;border-radius:999px;border:1px solid rgba(75,179,255,.40);background:rgba(8,47,83,.52);box-shadow:inset 0 0 0 1px rgba(64,127,255,.08)}
.gt165-coverage strong{font-size:10px;line-height:1;color:#bfe9ff;font-weight:950}
.gt165-coverage span{font-size:6px;line-height:1.05;color:#86a9c0;font-weight:850;text-transform:uppercase;letter-spacing:.06em}
.gt165-step4 .gt159-state{padding:7px 11px!important;border-radius:999px!important;font-size:8px!important;font-weight:950!important;letter-spacing:.04em}
.gt165-body{padding:10px 11px 12px!important}
.gt165-battles{display:grid;grid-template-columns:1fr;gap:10px}

.gt165-battle{border:1px solid rgba(64,184,238,.27);border-radius:13px;background:linear-gradient(145deg,rgba(5,28,49,.98),rgba(8,21,39,.98));overflow:hidden;box-shadow:inset 0 1px 0 rgba(255,255,255,.025)}
.gt165-battlehead{display:grid;grid-template-columns:minmax(0,1fr) 34px minmax(0,1fr) minmax(130px,auto);gap:10px;align-items:center;padding:11px 12px;border-bottom:1px solid rgba(70,152,196,.16);background:linear-gradient(90deg,rgba(7,35,58,.72),rgba(15,24,51,.56))}
.gt165-teamhead{display:grid;grid-template-columns:52px minmax(0,1fr);gap:9px;align-items:center;min-width:0}
.gt165-teamhead.right{grid-template-columns:minmax(0,1fr) 52px;text-align:right}
.gt165-logowrap{width:50px;height:46px;display:flex;align-items:center;justify-content:center;border-radius:12px;background:rgba(255,255,255,.94);box-shadow:inset 0 0 0 1px rgba(255,255,255,.28),0 0 14px rgba(80,163,255,.11)}
.gt165-logo{width:44px;height:38px;object-fit:contain}
.gt165-side{display:block;color:#68dfff;font-size:6px;font-weight:950;letter-spacing:.12em;text-transform:uppercase;margin-bottom:3px}
.gt165-teamname{display:block;color:#f4f9ff;font-size:11px;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gt165-teamrole{display:block;color:#819caf;font-size:6.5px;margin-top:2px}
.gt165-vs{display:flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:999px;color:#8fe7ff;font-size:8px;font-weight:950;border:1px solid rgba(82,188,255,.34);background:rgba(14,57,92,.48);box-shadow:0 0 12px rgba(48,172,255,.12)}
.gt165-read{max-width:170px;padding:8px 10px;border-radius:11px;border:1px solid rgba(86,234,180,.38);background:rgba(19,109,76,.16);text-align:right}
.gt165-read strong{display:block;color:#61efb4;font-size:8px}
.gt165-read span{display:block;color:#9fc7b7;font-size:6px;margin-top:2px}
.gt165-read.tough{border-color:rgba(255,102,116,.42);background:rgba(128,37,49,.18)}
.gt165-read.tough strong{color:#ff7a87}.gt165-read.tough span{color:#d8a4aa}
.gt165-read.mixed{border-color:rgba(244,204,90,.38);background:rgba(126,90,18,.16)}
.gt165-read.mixed strong{color:#f4ce63}.gt165-read.mixed span{color:#d6c18b}

.gt165-metrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px;padding:9px}
.gt165-metric{min-width:0;padding:7px 6px;border-radius:10px;background:rgba(8,42,62,.76);border:1px solid rgba(70,165,213,.18)}
.gt165-metric label{display:block;color:#91adbf;font-size:6px;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gt165-grade{display:inline-flex;align-items:center;justify-content:center;margin-top:5px;padding:2px 5px;min-width:25px;border-radius:7px;font-size:10px;font-weight:950}
.gt165-metric small{display:block;color:#6f8ea2;font-size:5.8px;line-height:1.25;margin-top:4px;min-height:15px}
.gt165-metric.fav{border-color:rgba(74,236,173,.28);background:rgba(12,77,59,.24)}.gt165-metric.fav .gt165-grade{color:#54efae;background:rgba(49,190,131,.16)}
.gt165-metric.tough{border-color:rgba(255,105,120,.27);background:rgba(89,31,43,.22)}.gt165-metric.tough .gt165-grade{color:#ff7b88;background:rgba(203,65,83,.15)}
.gt165-metric.mixed{border-color:rgba(244,202,91,.25);background:rgba(89,67,22,.20)}.gt165-metric.mixed .gt165-grade{color:#ffd46f;background:rgba(199,145,39,.15)}
.gt165-metric.limited{border-color:rgba(136,153,170,.19);background:rgba(29,43,55,.38)}.gt165-metric.limited .gt165-grade{color:#aebcc8;background:rgba(116,137,154,.12)}
.gt165-metric.neutral .gt165-grade{color:#8fd9ff;background:rgba(55,151,208,.14)}

.gt165-callouts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;padding:0 9px 9px}
.gt165-callout{border-radius:10px;padding:8px 9px;border:1px solid rgba(64,164,210,.21);background:rgba(6,32,51,.74)}
.gt165-callout strong{display:block;font-size:7px}.gt165-callout span{display:block;font-size:7px;color:#bed0dc;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gt165-callout.edge{border-color:rgba(75,233,172,.32)}.gt165-callout.edge strong{color:#62efb6}
.gt165-callout.risk{border-color:rgba(255,103,118,.31)}.gt165-callout.risk strong{color:#ff7c88}
.gt165-callout.impact{border-color:rgba(176,102,255,.34);background:rgba(69,31,100,.22)}.gt165-callout.impact strong{color:#ca9cff}

.gt165-integrity{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:9px}
.gt165-note{padding:8px 9px;border-radius:10px;border:1px solid rgba(79,171,217,.20);background:rgba(6,31,49,.76)}
.gt165-note strong{display:block;color:#76e3ff;font-size:7px}
.gt165-note span{display:block;color:#9db1c0;font-size:6.3px;line-height:1.4;margin-top:3px}
.gt165-note.purple{border-color:rgba(174,101,255,.28);background:rgba(66,28,96,.20)}.gt165-note.purple strong{color:#ca9cff}

.gt165-state.ready{color:#58edb3!important;border-color:rgba(88,237,179,.35)!important;background:rgba(24,111,77,.16)!important}
.gt165-state.check{color:#f6cf65!important;border-color:rgba(246,207,101,.35)!important;background:rgba(115,84,17,.16)!important}
.gt165-state.limited{color:#ff8993!important;border-color:rgba(255,137,147,.31)!important;background:rgba(112,42,50,.16)!important}

@media(max-width:760px){
  .gt165-step4 summary{grid-template-columns:48px minmax(0,1fr)!important;padding:10px 12px!important}
  .gt165-headstatus{grid-column:2;justify-content:flex-start;flex-wrap:wrap;margin-top:3px}
  .gt165-coverage{padding:6px 8px}
  .gt165-battlehead{grid-template-columns:1fr 28px 1fr;align-items:center;gap:7px;padding:9px}
  .gt165-teamhead{grid-template-columns:40px minmax(0,1fr);gap:6px}
  .gt165-teamhead.right{grid-template-columns:minmax(0,1fr) 40px}
  .gt165-logowrap{width:40px;height:38px;border-radius:9px}
  .gt165-logo{width:35px;height:31px}
  .gt165-teamname{font-size:9px}
  .gt165-teamrole{font-size:5.7px}
  .gt165-vs{width:28px;height:28px;font-size:7px}
  .gt165-read{grid-column:1/-1;justify-self:stretch;text-align:left;max-width:100%;margin-top:2px}
  .gt165-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}
  .gt165-callouts,.gt165-integrity{grid-template-columns:1fr}
}
@media(max-width:420px){
  .gt165-body{padding:8px!important}
  .gt165-battlehead{padding:8px}
  .gt165-metrics{gap:5px;padding:7px}
  .gt165-metric{padding:6px 5px}
  .gt165-callouts{padding:0 7px 7px}
}
</style>
"""

_UNAVAILABLE = {"", "—", "-", "none", "n/a", "na", "unavailable", "data limited"}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    text = _clean(value).replace(",", "").replace("%", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        number = float(match.group(0))
        return number if math.isfinite(number) else None
    except Exception:
        return None


def _usable(value: Any) -> bool:
    text = _clean(value)
    return bool(text) and text.casefold() not in _UNAVAILABLE


def _rank_text(value: Any) -> str:
    rank = _float(value)
    if rank is None:
        return ""
    return f"#{int(rank)}"


def _grade(edge: Any) -> tuple[str, str]:
    value = _float(edge)
    if value is None:
        return "DATA", "neutral"
    if value >= 0.34:
        return "A", "fav"
    if value >= 0.18:
        return "A-", "fav"
    if value >= 0.08:
        return "B+", "fav"
    if value > -0.08:
        return "B", "mixed"
    if value > -0.18:
        return "C+", "mixed"
    if value > -0.34:
        return "C", "tough"
    return "D", "tough"


def _legacy_rows(battle: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    return {
        _clean(row.get("label")): row
        for row in ((battle or {}).get("rows") or [])
        if isinstance(row, Mapping)
    }


def _legacy_tile(
    label: str,
    legacy_row: Mapping[str, Any] | None,
    *,
    unavailable_note: str,
) -> dict[str, Any]:
    row = legacy_row or {}
    ready = bool(row.get("complete"))
    if not ready:
        return {
            "label": label,
            "ready": False,
            "grade": "—",
            "tone": "limited",
            "edge": None,
            "detail": unavailable_note,
        }
    offense = legacy._fmt(row.get("offense_value"), signed=bool(row.get("epa")))
    defense = legacy._fmt(row.get("defense_value"), signed=bool(row.get("epa")))
    return {
        "label": label,
        "ready": True,
        "grade": "DATA",
        "tone": "neutral",
        "edge": None,
        "detail": f"OFF {offense} • DEF {defense}",
    }


def _engine_tile(
    label: str,
    dimension: Mapping[str, Any] | None,
    legacy_row: Mapping[str, Any] | None = None,
    *,
    unavailable_note: str = "Verified matchup row unavailable",
) -> dict[str, Any]:
    dim = dimension or {}
    if bool(dim.get("ready")):
        grade, tone = _grade(dim.get("edge"))
        offense = _clean(dim.get("offense_value")) or _rank_text(dim.get("offense_rank")) or "—"
        defense = _clean(dim.get("defense_value")) or _rank_text(dim.get("defense_rank")) or "—"
        return {
            "label": label,
            "ready": True,
            "grade": grade,
            "tone": tone,
            "edge": _float(dim.get("edge")),
            "detail": f"OFF {offense} • DEF {defense}",
            "offense_rank": dim.get("offense_rank"),
            "defense_rank": dim.get("defense_rank"),
        }
    return _legacy_tile(label, legacy_row, unavailable_note=unavailable_note)


def _direct_pair(
    offense: Mapping[str, Any],
    defense: Mapping[str, Any],
    offense_keys: tuple[str, ...],
    defense_keys: tuple[str, ...],
) -> tuple[float | None, float | None]:
    off = None
    deff = None
    for key in offense_keys:
        off = _float(offense.get(key))
        if off is not None:
            break
    for key in defense_keys:
        deff = _float(defense.get(key))
        if deff is not None:
            break
    return off, deff


def _direct_tile(
    label: str,
    offense: Mapping[str, Any],
    defense: Mapping[str, Any],
    offense_keys: tuple[str, ...],
    defense_keys: tuple[str, ...],
    *,
    unavailable_note: str,
) -> dict[str, Any]:
    off, deff = _direct_pair(offense, defense, offense_keys, defense_keys)
    if off is None or deff is None:
        return {
            "label": label,
            "ready": False,
            "grade": "—",
            "tone": "limited",
            "edge": None,
            "detail": unavailable_note,
        }
    return {
        "label": label,
        "ready": True,
        "grade": "DATA",
        "tone": "neutral",
        "edge": None,
        "detail": f"OFF {off:.1f} • DEF {deff:.1f}",
    }


def _safe_engine(
    game: Mapping[str, Any] | None,
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        result = matchup_engine.build_matchup_engine(game or {}, away, home)
        return dict(result or {})
    except Exception as exc:
        return {
            "ready": False,
            "model_ready": False,
            "reason": f"verified matchup source unavailable: {type(exc).__name__}",
        }


def _read_from_edges(edges: list[float]) -> tuple[str, str, str]:
    if len(edges) < 3:
        return "Verified matchup data limited", "mixed", "Need at least 3 verified ranked matchup rows"
    avg = sum(edges) / len(edges)
    if avg >= 0.20:
        return "Favorable offensive matchup", "fav", "Multiple matchup edges favor the offense"
    if avg >= 0.08:
        return "Slight offensive edge", "fav", "The verified matchup profile tilts offense"
    if avg <= -0.20:
        return "Tough offensive matchup", "tough", "Multiple matchup edges favor the defense"
    if avg <= -0.08:
        return "Slight defensive edge", "tough", "The verified matchup profile tilts defense"
    return "Balanced matchup", "mixed", "Verified edges are mixed or close to neutral"


def _biggest(edges: list[tuple[str, float]], *, want_max: bool) -> str:
    if len(edges) < 3:
        return "Verified edge data limited"
    label, value = (max(edges, key=lambda item: item[1]) if want_max else min(edges, key=lambda item: item[1]))
    if want_max and value <= 0.02:
        return "No clear offensive advantage"
    if not want_max and value >= -0.02:
        return "No verified defensive disadvantage"
    return label


def _impact(edges: list[float]) -> str:
    if len(edges) < 3:
        return "↔ Scoring impact unclear"
    avg = sum(edges) / len(edges)
    if avg >= 0.15:
        return "↑ Upward scoring pressure"
    if avg <= -0.15:
        return "↓ Downward scoring pressure"
    return "↔ Mixed scoring pressure"


def _battle_contract(
    *,
    offense_identity: Mapping[str, Any],
    defense_identity: Mapping[str, Any],
    offense_evidence: Mapping[str, Any],
    defense_evidence: Mapping[str, Any],
    engine_side: Mapping[str, Any] | None,
    legacy_battle: Mapping[str, Any] | None,
) -> dict[str, Any]:
    dims = dict((engine_side or {}).get("dimensions") or {})
    rows = _legacy_rows(legacy_battle)

    tiles = [
        _engine_tile(
            "Pass Yds/G",
            dims.get("passing"),
            rows.get("Passing"),
            unavailable_note="Verified passing matchup unavailable",
        ),
        _engine_tile(
            "Rush Yds/G",
            dims.get("rushing"),
            rows.get("Rushing"),
            unavailable_note="Verified rushing matchup unavailable",
        ),
        _engine_tile(
            "3rd Down",
            dims.get("third_down"),
            unavailable_note="Verified 3rd-down matchup unavailable",
        ),
        _engine_tile(
            "Red Zone",
            dims.get("red_zone"),
            unavailable_note="Verified red-zone matchup unavailable",
        ),
        _engine_tile(
            "Sack Matchup",
            dims.get("sack_pressure"),
            unavailable_note="Verified sack matchup unavailable",
        ),
        _engine_tile(
            "Turnover Pressure",
            dims.get("turnovers"),
            unavailable_note="Verified turnover matchup unavailable",
        ),
    ]

    ranked_edges = [
        (tile["label"], float(tile["edge"]))
        for tile in tiles
        if tile.get("edge") is not None
    ]
    read_edges = [value for _, value in ranked_edges]
    read_title, read_tone, read_note = _read_from_edges(read_edges)

    verified_tiles = sum(bool(tile.get("ready")) for tile in tiles)
    return {
        "offense_team": _clean(offense_identity.get("team") or offense_evidence.get("team")) or "Offense",
        "defense_team": _clean(defense_identity.get("team") or defense_evidence.get("team")) or "Defense",
        "offense_logo": _clean(offense_identity.get("logo") or offense_evidence.get("logo")),
        "defense_logo": _clean(defense_identity.get("logo") or defense_evidence.get("logo")),
        "offense_side": _clean(offense_identity.get("side")) or "OFFENSE",
        "defense_side": _clean(defense_identity.get("side")) or "DEFENSE",
        "tiles": tiles,
        "verified_tiles": verified_tiles,
        "read_title": read_title,
        "read_tone": read_tone,
        "read_note": read_note,
        "biggest_edge": _biggest(ranked_edges, want_max=True),
        "biggest_risk": _biggest(ranked_edges, want_max=False),
        "impact": _impact(read_edges),
    }


def build_step4_contract(
    identity: Mapping[str, Any] | None,
    away: Mapping[str, Any] | None,
    home: Mapping[str, Any] | None,
    game: Mapping[str, Any] | None = None,
    *,
    engine: Mapping[str, Any] | None = None,
    fallback: Mapping[str, Any] | None = None,
    load_engine: bool = False,
    load_fallback: bool = False,
) -> dict[str, Any]:
    identity = identity or {}
    away = away or {}
    home = home or {}
    ai = identity.get("away") if isinstance(identity.get("away"), Mapping) else {}
    hi = identity.get("home") if isinstance(identity.get("home"), Mapping) else {}

    legacy_contract = legacy.build_step4_contract(identity, away, home)
    engine_contract = dict(engine or (_safe_engine(game, away, home) if load_engine else {}))
    fallback_contract = dict(
        fallback
        or (
            multisource.build_display_fallback(game, away, home)
            if load_fallback
            else {}
        )
    )
    engine_contract, fallback_filled = multisource.merge_missing_dimensions(
        engine_contract,
        fallback_contract,
    )

    away_battle = _battle_contract(
        offense_identity={**dict(ai), "side": "AWAY"},
        defense_identity={**dict(hi), "side": "HOME"},
        offense_evidence=away,
        defense_evidence=home,
        engine_side=engine_contract.get("away_offense") or {},
        legacy_battle=legacy_contract.get("away_offense_vs_home_defense") or {},
    )
    home_battle = _battle_contract(
        offense_identity={**dict(hi), "side": "HOME"},
        defense_identity={**dict(ai), "side": "AWAY"},
        offense_evidence=home,
        defense_evidence=away,
        engine_side=engine_contract.get("home_offense") or {},
        legacy_battle=legacy_contract.get("home_offense_vs_away_defense") or {},
    )

    verified = away_battle["verified_tiles"] + home_battle["verified_tiles"]
    names_ready = _usable(away_battle["offense_team"]) and _usable(home_battle["offense_team"])
    if not names_ready or verified == 0:
        state = "DATA LIMITED"
    elif verified == 12:
        state = "READY"
    else:
        state = "CHECK"

    advanced_missing = []
    advanced_specs = (
        (
            "Success Rate",
            ("success_rate", "offensive_success_rate"),
            ("success_rate_allowed", "defensive_success_rate_allowed"),
        ),
        (
            "EPA / Play",
            ("epa_per_play", "offensive_epa_per_play", "epa_play"),
            ("epa_allowed_per_play", "defensive_epa_per_play", "epa_per_play_allowed"),
        ),
        (
            "Havoc",
            ("havoc_allowed_rate", "offensive_havoc_allowed_rate"),
            ("havoc_rate", "defensive_havoc_rate"),
        ),
    )
    for label, offense_keys, defense_keys in advanced_specs:
        away_pair = _direct_pair(away, home, offense_keys, defense_keys)
        home_pair = _direct_pair(home, away, offense_keys, defense_keys)
        if any(value is None for value in (*away_pair, *home_pair)):
            advanced_missing.append(label)

    return {
        "state": state,
        "ready": state == "READY",
        "away_offense_vs_home_defense": away_battle,
        "home_offense_vs_away_defense": home_battle,
        "verified_tiles": verified,
        "coverage": verified / 12.0,
        "engine_ready": bool(engine_contract.get("ready")),
        "engine_model_ready": bool(engine_contract.get("model_ready")),
        "engine_reason": _clean(engine_contract.get("reason")),
        "fallback_ready": bool(fallback_contract.get("ready")),
        "fallback_source": _clean(fallback_contract.get("source")),
        "fallback_filled": int(fallback_filled),
        "fallback_reason": _clean(fallback_contract.get("reason")),
        "advanced_missing": advanced_missing,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
    }


def _tile_html(tile: Mapping[str, Any]) -> str:
    tone = _clean(tile.get("tone")) or "limited"
    label = escape(_clean(tile.get("label")))
    grade = escape(_clean(tile.get("grade")) or "—")
    detail = escape(_clean(tile.get("detail")) or "Verified data unavailable")
    return (
        f'<div class="gt165-metric {escape(tone)}">'
        f'<label>{label}</label><span class="gt165-grade">{grade}</span>'
        f'<small>{detail}</small></div>'
    )


def _battle_html(battle: Mapping[str, Any], testid: str) -> str:
    offense_logo = _clean(battle.get("offense_logo"))
    defense_logo = _clean(battle.get("defense_logo"))
    team = _clean(battle.get("offense_team"))
    defense = _clean(battle.get("defense_team"))
    offense_side = _clean(battle.get("offense_side")) or "OFFENSE"
    defense_side = _clean(battle.get("defense_side")) or "DEFENSE"
    offense_logo_html = (
        f'<span class="gt165-logowrap"><img class="gt165-logo" src="{escape(offense_logo)}" alt="{escape(team)} logo"/></span>'
        if offense_logo else '<span class="gt165-logowrap" style="font-size:23px">🏈</span>'
    )
    defense_logo_html = (
        f'<span class="gt165-logowrap"><img class="gt165-logo" src="{escape(defense_logo)}" alt="{escape(defense)} logo"/></span>'
        if defense_logo else '<span class="gt165-logowrap" style="font-size:23px">🏈</span>'
    )
    tone = _clean(battle.get("read_tone")) or "mixed"
    tiles = "".join(_tile_html(tile) for tile in battle.get("tiles") or [])
    return f"""
<div class="gt165-battle" data-testid="{escape(testid)}">
  <div class="gt165-battlehead">
    <div class="gt165-teamhead">
      {offense_logo_html}
      <div><span class="gt165-side">{escape(offense_side)}</span><span class="gt165-teamname">{escape(team)}</span><span class="gt165-teamrole">Offense</span></div>
    </div>
    <div class="gt165-vs">VS</div>
    <div class="gt165-teamhead right">
      <div><span class="gt165-side">{escape(defense_side)}</span><span class="gt165-teamname">{escape(defense)}</span><span class="gt165-teamrole">Defense</span></div>
      {defense_logo_html}
    </div>
    <div class="gt165-read {escape(tone)}"><strong>{escape(_clean(battle.get('read_title')))}</strong><span>{escape(_clean(battle.get('read_note')))}</span></div>
  </div>
  <div class="gt165-metrics">{tiles}</div>
  <div class="gt165-callouts">
    <div class="gt165-callout edge"><strong>🏆 BIGGEST EDGE</strong><span>{escape(_clean(battle.get('biggest_edge')))}</span></div>
    <div class="gt165-callout risk"><strong>⚠ BIGGEST RISK</strong><span>{escape(_clean(battle.get('biggest_risk')))}</span></div>
    <div class="gt165-callout impact"><strong>▥ O/U IMPACT</strong><span>{escape(_clean(battle.get('impact')))}</span></div>
  </div>
</div>"""


def render_step4_html(
    status: str,
    identity: Mapping[str, Any] | None,
    away: Mapping[str, Any] | None,
    home: Mapping[str, Any] | None,
    game: Mapping[str, Any] | None = None,
    *,
    engine: Mapping[str, Any] | None = None,
    fallback: Mapping[str, Any] | None = None,
) -> str:
    contract = build_step4_contract(
        identity,
        away,
        home,
        game,
        engine=engine,
        fallback=fallback,
        load_engine=engine is None,
        load_fallback=fallback is None,
    )
    state = _clean(contract.get("state"))
    state_css = "ready" if state == "READY" else "limited" if state == "DATA LIMITED" else "check"
    missing = ", ".join(contract.get("advanced_missing") or []) or "None"
    coverage = int(round(float(contract.get("coverage") or 0.0) * 100.0))
    fallback_filled = int(contract.get("fallback_filled") or 0)
    fallback_source = _clean(contract.get("fallback_source")) or "multi-source display fallback"
    if fallback_filled:
        engine_note = (
            "NCAA matchup tables primary. "
            f"{fallback_source} recovered {fallback_filled} NCAA-missing matchup cells."
        )
    elif contract.get("engine_ready"):
        engine_note = "NCAA matchup tables connected; multi-source fallback not needed."
    elif contract.get("fallback_ready"):
        engine_note = "cfbstats fallback connected for verified display evidence."
    else:
        engine_note = (
            _clean(contract.get("engine_reason"))
            or _clean(contract.get("fallback_reason"))
            or "Verified matchup enrichment unavailable."
        )
    return f"""
<details class="gt159-step gt165-step4 {state_css}" data-testid="gt157-step-4" data-step4-state="{escape(state)}" data-step4-coverage="{coverage}" data-step4-fallback-filled="{fallback_filled}" open>
  <summary>
    <span class="gt159-num">4</span>
    <span class="gt159-stepcopy"><b>Matchup</b><span>Off vs Def · Pass · Rush · Situational</span></span>
    <span class="gt165-headstatus">
      <span class="gt165-coverage" data-testid="gt165-step4-header-coverage"><strong>{coverage}%</strong><span>Matchup<br/>Coverage</span></span>
      <span class="gt159-state gt165-state {state_css}">{escape(state)}</span>
    </span>
  </summary>
  <div class="gt159-stepbody gt165-body">
    <div class="gt165-battles">
      {_battle_html(contract['away_offense_vs_home_defense'], 'gt165-step4-away-off-home-def')}
      {_battle_html(contract['home_offense_vs_away_defense'], 'gt165-step4-home-off-away-def')}
    </div>
    <div class="gt165-integrity">
      <div class="gt165-note" data-testid="gt165-step4-source-integrity"><strong>✓ VERIFIED MATCHUP DATA</strong><span>{escape(engine_note)} Visible matchup coverage: {coverage}%.</span></div>
      <div class="gt165-note purple" data-testid="gt165-step4-advanced-integrity"><strong>◈ ADVANCED-METRIC INTEGRITY</strong><span>Optional advanced fields not fully verified: {escape(missing)}. Core Step 4 uses NCAA as primary plus source-verified display fallback only when NCAA leaves a tile blank; no advanced value is fabricated. Projection mutation: OFF · sportsbook influence: 0.0%.</span></div>
    </div>
  </div>
</details>"""


__all__ = [
    "FROZEN_PREDECESSOR",
    "MAY_MODIFY_PROJECTION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP4_CSS",
    "STEP4_DATA_MARKER",
    "STEP4_DEPLOYMENT_MARKER",
    "STEP4_PRESENTATION_MARKER",
    "build_step4_contract",
    "render_step4_html",
]
