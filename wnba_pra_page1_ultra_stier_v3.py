"""MONSTER WNBA PRA Page 1 V3 — stale final-card eligibility guard.

Presentation successor only.  A certified/final pick may render only when its
exact player + line remains present in the already-filtered current Page 1 rows.
That makes the upstream upcoming-games-only schedule gate authoritative for the
leaderboard, discovery cards, and the bottom certified-pick section alike.
"""
from __future__ import annotations

from typing import Any, Mapping

import wnba_pra_page1_ultra_stier_v2 as previous

MODEL_VERSION = "MONSTER WNBA PRA PAGE1 ULTRA STIER V3 • UPCOMING-ONLY FINAL CARD"
_ORIGINAL_FINAL_SECTION_HTML = previous._final_section_html


def _key(player: Any, line: Any) -> tuple[str, float] | None:
    name = str(player or "").strip()
    value = previous._finite(line)
    if not name or value is None:
        return None
    return name, value


def _eligible_final_cards(
    finals: list[Mapping[str, Any]],
    rows: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    eligible = {
        key
        for row in rows
        if (key := _key(row.get("player_name"), row.get("line"))) is not None
    }
    kept: list[dict[str, Any]] = []
    for card in finals:
        if not isinstance(card, Mapping):
            continue
        key = _key(card.get("player_name") or card.get("player"), card.get("line"))
        if key is not None and key in eligible:
            kept.append(dict(card))
    return kept


def _final_section_html(
    finals: list[Mapping[str, Any]],
    rows: list[Mapping[str, Any]],
) -> str:
    return _ORIGINAL_FINAL_SECTION_HTML(_eligible_final_cards(finals, rows), rows)


def install() -> dict[str, Any]:
    previous._final_section_html = _final_section_html
    return {
        "model_version": MODEL_VERSION,
        "authority": "MONSTER_ONLY",
        "rule": "FINAL_CARD_REQUIRES_CURRENT_ELIGIBLE_ROW",
        "live_or_final_game_card_allowed": False,
    }


install()
render_page_snapshot = previous.render_page_snapshot

__all__ = [
    "MODEL_VERSION",
    "_eligible_final_cards",
    "_final_section_html",
    "install",
    "render_page_snapshot",
]
