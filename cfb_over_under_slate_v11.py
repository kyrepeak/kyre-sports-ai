"""CFB Over/Under Slate V11 — Upgrade Step 12 final certification.

Read-only wrapper over permanently frozen Step 11. No model or selection math
changes. Each result receives a Step-12 integrity certificate; raw/final numeric
outputs remain exactly inherited from Step 11.
"""
from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

import cfb_over_under_certification_v1 as certifier
import cfb_over_under_slate_v10 as frozen

MODEL_VERSION = "CFB OVER/UNDER SLATE V11 • UPGRADE STEP 12 FINAL CERTIFICATION"
FROZEN_SLATE = "cfb_over_under_slate_v10"
MAX_WORKERS = frozen.MAX_WORKERS


def _attach_certificate(base: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(base)
    certificate = certifier.certify_result(result)

    raw = dict(result.get("raw") or {})
    raw["upgrade_step12_certification"] = dict(certificate)
    raw["upgrade_step12_certified"] = bool(certificate.get("certified"))
    raw["upgrade_step12_integrity_passed"] = bool(certificate.get("integrity_passed"))

    result.update({
        "version": MODEL_VERSION,
        "raw": raw,
        "certification": dict(certificate),
        "step11_raw": dict(base.get("raw") or {}),
        "step12_projection_math_changed": False,
        "step12_selection_math_changed": False,
    })
    return result


@st.cache_data(ttl=120, show_spinner=False)
def analyze_game(
    game: Mapping[str, Any],
    as_of_day: str,
    analysis_line: float,
) -> dict[str, Any]:
    base = frozen.analyze_game(game, as_of_day, float(analysis_line))
    return _attach_certificate(base)


def scan_slate(
    games: list[Mapping[str, Any]],
    as_of_day: str,
    analysis_lines: Mapping[str, Any],
    workers: int = MAX_WORKERS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base_rows, base_diag = frozen.scan_slate(
        games,
        as_of_day,
        analysis_lines,
        workers=workers,
    )
    rows = [_attach_certificate(row) for row in base_rows]

    certified = sum(
        (row.get("certification") or {}).get("status") == "CERTIFIED"
        for row in rows
    )
    data_gated = sum(
        (row.get("certification") or {}).get("status") == "DATA_GATED"
        for row in rows
    )
    integrity_failed = sum(
        (row.get("certification") or {}).get("status") == "INTEGRITY_FAIL"
        for row in rows
    )

    diag = dict(base_diag)
    diag.update({
        "version": MODEL_VERSION,
        "step12_certified_games": int(certified),
        "step12_data_gated_games": int(data_gated),
        "step12_integrity_failed_games": int(integrity_failed),
        "step12_integrity_pass_rate": (
            sum(bool((row.get("certification") or {}).get("integrity_passed")) for row in rows)
            / len(rows)
            if rows else 0.0
        ),
        "step12_projection_math_changed": False,
        "step12_selection_math_changed": False,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
    })
    return rows, diag


def clear_scan_cache() -> None:
    try:
        analyze_game.clear()
    except Exception:
        pass


__all__ = [
    "FROZEN_SLATE",
    "MAX_WORKERS",
    "MODEL_VERSION",
    "_attach_certificate",
    "analyze_game",
    "clear_scan_cache",
    "scan_slate",
]
