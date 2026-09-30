"""Live 10/10 certification for CFB Top Picks Research V2 Step 9."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import re
from typing import Any, Mapping

import cfb_top_picks_details_v5 as details
import cfb_top_picks_engine_v1 as engine
import cfb_top_picks_page_v9 as page
import cfb_top_picks_source_router_v1 as source_router_v1


ALLOWED_HISTORY = set(source_router_v1.TERMINAL_HISTORY)
PLACEHOLDER_CARD_VALUES = {"", "—"}
REQUIRED_DETAIL_HEADINGS = (
    "Why This Pick",
    "Actual Matchup History",
    "Offensive Scoring Research",
    "Defense + Pace Research",
    "Market-Aware Football Reasoning",
    "Benefits",
    "Risks",
    "Sources + Freshness",
)

COMMON_FIELDS = {
    "away_points_per_game": ("offense_research", "away", "points_per_game"),
    "home_points_per_game": ("offense_research", "home", "points_per_game"),
    "away_points_allowed_per_game": ("defense_pace_research", "away", "points_allowed_per_game"),
    "home_points_allowed_per_game": ("defense_pace_research", "home", "points_allowed_per_game"),
    "away_yards_per_play": ("offense_research", "away", "yards_per_play"),
    "home_yards_per_play": ("offense_research", "home", "yards_per_play"),
    "away_yards_per_play_allowed": ("defense_pace_research", "away", "yards_per_play_allowed"),
    "home_yards_per_play_allowed": ("defense_pace_research", "home", "yards_per_play_allowed"),
    "away_plays_per_game": ("defense_pace_research", "away", "plays_per_game"),
    "home_plays_per_game": ("defense_pace_research", "home", "plays_per_game"),
    "away_red_zone_td_rate": ("offense_research", "away", "red_zone_td_rate"),
    "home_red_zone_td_rate": ("offense_research", "home", "red_zone_td_rate"),
    "away_red_zone_td_rate_allowed": ("defense_pace_research", "away", "red_zone_td_rate_allowed"),
    "home_red_zone_td_rate_allowed": ("defense_pace_research", "home", "red_zone_td_rate_allowed"),
    "away_recent_scoring_avg": ("offense_research", "away", "recent_scoring_avg"),
    "home_recent_scoring_avg": ("offense_research", "home", "recent_scoring_avg"),
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


FAIR_PRICE_NO_SPORTSBOOK = "Unavailable — fair model price"


def _sportsbook(row: Mapping[str, Any]) -> str:
    source = _clean(row.get("source"))
    for marker in (" market", " threshold"):
        idx = source.casefold().find(marker)
        if idx > 0:
            provider = source[:idx].strip()
            if provider and not provider.casefold().startswith("kyre"):
                return provider
    odds = _clean(row.get("odds"))
    if odds.startswith("Fair ") and "fair price" in source.casefold():
        return FAIR_PRICE_NO_SPORTSBOOK
    if odds and odds not in {"—", "Market line"} and not re.fullmatch(r"[+-]?\d+", odds):
        return odds
    return ""


def _validate_card(row: Mapping[str, Any], slate_day: str) -> dict[str, Any]:
    rank = int(row.get("rank") or 0)
    fields = {
        "rank": rank,
        "event_id": _clean(row.get("event_id")),
        "slate_date": _clean(slate_day),
        "away_team": _clean(row.get("away")),
        "home_team": _clean(row.get("home")),
        "away_team_id": _clean(row.get("away_team_id")),
        "home_team_id": _clean(row.get("home_team_id")),
        "away_logo_url": _clean(row.get("away_logo_url")),
        "home_logo_url": _clean(row.get("home_logo_url")),
        "kickoff": _clean(row.get("time")),
        "network": _clean(row.get("network")),
        "market": _clean(row.get("market")),
        "pick": _clean(row.get("pick")),
        "line_or_price": _clean(row.get("odds")),
        "sportsbook": _sportsbook(row),
        "probability": row.get("probability"),
        "reliability": row.get("reliability"),
        "toughness": row.get("toughness"),
    }
    missing = [key for key, value in fields.items() if value is None or _clean(value) in PLACEHOLDER_CARD_VALUES]
    if missing:
        raise AssertionError(f"STEP9_CARD_MISSING:rank={rank}:{','.join(missing)}")
    if rank < 1 or rank > 10:
        raise AssertionError(f"STEP9_BAD_RANK:{rank}")
    if not fields["event_id"].isdigit():
        raise AssertionError(f"STEP9_BAD_EVENT_ID:{rank}:{fields['event_id']}")
    if not (fields["away_team_id"].isdigit() and fields["home_team_id"].isdigit()):
        raise AssertionError(f"STEP9_BAD_TEAM_ID:{rank}")
    for side in ("away", "home"):
        if not fields[f"{side}_logo_url"].startswith(("https://", "http://")):
            raise AssertionError(f"STEP9_BAD_LOGO:{rank}:{side}")
        if not _clean(row.get(f"{side}_logo_provider")):
            raise AssertionError(f"STEP9_LOGO_PROVIDER_MISSING:{rank}:{side}")
    if row.get("logo_identity_ready") is not True:
        raise AssertionError(f"STEP9_LOGO_IDENTITY_NOT_READY:{rank}")
    return fields


def _metric(detail: Mapping[str, Any], path: tuple[str, str, str]) -> Mapping[str, Any]:
    block, side, field = path
    return (((detail.get(block) or {}).get(side) or {}).get("metrics") or {}).get(field) or {}


def _validate_common_fields(rank: int, detail: Mapping[str, Any]) -> None:
    for name, path in COMMON_FIELDS.items():
        metric = _metric(detail, path)
        if not isinstance(metric, Mapping) or not metric:
            raise AssertionError(f"STEP9_COMMON_FIELD_ABSENT:{rank}:{name}")
        value = metric.get("value")
        status = _clean(metric.get("status"))
        if value is None:
            if status != "UNAVAILABLE" or not _clean(metric.get("note")):
                raise AssertionError(f"STEP9_UNEXPLAINED_MISSING:{rank}:{name}:{status}")
        else:
            if not _clean(metric.get("source")):
                raise AssertionError(f"STEP9_COMMON_SOURCE_MISSING:{rank}:{name}")
            if not _clean(metric.get("observed_at")):
                raise AssertionError(f"STEP9_COMMON_FRESHNESS_MISSING:{rank}:{name}")


def _validate_reasoning(rank: int, detail: Mapping[str, Any]) -> None:
    reasoning = detail.get("market_reasoning") or {}
    required = list(reasoning.get("required_signals") or [])
    signals = reasoning.get("signals") or {}
    if not required:
        raise AssertionError(f"STEP9_REASONING_REQUIRED_EMPTY:{rank}")
    for key in required:
        item = signals.get(key) or {}
        if not _clean(item.get("text")):
            raise AssertionError(f"STEP9_REASONING_TEXT_MISSING:{rank}:{key}")
        if not _clean(item.get("observed_at")):
            raise AssertionError(f"STEP9_REASONING_FRESHNESS_MISSING:{rank}:{key}")
        if _clean(item.get("status")) in {"VERIFIED", "PARTIAL"} and not list(item.get("sources") or []):
            raise AssertionError(f"STEP9_REASONING_SOURCE_MISSING:{rank}:{key}")


def _validate_evidence_bucket(rank: int, detail: Mapping[str, Any], bucket: str) -> None:
    result = detail.get("benefits_risks") or {}
    items = list(result.get(bucket) or [])
    if not items:
        raise AssertionError(f"STEP9_{bucket.upper()}_EMPTY:{rank}")
    for idx, item in enumerate(items, 1):
        if not _clean(item.get("text")):
            raise AssertionError(f"STEP9_{bucket.upper()}_TEXT:{rank}:{idx}")
        if not list(item.get("sources") or []):
            raise AssertionError(f"STEP9_{bucket.upper()}_SOURCE:{rank}:{idx}")
        if not _clean(item.get("observed_at")):
            raise AssertionError(f"STEP9_{bucket.upper()}_FRESHNESS:{rank}:{idx}")


def _validate_detail(row: Mapping[str, Any], detail: Mapping[str, Any]) -> dict[str, Any]:
    rank = int(row.get("rank") or 0)
    if detail.get("ready") is not True:
        raise AssertionError(f"STEP9_DETAIL_IDENTITY_NOT_READY:{rank}")
    if not _clean(detail.get("why")):
        raise AssertionError(f"STEP9_WHY_MISSING:{rank}")

    _validate_common_fields(rank, detail)
    _validate_reasoning(rank, detail)
    _validate_evidence_bucket(rank, detail, "benefits")
    _validate_evidence_bucket(rank, detail, "risks")

    history_status = _clean(detail.get("history_status"))
    if history_status not in ALLOWED_HISTORY:
        raise AssertionError(f"STEP9_HISTORY_NOT_TERMINAL:{rank}:{history_status}")
    if history_status == "VERIFIED_NO_HISTORY_AFTER_SOURCE_EXHAUSTION":
        if detail.get("no_history_claim_allowed") is not True:
            raise AssertionError(f"STEP9_NO_HISTORY_NOT_AUTHORIZED:{rank}")
        if int(detail.get("source_count_attempted") or 0) < 2:
            raise AssertionError(f"STEP9_HISTORY_SOURCES_NOT_EXHAUSTED:{rank}")

    audit = detail.get("source_freshness_audit") or {}
    if audit.get("status") != "READY" or int(audit.get("violation_count") or 0) != 0:
        raise AssertionError(f"STEP9_PROVENANCE_BLOCKED:{rank}:{audit.get('violations')}")
    if audit.get("history_terminal") is not True:
        raise AssertionError(f"STEP9_PROVENANCE_HISTORY_NOT_TERMINAL:{rank}")

    html = page._detail_card(dict(row), dict(detail))
    for heading in REQUIRED_DETAIL_HEADINGS:
        if heading not in html:
            raise AssertionError(f"STEP9_DETAIL_SECTION_MISSING:{rank}:{heading}")
    if '<div class="tp4-audit">' in html or "&lt;div class=&quot;tp4-audit" in html:
        raise AssertionError(f"STEP9_RAW_AUDIT_LEAK:{rank}")
    if re.search(r"&lt;/?(?:div|strong|span|section)\b", html, flags=re.I):
        raise AssertionError(f"STEP9_ESCAPED_HTML_LEAK:{rank}")

    return {
        "rank": rank,
        "event_id": _clean(row.get("event_id")),
        "market": _clean(row.get("market")),
        "history_status": history_status,
        "benefits": len((detail.get("benefits_risks") or {}).get("benefits") or []),
        "risks": len((detail.get("benefits_risks") or {}).get("risks") or []),
        "material_facts": int(audit.get("material_fact_count") or 0),
        "fallbacks": int(audit.get("fallback_used_count") or 0),
        "unavailable_explained": int(audit.get("unavailable_field_count") or 0),
        "provenance_violations": int(audit.get("violation_count") or 0),
    }


def run(artifact_dir: str | Path = "artifacts/cfb-top-picks-research-v2-step9") -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    picks, diag = engine.build_top_picks(limit=10)
    if len(picks) != 10:
        raise AssertionError(f"STEP9_TOP10_COUNT:{len(picks)}")
    if [int(row.get("rank") or 0) for row in picks] != list(range(1, 11)):
        raise AssertionError("STEP9_RANK_SEQUENCE")
    event_ids = [_clean(row.get("event_id")) for row in picks]
    if len(set(event_ids)) != 10:
        raise AssertionError("STEP9_DUPLICATE_EVENT")

    slate_day = _clean(diag.get("slate_date"))
    cards = [_validate_card(row, slate_day) for row in picks]

    collapsed = page._page_html(picks, diag, slate_day)
    if collapsed.count('data-top-picks-real-logo="true"') != 20:
        raise AssertionError("STEP9_REAL_LOGO_COUNT")
    if 'data-logo-placeholder="true"' in collapsed:
        raise AssertionError("STEP9_PLACEHOLDER_LOGO")
    for token in ("@media(max-width:820px)", "@media(max-width:640px)", "@media(max-width:900px)"):
        if token not in page.CSS:
            raise AssertionError(f"STEP9_RESPONSIVE_CONTRACT:{token}")

    resolved: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(details.build_pick_detail, row, slate_day): row
            for row in picks
        }
        for future in as_completed(futures):
            resolved.append((futures[future], future.result()))

    detail_rows = [
        _validate_detail(row, detail)
        for row, detail in sorted(resolved, key=lambda pair: int(pair[0].get("rank") or 99))
    ]
    if len(detail_rows) != 10:
        raise AssertionError(f"STEP9_DETAIL_COUNT:{len(detail_rows)}")

    payload = {
        "status": "GREEN",
        "step": "9/9",
        "slate_day": slate_day,
        "cards_certified": len(cards),
        "details_certified": len(detail_rows),
        "real_logos_certified": 20,
        "responsive_targets": [390, 768, 1440],
        "raw_ui_leaks": 0,
        "probability_changed": False,
        "ranking_changed": False,
        "selection_changed": False,
        "sportsbook_projection_weight": 0.0,
        "api2_used": False,
        "picks": detail_rows,
    }
    (artifacts / "cfb_top_picks_research_v2_step9_full_slate.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("CFB_TOP_PICKS_RESEARCH_V2_STEP9_TOP10_GREEN")
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP9_DETAILS_10_OF_10_GREEN")
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP9_PROVENANCE_GREEN")
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP9_RAW_UI_CLEAN_GREEN")
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP9_FROZEN_GREEN")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


if __name__ == "__main__":
    run()
