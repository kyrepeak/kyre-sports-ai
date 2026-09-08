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

    # FCS membership must be proven by the NCAA FCS team-stat universe.
    # Merely appearing in a division-12 contest is insufficient because the
    # FBS opponent is also present in that contest ledger.
    side_games = list(ledgers.get(key) or [])
    side_stats = dict(fcs_stats.get(side) or {})
    if not side_stats:
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




def _games_from_stat_rows(stats: Mapping[str, Mapping[str, Any]]) -> int:
    """Read the published games-played column from an NCAA team-stat row."""
    for item in stats.values():
        headers = [str(x or "").strip().lower() for x in item.get("headers") or []]
        row = list(item.get("row") or [])
        for idx, header in enumerate(headers):
            if header in {"g", "gp", "games", "games played"}:
                if idx >= len(row):
                    continue
                value = frozen._int(row[idx])
                if value is not None and value > 0:
                    return int(value)
    return 0


def _record_from_summary(summary: Any, games_hint: int) -> tuple[dict[str, Any], str]:
    text = frozen._clean(summary)
    match = __import__("re").fullmatch(r"(\d+)-(\d+)(?:-(\d+))?", text)
    if match:
        wins = int(match.group(1))
        losses = int(match.group(2))
        ties = int(match.group(3) or 0)
        games = max(int(games_hint or 0), wins + losses + ties)
        record = {
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "games": games,
        }
        return record, frozen._record_text(record)

    games = max(0, int(games_hint or 0))
    return {"games": games}, (
        f"{games} GAME SAMPLE • W-L UNAVAILABLE" if games else "0-0"
    )


def _stats_only_repair(
    side: str,
    game: Mapping[str, Any],
    frozen_profile: Mapping[str, Any],
    stats: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """Repair a CHECK profile from official NCAA stats + verified event record.

    This path is used when NCAA's season-schedule persisted query is empty but
    NCAA.com team-stat pages are live. It never invents recent form, splits or
    SOS; those remain explicitly unavailable.
    """
    official = dict(stats or {})
    scoring_off = official.get("scoring_offense") or {}
    scoring_def = official.get("scoring_defense") or {}
    ppg = frozen._float(scoring_off.get("value_numeric"))
    if ppg is None:
        ppg = frozen._float(scoring_off.get("value"))
    allowed = frozen._float(scoring_def.get("value_numeric"))
    if allowed is None:
        allowed = frozen._float(scoring_def.get("value"))

    games = _games_from_stat_rows(official)
    record, record_text = _record_from_summary(
        game.get(f"{side}_record_summary"),
        games,
    )
    games = int(record.get("games") or 0)

    if games <= 0 or ppg is None or allowed is None:
        return dict(frozen_profile), False

    profile = dict(frozen_profile)
    profile.update({
        "side": side,
        "team": frozen._clean(game.get(f"{side}_team")) or profile.get("team") or side.title(),
        "team_slug": frozen._clean(game.get(f"{side}_team_slug")) or profile.get("team_slug") or "",
        "conference": frozen._clean(
            game.get(f"{side}_conference") or profile.get("conference")
        ) or "Conference unavailable",
        "official_stats": official,
        "record": record,
        "record_text": record_text,
        "ppg": float(ppg),
        "points_allowed_pg": float(allowed),
        "point_diff_pg": float(ppg - allowed),
        "home_record": {},
        "away_record": {},
        "neutral_record": {},
        "recent_form": "—",
        "recent_record": {},
        "recent_ppg": None,
        "recent_points_allowed_pg": None,
        "recent_point_diff_pg": None,
        "sos_opponent_win_pct": None,
        "sos_coverage": 0.0,
        "completed_games": [],
        "data_source": (
            "NCAA.com official team stats + verified ESPN FBS event record • "
            "schedule-query fallback"
        ),
    })
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
        if not ok:
            merged_stats = dict(away_base.get("official_stats") or {})
            if fcs_stats.get("away"):
                merged_stats.update(fcs_stats["away"])
            away, ok = _stats_only_repair(
                "away", game, away_base, merged_stats
            )
        if ok:
            repaired.append("away")

    if needs_repair["home"]:
        home, ok = _repair_profile(
            "home", game, home_base, ledgers, meta, fcs_stats
        )
        if not ok:
            merged_stats = dict(home_base.get("official_stats") or {})
            if fcs_stats.get("home"):
                merged_stats.update(fcs_stats["home"])
            home, ok = _stats_only_repair(
                "home", game, home_base, merged_stats
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
    "_stats_only_repair",
    "_games_from_stat_rows",
    "clear_team_data_cache",
    "load_matchup_team_data",
]
