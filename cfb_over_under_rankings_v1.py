"""CFB Over/Under Intelligence V2 — Upgrade Step 2 ranking context.

Additive evidence provider above permanently frozen CFB Steps 1-12 and the
permanently frozen O/U Upgrade Step 1 presentation layer.

Step 2 adds display-only context:
- AP rank already carried by the certified team-data profile,
- current Coaches Poll rank from NCAA.com when available,
- CFP rank from NCAA.com only in November/December and only when available,
- official NCAA category ranks for scoring/total/pass/rush offense and defense,
- conference, overall record, home/road splits, and recent form.

The provider never changes Step-8 projected totals, Step-9 O/U/PASS
qualification, Top-5 ranking, analysis-line behavior, sportsbook inputs, or
Monte Carlo behavior.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from typing import Any, Mapping
from urllib.parse import urljoin

import streamlit as st

import cfb_team_data_v1 as frozen_team

MODEL_VERSION = "CFB O/U RANKINGS V1 • UPGRADE STEP 2"
FROZEN_TEAM_DATA = "cfb_team_data_v2"

NCAA_FBS_STATS_INDEX = frozen_team.NCAA_STATS_INDEX
NCAA_FCS_STATS_INDEX = "https://www.ncaa.com/stats/football/fcs"
NCAA_COACHES_RANKINGS = "https://www.ncaa.com/rankings/football/fbs/coaches-poll"
NCAA_CFP_RANKINGS = "https://www.ncaa.com/rankings/football/fbs/college-football-playoff"

_SUPPLEMENTAL_PATTERNS = {
    "passing_offense": (
        ("passing offense",),
    ),
    "rushing_offense": (
        ("rushing offense",),
    ),
    "passing_defense": (
        ("passing yards allowed",),
        ("passing defense",),
    ),
    "rushing_defense": (
        ("rushing defense",),
    ),
}

_METRIC_LABELS = {
    "scoring_offense": "Scoring offense",
    "total_offense": "Total offense",
    "passing_offense": "Pass offense",
    "rushing_offense": "Rush offense",
    "scoring_defense": "Scoring defense",
    "total_defense": "Total defense",
    "passing_defense": "Pass defense",
    "rushing_defense": "Rush defense",
}

_METRIC_ORDER = (
    "total_offense",
    "scoring_offense",
    "passing_offense",
    "rushing_offense",
    "total_defense",
    "scoring_defense",
    "passing_defense",
    "rushing_defense",
)


def _clean(value: Any) -> str:
    return frozen_team._clean(value)


def _int(value: Any) -> int | None:
    return frozen_team._int(value)


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


def _discover_supplemental_categories(
    html: str,
) -> dict[str, dict[str, str]]:
    if not html:
        return {}
    parser = frozen_team._OptionParser()
    parser.feed(html)
    out: dict[str, dict[str, str]] = {}
    for metric, alternatives in _SUPPLEMENTAL_PATTERNS.items():
        for label, path in parser.options:
            lower = _clean(label).lower()
            matched = False
            for terms in alternatives:
                if all(term in lower for term in terms):
                    matched = True
                    break
            if not matched:
                continue
            out[metric] = {
                "label": _clean(label) or _METRIC_LABELS[metric],
                "url": urljoin(frozen_team.NCAA_ROOT, path),
            }
            break
    return out


def _targets(
    away_name: str,
    away_slug: str,
    home_name: str,
    home_slug: str,
) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    if _clean(away_name):
        out["away"] = frozen_team._team_keys(away_name, away_slug)
    if _clean(home_name):
        out["home"] = frozen_team._team_keys(home_name, home_slug)
    return out


@st.cache_data(ttl=300, show_spinner=False)
def _load_supplemental_stat_ranks(
    stats_index: str,
    away_name: str,
    away_slug: str,
    home_name: str,
    home_slug: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    targets = _targets(away_name, away_slug, home_name, home_slug)
    attempts: list[dict[str, Any]] = []
    values: dict[str, dict[str, Any]] = {side: {} for side in targets}
    if not targets:
        return values, {
            "categories_discovered": [],
            "attempts": attempts,
            "metrics_found": 0,
        }

    index_html, index_attempts = frozen_team._fetch_text_with_fallback(
        stats_index,
        f"NCAA {'FCS' if '/fcs' in stats_index else 'FBS'} supplemental stats index",
    )
    attempts.extend(index_attempts)
    categories = _discover_supplemental_categories(index_html)

    if categories:
        with ThreadPoolExecutor(max_workers=min(4, len(categories))) as pool:
            futures = [
                pool.submit(
                    frozen_team._fetch_stat_metric,
                    metric,
                    cfg,
                    targets,
                )
                for metric, cfg in categories.items()
            ]
            for future in as_completed(futures):
                metric, found, metric_attempts = future.result()
                attempts.extend(metric_attempts)
                for side, item in found.items():
                    values.setdefault(side, {})[metric] = {
                        "label": _METRIC_LABELS.get(metric, metric),
                        **dict(item),
                    }

    return values, {
        "categories_discovered": sorted(categories),
        "attempts": attempts,
        "metrics_found": sum(len(v) for v in values.values()),
    }


@st.cache_data(ttl=300, show_spinner=False)
def _load_poll_rankings(
    url: str,
    provider: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    html, attempts = frozen_team._fetch_text_with_fallback(url, provider)
    headers, rows = frozen_team._table_rows(html) if html else ([], [])
    rankings: dict[str, dict[str, Any]] = {}
    if rows:
        team_idx = frozen_team._team_cell_index(headers, rows)
        rank_idx = 0
        for i, header in enumerate(headers):
            if "rank" in _clean(header).lower():
                rank_idx = i
                break
        for cells in rows:
            if team_idx >= len(cells):
                continue
            team = _clean(cells[team_idx])
            rank = _int(cells[rank_idx]) if rank_idx < len(cells) else None
            if not team or rank is None:
                continue
            rankings[frozen_team._canonical_name(team)] = {
                "rank": rank,
                "team_text": team,
                "headers": list(headers),
                "row": list(cells),
            }
    return rankings, {
        "rows": len(rankings),
        "attempts": attempts,
        "provider": provider,
    }


def _rank_from_stat_item(item: Mapping[str, Any]) -> int | None:
    headers = list(item.get("headers") or [])
    row = list(item.get("row") or [])
    if not row:
        return None
    rank_idx = None
    for idx, header in enumerate(headers):
        if "rank" in _clean(header).lower():
            rank_idx = idx
            break
    if rank_idx is None:
        rank_idx = 0
    if rank_idx >= len(row):
        return None
    return _int(row[rank_idx])


def _metric_entry(
    profile: Mapping[str, Any],
    supplemental: Mapping[str, Any],
    metric: str,
) -> dict[str, Any]:
    core = (profile.get("official_stats") or {}).get(metric) or {}
    item = dict(core or supplemental.get(metric) or {})
    rank = _rank_from_stat_item(item)
    return {
        "key": metric,
        "label": _METRIC_LABELS.get(metric, metric.replace("_", " ").title()),
        "rank": rank,
        "value": _clean(item.get("value")),
        "available": rank is not None,
    }


def _record_text(value: Any) -> str:
    if isinstance(value, Mapping):
        try:
            return frozen_team._record_text(value)
        except Exception:
            pass
    text = _clean(value)
    return text or "—"


def _poll_state(
    profile: Mapping[str, Any],
    rankings: Mapping[str, Mapping[str, Any]],
    rows: int,
) -> dict[str, Any]:
    if rows <= 0:
        return {"rank": None, "state": "unavailable"}
    found = frozen_team._ranking_for_team(
        rankings,
        _clean(profile.get("team")),
        _clean(profile.get("team_slug")),
    )
    rank = _int((found or {}).get("rank"))
    return {
        "rank": rank,
        "state": "ranked" if rank is not None else "unranked",
    }


def _ap_state(profile: Mapping[str, Any]) -> dict[str, Any]:
    rank = _int(profile.get("ap_rank"))
    source = _clean(profile.get("rank_source")).lower()
    if rank is not None:
        state = "ranked"
    elif "unranked" in source and "unavailable" not in source:
        state = "unranked"
    elif "ap rankings" in source:
        state = "unranked"
    else:
        state = "unavailable"
    return {"rank": rank, "state": state}


def _side_context(
    profile: Mapping[str, Any],
    supplemental: Mapping[str, Any],
    coaches: Mapping[str, Mapping[str, Any]],
    coaches_rows: int,
    cfp: Mapping[str, Mapping[str, Any]],
    cfp_rows: int,
    cfp_released: bool,
) -> dict[str, Any]:
    metrics = {
        metric: _metric_entry(profile, supplemental, metric)
        for metric in _METRIC_ORDER
    }
    metric_ready = sum(int(v.get("available") is True) for v in metrics.values())

    if cfp_released:
        cfp_state = _poll_state(profile, cfp, cfp_rows)
    else:
        cfp_state = {"rank": None, "state": "not_released"}

    return {
        "team": _clean(profile.get("team")) or "Team",
        "conference": _clean(profile.get("conference")) or "Conference unavailable",
        "division": _profile_division(profile),
        "record": _clean(profile.get("record_text")) or _record_text(profile.get("record")),
        "home_record": _record_text(profile.get("home_record")),
        "away_record": _record_text(profile.get("away_record")),
        "recent_form": _clean(profile.get("recent_form")) or "—",
        "ap": _ap_state(profile),
        "coaches": _poll_state(profile, coaches, coaches_rows)
        if _profile_division(profile) == "FBS"
        else {"rank": None, "state": "not_applicable"},
        "cfp": cfp_state
        if _profile_division(profile) == "FBS"
        else {"rank": None, "state": "not_applicable"},
        "metrics": metrics,
        "metric_coverage": metric_ready / len(_METRIC_ORDER),
        "metric_ready": metric_ready,
        "metric_total": len(_METRIC_ORDER),
    }


def build_ranking_context(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> dict[str, Any]:
    """Build display-only ranking/record context for a frozen Step-9 matchup."""
    attempts: list[dict[str, Any]] = []

    divisions = {
        "away": _profile_division(away),
        "home": _profile_division(home),
    }
    supplemental = {"away": {}, "home": {}}

    if "FBS" in divisions.values():
        fbs_values, fbs_diag = _load_supplemental_stat_ranks(
            NCAA_FBS_STATS_INDEX,
            _clean(away.get("team")) if divisions["away"] == "FBS" else "",
            _clean(away.get("team_slug")) if divisions["away"] == "FBS" else "",
            _clean(home.get("team")) if divisions["home"] == "FBS" else "",
            _clean(home.get("team_slug")) if divisions["home"] == "FBS" else "",
        )
        attempts.extend(fbs_diag.get("attempts") or [])
        for side, values in fbs_values.items():
            supplemental.setdefault(side, {}).update(values)

    if "FCS" in divisions.values():
        fcs_values, fcs_diag = _load_supplemental_stat_ranks(
            NCAA_FCS_STATS_INDEX,
            _clean(away.get("team")) if divisions["away"] == "FCS" else "",
            _clean(away.get("team_slug")) if divisions["away"] == "FCS" else "",
            _clean(home.get("team")) if divisions["home"] == "FCS" else "",
            _clean(home.get("team_slug")) if divisions["home"] == "FCS" else "",
        )
        attempts.extend(fcs_diag.get("attempts") or [])
        for side, values in fcs_values.items():
            supplemental.setdefault(side, {}).update(values)

    coaches, coaches_diag = _load_poll_rankings(
        NCAA_COACHES_RANKINGS,
        "NCAA Coaches Poll rankings",
    )
    attempts.extend(coaches_diag.get("attempts") or [])

    game_day = _day(game.get("game_date"))
    try:
        month = int(game_day[5:7])
    except Exception:
        month = 0
    cfp_released = month in {11, 12}
    cfp: dict[str, dict[str, Any]] = {}
    cfp_diag: dict[str, Any] = {"rows": 0, "attempts": []}
    if cfp_released:
        cfp, cfp_diag = _load_poll_rankings(
            NCAA_CFP_RANKINGS,
            "NCAA College Football Playoff rankings",
        )
        attempts.extend(cfp_diag.get("attempts") or [])

    away_context = _side_context(
        away,
        supplemental.get("away") or {},
        coaches,
        int(coaches_diag.get("rows") or 0),
        cfp,
        int(cfp_diag.get("rows") or 0),
        cfp_released,
    )
    home_context = _side_context(
        home,
        supplemental.get("home") or {},
        coaches,
        int(coaches_diag.get("rows") or 0),
        cfp,
        int(cfp_diag.get("rows") or 0),
        cfp_released,
    )

    total_available = (
        int(away_context.get("metric_ready") or 0)
        + int(home_context.get("metric_ready") or 0)
    )
    total_metrics = (
        int(away_context.get("metric_total") or 0)
        + int(home_context.get("metric_total") or 0)
    )

    return {
        "version": MODEL_VERSION,
        "ready": total_available > 0,
        "away": away_context,
        "home": home_context,
        "metric_coverage": (total_available / total_metrics) if total_metrics else 0.0,
        "coaches_poll_available": int(coaches_diag.get("rows") or 0) > 0,
        "cfp_released_for_date": cfp_released,
        "cfp_poll_available": int(cfp_diag.get("rows") or 0) > 0,
        "attempts": attempts,
        "presentation_only": True,
        "projection_weight": 0.0,
        "selection_weight": 0.0,
        "ranking_selection_weight": 0.0,
    }


def clear_rankings_cache() -> None:
    for fn in (
        _load_supplemental_stat_ranks,
        _load_poll_rankings,
    ):
        try:
            fn.clear()
        except Exception:
            pass


__all__ = [
    "FROZEN_TEAM_DATA",
    "MODEL_VERSION",
    "NCAA_CFP_RANKINGS",
    "NCAA_COACHES_RANKINGS",
    "NCAA_FBS_STATS_INDEX",
    "NCAA_FCS_STATS_INDEX",
    "_discover_supplemental_categories",
    "_metric_entry",
    "_profile_division",
    "_rank_from_stat_item",
    "build_ranking_context",
    "clear_rankings_cache",
]
