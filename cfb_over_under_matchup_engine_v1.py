"""CFB Over/Under Intelligence V2 — Upgrade Step 3 offense-vs-defense engine.

Additive model layer above permanently frozen CFB Steps 1-12 and frozen O/U
Upgrade Steps 1-2.

The engine makes each offense-vs-opponent-defense matchup an explicit model
input using current NCAA team-stat rankings. It is intentionally conservative:
- same-division rank pools only (FBS-vs-FBS or FCS-vs-FCS),
- missing categories contribute zero rather than being invented,
- a minimum evidence threshold is required before any projection adjustment,
- the incremental adjustment is capped at +/- 3.5 points per team,
- the analysis total line has exactly 0% influence on the matchup adjustment.

Active matchup dimensions
-------------------------
1. scoring offense vs scoring defense,
2. total offense vs total defense,
3. passing offense vs passing defense,
4. rushing offense vs rushing defense,
5. third-down offense vs third-down defense,
6. red-zone offense vs red-zone defense,
7. sacks allowed vs defensive team sacks,
8. turnovers lost vs turnovers gained.

EPA/play and success-rate fields are intentionally NOT fabricated because the
current certified NCAA team-stat source does not publish those measures in a
stable first-party table. Later additive upgrades may add them when a verified
source/derivation is certified.

No sportsbook feed, market-implied probability, EV, price, or Monte Carlo is
introduced here.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from html.parser import HTMLParser
import math
from typing import Any, Mapping
from urllib.parse import urljoin

import streamlit as st

import cfb_over_under_model_v1 as frozen_raw
import cfb_team_data_v1 as frozen_team

MODEL_VERSION = "CFB O/U MATCHUP ENGINE V1 • UPGRADE STEP 3 OFFENSE VS DEFENSE"
FROZEN_RAW_MODEL = "cfb_over_under_model_v1"
FROZEN_TEAM_DATA = "cfb_team_data_v2"

NCAA_FBS_STATS_INDEX = frozen_team.NCAA_STATS_INDEX
NCAA_FCS_STATS_INDEX = "https://www.ncaa.com/stats/football/fcs"

MAX_TEAM_MATCHUP_ADJUSTMENT = 3.5
MIN_ENGINE_MODEL_COVERAGE = 0.40
MIN_ENGINE_DIMENSIONS = 3
ANALYSIS_LINE_MATCHUP_WEIGHT = 0.0

_DIMENSIONS = (
    ("scoring", "scoring_offense", "scoring_defense", 0.05),
    ("total_yards", "total_offense", "total_defense", 0.05),
    ("passing", "passing_offense", "passing_defense", 0.20),
    ("rushing", "rushing_offense", "rushing_defense", 0.18),
    ("third_down", "third_down_offense", "third_down_defense", 0.16),
    ("red_zone", "red_zone_offense", "red_zone_defense", 0.16),
    ("sack_pressure", "sacks_allowed", "team_sacks", 0.10),
    ("turnovers", "turnovers_lost", "turnovers_gained", 0.10),
)

_CATEGORY_RULES = {
    "scoring_offense": {
        "alternatives": (("scoring offense",),),
        "excludes": ("defense",),
    },
    "scoring_defense": {
        "alternatives": (("scoring defense",),),
        "excludes": (),
    },
    "total_offense": {
        "alternatives": (("total offense",),),
        "excludes": ("defense",),
    },
    "total_defense": {
        "alternatives": (("total defense",),),
        "excludes": (),
    },
    "passing_offense": {
        "alternatives": (("passing offense",),),
        "excludes": ("defense", "allowed"),
    },
    "passing_defense": {
        "alternatives": (("passing yards allowed",), ("passing defense",)),
        "excludes": (),
    },
    "rushing_offense": {
        "alternatives": (("rushing offense",),),
        "excludes": ("defense",),
    },
    "rushing_defense": {
        "alternatives": (("rushing defense",),),
        "excludes": (),
    },
    "third_down_offense": {
        "alternatives": (
            ("3rd down conversion",),
            ("third down conversion",),
        ),
        "excludes": ("defense",),
    },
    "third_down_defense": {
        "alternatives": (
            ("3rd down conversion", "defense"),
            ("third down", "defense"),
        ),
        "excludes": (),
    },
    "red_zone_offense": {
        "alternatives": (("red zone offense",),),
        "excludes": ("defense",),
    },
    "red_zone_defense": {
        "alternatives": (("red zone defense",),),
        "excludes": (),
    },
    "sacks_allowed": {
        "alternatives": (("sacks allowed",),),
        "excludes": (),
    },
    "team_sacks": {
        "alternatives": (("team sacks",), ("sacks",)),
        "excludes": ("allowed", "sack yards", "sacks per game"),
    },
    "turnovers_lost": {
        "alternatives": (("turnovers lost",),),
        "excludes": (),
    },
    "turnovers_gained": {
        "alternatives": (("turnovers gained",),),
        "excludes": (),
    },
}

_LABELS = {
    "scoring": "Scoring",
    "total_yards": "Total yards",
    "passing": "Passing",
    "rushing": "Rushing",
    "third_down": "3rd down",
    "red_zone": "Red zone",
    "sack_pressure": "Sack pressure",
    "turnovers": "Turnover pressure",
}


def _clean(value: Any) -> str:
    return frozen_team._clean(value)


def _int(value: Any) -> int | None:
    return frozen_team._int(value)


def _float(value: Any) -> float | None:
    return frozen_team._float(value)


def _clamp(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def _day(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = _clean(value)
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return text[:10]


def _profile_division(profile: Mapping[str, Any]) -> str:
    explicit = _clean(profile.get("division_context")).upper()
    if explicit == "FCS":
        return "FCS"
    source = _clean(profile.get("data_source")).lower()
    return "FCS" if "fcs" in source else "FBS"


class _CategoryOptionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._value = ""
        self._parts: list[str] = []
        self._in_option = False
        self.options: list[tuple[str, str]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "option":
            return
        self._in_option = True
        self._parts = []
        self._value = dict(attrs).get("value") or ""

    def handle_data(self, data: str) -> None:
        if self._in_option:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "option" or not self._in_option:
            return
        label = _clean(" ".join(self._parts))
        value = _clean(self._value)
        if (
            label
            and (
                "/stats/football/fbs/" in value
                or "/stats/football/fcs/" in value
            )
        ):
            self.options.append((label, value))
        self._in_option = False
        self._parts = []
        self._value = ""


def _matches_rule(label: str, rule: Mapping[str, Any]) -> bool:
    lower = _clean(label).lower()
    if any(term in lower for term in rule.get("excludes") or ()):
        return False
    for terms in rule.get("alternatives") or ():
        if all(term in lower for term in terms):
            return True
    return False


def _discover_categories(html: str) -> dict[str, dict[str, str]]:
    parser = _CategoryOptionParser()
    parser.feed(html or "")
    out: dict[str, dict[str, str]] = {}
    used_paths: set[str] = set()
    for metric, rule in _CATEGORY_RULES.items():
        for label, path in parser.options:
            if path in used_paths:
                continue
            if not _matches_rule(label, rule):
                continue
            out[metric] = {
                "label": _clean(label),
                "url": urljoin(frozen_team.NCAA_ROOT, path),
            }
            used_paths.add(path)
            break
    return out


def _rank_index(headers: list[str]) -> int:
    for idx, header in enumerate(headers):
        if "rank" in _clean(header).lower():
            return idx
    return 0


def _category_rows(html: str) -> dict[str, dict[str, Any]]:
    headers, rows = frozen_team._table_rows(html or "")
    if not rows:
        return {}
    team_idx = frozen_team._team_cell_index(headers, rows)
    rank_idx = _rank_index(headers)
    out: dict[str, dict[str, Any]] = {}
    for cells in rows:
        if team_idx >= len(cells):
            continue
        team = _clean(cells[team_idx])
        key = frozen_team._canonical_name(team)
        if not key:
            continue
        rank = _int(cells[rank_idx]) if rank_idx < len(cells) else None
        if rank is None:
            continue
        value = _clean(cells[-1]) if cells else ""
        out[key] = {
            "team": team,
            "rank": rank,
            "value": value,
            "value_numeric": _float(value),
            "headers": list(headers),
            "row": list(cells),
        }
    return out


@st.cache_data(ttl=300, show_spinner=False)
def _load_category_table(
    url: str,
    provider: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    first, first_attempts = frozen_team._fetch_text_with_fallback(url, provider)
    attempts.extend(first_attempts)
    if not first:
        return {}, {
            "rows": 0,
            "field_size": 0,
            "attempts": attempts,
        }

    found = _category_rows(first)
    max_pages = frozen_team._max_stat_pages(first)
    for page in range(2, max_pages + 1):
        page_url = url.rstrip("/") + f"/p{page}"
        html, page_attempts = frozen_team._fetch_text_with_fallback(
            page_url,
            f"{provider} p{page}",
        )
        attempts.extend(page_attempts)
        if html:
            found.update(_category_rows(html))

    field_size = max(
        [int(item.get("rank") or 0) for item in found.values()] or [0]
    )
    for item in found.values():
        item["field_size"] = field_size

    return found, {
        "rows": len(found),
        "field_size": field_size,
        "attempts": attempts,
        "pages": max_pages,
    }


@st.cache_data(ttl=300, show_spinner=False)
def _load_division_tables(
    stats_index: str,
    division: str,
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    index_html, index_attempts = frozen_team._fetch_text_with_fallback(
        stats_index,
        f"NCAA {division} offense-defense category index",
    )
    attempts.extend(index_attempts)
    categories = _discover_categories(index_html)
    tables: dict[str, dict[str, dict[str, Any]]] = {}
    table_diag: dict[str, Any] = {}

    if categories:
        with ThreadPoolExecutor(max_workers=min(6, len(categories))) as pool:
            futures = {
                pool.submit(
                    _load_category_table,
                    cfg["url"],
                    f"NCAA {division} {cfg.get('label') or metric}",
                ): metric
                for metric, cfg in categories.items()
            }
            for future in as_completed(futures):
                metric = futures[future]
                table, diag = future.result()
                tables[metric] = table
                table_diag[metric] = diag
                attempts.extend(diag.get("attempts") or [])

    return tables, {
        "division": division,
        "categories_discovered": sorted(categories),
        "category_count": len(categories),
        "tables_loaded": sum(bool(v) for v in tables.values()),
        "table_diagnostics": table_diag,
        "attempts": attempts,
    }


def _lookup_team(
    table: Mapping[str, Mapping[str, Any]],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    keys = frozen_team._team_keys(
        _clean(profile.get("team")),
        _clean(profile.get("team_slug")),
    )
    for key in keys:
        if key in table:
            return dict(table[key])
    for key, item in table.items():
        if any(
            len(key) >= 5
            and len(candidate) >= 5
            and (key in candidate or candidate in key)
            for candidate in keys
        ):
            return dict(item)
    return {}


def _fallback_profile_stat(
    profile: Mapping[str, Any],
    metric: str,
    division: str,
) -> dict[str, Any]:
    item = dict((profile.get("official_stats") or {}).get(metric) or {})
    if not item:
        return {}
    headers = list(item.get("headers") or [])
    row = list(item.get("row") or [])
    rank_idx = _rank_index(headers)
    rank = _int(row[rank_idx]) if row and rank_idx < len(row) else None
    if rank is None:
        return {}
    return {
        **item,
        "team": _clean(profile.get("team")),
        "rank": rank,
        "field_size": 136 if division == "FBS" else 129,
    }


def _team_metric(
    tables: Mapping[str, Mapping[str, Mapping[str, Any]]],
    profile: Mapping[str, Any],
    metric: str,
    division: str,
) -> dict[str, Any]:
    found = _lookup_team(tables.get(metric) or {}, profile)
    if found:
        return found
    return _fallback_profile_stat(profile, metric, division)


def _edge_label(edge: float | None) -> str:
    if edge is None:
        return "UNAVAILABLE"
    if edge >= 0.35:
        return "STRONG OFFENSE EDGE"
    if edge >= 0.12:
        return "OFFENSE EDGE"
    if edge <= -0.35:
        return "STRONG DEFENSE EDGE"
    if edge <= -0.12:
        return "DEFENSE EDGE"
    return "NEUTRAL"


def _dimension(
    label: str,
    offense_metric: Mapping[str, Any],
    defense_metric: Mapping[str, Any],
    weight: float,
) -> dict[str, Any]:
    offense_rank = _int(offense_metric.get("rank"))
    defense_rank = _int(defense_metric.get("rank"))
    field_size = max(
        int(offense_metric.get("field_size") or 0),
        int(defense_metric.get("field_size") or 0),
        2,
    )
    if offense_rank is None or defense_rank is None:
        return {
            "label": _LABELS.get(label, label),
            "ready": False,
            "offense_rank": offense_rank,
            "defense_rank": defense_rank,
            "edge": None,
            "weight": float(weight),
            "weighted_edge": 0.0,
            "edge_label": "UNAVAILABLE",
            "offense_value": _clean(offense_metric.get("value")),
            "defense_value": _clean(defense_metric.get("value")),
        }

    edge = _clamp(
        (float(defense_rank) - float(offense_rank))
        / max(1.0, float(field_size - 1)),
        -1.0,
        1.0,
    )
    return {
        "label": _LABELS.get(label, label),
        "ready": True,
        "offense_rank": offense_rank,
        "defense_rank": defense_rank,
        "field_size": field_size,
        "edge": float(edge),
        "weight": float(weight),
        "weighted_edge": float(edge * weight),
        "edge_label": _edge_label(edge),
        "offense_value": _clean(offense_metric.get("value")),
        "defense_value": _clean(defense_metric.get("value")),
    }


def _side_matchup(
    offense: Mapping[str, Any],
    defense: Mapping[str, Any],
    tables: Mapping[str, Mapping[str, Mapping[str, Any]]],
    division: str,
) -> dict[str, Any]:
    dimensions: dict[str, dict[str, Any]] = {}
    for key, offense_key, defense_key, weight in _DIMENSIONS:
        dimensions[key] = _dimension(
            key,
            _team_metric(tables, offense, offense_key, division),
            _team_metric(tables, defense, defense_key, division),
            weight,
        )

    weighted_signal = sum(
        float(row.get("weighted_edge") or 0.0)
        for row in dimensions.values()
    )
    coverage = sum(
        float(row.get("weight") or 0.0)
        for row in dimensions.values()
        if row.get("ready")
    )
    ready_dimensions = sum(bool(row.get("ready")) for row in dimensions.values())
    model_ready = (
        coverage >= MIN_ENGINE_MODEL_COVERAGE
        and ready_dimensions >= MIN_ENGINE_DIMENSIONS
    )
    adjustment = (
        _clamp(
            weighted_signal * MAX_TEAM_MATCHUP_ADJUSTMENT,
            -MAX_TEAM_MATCHUP_ADJUSTMENT,
            MAX_TEAM_MATCHUP_ADJUSTMENT,
        )
        if model_ready
        else 0.0
    )

    if weighted_signal >= 0.20:
        overall = "OFFENSE ADVANTAGE"
    elif weighted_signal <= -0.20:
        overall = "DEFENSE ADVANTAGE"
    else:
        overall = "BALANCED"

    return {
        "offense_team": _clean(offense.get("team")) or "Offense",
        "defense_team": _clean(defense.get("team")) or "Defense",
        "division": division,
        "dimensions": dimensions,
        "ready_dimensions": ready_dimensions,
        "total_dimensions": len(_DIMENSIONS),
        "coverage": float(coverage),
        "weighted_signal": float(weighted_signal),
        "points_adjustment": float(adjustment),
        "model_ready": bool(model_ready),
        "overall": overall,
    }


def build_matchup_engine(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> dict[str, Any]:
    away_division = _profile_division(away)
    home_division = _profile_division(home)
    same_division = away_division == home_division
    division = away_division if same_division else "MIXED"

    if not same_division:
        return {
            "version": MODEL_VERSION,
            "ready": True,
            "model_ready": False,
            "same_division": False,
            "division": division,
            "reason": "cross-division rank pools are not directly comparable",
            "away_offense": {},
            "home_offense": {},
            "coverage": 0.0,
            "analysis_line_matchup_weight": ANALYSIS_LINE_MATCHUP_WEIGHT,
            "advanced_metrics_unavailable": ["EPA/play", "success rate"],
            "sportsbook_input_used": False,
            "monte_carlo_used": False,
        }

    stats_index = (
        NCAA_FCS_STATS_INDEX if division == "FCS" else NCAA_FBS_STATS_INDEX
    )
    tables, diag = _load_division_tables(stats_index, division)

    away_offense = _side_matchup(away, home, tables, division)
    home_offense = _side_matchup(home, away, tables, division)
    coverage = (
        float(away_offense.get("coverage") or 0.0)
        + float(home_offense.get("coverage") or 0.0)
    ) / 2.0
    model_ready = bool(
        away_offense.get("model_ready")
        and home_offense.get("model_ready")
    )

    return {
        "version": MODEL_VERSION,
        "ready": True,
        "model_ready": model_ready,
        "same_division": True,
        "division": division,
        "away_offense": away_offense,
        "home_offense": home_offense,
        "coverage": float(coverage),
        "category_diagnostics": diag,
        "analysis_line_matchup_weight": ANALYSIS_LINE_MATCHUP_WEIGHT,
        "max_team_adjustment": MAX_TEAM_MATCHUP_ADJUSTMENT,
        "advanced_metrics_unavailable": ["EPA/play", "success rate"],
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
    }


def _lean(p_over: float, p_under: float, p_push: float) -> str:
    if p_push >= max(p_over, p_under):
        return "PASS"
    if p_over > p_under:
        return "OVER"
    if p_under > p_over:
        return "UNDER"
    return "PASS"


def apply_to_raw(
    base_raw: Mapping[str, Any],
    engine: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply bounded Step-3 matchup adjustments to a frozen Step-8 raw output."""
    out = dict(base_raw)
    out["base_model_version"] = _clean(base_raw.get("version"))
    out["version"] = MODEL_VERSION
    out["upgrade_step3_engine_ready"] = bool(engine.get("model_ready"))
    out["upgrade_step3_applied"] = False
    out["matchup_engine_coverage"] = float(engine.get("coverage") or 0.0)
    out["analysis_line_matchup_weight"] = ANALYSIS_LINE_MATCHUP_WEIGHT

    if not base_raw.get("ready") or not engine.get("model_ready"):
        out["matchup_engine_reason"] = _clean(
            engine.get("reason")
            or "matchup evidence below Step-3 minimum coverage"
        )
        return out

    away_adjustment = float(
        (engine.get("away_offense") or {}).get("points_adjustment") or 0.0
    )
    home_adjustment = float(
        (engine.get("home_offense") or {}).get("points_adjustment") or 0.0
    )

    base_away = float(base_raw.get("projected_away_points") or 0.0)
    base_home = float(base_raw.get("projected_home_points") or 0.0)
    projected_away = frozen_raw._clamp(
        base_away + away_adjustment,
        frozen_raw.MIN_TEAM_POINTS,
        frozen_raw.MAX_TEAM_POINTS,
    )
    projected_home = frozen_raw._clamp(
        base_home + home_adjustment,
        frozen_raw.MIN_TEAM_POINTS,
        frozen_raw.MAX_TEAM_POINTS,
    )
    projected_total = projected_away + projected_home

    sigma = float(base_raw.get("structural_total_sigma") or frozen_raw.BASE_TOTAL_SIGMA)
    line = float(base_raw.get("analysis_line") or 0.0)
    p_over, p_under, p_push = frozen_raw._line_probabilities(
        projected_total,
        sigma,
        line,
    )
    interval_low = max(0.0, projected_total - 1.645 * sigma)
    interval_high = projected_total + 1.645 * sigma

    components = dict(base_raw.get("components") or {})
    components.update({
        "step3_away_matchup_adjustment": float(away_adjustment),
        "step3_home_matchup_adjustment": float(home_adjustment),
        "step3_total_matchup_adjustment": float(
            (projected_away + projected_home) - (base_away + base_home)
        ),
    })

    out.update({
        "upgrade_step3_applied": True,
        "base_projected_away_points": float(base_away),
        "base_projected_home_points": float(base_home),
        "base_projected_total": float(base_away + base_home),
        "projected_away_points": float(projected_away),
        "projected_home_points": float(projected_home),
        "projected_total": float(projected_total),
        "over_probability": float(p_over),
        "under_probability": float(p_under),
        "push_probability": float(p_push),
        "model_lean": _lean(p_over, p_under, p_push),
        "total_uncertainty_90": {
            "low": float(interval_low),
            "high": float(interval_high),
        },
        "components": components,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
    })
    return out


def clear_matchup_engine_cache() -> None:
    for fn in (
        _load_category_table,
        _load_division_tables,
    ):
        try:
            fn.clear()
        except Exception:
            pass


__all__ = [
    "ANALYSIS_LINE_MATCHUP_WEIGHT",
    "FROZEN_RAW_MODEL",
    "FROZEN_TEAM_DATA",
    "MAX_TEAM_MATCHUP_ADJUSTMENT",
    "MIN_ENGINE_DIMENSIONS",
    "MIN_ENGINE_MODEL_COVERAGE",
    "MODEL_VERSION",
    "_discover_categories",
    "_dimension",
    "_edge_label",
    "_load_category_table",
    "_load_division_tables",
    "apply_to_raw",
    "build_matchup_engine",
    "clear_matchup_engine_cache",
]
