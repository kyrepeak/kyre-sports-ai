"""College Football Team Data V2 — FCS crossover repair hotfix.

Additive correctness layer over permanently frozen cfb_team_data_v1.

When an FBS slate includes an NCAA-verified FCS crossover game, the frozen
Step-3 provider can mark the FCS side CHECK because it only reads the FBS
schedule/stat universe. V2 preserves every non-CHECK frozen profile exactly and
repairs only a CHECK side that is verifiably present in NCAA division-12 data.

Repair inputs:
- NCAA official FCS season schedule GraphQL (division 12),
- NCAA.com FCS team-stat pages.

No model/probability/price logic is added.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Mapping

import streamlit as st

import cfb_schedule_v2 as schedule_v2
import cfb_team_data_v1 as frozen

MODEL_VERSION = "CFB TEAM DATA V2 • FCS CROSSOVER REPAIR"
FROZEN_TEAM_DATA = "cfb_team_data_v1"

NCAA_FCS_STATS_INDEX = "https://www.ncaa.com/stats/football/fcs"


def _fcs_categories(index_html: str) -> dict[str, dict[str, str]]:
    """Reuse frozen category discovery without modifying the frozen FBS parser."""
    if not index_html:
        return {}
    normalized = index_html.replace(
        "/stats/football/fcs/",
        "/stats/football/fbs/",
    )
    categories = frozen._discover_stat_categories(normalized)
    out: dict[str, dict[str, str]] = {}
    for metric, cfg in categories.items():
        row = dict(cfg)
        row["url"] = str(row.get("url") or "").replace(
            "/stats/football/fbs/",
            "/stats/football/fcs/",
        )
        out[metric] = row
    return out


@st.cache_data(ttl=300, show_spinner=False)
def _load_fcs_official_stats(
    away_name: str,
    away_slug: str,
    home_name: str,
    home_slug: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    targets = {
        "away": frozen._team_keys(away_name, away_slug),
        "home": frozen._team_keys(home_name, home_slug),
    }
    attempts: list[dict[str, Any]] = []

    index_html, index_attempts = frozen._fetch_text_with_fallback(
        NCAA_FCS_STATS_INDEX,
        "NCAA FCS stats category index",
    )
    attempts.extend(index_attempts)
    categories = _fcs_categories(index_html)

    values = {"away": {}, "home": {}}
    if categories:
        with ThreadPoolExecutor(max_workers=min(5, len(categories))) as pool:
            futures = [
                pool.submit(frozen._fetch_stat_metric, metric, cfg, targets)
                for metric, cfg in categories.items()
            ]
            for future in as_completed(futures):
                metric, found, metric_attempts = future.result()
                attempts.extend(metric_attempts)
                label = frozen._CORE_STAT_LABELS.get(metric, metric)
                for side, item in found.items():
                    values[side][metric] = {
                        "label": f"{label} • FCS",
                        **item,
                    }

    return values, {
        "categories_discovered": sorted(categories),
        "away_metrics_found": len(values["away"]),
        "home_metrics_found": len(values["home"]),
        "attempts": attempts,
    }


def _side_key_in_fcs(
    side: str,
    game: Mapping[str, Any],
    ledgers: Mapping[str, Any],
    meta: Mapping[str, Any],
) -> str | None:
    name = frozen._clean(game.get(f"{side}_team"))
    slug = frozen._clean(game.get(f"{side}_team_slug"))
    key = frozen._resolve_key(ledgers, meta, name, slug)
    if key in ledgers or key in meta:
        return key
    return None


def _repair_profile(
    side: str,
    game: Mapping[str, Any],
    frozen_profile: Mapping[str, Any],
    ledgers: Mapping[str, Any],
    meta: Mapping[str, Any],
    fcs_stats: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], bool]:
    key = _side_key_in_fcs(side, game, ledgers, meta)
    if key is None:
        return dict(frozen_profile), False

    # Require actual FCS evidence for the side. A cross-division opponent can
    # appear in a future FCS contest without itself being an FCS member.
    side_games = list(ledgers.get(key) or [])
    side_stats = dict(fcs_stats.get(side) or {})
    if not side_games and not side_stats:
        return dict(frozen_profile), False

    profile = frozen._build_profile(
        side,
        game,
        ledgers,
        meta,
        {side: side_stats},
        {},
    )
    profile["division_context"] = "FCS"
    profile["data_source"] = (
        "NCAA official FCS schedule + NCAA.com FCS team stats • crossover repair"
    )
    profile["ap_rank"] = None
    profile["rank_source"] = "FCS ranking not used in Moneyline Model V1"
    profile["data_quality"] = frozen._quality(profile)
    return profile, True


@st.cache_data(ttl=300, show_spinner=False)
def load_matchup_team_data(
    game: Mapping[str, Any],
    as_of_day: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Preserve frozen profiles and repair only verified FCS CHECK sides."""
    profiles, base_diag = frozen.load_matchup_team_data(game, as_of_day)
    away_base = dict(profiles.get("away") or {})
    home_base = dict(profiles.get("home") or {})

    needs_repair = {
        "away": str((away_base.get("data_quality") or {}).get("grade") or "CHECK").upper() == "CHECK",
        "home": str((home_base.get("data_quality") or {}).get("grade") or "CHECK").upper() == "CHECK",
    }
    if not any(needs_repair.values()):
        diag = dict(base_diag)
        diag.update({
            "version": MODEL_VERSION,
            "fcs_repair_attempted": False,
            "fcs_profiles_repaired": 0,
        })
        return {"away": away_base, "home": home_base}, diag

    day = schedule_v2.frozen._day(as_of_day)
    season_year = schedule_v2.frozen._season_year(day)
    attempts = list(base_diag.get("attempts") or [])

    fcs_payload, fcs_schedule_attempts = schedule_v2._fetch_ncaa_division_payload(
        season_year,
        schedule_v2.NCAA_FCS_DIVISION,
    )
    attempts.extend(fcs_schedule_attempts)

    if fcs_payload:
        ledgers, meta, fcs_ledger_diag = frozen._season_games_from_payload(
            fcs_payload,
            day,
        )
    else:
        ledgers, meta = {}, {}
        fcs_ledger_diag = {
            "raw_contests": 0,
            "completed_contests": 0,
            "future_contests_ignored": 0,
            "unscored_finals_ignored": 0,
        }

    fcs_stats, fcs_stats_diag = _load_fcs_official_stats(
        frozen._clean(game.get("away_team")),
        frozen._clean(game.get("away_team_slug")),
        frozen._clean(game.get("home_team")),
        frozen._clean(game.get("home_team_slug")),
    )
    attempts.extend(fcs_stats_diag.get("attempts") or [])

    away = away_base
    home = home_base
    repaired = []

    if needs_repair["away"]:
        away, ok = _repair_profile(
            "away", game, away_base, ledgers, meta, fcs_stats
        )
        if ok:
            repaired.append("away")

    if needs_repair["home"]:
        home, ok = _repair_profile(
            "home", game, home_base, ledgers, meta, fcs_stats
        )
        if ok:
            repaired.append("home")

    diag = dict(base_diag)
    diag.update({
        "version": MODEL_VERSION,
        "attempts": attempts,
        "fcs_repair_attempted": True,
        "fcs_profiles_repaired": len(repaired),
        "fcs_repaired_sides": repaired,
        "fcs_schedule_raw_contests": int(fcs_ledger_diag.get("raw_contests") or 0),
        "fcs_schedule_completed_contests": int(
            fcs_ledger_diag.get("completed_contests") or 0
        ),
        "fcs_away_metrics_found": int(
            fcs_stats_diag.get("away_metrics_found") or 0
        ),
        "fcs_home_metrics_found": int(
            fcs_stats_diag.get("home_metrics_found") or 0
        ),
    })
    return {"away": away, "home": home}, diag


def clear_team_data_cache() -> None:
    for fn in (
        load_matchup_team_data,
        _load_fcs_official_stats,
    ):
        try:
            fn.clear()
        except Exception:
            pass


__all__ = [
    "FROZEN_TEAM_DATA",
    "MODEL_VERSION",
    "NCAA_FCS_STATS_INDEX",
    "_fcs_categories",
    "_load_fcs_official_stats",
    "_repair_profile",
    "clear_team_data_cache",
    "load_matchup_team_data",
]
