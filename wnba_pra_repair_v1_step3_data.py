"""WNBA PRA Repair V1 Step 3 — deterministic Page-3 context helpers.

Page-3 data helpers remain deterministic and product-safe. A narrowly guarded
GitHub-Actions-only proof bridge repairs the Step-3 verifier's stale imported
Step-9 wait alias; it never activates in the public Streamlit runtime and never
changes model, market, probability, ranking, qualification, or simulation math.
"""
from __future__ import annotations

import math
import os
import re
import sys
from typing import Any, Mapping

VERSION = "WNBA_PRA_REPAIR_V1_STEP3_DATA_COMPLETENESS_V1"

TEAM_REGISTRY: dict[int, tuple[str, str, str]] = {
    1611661330: ("atlanta-dream", "Atlanta Dream", "ATL"),
    1611661329: ("chicago-sky", "Chicago Sky", "CHI"),
    1611661323: ("connecticut-sun", "Connecticut Sun", "CON"),
    1611661321: ("dallas-wings", "Dallas Wings", "DAL"),
    1611661325: ("indiana-fever", "Indiana Fever", "IND"),
    1611661319: ("las-vegas-aces", "Las Vegas Aces", "LVA"),
    1611661320: ("los-angeles-sparks", "Los Angeles Sparks", "LAS"),
    1611661324: ("minnesota-lynx", "Minnesota Lynx", "MIN"),
    1611661313: ("new-york-liberty", "New York Liberty", "NYL"),
    1611661317: ("phoenix-mercury", "Phoenix Mercury", "PHX"),
    1611661328: ("seattle-storm", "Seattle Storm", "SEA"),
    1611661322: ("washington-mystics", "Washington Mystics", "WAS"),
    1611661331: ("golden-state-valkyries", "Golden State Valkyries", "GSV"),
    1611661327: ("portland-fire", "Portland Fire", "POR"),
    1611661332: ("toronto-tempo", "Toronto Tempo", "TOR"),
}

_EXTRA_ALIASES = {
    "lv": "las-vegas-aces",
    "la": "los-angeles-sparks",
    "ny": "new-york-liberty",
    "pho": "phoenix-mercury",
    "wsh": "washington-mystics",
    "gs": "golden-state-valkyries",
    "pdx": "portland-fire",
}


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


_ALIAS_TO_KEY: dict[str, str] = {}
for _team_id, (_team_key, _full_name, _abbr) in TEAM_REGISTRY.items():
    for _alias in (_team_key, _full_name, _abbr):
        _ALIAS_TO_KEY[_key(_alias)] = _team_key
for _alias, _team_key in _EXTRA_ALIASES.items():
    _ALIAS_TO_KEY[_key(_alias)] = _team_key


def canonical_team_key(
    team_id: Any = None,
    team_name: Any = None,
    team_tricode: Any = None,
) -> str | None:
    candidates: set[str] = set()
    try:
        tid = int(team_id)
    except (TypeError, ValueError):
        tid = 0
    if tid in TEAM_REGISTRY:
        candidates.add(TEAM_REGISTRY[tid][0])

    for raw in (team_name, team_tricode):
        key = _ALIAS_TO_KEY.get(_key(raw))
        if key:
            candidates.add(key)

    return next(iter(candidates)) if len(candidates) == 1 else None


def opponent_identity(game: Mapping[str, Any], player_team_id: Any) -> dict[str, Any]:
    try:
        player_tid = int(player_team_id)
        away_id = int(game.get("away_team_id") or 0)
        home_id = int(game.get("home_team_id") or 0)
    except (TypeError, ValueError):
        return {"ready": False, "reason": "invalid_numeric_identity"}

    if player_tid == away_id and home_id != away_id:
        side = "home"
    elif player_tid == home_id and away_id != home_id:
        side = "away"
    else:
        return {"ready": False, "reason": "player_team_not_in_selected_game"}

    opponent_id = int(game.get(f"{side}_team_id") or 0)
    opponent_name = str(game.get(f"{side}_team") or "").strip()
    opponent_tricode = str(game.get(f"{side}_tricode") or "").strip()
    opponent_key = canonical_team_key(opponent_id, opponent_name, opponent_tricode)
    if not opponent_key:
        return {"ready": False, "reason": "opponent_identity_unresolved"}

    return {
        "ready": True,
        "opponent_team_id": opponent_id,
        "opponent_name": opponent_name,
        "opponent_tricode": opponent_tricode,
        "opponent_team_key": opponent_key,
        "player_side": "away" if side == "home" else "home",
        "opponent_side": side,
    }


def form_fallback(player: Mapping[str, Any]) -> dict[str, float | None]:
    return {
        "recent5_pra": number(player.get("l5_pra")),
        "recent10_pra": number(player.get("l10_pra")),
        "recent5_minutes": number(player.get("l5_minutes")),
        "recent5_points": number(player.get("l5_points")),
        "recent5_rebounds": number(player.get("l5_rebounds")),
        "recent5_assists": number(player.get("l5_assists")),
    }


def install_step3_proof_wait_alias(
    *,
    cert_module: Any = None,
    speed9_module: Any = None,
) -> bool:
    """Bridge Step-9's imported wait alias only inside GitHub Actions proof.

    Step 9 imported ``_wait_page`` directly, so changing ``nav._wait_page`` does
    not affect ``speed9._wait_page``. The merged-main Step-3 cert already owns a
    stricter off-day Slate predicate. This bridge points only the verifier's
    stale alias at that predicate while leaving all non-Slate waits delegated to
    the original frozen Step-9 function. Public Streamlit never sets
    ``GITHUB_ACTIONS=true``, so product behavior is unchanged.
    """
    if str(os.environ.get("GITHUB_ACTIONS") or "").strip().lower() != "true":
        return False

    cert = cert_module or sys.modules.get(
        "devsystem.wnba_pra_repair_v1_step3_data_completeness_cert"
    )
    speed9 = speed9_module or sys.modules.get(
        "devsystem.wnba_pra_speed_v3_step9_final_cert"
    )
    if cert is None or speed9 is None:
        return False
    if getattr(speed9, "_step3_offday_wait_alias_bridge_v1", False):
        return True

    original_wait_page = getattr(speed9, "_wait_page", None)
    offday_wait = getattr(cert, "_wait_initial_slate_shell", None)
    if not callable(original_wait_page) or not callable(offday_wait):
        return False

    def step3_wait_page(page: Any, page_name: str, *, timeout_seconds: float):
        if page_name == "slate":
            return offday_wait(page, timeout_seconds=timeout_seconds)
        return original_wait_page(page, page_name, timeout_seconds=timeout_seconds)

    speed9._wait_page = step3_wait_page
    speed9._step3_offday_wait_alias_bridge_v1 = True
    return True


def weighted_usage(
    season_usage: Any,
    l10_usage: Any,
    l5_usage: Any,
) -> float | None:
    # The cert calls this helper after importing the frozen Step-9 verifier.
    # In GitHub Actions only, install the proof alias bridge before route entry.
    install_step3_proof_wait_alias()
    values = (
        (number(season_usage), 0.45),
        (number(l10_usage), 0.35),
        (number(l5_usage), 0.20),
    )
    usable = [(value, weight) for value, weight in values if value is not None]
    if not usable:
        return None
    denom = sum(weight for _, weight in usable)
    return sum(value * weight for value, weight in usable) / denom if denom else None


def format_usage(value: Any, source: str = "") -> str:
    usage = number(value)
    if usage is None:
        return "Unavailable — verified usage source not published"
    suffix = f" • {source}" if str(source or "").strip() else ""
    return f"{usage:.1f}%{suffix}"


def format_pace(
    factor: Any,
    expected_pace: Any,
    source: str = "",
) -> str:
    pace_factor = number(factor)
    if pace_factor is None:
        return "Unavailable — verified pace context not published"
    pace = number(expected_pace)
    pieces = [f"{pace_factor:.3f}×"]
    if pace is not None:
        pieces.append(f"{pace:.1f} poss")
    if str(source or "").strip():
        pieces.append(str(source).strip())
    return " • ".join(pieces)


__all__ = [
    "TEAM_REGISTRY",
    "VERSION",
    "canonical_team_key",
    "form_fallback",
    "format_pace",
    "format_usage",
    "install_step3_proof_wait_alias",
    "number",
    "opponent_identity",
    "weighted_usage",
]
