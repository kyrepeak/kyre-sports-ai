"""CFB Over/Under Clean Page V20 — Step 6 market-intelligence activation.

Additive presentation wrapper over certified Clean Page V19.

V20 activates the already-certified Step 5C market-intelligence layer only after
Market Adapter V2 has passed its freshness firewall and frozen V1 has attached a
line by exact official ESPN event ID. Market intelligence is display/context
only and has exactly 0.0 projection weight. Frozen Steps 3-12 projection math,
Schedule V5/V6 behavior, and Market Adapter V2 remain unchanged.
"""
from __future__ import annotations

from types import FunctionType, SimpleNamespace
from typing import Any, Callable, Mapping

import streamlit as st

import cfb_over_under_clean_page_v19 as frozen_page
import cfb_over_under_market_adapter_v2 as market_adapter_v2
import cfb_over_under_market_intelligence_v1 as market_intelligence

MODEL_VERSION = "CFB O/U CLEAN PAGE V20 • STEP 6 MARKET INTELLIGENCE LIVE"
MARKET = "Over/Under"
FROZEN_PAGE = "cfb_over_under_clean_page_v19"
ACTIVE_MARKET_ADAPTER = "cfb_over_under_market_adapter_v2"
ACTIVE_MARKET_INTELLIGENCE = "cfb_over_under_market_intelligence_v1"
ACTIVE_SCHEDULE = frozen_page.ACTIVE_SCHEDULE
FROZEN_RUNTIME_SLATE = frozen_page.FROZEN_RUNTIME_SLATE

_V19_MARKER = (
    "🟢 CFB O/U • CLEAN PAGE V19 ACTIVE • FRESHNESS FIREWALL ACTIVE • "
    "FROZEN PROJECTION MATH PRESERVED"
)
_V20_MARKER = (
    "🟢 CFB O/U • CLEAN PAGE V20 ACTIVE • STEP 6 MARKET INTELLIGENCE LIVE • "
    "DISPLAY ONLY • 0.0% PROJECTION INFLUENCE"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _certified_intelligence_item(item: Any, *, event_id: str) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise ValueError("unsafe_market_intelligence_item")
    if _clean(item.get("game_id")) != event_id:
        raise ValueError("unsafe_market_intelligence_event_id_mismatch")
    if float(item.get("projection_weight")) != 0.0:
        raise ValueError("unsafe_market_intelligence_projection_weight")
    if item.get("market_context_only") is not True:
        raise ValueError("unsafe_market_intelligence_not_context_only")
    if item.get("may_modify_projection") is not False:
        raise ValueError("unsafe_market_intelligence_may_modify_projection")
    providers = int(item.get("provider_count") or 0)
    consensus = item.get("consensus_available") is True
    state = _clean(item.get("market_state"))
    if providers < 1:
        raise ValueError("unsafe_market_intelligence_provider_count")
    if providers == 1 and (consensus or state != "SINGLE_BOOK"):
        raise ValueError("unsafe_single_book_consensus_claim")
    if providers >= 2 and not consensus:
        raise ValueError("unsafe_multibook_consensus_state")
    return dict(item)


def load_odds_for_date(target_date: Any, sportsbook: str = "FanDuel"):
    """Delegate the certified V2 market fetch/freshness path unchanged."""
    return market_adapter_v2.load_odds_for_date(target_date, sportsbook)


def attach_market_lines(
    games: list[Mapping[str, Any]],
    odds_payload: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Attach V2 lines, then add Step 5C display metadata by exact ESPN ID.

    Any Step 5C certification failure removes only the intelligence annotation.
    The V2 market attachment and every frozen projection input remain unchanged.
    """
    attached, base_diag = market_adapter_v2.attach_market_lines(games, odds_payload)
    out = [dict(game) for game in attached]
    diag = dict(base_diag or {})
    diag.update(
        {
            "market_intelligence_version": market_intelligence.MODEL_VERSION,
            "market_intelligence_status": "UNAVAILABLE",
            "market_intelligence_games": 0,
            "market_intelligence_error": "",
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        }
    )

    try:
        board = market_intelligence.build_market_intelligence(odds_payload)
        board_diag = board.get("diagnostics")
        if not isinstance(board_diag, Mapping):
            raise ValueError("unsafe_market_intelligence_diagnostics")
        if float(board_diag.get("projection_weight")) != 0.0:
            raise ValueError("unsafe_market_intelligence_projection_weight")
        if board_diag.get("market_context_only") is not True:
            raise ValueError("unsafe_market_intelligence_not_context_only")
        if board_diag.get("may_modify_projection") is not False:
            raise ValueError("unsafe_market_intelligence_may_modify_projection")
        if board_diag.get("official_event_id_only") is not True:
            raise ValueError("unsafe_market_intelligence_identity_policy")
        if board_diag.get("fuzzy_matching") is not False:
            raise ValueError("unsafe_market_intelligence_fuzzy_policy")
        if board_diag.get("synthetic_official_ids") is not False:
            raise ValueError("unsafe_market_intelligence_synthetic_id_policy")
        if board_diag.get("single_book_is_consensus") is not False:
            raise ValueError("unsafe_single_book_consensus_policy")

        intelligence_games = board.get("games")
        if not isinstance(intelligence_games, Mapping):
            raise ValueError("unsafe_market_intelligence_games")

        activated = 0
        for game in out:
            if game.get("market_line_available") is not True:
                continue
            if game.get("market_identity_verified") is not True:
                raise ValueError("unsafe_attached_market_identity")
            event_id = _clean(game.get("espn_event_id"))
            attached_id = _clean(game.get("market_official_game_id"))
            if not event_id or not event_id.isdigit() or attached_id != event_id:
                raise ValueError("unsafe_attached_official_event_id")
            item = intelligence_games.get(event_id)
            if item is None:
                raise ValueError("unsafe_missing_market_intelligence_event")
            game["market_intelligence"] = _certified_intelligence_item(
                item,
                event_id=event_id,
            )
            game["market_intelligence_status"] = "LIVE"
            activated += 1

        diag.update(
            {
                "market_intelligence_status": "LIVE",
                "market_intelligence_games": activated,
            }
        )
    except Exception as exc:
        for game in out:
            game.pop("market_intelligence", None)
            game["market_intelligence_status"] = "UNAVAILABLE"
        diag["market_intelligence_error"] = f"{type(exc).__name__}: {exc}"[:300]

    return out, diag


def market_line(game: Mapping[str, Any]) -> float | None:
    return market_adapter_v2.market_line(game)


def clear_market_cache() -> None:
    return market_adapter_v2.clear_market_cache()


_market_adapter_facade = SimpleNamespace(
    load_odds_for_date=load_odds_for_date,
    attach_market_lines=attach_market_lines,
    market_line=market_line,
    clear_market_cache=clear_market_cache,
)


class _StreamlitV20Proxy:
    """Delegate Streamlit while replacing only the V19 active-page marker."""

    def __getattr__(self, name: str) -> Any:
        return getattr(st, name)

    def caption(self, body: Any, *args: Any, **kwargs: Any) -> Any:
        text = str(body or "")
        if _V19_MARKER in text:
            body = _V20_MARKER
        return st.caption(body, *args, **kwargs)


def _clone_function(
    fn: Callable[..., Any],
    replacements: dict[str, Any],
) -> Callable[..., Any]:
    globals_copy = dict(fn.__globals__)
    globals_copy.update(replacements)
    cloned = FunctionType(
        fn.__code__,
        globals_copy,
        name=fn.__name__,
        argdefs=fn.__defaults__,
        closure=fn.__closure__,
    )
    cloned.__kwdefaults__ = getattr(fn, "__kwdefaults__", None)
    cloned.__doc__ = fn.__doc__
    return cloned


def _market_caption(
    game: Mapping[str, Any],
    market_diag: Mapping[str, Any],
) -> str:
    base = frozen_page._market_caption(game, market_diag)
    item = game.get("market_intelligence")
    if not isinstance(item, Mapping):
        if market_adapter_v2.market_line(game) is None:
            return base
        return (
            base
            + "<br>🟡 STEP 5C MARKET INTELLIGENCE UNAVAILABLE — fail-closed; "
            "display context only and projection influence remains <b>0.0%</b>."
        )

    event_id = _clean(item.get("game_id"))
    providers = int(item.get("provider_count") or 0)
    state = _clean(item.get("market_state"))
    reference = float(item.get("reference_total"))
    sportsbooks = item.get("sportsbooks") if isinstance(item.get("sportsbooks"), list) else []
    names = [
        _clean(row.get("sportsbook"))
        for row in sportsbooks
        if isinstance(row, Mapping) and _clean(row.get("sportsbook"))
    ]
    books = ", ".join(names) or "verified sportsbook"

    if providers == 1:
        label = "SINGLE-BOOK CONTEXT"
    else:
        label = f"{state} MULTI-BOOK CONTEXT"

    return (
        base
        + f"<br>🧠 STEP 5C MARKET INTELLIGENCE LIVE — <b>{label}</b> • "
        + f"reference <b>{reference:.1f}</b> • {books} • ESPN event {event_id} • "
        + "DISPLAY ONLY • projection influence <b>0.0%</b>"
    )


_line_board = _clone_function(
    frozen_page._line_board,
    {"market_adapter": _market_adapter_facade},
)
_RENDER_V20 = _clone_function(
    frozen_page._RENDER_V19,
    {
        "market_adapter": _market_adapter_facade,
        "_market_caption": _market_caption,
        "_line_board": _line_board,
        "st": _StreamlitV20Proxy(),
    },
)


def render_over_under_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    return _RENDER_V20(section_header, status_info, team_logo, h)


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Clean O/U Page V20 received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKET_ADAPTER",
    "ACTIVE_MARKET_INTELLIGENCE",
    "ACTIVE_SCHEDULE",
    "FROZEN_PAGE",
    "FROZEN_RUNTIME_SLATE",
    "MARKET",
    "MODEL_VERSION",
    "attach_market_lines",
    "load_odds_for_date",
    "market_line",
    "_line_board",
    "_market_caption",
    "render_cfb_hub",
    "render_over_under_hub",
]
