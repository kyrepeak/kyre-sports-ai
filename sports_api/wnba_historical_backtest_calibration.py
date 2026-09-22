"""WNBA Step 5I: audit-aware historical backtest and probability calibration."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import hmac
import json
from math import isfinite, log, sqrt
import os
from statistics import median
from typing import Any

from sports_api.wnba_game_history import (
    ALLOWED_SEASON_TYPES,
    WNBAHistoryNotFoundError,
    WNBAHistoryUpstreamError,
    get_player_game_log_dataset,
)
from sports_api.wnba_prop_threshold_probability import (
    MODEL_VERSION as THRESHOLD_MODEL_VERSION,
    SUPPORTED_STATS,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5I historical backtest and calibration engine"
MODEL_VERSION = "wnba_step_5i_historical_backtest_calibration_v1"
ARCHIVE_SCHEMA_VERSION = "wnba_step_5i_pregame_archive_v1"
OBSERVATION_SCHEMA_VERSION = "wnba_step_5i_backtest_observation_v1"
CALIBRATION_SCHEMA_VERSION = "wnba_step_5i_calibration_report_v1"
ARCHIVE_SIGNING_ENV = "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET"
SCENARIOS = ("low", "base", "high")
MAX_BACKTEST_OBSERVATIONS = 10_000
MIN_RESOLVED_FOR_CALIBRATION_CLAIM = 30
CALIBRATION_BIN_COUNT = 10
LOG_EPS = 1e-12


class WNBAHistoricalBacktestNotReadyError(RuntimeError):
    pass


class WNBAHistoricalBacktestNotFoundError(LookupError):
    pass


class WNBAHistoricalBacktestUpstreamError(RuntimeError):
    pass


class WNBAHistoricalBacktestModelInputError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _int(v: Any) -> int | None:
    try:
        return None if _clean(v) is None else int(float(str(v)))
    except (TypeError, ValueError):
        return None


def _float(v: Any) -> float | None:
    try:
        x = float(str(v))
    except (TypeError, ValueError):
        return None
    return x if isfinite(x) else None


def _dt(v: Any, label: str) -> datetime:
    s = _clean(v)
    if not s:
        raise WNBAHistoricalBacktestUpstreamError(f"{label} is missing.")
    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"
    try:
        x = datetime.fromisoformat(s)
    except ValueError as exc:
        raise WNBAHistoricalBacktestUpstreamError(
            f"{label} must be timezone-aware ISO-8601."
        ) from exc
    if x.tzinfo is None or x.utcoffset() is None:
        raise WNBAHistoricalBacktestUpstreamError(
            f"{label} must include a timezone offset or Z."
        )
    return x.astimezone(timezone.utc)


def _hash(v: Any) -> str:
    raw = json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _sha(v: Any) -> bool:
    s = _clean(v)
    return bool(s and len(s) == 64 and all(c in "0123456789abcdefABCDEF" for c in s))


def _secret(v: str | bytes | None) -> bytes | None:
    v = os.environ.get(ARCHIVE_SIGNING_ENV) if v is None else v
    if v is None:
        return None
    b = v if isinstance(v, bytes) else str(v).encode()
    if len(b) < 32:
        raise WNBAHistoricalBacktestModelInputError(
            f"{ARCHIVE_SIGNING_ENV} must contain at least 32 bytes."
        )
    return b


def _sign(secret: bytes, digest: str) -> str:
    return hmac.new(secret, digest.encode("ascii"), hashlib.sha256).hexdigest()


def _verify_snapshot(snapshot: dict[str, Any]) -> None:
    if not isinstance(snapshot, dict):
        raise ValueError("WNBA Step 5I snapshot must be an object.")
    if snapshot.get("schema_version") != "wnba_step_4w_v1":
        raise WNBAHistoricalBacktestUpstreamError("Unexpected Step 4W snapshot schema.")
    content = {k: snapshot.get(k) for k in (
        "schema_version", "season", "season_type", "game_id", "player_id",
        "recent_window_games", "game_identity", "focal_identity",
        "component_status", "inputs",
    )}
    if not _sha(snapshot.get("content_sha256")) or _hash(content) != snapshot.get("content_sha256"):
        raise WNBAHistoricalBacktestUpstreamError("Step 4W snapshot content hash mismatch.")


def _verify_threshold(threshold: dict[str, Any]) -> None:
    if not isinstance(threshold, dict):
        raise ValueError("WNBA Step 5I threshold must be an object.")
    if threshold.get("model_version") != THRESHOLD_MODEL_VERSION:
        raise WNBAHistoricalBacktestUpstreamError("Unexpected Step 5F model version.")
    ref, config = threshold.get("step_5e_reference"), threshold.get("model_config")
    results, sens = threshold.get("conditional_scenario_results"), threshold.get("scenario_sensitivity")
    if not all(isinstance(x, dict) for x in (ref, config, results, sens)):
        raise WNBAHistoricalBacktestUpstreamError("Step 5F fingerprint fields are missing.")
    sim = ref.get("simulation_fingerprint_sha256")
    expected = _hash({
        "step_5e_simulation_fingerprint_sha256": sim,
        "model_config": config,
        "conditional_threshold_results": results,
        "scenario_sensitivity": sens,
    })
    if not _sha(sim) or not _sha(threshold.get("probability_fingerprint_sha256")) or expected != threshold.get("probability_fingerprint_sha256"):
        raise WNBAHistoricalBacktestUpstreamError("Step 5F probability fingerprint mismatch.")


def _identity(threshold: dict[str, Any], snapshot: dict[str, Any]) -> tuple[int, str, str, str, str, float]:
    _verify_threshold(threshold)
    _verify_snapshot(snapshot)
    pid, gid = _int(threshold.get("player_id")), _clean(threshold.get("game_id"))
    team, opp = _clean(threshold.get("team_key")), _clean(threshold.get("opponent_team_key"))
    prop = threshold.get("prop")
    focal = snapshot.get("focal_identity")
    if pid is None or pid <= 0 or not gid or not team or not opp or not isinstance(prop, dict) or not isinstance(focal, dict):
        raise WNBAHistoricalBacktestUpstreamError("Step 5F/4W identity is malformed.")
    stat, line = _clean(prop.get("stat")), _float(prop.get("line"))
    if stat not in SUPPORTED_STATS or line is None or line < 0:
        raise WNBAHistoricalBacktestUpstreamError("Step 5F prop is invalid.")
    if (
        _int(snapshot.get("player_id")) != pid
        or _clean(snapshot.get("game_id")) != gid
        or _clean(focal.get("team_key")) != team
        or _clean(focal.get("opponent_team_key")) != opp
    ):
        raise WNBAHistoricalBacktestUpstreamError("Step 5F and Step 4W identity disagree.")
    reference = threshold.get("snapshot_reference")
    if not isinstance(reference, dict):
        raise WNBAHistoricalBacktestUpstreamError("Step 5F snapshot reference is missing.")
    for k in ("snapshot_id", "content_sha256", "captured_at_utc", "finalized_at_utc",
              "season", "season_type", "game_id", "player_id", "recent_window_games"):
        if reference.get(k) != snapshot.get(k):
            raise WNBAHistoricalBacktestUpstreamError(f"Step 5F snapshot reference mismatch: {k}.")
    results = threshold.get("conditional_scenario_results")
    if not isinstance(results, dict) or threshold.get("primary_result") != results.get("base"):
        raise WNBAHistoricalBacktestUpstreamError("Step 5F BASE/primary result mismatch.")
    return pid, gid, team, opp, stat, float(line)


def _prediction(threshold: dict[str, Any]) -> dict[str, Any]:
    means, over, under, pushes = {}, {}, {}, {}
    for name in SCENARIOS:
        row = threshold["conditional_scenario_results"].get(name)
        if not isinstance(row, dict) or _clean(row.get("conditional_scenario")) != name:
            raise WNBAHistoricalBacktestUpstreamError(f"Missing {name} Step 5F scenario.")
        if _clean(row.get("stat")) != _clean(threshold["prop"].get("stat")) or _float(row.get("line")) != _float(threshold["prop"].get("line")):
            raise WNBAHistoricalBacktestUpstreamError(f"{name} Step 5F prop identity mismatch.")
        src, fair, raw = row.get("source_distribution_summary"), row.get("fair_odds"), row.get("raw_probabilities")
        if not all(isinstance(x, dict) for x in (src, fair, raw)):
            raise WNBAHistoricalBacktestUpstreamError(f"{name} Step 5F probability fields missing.")
        means[name] = _float(src.get("mean"))
        try:
            over[name] = _float(fair["over"].get("fair_probability")) if fair["over"].get("available") is True else None
            under[name] = _float(fair["under"].get("fair_probability")) if fair["under"].get("available") is True else None
            po, pu, pp = (_float(raw[k].get("probability")) for k in ("over", "under", "push"))
        except Exception as exc:
            raise WNBAHistoricalBacktestUpstreamError(f"{name} Step 5F probability structure invalid.") from exc
        if means[name] is None or means[name] < 0 or over[name] is None or under[name] is None or po is None or pu is None or pp is None:
            raise WNBAHistoricalBacktestNotReadyError(f"{name} Step 5F scenario is not gradeable.")
        if abs(po + pu + pp - 1) > 1e-8 or po + pu <= 0:
            raise WNBAHistoricalBacktestUpstreamError(f"{name} Step 5F raw probabilities invalid.")
        if abs(over[name] - po / (po + pu)) > 1e-8 or abs(under[name] - pu / (po + pu)) > 1e-8:
            raise WNBAHistoricalBacktestUpstreamError(f"{name} Step 5F fair probabilities inconsistent.")
        pushes[name] = pp
    if means["low"] > means["base"] + 1e-9 or means["base"] > means["high"] + 1e-9:
        raise WNBAHistoricalBacktestUpstreamError("LOW/BASE/HIGH means are not ordered.")
    favored = "balanced" if abs(over["base"] - .5) < 1e-12 else ("over" if over["base"] > .5 else "under")
    return {
        "scenario_mean_by_name": means,
        "resolved_over_probability_by_scenario": over,
        "resolved_under_probability_by_scenario": under,
        "raw_push_probability_by_scenario": pushes,
        "model_favored_side_base": favored,
    }


def _context(snapshot: dict[str, Any]) -> dict[str, Any]:
    focal, inputs = snapshot["focal_identity"], snapshot.get("inputs") or {}
    side = _clean(focal.get("side"))
    role = (((inputs.get("player_opportunity_context") or {}).get("observed_role_context") or {}).get("observed_role_band"))
    side_ctx = ((inputs.get("game_rest_travel_context") or {}).get(f"{side}_context") or {})
    rest, road = side_ctx.get("rest") or {}, side_ctx.get("road_trip") or {}
    full = _int(rest.get("full_rest_days_before_date"))
    b2b = rest.get("is_second_night_of_back_to_back") is True
    bucket = "back_to_back_second_night" if b2b else (
        "unknown" if full is None else
        "zero_full_rest_days" if full <= 0 else
        "one_full_rest_day" if full == 1 else
        "two_plus_full_rest_days"
    )
    return {
        "home_away": side or "unknown",
        "pregame_observed_role_band": _clean(role) or "unresolved",
        "full_rest_days_before_game": full,
        "is_second_night_of_back_to_back": b2b,
        "back_to_back_position": _clean(rest.get("back_to_back_position")) or "unknown",
        "rest_bucket": bucket,
        "road_trip_game_number": _int(road.get("road_trip_game_number")),
    }


def build_pregame_archive_envelope(
    threshold: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    archived_at_utc: datetime | None = None,
    signing_secret: str | bytes | None = None,
) -> dict[str, Any]:
    pid, gid, team, opp, stat, line = _identity(threshold, snapshot)
    game = snapshot.get("game_identity")
    if not isinstance(game, dict):
        raise WNBAHistoricalBacktestUpstreamError("Step 4W game identity is missing.")
    tip = _dt(game.get("game_datetime_utc"), "official game tip")
    captured = _dt(snapshot.get("captured_at_utc"), "snapshot captured_at_utc")
    finalized = _dt(snapshot.get("finalized_at_utc"), "snapshot finalized_at_utc")
    generated = _dt(threshold.get("generated_at_utc"), "probability generated_at_utc")
    archived = archived_at_utc or _now()
    if not isinstance(archived, datetime):
        raise ValueError("WNBA archived_at_utc must be a datetime when supplied.")
    archived = archived.replace(tzinfo=timezone.utc) if archived.tzinfo is None else archived.astimezone(timezone.utc)
    stamps = {"snapshot_capture": captured, "snapshot_finalize": finalized, "probability_generation": generated, "archive_creation": archived}
    bad = [k for k, v in stamps.items() if v >= tip]
    if bad:
        raise WNBAHistoricalBacktestNotReadyError(
            "Pregame archive timestamps must be strictly before official tip: " + ", ".join(bad)
        )
    content = {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "archived_at_utc": archived.isoformat(),
        "official_game_tip_utc": tip.isoformat(),
        "season": threshold.get("season"),
        "season_type": threshold.get("season_type"),
        "game_id": gid, "player_id": pid, "team_key": team, "opponent_team_key": opp,
        "prop": {"stat": stat, "line": line},
        "threshold_reference": {
            "model_version": threshold.get("model_version"),
            "probability_id": threshold.get("probability_id"),
            "probability_fingerprint_sha256": threshold.get("probability_fingerprint_sha256"),
            "generated_at_utc": generated.isoformat(),
        },
        "snapshot_reference": {
            "snapshot_id": snapshot.get("snapshot_id"),
            "content_sha256": snapshot.get("content_sha256"),
            "captured_at_utc": captured.isoformat(),
            "finalized_at_utc": finalized.isoformat(),
        },
        "prediction": _prediction(threshold),
        "context": _context(snapshot),
        "lead_time_minutes": {
            "snapshot_capture_to_tip": round((tip-captured).total_seconds()/60, 6),
            "probability_generation_to_tip": round((tip-generated).total_seconds()/60, 6),
            "archive_creation_to_tip": round((tip-archived).total_seconds()/60, 6),
        },
    }
    digest = _hash(content)
    secret = _secret(signing_secret)
    sig = _sign(secret, digest) if secret else None
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_pregame_prediction_archive_envelope",
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "archive_id": f"wnba-5i-archive-{gid}-{pid}-{stat}-{digest[:16]}",
        "content_sha256": digest,
        "content": content,
        "signature": {"algorithm": "hmac-sha256" if sig else None, "value": sig, "signed": bool(sig)},
        "trust": {
            "hmac_signed": bool(sig),
            "audit_grade_candidate": bool(sig),
            "unsigned_archive_is_not_cryptographic_proof_of_historical_existence": True,
        },
    }


def _verify_archive(archive: dict[str, Any], secret: str | bytes | None, require_audit_grade: bool) -> tuple[dict[str, Any], bool]:
    if not isinstance(archive, dict) or archive.get("schema_version") != ARCHIVE_SCHEMA_VERSION:
        raise WNBAHistoricalBacktestUpstreamError("Invalid Step 5I archive schema.")
    content, digest, sig = archive.get("content"), archive.get("content_sha256"), archive.get("signature")
    if not isinstance(content, dict) or not _sha(digest) or _hash(content) != digest or not isinstance(sig, dict):
        raise WNBAHistoricalBacktestUpstreamError("Step 5I archive integrity check failed.")
    verified = False
    if sig.get("signed") is True:
        if sig.get("algorithm") != "hmac-sha256" or not _sha(sig.get("value")):
            raise WNBAHistoricalBacktestUpstreamError("Step 5I archive signature metadata is invalid.")
        key = _secret(secret)
        if key is not None:
            if not hmac.compare_digest(_sign(key, digest), sig["value"]):
                raise WNBAHistoricalBacktestUpstreamError("Step 5I archive signature verification failed.")
            verified = True
    if require_audit_grade and not verified:
        raise WNBAHistoricalBacktestNotReadyError(
            "Audit-grade backtesting requires a verifiable HMAC-signed pregame archive."
        )
    tip = _dt(content.get("official_game_tip_utc"), "archive official tip")
    for label, value in (
        ("archive timestamp", content.get("archived_at_utc")),
        ("probability timestamp", (content.get("threshold_reference") or {}).get("generated_at_utc")),
        ("snapshot capture timestamp", (content.get("snapshot_reference") or {}).get("captured_at_utc")),
        ("snapshot finalize timestamp", (content.get("snapshot_reference") or {}).get("finalized_at_utc")),
    ):
        if _dt(value, label) >= tip:
            raise WNBAHistoricalBacktestUpstreamError(f"{label} is not strictly pregame.")
    return content, verified


# Backward-compatible internal names used by the deterministic Step-5I harness.
_canonical_hash = _hash


def _verify_archive_envelope(
    archive: dict[str, Any],
    *,
    signing_secret: str | bytes | None,
    require_audit_grade: bool,
) -> tuple[dict[str, Any], bool]:
    return _verify_archive(archive, signing_secret, require_audit_grade)


def _actual(content: dict[str, Any], game_log: dict[str, Any]) -> dict[str, Any]:
    pid, season = _int(content.get("player_id")), _int(content.get("season"))
    stype, gid = _clean(content.get("season_type")), _clean(content.get("game_id"))
    if not isinstance(game_log, dict) or _int(game_log.get("player_id")) != pid or _int(game_log.get("season")) != season or _clean(game_log.get("season_type")) != stype:
        raise WNBAHistoricalBacktestUpstreamError("Official WNBA game-log identity mismatch.")
    games = game_log.get("games")
    if not isinstance(games, list):
        raise WNBAHistoricalBacktestUpstreamError("Official WNBA game log is malformed.")
    matches = [r for r in games if isinstance(r, dict) and _clean(r.get("game_id")) == gid]
    if not matches:
        raise WNBAHistoricalBacktestNotFoundError(f"Official result for game {gid} was not found.")
    if len(matches) != 1:
        raise WNBAHistoricalBacktestUpstreamError("Duplicate official target-game rows.")
    r = matches[0]
    matchup = r.get("matchup")
    if not isinstance(matchup, dict) or _clean(matchup.get("team_key")) != _clean(content.get("team_key")) or _clean(matchup.get("opponent_team_key")) != _clean(content.get("opponent_team_key")):
        raise WNBAHistoricalBacktestUpstreamError("Official result matchup identity mismatch.")
    tip = _dt(content.get("official_game_tip_utc"), "archive official tip")
    if _clean(r.get("game_date")) != tip.date().isoformat():
        raise WNBAHistoricalBacktestUpstreamError("Official result date mismatch.")
    minutes = _float(r.get("minutes"))
    if minutes is None or minutes <= 0:
        raise WNBAHistoricalBacktestNotReadyError("Zero-minute/DNP result is not graded.")
    p, reb, ast = _int(r.get("points")), _int(r.get("rebounds")), _int(r.get("assists"))
    if None in (p, reb, ast) or min(p, reb, ast) < 0:
        raise WNBAHistoricalBacktestUpstreamError("Official result P/R/A is incomplete or invalid.")
    return {
        "game_date": r.get("game_date"), "minutes": minutes,
        "points": p, "rebounds": reb, "assists": ast, "pra": p+reb+ast,
        "official_matchup": deepcopy(matchup), "result": r.get("result"),
    }


def grade_archived_prediction(
    archive: dict[str, Any],
    game_log: dict[str, Any],
    *,
    signing_secret: str | bytes | None = None,
    require_audit_grade: bool = True,
) -> dict[str, Any]:
    content, verified = _verify_archive(archive, signing_secret, require_audit_grade)
    actual = _actual(content, game_log)
    prop, pred = content.get("prop"), content.get("prediction")
    if not isinstance(prop, dict) or not isinstance(pred, dict):
        raise WNBAHistoricalBacktestUpstreamError("Archived prop/prediction is malformed.")
    stat, line = _clean(prop.get("stat")), _float(prop.get("line"))
    if stat not in SUPPORTED_STATS or line is None:
        raise WNBAHistoricalBacktestUpstreamError("Archived prop is invalid.")
    value = float(actual[stat])
    settlement = "over" if value > line else ("under" if value < line else "push")
    means = pred.get("scenario_mean_by_name") or {}
    over = pred.get("resolved_over_probability_by_scenario") or {}
    under = pred.get("resolved_under_probability_by_scenario") or {}
    low, base, high = _float(means.get("low")), _float(means.get("base")), _float(means.get("high"))
    po, pu = _float(over.get("base")), _float(under.get("base"))
    if None in (low, base, high, po, pu) or not 0 < po < 1 or not 0 < pu < 1 or low > base or base > high:
        raise WNBAHistoricalBacktestUpstreamError("Archived prediction summary is invalid.")
    signed = base - value
    resolved = settlement != "push"
    y = 1.0 if settlement == "over" else (0.0 if settlement == "under" else None)
    if resolved:
        brier = (po-y)**2
        q = min(1-LOG_EPS, max(LOG_EPS, po))
        ll = -(y*log(q)+(1-y)*log(1-q))
    else:
        brier = ll = None
    favored = _clean(pred.get("model_favored_side_base")) or "balanced"
    favored_correct = favored == settlement if resolved and favored in {"over", "under"} else None
    obs = {
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "archive_reference": {
            "archive_id": archive.get("archive_id"), "content_sha256": archive.get("content_sha256"),
            "signature_verified": verified,
        },
        "probability_model_version": (content.get("threshold_reference") or {}).get("model_version"),
        "probability_fingerprint_sha256": (content.get("threshold_reference") or {}).get("probability_fingerprint_sha256"),
        "snapshot_content_sha256": (content.get("snapshot_reference") or {}).get("content_sha256"),
        "season": content.get("season"), "season_type": content.get("season_type"),
        "game_id": content.get("game_id"), "player_id": content.get("player_id"),
        "team_key": content.get("team_key"), "opponent_team_key": content.get("opponent_team_key"),
        "prop": deepcopy(prop), "prediction": deepcopy(pred),
        "actual": {**actual, "target_stat_value": value, "settlement": settlement},
        "projection_error": {
            "base_projection_mean": base, "actual_value": value,
            "signed_error_prediction_minus_actual": round(signed, 10),
            "absolute_error": round(abs(signed), 10), "squared_error": round(signed*signed, 10),
        },
        "probability_scoring": {
            "eligible_resolved_non_push": resolved, "over_event_outcome_binary": y,
            "base_resolved_over_probability": po, "base_resolved_under_probability": pu,
            "brier_score": round(brier, 10) if brier is not None else None,
            "log_loss": round(ll, 10) if ll is not None else None,
            "base_model_favored_side": favored, "favored_side_correct": favored_correct,
        },
        "scenario_envelope": {
            "low_mean": low, "base_mean": base, "high_mean": high,
            "actual_within_low_high_inclusive": low <= value <= high,
            "width": round(high-low, 10), "not_a_confidence_interval": True,
        },
        "context": deepcopy(content.get("context")),
        "pregame_timing": {
            "official_game_tip_utc": content.get("official_game_tip_utc"),
            "archived_at_utc": content.get("archived_at_utc"),
            "lead_time_minutes": deepcopy(content.get("lead_time_minutes")),
        },
        "trust": {"archive_hmac_signature_verified": verified, "audit_grade": verified},
    }
    digest = _hash(obs)
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_graded_archived_player_prop_backtest_observation",
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "generated_at_utc": _now().isoformat(),
        "observation_id": f"wnba-5i-observation-{content.get('game_id')}-{content.get('player_id')}-{stat}-{digest[:16]}",
        "observation_content_sha256": digest,
        "content": obs,
    }


def get_graded_archived_prediction(
    archive: dict[str, Any],
    *,
    signing_secret: str | bytes | None = None,
    require_audit_grade: bool = True,
) -> dict[str, Any]:
    content = archive.get("content") if isinstance(archive, dict) else None
    if not isinstance(content, dict):
        raise ValueError("WNBA Step 5I archive content is required.")
    pid, season, stype = _int(content.get("player_id")), _int(content.get("season")), _clean(content.get("season_type"))
    if pid is None or pid <= 0 or season is None or stype not in ALLOWED_SEASON_TYPES:
        raise ValueError("WNBA Step 5I archive player/season identity is invalid.")
    try:
        gl = get_player_game_log_dataset(pid, season, season_type=stype)
    except WNBAHistoryNotFoundError as exc:
        raise WNBAHistoricalBacktestNotFoundError(str(exc)) from exc
    except WNBAHistoryUpstreamError as exc:
        raise WNBAHistoricalBacktestUpstreamError(str(exc)) from exc
    return grade_archived_prediction(
        archive, gl, signing_secret=signing_secret, require_audit_grade=require_audit_grade
    )


def _verify_observation(o: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(o, dict) or o.get("schema_version") != OBSERVATION_SCHEMA_VERSION:
        raise WNBAHistoricalBacktestUpstreamError("Invalid Step 5I observation schema.")
    c, digest = o.get("content"), o.get("observation_content_sha256")
    if not isinstance(c, dict) or not _sha(digest) or _hash(c) != digest or c.get("schema_version") != OBSERVATION_SCHEMA_VERSION:
        raise WNBAHistoricalBacktestUpstreamError("Step 5I observation integrity check failed.")
    prop, actual, score, err, env = (c.get(k) for k in ("prop","actual","probability_scoring","projection_error","scenario_envelope"))
    if not all(isinstance(x, dict) for x in (prop,actual,score,err,env)):
        raise WNBAHistoricalBacktestUpstreamError("Step 5I observation fields are missing.")
    if _clean(prop.get("stat")) not in SUPPORTED_STATS or _clean(actual.get("settlement")) not in {"over","under","push"}:
        raise WNBAHistoricalBacktestUpstreamError("Step 5I observation prop/settlement is invalid.")
    resolved = score.get("eligible_resolved_non_push") is True
    if resolved != (actual.get("settlement") != "push"):
        raise WNBAHistoricalBacktestUpstreamError("Step 5I push/resolved state mismatch.")
    p = _float(score.get("base_resolved_over_probability"))
    if p is None or not 0 < p < 1:
        raise WNBAHistoricalBacktestUpstreamError("Step 5I base probability is invalid.")
    if resolved:
        y, b = _float(score.get("over_event_outcome_binary")), _float(score.get("brier_score"))
        if y not in {0.0,1.0} or b is None or abs(b-(p-y)**2) > 1e-8:
            raise WNBAHistoricalBacktestUpstreamError("Step 5I binary score is inconsistent.")
    elif score.get("over_event_outcome_binary") is not None:
        raise WNBAHistoricalBacktestUpstreamError("Push unexpectedly has binary outcome.")
    pred, val, signed = _float(err.get("base_projection_mean")), _float(err.get("actual_value")), _float(err.get("signed_error_prediction_minus_actual"))
    if None in (pred,val,signed) or abs((pred-val)-signed) > 1e-8:
        raise WNBAHistoricalBacktestUpstreamError("Step 5I projection error is inconsistent.")
    return c


def _dedupe_projection(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: dict[tuple[Any,...],dict[str,Any]] = {}
    for r in rows:
        key = (r.get("game_id"), r.get("player_id"), (r.get("prop") or {}).get("stat"),
               r.get("snapshot_content_sha256"), r.get("probability_model_version"))
        if key not in out:
            out[key] = r
            continue
        a, b = out[key], r
        for path in (("projection_error","base_projection_mean"),("projection_error","actual_value"),
                     ("scenario_envelope","low_mean"),("scenario_envelope","base_mean"),("scenario_envelope","high_mean")):
            if _float((a.get(path[0]) or {}).get(path[1])) != _float((b.get(path[0]) or {}).get(path[1])):
                raise WNBAHistoricalBacktestUpstreamError(
                    "Alternate-line observations disagree on the frozen central projection/result."
                )
    return list(out.values())


def _projection(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"observation_count":0,"mae":None,"rmse":None,"median_absolute_error":None,"mean_signed_error_prediction_minus_actual":None}
    s = [float(r["projection_error"]["signed_error_prediction_minus_actual"]) for r in rows]
    a = [abs(x) for x in s]
    return {
        "observation_count": len(rows),
        "mae": round(sum(a)/len(a),10),
        "rmse": round(sqrt(sum(x*x for x in s)/len(s)),10),
        "median_absolute_error": round(float(median(a)),10),
        "mean_signed_error_prediction_minus_actual": round(sum(s)/len(s),10),
        "bias_semantics": "Positive means model overprediction.",
    }


def _bins(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bins=[]
    for i in range(CALIBRATION_BIN_COUNT):
        lo,hi=i/CALIBRATION_BIN_COUNT,(i+1)/CALIBRATION_BIN_COUNT
        m=[r for r in rows if lo <= float(r["probability_scoring"]["base_resolved_over_probability"]) < hi or (i==9 and float(r["probability_scoring"]["base_resolved_over_probability"])==1)]
        if m:
            ps=[float(r["probability_scoring"]["base_resolved_over_probability"]) for r in m]
            ys=[float(r["probability_scoring"]["over_event_outcome_binary"]) for r in m]
            mp,obs=sum(ps)/len(ps),sum(ys)/len(ys); gap=obs-mp
        else:
            mp=obs=gap=None
        bins.append({
            "bin_index":i,"lower_bound_inclusive":round(lo,4),"upper_bound":round(hi,4),
            "resolved_observation_count":len(m),
            "mean_predicted_over_probability":round(mp,10) if mp is not None else None,
            "observed_over_rate":round(obs,10) if obs is not None else None,
            "calibration_gap_observed_minus_predicted":round(gap,10) if gap is not None else None,
            "absolute_calibration_gap":round(abs(gap),10) if gap is not None else None,
        })
    non=[b for b in bins if b["resolved_observation_count"]]
    total=len(rows)
    ece=sum(b["resolved_observation_count"]/total*b["absolute_calibration_gap"] for b in non) if total else None
    mce=max((b["absolute_calibration_gap"] for b in non),default=None)
    return {"bin_count":10,"bins":bins,"expected_calibration_error":round(ece,10) if ece is not None else None,"maximum_calibration_error":round(mce,10) if mce is not None else None}


def _probability(rows: list[dict[str, Any]]) -> dict[str, Any]:
    resolved=[r for r in rows if r["probability_scoring"]["eligible_resolved_non_push"] is True]
    if not resolved:
        return {"total_observation_count":len(rows),"resolved_observation_count":0,"push_count_excluded_from_binary_scoring":len(rows),"brier_score":None,"log_loss":None,"favored_side_hit_rate":None,"calibration":_bins([]),"calibration_claim_ready":False,"minimum_resolved_for_calibration_claim":MIN_RESOLVED_FOR_CALIBRATION_CLAIM}
    b=[float(r["probability_scoring"]["brier_score"]) for r in resolved]
    ll=[float(r["probability_scoring"]["log_loss"]) for r in resolved]
    ps=[float(r["probability_scoring"]["base_resolved_over_probability"]) for r in resolved]
    ys=[float(r["probability_scoring"]["over_event_outcome_binary"]) for r in resolved]
    fav=[r["probability_scoring"]["favored_side_correct"] for r in resolved if isinstance(r["probability_scoring"].get("favored_side_correct"),bool)]
    return {
        "total_observation_count":len(rows),"resolved_observation_count":len(resolved),
        "push_count_excluded_from_binary_scoring":len(rows)-len(resolved),
        "brier_score":round(sum(b)/len(b),10),"log_loss":round(sum(ll)/len(ll),10),
        "mean_predicted_over_probability":round(sum(ps)/len(ps),10),"observed_over_rate":round(sum(ys)/len(ys),10),
        "favored_side_graded_count":len(fav),"favored_side_hit_rate":round(sum(fav)/len(fav),10) if fav else None,
        "calibration":_bins(resolved),
        "calibration_claim_ready":len(resolved)>=MIN_RESOLVED_FOR_CALIBRATION_CLAIM,
        "minimum_resolved_for_calibration_claim":MIN_RESOLVED_FOR_CALIBRATION_CLAIM,
    }


def _coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"observation_count":0,"inside_low_high_rate":None,"mean_envelope_width":None,"not_a_confidence_interval":True}
    inside=sum(r["scenario_envelope"]["actual_within_low_high_inclusive"] is True for r in rows)
    widths=[float(r["scenario_envelope"]["width"]) for r in rows]
    return {"observation_count":len(rows),"inside_low_high_count":inside,"inside_low_high_rate":round(inside/len(rows),10),"mean_envelope_width":round(sum(widths)/len(widths),10),"not_a_confidence_interval":True}


def _group(rows: list[dict[str, Any]], fn) -> dict[str, Any]:
    groups={}
    for r in rows:
        groups.setdefault(str(fn(r) if fn(r) is not None else "unknown"),[]).append(r)
    out={}
    for k,v in sorted(groups.items()):
        d=_dedupe_projection(v); p=_probability(v)
        out[k]={"observation_count":len(v),"projection_observation_count":len(d),"projection_error":_projection(d),"probability":{"resolved_observation_count":p["resolved_observation_count"],"brier_score":p["brier_score"],"log_loss":p["log_loss"],"favored_side_hit_rate":p["favored_side_hit_rate"]},"scenario_envelope":_coverage(d)}
    return out


def _report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    d=_dedupe_projection(rows)
    counts={k:sum(r["actual"]["settlement"]==k for r in rows) for k in ("over","under","push")}
    return {
        "observation_count":len(rows),"projection_observation_count":len(d),
        "projection_error":_projection(d),"probability":_probability(rows),
        "settlement":{"counts":counts,"rates":{k:round(v/len(rows),10) for k,v in counts.items()}},
        "scenario_envelope":_coverage(d),
        "by_stat":_group(rows,lambda r:r["prop"]["stat"]),
        "bias_slices":{
            "by_player_id":_group(rows,lambda r:r.get("player_id")),
            "by_team_key":_group(rows,lambda r:r.get("team_key")),
            "by_opponent_team_key":_group(rows,lambda r:r.get("opponent_team_key")),
            "by_home_away":_group(rows,lambda r:(r.get("context") or {}).get("home_away")),
            "by_pregame_observed_role_band":_group(rows,lambda r:(r.get("context") or {}).get("pregame_observed_role_band")),
            "by_rest_bucket":_group(rows,lambda r:(r.get("context") or {}).get("rest_bucket")),
            "by_second_night_back_to_back":_group(rows,lambda r:(r.get("context") or {}).get("is_second_night_of_back_to_back")),
        },
    }


def evaluate_backtest_observations(
    observations: list[dict[str, Any]],
    *,
    require_audit_grade: bool = True,
    require_single_probability_model_version: bool = True,
) -> dict[str, Any]:
    if not isinstance(observations,list) or not 1 <= len(observations) <= MAX_BACKTEST_OBSERVATIONS:
        raise ValueError(f"WNBA Step 5I observations must contain 1 through {MAX_BACKTEST_OBSERVATIONS:,} records.")
    if not isinstance(require_audit_grade,bool) or not isinstance(require_single_probability_model_version,bool):
        raise ValueError("WNBA Step 5I calibration flags must be boolean.")
    rows=[]; hashes=set(); keys=set()
    for o in observations:
        c=_verify_observation(o); digest=o["observation_content_sha256"]
        if digest in hashes:
            raise WNBAHistoricalBacktestModelInputError("Duplicate Step 5I observation hash.")
        hashes.add(digest)
        key=(c.get("game_id"),c.get("player_id"),(c.get("prop") or {}).get("stat"),(c.get("prop") or {}).get("line"),c.get("probability_fingerprint_sha256"))
        if key in keys:
            raise WNBAHistoricalBacktestModelInputError("Duplicate Step 5I logical observation.")
        keys.add(key)
        if require_audit_grade and (c.get("trust") or {}).get("audit_grade") is not True:
            raise WNBAHistoricalBacktestNotReadyError("Calibration requires audit-grade observations.")
        rows.append(c)
    versions=sorted({_clean(r.get("probability_model_version")) or "unknown" for r in rows})
    if require_single_probability_model_version and len(versions)!=1:
        raise WNBAHistoricalBacktestModelInputError("Mixed probability model versions cannot be pooled.")
    reports={v:_report([r for r in rows if (_clean(r.get("probability_model_version")) or "unknown")==v]) for v in versions}
    config={
        "model_version":MODEL_VERSION,"require_audit_grade":require_audit_grade,
        "require_single_probability_model_version":require_single_probability_model_version,
        "calibration_bin_count":CALIBRATION_BIN_COUNT,
        "minimum_resolved_for_calibration_claim":MIN_RESOLVED_FOR_CALIBRATION_CLAIM,
        "mixed_versions_never_pooled":True,
    }
    payload={"observation_hashes":sorted(hashes),"probability_model_versions":versions,"model_config":config,"reports_by_probability_model_version":reports}
    digest=_hash(payload)
    return {
        "source":MODEL_SOURCE,"data_type":"wnba_historical_projection_backtest_and_probability_calibration",
        "schema_version":CALIBRATION_SCHEMA_VERSION,"model_version":MODEL_VERSION,
        "generated_at_utc":_now().isoformat(),"calibration_report_id":f"wnba-5i-calibration-{digest[:20]}",
        "calibration_report_fingerprint_sha256":digest,"observation_count":len(rows),
        "observation_hashes":sorted(hashes),"probability_model_versions":versions,
        "pooled_report_available":len(versions)==1,"pooled_report":reports[versions[0]] if len(versions)==1 else None,
        "reports_by_probability_model_version":reports,
        "trust":{"require_audit_grade":require_audit_grade,"all_observations_audit_grade":all((r.get("trust") or {}).get("audit_grade") is True for r in rows)},
        "guardrails":{
            "no_retroactive_timestamp_claim_creates_audit_grade_history":True,
            "pushes_excluded_from_binary_calibration":True,
            "alternate_lines_do_not_duplicate_central_projection_error":True,
            "mixed_model_versions_never_pooled":True,
            "scenario_envelope_is_not_a_confidence_interval":True,
            "report_does_not_recalibrate_future_probabilities":True,
        },
        "model_config":config,
    }
