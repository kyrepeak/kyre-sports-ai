"""CFB Top Picks Research V2 Step 8 — DATA_FIELD source-router audit.

Read-only provenance/fallback layer over frozen Steps 1-7.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

MODEL_VERSION = "CFB TOP PICKS RESEARCH V2 STEP 8 • DATA_FIELD SOURCE ROUTER"
SOURCE_ROUTER_PROJECTION_WEIGHT = 0.0
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
API2_USED = False
UNIT_OF_WORK = "DATA_FIELD"
NO_SOURCE_LOYALTY = True

TERMINAL_HISTORY = {
    "VERIFIED_HISTORY",
    "VERIFIED_NO_HISTORY_AFTER_SOURCE_EXHAUSTION",
    "SOURCE_CONFLICT_REVIEW",
}

FIELD_POLICIES = {
    "offense_core": {
        "primary": "ESPN Core exact-team current-season statistics",
        "fallbacks": ["Checked-in 2026 CFB Step-3 verified snapshot fallback"],
    },
    "offense_recent": {
        "primary": "ESPN exact-team completed-game schedule",
        "fallbacks": [],
    },
    "red_zone_offense": {
        "primary": "NCAA red-zone offense",
        "fallbacks": ["verified team-official current-season statistics"],
    },
    "explosive_offense": {
        "primary": "NCAA passing/rushing efficiency tables",
        "fallbacks": [],
    },
    "defense_core": {
        "primary": "ESPN exact-event completed-game summaries",
        "fallbacks": ["Checked-in 2026 CFB Step-3 verified snapshot fallback"],
    },
    "defense_recent": {
        "primary": "ESPN exact-team completed-game schedule",
        "fallbacks": [],
    },
    "red_zone_defense": {
        "primary": "NCAA red-zone defense",
        "fallbacks": [],
    },
    "explosive_defense": {
        "primary": "NCAA passing/rushing defense efficiency tables",
        "fallbacks": [],
    },
    "pace": {
        "primary": "NCAA pace tables",
        "fallbacks": ["ESPN Core exact-team current-season statistics"],
    },
    "history": {
        "primary": "ESPN exact-team-ID schedule history",
        "fallbacks": ["Winsipedia all-time game-by-game history"],
    },
    "derived": {
        "primary": "verified upstream evidence",
        "fallbacks": [],
    },
}

OFFENSE_RECENT = {"recent_scoring_avg"}
OFFENSE_RED = {"red_zone_td_rate"}
OFFENSE_EXPLOSIVE = {"explosive_efficiency_proxy"}
DEFENSE_RECENT = {"recent_points_allowed_avg"}
DEFENSE_RED = {"red_zone_td_rate_allowed"}
DEFENSE_EXPLOSIVE = {"explosive_susceptibility_proxy"}
PACE_FIELDS = {"plays_per_game", "seconds_per_play", "pace_index"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _policy(domain: str, field: str) -> str:
    if domain == "offense":
        if field in OFFENSE_RECENT:
            return "offense_recent"
        if field in OFFENSE_RED:
            return "red_zone_offense"
        if field in OFFENSE_EXPLOSIVE:
            return "explosive_offense"
        return "offense_core"
    if domain == "defense":
        if field in DEFENSE_RECENT:
            return "defense_recent"
        if field in DEFENSE_RED:
            return "red_zone_defense"
        if field in DEFENSE_EXPLOSIVE:
            return "explosive_defense"
        if field in PACE_FIELDS:
            return "pace"
        return "defense_core"
    return domain if domain in FIELD_POLICIES else "derived"


def _metric_record(domain: str, side: str, field: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    policy_key = _policy(domain, field)
    policy = FIELD_POLICIES[policy_key]
    value = raw.get("value")
    status = _clean(raw.get("status")) or ("VERIFIED" if value is not None else "UNAVAILABLE")
    source = _clean(raw.get("source"))
    observed = _clean(raw.get("observed_at"))
    note = _clean(raw.get("note"))
    available = value is not None
    fallback_used = "FALLBACK" in status.upper() or "fallback" in source.casefold()

    violations: list[str] = []
    if available and not source:
        violations.append("material fact missing source")
    if available and not observed:
        violations.append("material fact missing observed_at")
    if not available and not note:
        violations.append("unavailable field missing explanation")

    chain = [policy["primary"], *list(policy["fallbacks"])]
    return {
        "domain": domain,
        "side": side,
        "field": field,
        "value": value,
        "status": status,
        "selected_source": source,
        "observed_at": observed,
        "note": note,
        "available": available,
        "fallback_used": fallback_used,
        "route_policy": policy_key,
        "route_chain": chain,
        "no_source_lock": True,
        "violations": violations,
    }


def _derived_record(domain: str, field: str, text: str, sources: list[str], observed_at: str, status: str) -> dict[str, Any]:
    sources = [str(x) for x in sources if _clean(x)]
    material = bool(_clean(text)) and status not in {"UNAVAILABLE", "IDENTITY_UNAVAILABLE", "LOADING"}
    violations: list[str] = []
    if material and not sources:
        violations.append("material fact missing source")
    if material and not _clean(observed_at):
        violations.append("material fact missing observed_at")
    return {
        "domain": domain,
        "side": "",
        "field": field,
        "value": _clean(text),
        "status": status,
        "selected_source": " • ".join(sources),
        "observed_at": _clean(observed_at),
        "note": "",
        "available": material,
        "fallback_used": False,
        "route_policy": "derived",
        "route_chain": ["verified upstream evidence"],
        "no_source_lock": True,
        "violations": violations,
    }


def build_source_freshness_audit(row: Mapping[str, Any], detail: Mapping[str, Any]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []

    for domain, payload_key in (
        ("offense", "offense_research"),
        ("defense", "defense_pace_research"),
    ):
        payload = detail.get(payload_key) or {}
        for side in ("away", "home"):
            profile = payload.get(side) or {}
            for field, raw in (profile.get("metrics") or {}).items():
                if isinstance(raw, Mapping):
                    records.append(_metric_record(domain, side, str(field), raw))

    reasoning = detail.get("market_reasoning") or {}
    signals = reasoning.get("signals") or {}
    for field in reasoning.get("required_signals") or []:
        raw = signals.get(field) or {}
        if not isinstance(raw, Mapping):
            continue
        records.append(_derived_record(
            "market_reasoning", str(field), _clean(raw.get("text")),
            [str(x) for x in (raw.get("sources") or [])],
            _clean(raw.get("observed_at")), _clean(raw.get("status")) or "UNAVAILABLE",
        ))

    br = detail.get("benefits_risks") or {}
    for bucket in ("benefits", "risks"):
        for idx, raw in enumerate(br.get(bucket) or [], 1):
            if not isinstance(raw, Mapping):
                continue
            records.append(_derived_record(
                bucket, f"{bucket}_{idx}", _clean(raw.get("text")),
                [str(x) for x in (raw.get("sources") or [])],
                _clean(raw.get("observed_at")), _clean(raw.get("status")) or "UNAVAILABLE",
            ))

    history_status = _clean(detail.get("history_status"))
    history_sources = [str(x) for x in (detail.get("sources_verified") or []) if _clean(x)]
    history_source = _clean(detail.get("history_source"))
    if history_source and history_source not in history_sources:
        history_sources.insert(0, history_source)
    history_record = _derived_record(
        "history", "actual_matchup_history",
        history_status or "history status unavailable",
        history_sources if history_status == "VERIFIED_HISTORY" else [
            str(x.get("source") or x.get("source_id") or "")
            for x in (detail.get("source_attempts") or [])
            if isinstance(x, Mapping)
        ],
        _clean(detail.get("history_observed_at")),
        history_status or "UNAVAILABLE",
    )
    history_record["route_policy"] = "history"
    history_record["route_chain"] = [
        FIELD_POLICIES["history"]["primary"],
        *FIELD_POLICIES["history"]["fallbacks"],
    ]
    if history_status and history_status not in TERMINAL_HISTORY:
        history_record["violations"].append("history router not in terminal state")
    records.append(history_record)

    violations = [
        f"{r['domain']}:{r['side']}:{r['field']}:{v}"
        for r in records for v in r.get("violations") or []
    ]
    material = [r for r in records if r.get("available")]
    unavailable = [r for r in records if not r.get("available")]
    fallback_count = sum(bool(r.get("fallback_used")) for r in records)

    source_counter: Counter[str] = Counter()
    freshest: dict[str, str] = {}
    for r in material:
        source = _clean(r.get("selected_source"))
        if not source:
            continue
        source_counter[source] += 1
        observed = _clean(r.get("observed_at"))
        if observed and observed > freshest.get(source, ""):
            freshest[source] = observed

    sources = [
        {"source": source, "material_fact_count": count, "observed_at": freshest.get(source, "")}
        for source, count in source_counter.most_common()
    ]

    return {
        "version": MODEL_VERSION,
        "status": "READY" if not violations else "BLOCKED",
        "unit_of_work": UNIT_OF_WORK,
        "no_source_loyalty": NO_SOURCE_LOYALTY,
        "records": records,
        "sources": sources,
        "material_fact_count": len(material),
        "unavailable_field_count": len(unavailable),
        "fallback_used_count": fallback_count,
        "violation_count": len(violations),
        "violations": violations,
        "history_terminal": history_status in TERMINAL_HISTORY,
        "projection_weight": SOURCE_ROUTER_PROJECTION_WEIGHT,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        "may_modify_probability": MAY_MODIFY_PROBABILITY,
        "may_modify_ranking": MAY_MODIFY_RANKING,
        "may_modify_selection": MAY_MODIFY_SELECTION,
        "api2_used": API2_USED,
    }


__all__ = [
    "API2_USED", "FIELD_POLICIES", "MODEL_VERSION", "NO_SOURCE_LOYALTY",
    "SOURCE_ROUTER_PROJECTION_WEIGHT", "SPORTSBOOK_PROJECTION_WEIGHT",
    "TERMINAL_HISTORY", "UNIT_OF_WORK", "build_source_freshness_audit",
]
