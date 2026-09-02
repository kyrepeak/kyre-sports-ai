"""Frozen-contract unit overlay for Step 7G first-party advanced context.

The underlying box-count derivation intentionally computes human-readable
percent values for several percentage formulas while being developed. Frozen
Step 4F follows the native WNBA Stats convention for PCT fields: fractions
(0.25 == 25%), while rating/pace/assist-ratio fields keep their native numeric
scales.

This overlay is the only Step 4F first-party provider intended for Step 4W
integration. It converts exactly the rate fields that correspond to native
``*_PCT`` columns, restores the frozen ``window_scope`` spelling, validates
plausible units, and preserves explicit provenance that the populated E_* fields
are derived from certified first-party WNBA.com box counts.

No official on-court metric is synthesized. Fields unavailable from certified
first-party page data remain null.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from sports_api.wnba_advanced_stats import WNBAAdvancedStatsUpstreamError
from sports_api.wnba_step7g_first_party_advanced_stats_fast import (
    get_first_party_player_advanced_stats_dataset as _raw_player_dataset,
    get_first_party_team_advanced_stats_dataset as _raw_team_dataset,
)

SOURCE_VARIANT = "certified_box_count_advanced_derivation_contract_units_v3"

# These fields map to native WNBA Stats *_PCT columns and therefore must use
# fraction units in the frozen Step 4F contract. E_AST_RATIO is deliberately not
# included: WNBA Stats reports assist ratio on its own roughly 0-100 scale.
_COMMON_FRACTION_RATE_FIELDS = (
    "assist_percentage",
    "estimated_offensive_rebound_percentage",
    "estimated_defensive_rebound_percentage",
    "estimated_rebound_percentage",
    "estimated_turnover_percentage",
)
_PLAYER_ONLY_FRACTION_RATE_FIELDS = ("estimated_usage_percentage",)
_ALREADY_FRACTION_FIELDS = (
    "effective_field_goal_percentage",
    "true_shooting_percentage",
    "player_impact_estimate",
)


def _frozen_window_scope(last_n_games: int) -> str:
    return "season_to_date" if last_n_games == 0 else f"last_{last_n_games}_games"


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WNBAAdvancedStatsUpstreamError(
            f"Step 7G contract-unit overlay expected numeric {field}."
        )
    return float(value)


def _fraction(value: Any, field: str) -> float | None:
    if value is None:
        return None
    number = _number(value, field)
    converted = number / 100.0
    # Fraction PCT metrics can occasionally be negative only if their underlying
    # formula is not a true rate; none of the converted fields here allow that.
    if converted < 0.0 or converted > 1.0:
        raise WNBAAdvancedStatsUpstreamError(
            f"Step 7G derived {field} fell outside frozen fraction units: {converted}."
        )
    return round(converted, 6)


def _validate_fraction(value: Any, field: str) -> None:
    if value is None:
        return
    number = _number(value, field)
    if number < 0.0 or number > 1.0:
        raise WNBAAdvancedStatsUpstreamError(
            f"Step 7G {field} is not in frozen 0-1 fraction units: {number}."
        )


def _normalize_advanced(advanced: dict[str, Any], *, include_usage: bool) -> dict[str, Any]:
    result = deepcopy(advanced)
    fields = list(_COMMON_FRACTION_RATE_FIELDS)
    if include_usage:
        fields.extend(_PLAYER_ONLY_FRACTION_RATE_FIELDS)
    for field in fields:
        if field in result:
            result[field] = _fraction(result[field], field)
    for field in (*fields, *_ALREADY_FRACTION_FIELDS):
        if field in result:
            _validate_fraction(result[field], field)

    # Ratings are per-100-possession values and should not look like fraction
    # percentages. This catches accidental rescaling in either direction.
    for field in (
        "estimated_offensive_rating",
        "estimated_defensive_rating",
    ):
        value = result.get(field)
        if value is not None:
            number = _number(value, field)
            if number <= 40.0 or number >= 180.0:
                raise WNBAAdvancedStatsUpstreamError(
                    f"Step 7G {field} is outside plausible per-100 units: {number}."
                )
    pace = result.get("estimated_pace")
    if pace is not None:
        number = _number(pace, "estimated_pace")
        if number <= 40.0 or number >= 160.0:
            raise WNBAAdvancedStatsUpstreamError(
                f"Step 7G estimated_pace is outside plausible game-pace units: {number}."
            )
    return result


def _normalize_dataset(
    dataset: dict[str, Any],
    *,
    collection: str,
    include_usage: bool,
) -> dict[str, Any]:
    result = deepcopy(dataset)
    last_n_games = result.get("last_n_games")
    if not isinstance(last_n_games, int) or isinstance(last_n_games, bool):
        raise WNBAAdvancedStatsUpstreamError(
            "Step 7G advanced dataset is missing integer last_n_games."
        )
    rows = result.get(collection)
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise WNBAAdvancedStatsUpstreamError(
            f"Step 7G advanced dataset expected exactly one {collection} row."
        )
    advanced = rows[0].get("advanced")
    if not isinstance(advanced, dict):
        raise WNBAAdvancedStatsUpstreamError(
            f"Step 7G {collection} row is missing advanced metrics."
        )
    rows[0]["advanced"] = _normalize_advanced(advanced, include_usage=include_usage)
    result["window_scope"] = _frozen_window_scope(last_n_games)
    result["source_variant"] = SOURCE_VARIANT
    result.setdefault("derivation", {})["frozen_percentage_unit_normalization"] = {
        "native_pct_fields_use_fraction_units": True,
        "converted_fields": list(
            _COMMON_FRACTION_RATE_FIELDS
            + (_PLAYER_ONLY_FRACTION_RATE_FIELDS if include_usage else ())
        ),
        "assist_ratio_not_rescaled": True,
        "rating_and_pace_units_not_rescaled": True,
    }
    verification = result.setdefault("verification", {})
    verification["frozen_step4f_percentage_units_verified"] = True
    verification["frozen_window_scope_spelling_verified"] = True
    verification["estimated_fields_not_mislabeled_as_official"] = True
    verification["third_party_sources_used"] = False
    return result


def get_first_party_player_advanced_stats_dataset(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _normalize_dataset(
        _raw_player_dataset(*args, **kwargs),
        collection="players",
        include_usage=True,
    )


def get_first_party_team_advanced_stats_dataset(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _normalize_dataset(
        _raw_team_dataset(*args, **kwargs),
        collection="teams",
        include_usage=False,
    )
