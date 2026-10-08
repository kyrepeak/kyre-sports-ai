"""CFB Game Total Page 1 V2 Step 2 — multi-source display evidence engine.

Additive, display-only enrichment above the frozen Game Total runtime/model path.
It reuses the already-certified official-audit + cfbstats fallback to fill visible
Page-1 evidence gaps without changing projection, probability, ranking,
qualification, distribution, or sportsbook influence.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

import cfb_game_total_step4_multisource_v1 as multisource

MODEL_VERSION = "CFB GAME TOTAL PAGE1 V2 STEP2 • MULTI-SOURCE DATA ENGINE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_QUALIFICATION = False


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _team_key(value: Any) -> str:
    text = _clean(value).casefold().replace("&", " and ")
    text = re.sub(r"\buniversity\b", " ", text)
    text = re.sub(r"\bthe\b", " ", text)
    text = re.sub(r"\bst\.?\b", " state ", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def _number(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: Any, unit: str) -> str:
    number = _number(value)
    if number is None:
        return ""
    if unit == "%":
        return f"{number:.1f}%"
    return f"{number:.2f}/g"


def _row_haystack(key: Any, row: Mapping[str, Any]) -> str:
    return f"{_clean(key)} {_clean(row.get('label'))}".casefold()


def _has_row(stats: Mapping[str, Any], *needles: str) -> bool:
    for key, raw in stats.items():
        if not isinstance(raw, Mapping):
            continue
        haystack = _row_haystack(key, raw)
        if any(needle.casefold() in haystack for needle in needles):
            return True
    return False


def _append_verified_row(
    stats: dict[str, Any],
    *,
    key: str,
    label: str,
    value: Any,
    unit: str,
    source: str,
    needles: tuple[str, ...],
) -> bool:
    """Fill only a missing display category; never overwrite verified evidence."""
    if _has_row(stats, *needles):
        return False
    display = _fmt(value, unit)
    if not display:
        return False
    stats[key] = {
        "label": label,
        "value": display,
        "rank": "",
        "source": source,
        "verified": True,
        "display_only": True,
    }
    return True


def _enrich_team_stats(
    profile: Mapping[str, Any] | None,
    metrics: Mapping[str, Any] | None,
    *,
    side: str,
    source: str,
) -> tuple[dict[str, Any], int]:
    out = dict(profile or {})
    stats = {
        str(key): dict(row) if isinstance(row, Mapping) else row
        for key, row in dict(out.get("official_stats") or {}).items()
    }
    metrics = metrics or {}
    filled = 0

    rows = (
        (
            f"page1_{side}_third_down_offense",
            "3rd Down Offense",
            metrics.get("third_down_offense_pct"),
            "%",
            ("3rd down offense", "third down offense"),
        ),
        (
            f"page1_{side}_third_down_defense",
            "3rd Down Defense",
            metrics.get("third_down_defense_pct"),
            "%",
            ("3rd down defense", "third down defense"),
        ),
        (
            f"page1_{side}_red_zone_offense",
            "Red Zone Offense",
            metrics.get("red_zone_offense_pct"),
            "%",
            ("red zone offense",),
        ),
        (
            f"page1_{side}_red_zone_defense",
            "Red Zone Defense",
            metrics.get("red_zone_defense_pct"),
            "%",
            ("red zone defense",),
        ),
        (
            f"page1_{side}_turnovers_lost",
            "Turnovers Lost",
            metrics.get("turnovers_lost_pg"),
            "per_game",
            ("turnovers lost", "giveaway"),
        ),
        (
            f"page1_{side}_turnovers_gained",
            "Turnovers Gained",
            metrics.get("turnovers_gained_pg"),
            "per_game",
            ("turnovers gained", "takeaway"),
        ),
    )
    for key, label, value, unit, needles in rows:
        if _append_verified_row(
            stats,
            key=key,
            label=label,
            value=value,
            unit=unit,
            source=source,
            needles=needles,
        ):
            filled += 1

    out["official_stats"] = stats
    return out, filled


def _completed_games(profile: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    rows = (profile or {}).get("completed_games") or []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _opponent(row: Mapping[str, Any]) -> str:
    return _clean(
        row.get("opponent")
        or row.get("opponent_name")
        or row.get("opponent_team")
    )


def _history_label(row: Mapping[str, Any], team: str) -> str:
    date_text = _clean(row.get("date") or row.get("game_date"))
    result = _clean(row.get("result"))
    score = _clean(row.get("score"))
    if not score:
        pf, pa = row.get("points_for"), row.get("points_against")
        if pf not in (None, "") and pa not in (None, ""):
            score = f"{pf}-{pa}"
    pieces = [piece for piece in (date_text, team, result, score) if piece]
    return " ".join(pieces) or "Verified prior meeting"


def _verified_sample_history(
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> dict[str, Any]:
    away_name = _clean(away.get("team")) or "Away"
    home_name = _clean(home.get("team")) or "Home"
    away_key = _team_key(away_name)
    home_key = _team_key(home_name)
    away_games = _completed_games(away)
    home_games = _completed_games(home)

    matches: list[str] = []
    for team_name, target, rows in (
        (away_name, home_key, away_games),
        (home_name, away_key, home_games),
    ):
        for row in rows:
            if target and _team_key(_opponent(row)) == target:
                label = _history_label(row, team_name)
                if label not in matches:
                    matches.append(label)

    if matches:
        return {
            "status": "Verified recent meeting found",
            "latest": matches[-1],
            "source": "verified completed-game samples",
        }
    return {
        "status": "No recent meeting in verified completed-game samples",
        "sample": f"{away_name} {len(away_games)} games • {home_name} {len(home_games)} games",
        "source": "verified completed-game samples",
    }


def enrich_display_bundle(
    display_game: Mapping[str, Any] | None,
    selected_day: Any,
    away: Mapping[str, Any] | None,
    home: Mapping[str, Any] | None,
    diag: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return copied display objects enriched by verified secondary evidence only."""
    out_game = dict(display_game or {})
    out_away = dict(away or {})
    out_home = dict(home or {})
    out_diag = dict(diag or {})

    fallback: dict[str, Any] = {}
    fallback_error = ""
    try:
        fallback = dict(
            multisource.build_display_fallback(out_game, out_away, out_home) or {}
        )
    except Exception as exc:  # display-only fallback must never break frozen output
        fallback_error = f"{type(exc).__name__}: {exc}"[:300]

    source = _clean(fallback.get("source")) or "existing verified Page-1 evidence"
    out_away, away_filled = _enrich_team_stats(
        out_away,
        fallback.get("away_metrics") if isinstance(fallback.get("away_metrics"), Mapping) else {},
        side="away",
        source=source,
    )
    out_home, home_filled = _enrich_team_stats(
        out_home,
        fallback.get("home_metrics") if isinstance(fallback.get("home_metrics"), Mapping) else {},
        side="home",
        source=source,
    )

    if not any(out_game.get(key) not in (None, "", [], {}) for key in ("history", "series_history", "head_to_head")):
        out_game["history"] = _verified_sample_history(out_away, out_home)
        history_filled = True
    else:
        history_filled = False

    out_diag["page1_multisource_step2"] = {
        "version": MODEL_VERSION,
        "selected_day": _clean(selected_day),
        "fallback_ready": bool(fallback.get("ready")),
        "fallback_source": source,
        "fallback_error": fallback_error,
        "official_stats_rows_filled": away_filled + home_filled,
        "history_filled": history_filled,
        "history_scope": "verified completed-game samples only",
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
    }
    out_diag["sportsbook_projection_influence"] = SPORTSBOOK_PROJECTION_INFLUENCE
    out_diag["may_modify_projection"] = MAY_MODIFY_PROJECTION
    return out_game, out_away, out_home, out_diag


__all__ = [
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_QUALIFICATION",
    "MAY_MODIFY_RANKING",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "enrich_display_bundle",
]
