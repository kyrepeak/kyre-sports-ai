"""NFL Passing Yards V20 — Kyre Sports API automatic Step 10 market bridge.

Presentation/input-routing wrapper over certified V19. Steps 1–9 and the frozen
Step 10 evaluator remain unchanged. V20 captures the already-verified ESPN event
and QB athlete IDs, asks the Kyre Sports API for the fresh FanDuel Passing Yards
market, and pre-fills only Step 10's post-model comparison inputs.

The API never feeds projection/distribution math. If the endpoint is unavailable,
stale, malformed, missing the exact quarterback, or violates any permanent safety
contract, V20 falls back to the existing manual verified-market fields instead of
inventing a line or price.

Sportsbook projection influence remains 0.0%. Stake sizing remains OFF.
"""
from __future__ import annotations

import re
from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v11 as step10_ui
import nfl_passing_yards_hub_v19 as prior
import nfl_passing_yards_hub_v8 as step7_ui
import nfl_passing_yards_market_api_v1 as market_api

MODEL_VERSION = "NFL PASSING YARDS V20 • KYRE SPORTS API AUTO MARKET • EXACT ESPN IDS"
FROZEN_PRIOR = "nfl_passing_yards_hub_v19"

_API_CSS = r"""
<style>
.kpy20-api{border:1px solid #2e7658;background:linear-gradient(135deg,#071c15,#0a2a20);border-radius:13px;padding:9px 11px;margin:4px 0 9px;color:#dff8ec}
.kpy20-api b{color:#7ff2bd;font-size:.76rem}.kpy20-api span{display:block;color:#8fa9a0;font-size:.49rem;line-height:1.5;margin-top:3px}
</style>
"""

_STEP10_KEY = re.compile(r"^kpy10_(\d+)_.*_(source|line|over|under|timestamp)$")
_MANUAL_INFO_PREFIX = "Enter the current passing-yards prop exactly as shown by the sportsbook."


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _qb_athlete_ids(identity_result: dict) -> list[str]:
    ids: list[str] = []
    for side in ("away", "home"):
        ctx = (identity_result or {}).get(side) or {}
        qb = ctx.get("qb1") or {}
        athlete_id = _safe(qb.get("athlete_id"))
        ids.append(athlete_id if athlete_id.isdigit() else "")
    return ids


def _api_value(row: dict, field: str) -> str:
    if field == "source":
        return f"Kyre Sports API • {_safe(row.get('sportsbook'),'FanDuel')}"
    if field == "line":
        try:
            return f"{float(row.get('line')):g}"
        except Exception:
            return ""
    if field == "over":
        try:
            return str(int(float(row.get("over_odds"))))
        except Exception:
            return ""
    if field == "under":
        try:
            return str(int(float(row.get("under_odds"))))
        except Exception:
            return ""
    if field == "timestamp":
        return _safe(row.get("captured_at_utc"))
    return ""


def _ensure_event_market(context: dict) -> dict:
    if context.get("api_attempted"):
        return context.get("event_market") or {}
    context["api_attempted"] = True
    event_id = _safe(context.get("event_id"))
    if not event_id.isdigit():
        context["event_market"] = {
            "ready": False,
            "reason": "verified ESPN event ID was not captured before Step 10",
            "projection_weight": 0.0,
        }
        return context["event_market"]
    context["event_market"] = market_api.fetch_event_market(event_id)
    return context["event_market"]


def _market_row_for_index(context: dict, index: int) -> dict:
    event_market = _ensure_event_market(context)
    athlete_ids = list(context.get("athlete_ids") or [])
    athlete_id = athlete_ids[index] if 0 <= index < len(athlete_ids) else ""
    row = market_api.market_for_athlete(event_market, athlete_id)
    context.setdefault("athlete_markets", {})[index] = row
    return row


class _Step10StreamlitProxy:
    """Intercept only V11 Step 10 inputs; all other Streamlit calls pass through."""

    def __init__(self, wrapped: Any, context: dict) -> None:
        self._wrapped = wrapped
        self._context = context

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)

    def info(self, body: Any, *args, **kwargs):
        text = _safe(body)
        if text.startswith(_MANUAL_INFO_PREFIX):
            return self._wrapped.info(
                "Kyre Sports API is the primary Step 10 market source. Fresh FanDuel Passing Yards lines and both prices auto-load only when the official ESPN event ID and QB athlete ID match exactly. If the API is unavailable, stale, or missing that exact player, the original manual verified-market fields remain available; no fallback line or price is invented.",
                *args,
                **kwargs,
            )
        return self._wrapped.info(body, *args, **kwargs)

    def text_input(self, label: str, value: str = "", *args, **kwargs):
        key = _safe(kwargs.get("key"))
        match = _STEP10_KEY.match(key)
        if not match:
            return self._wrapped.text_input(label, value=value, *args, **kwargs)

        index = int(match.group(1))
        field = match.group(2)
        row = _market_row_for_index(self._context, index)
        marker = f"_kpy20_api_autofill_{key}"

        if row.get("ready"):
            api_value = _api_value(row, field)
            if api_value:
                # Replace any previous manual/stale value before this widget is
                # instantiated on the current rerun. The disabled widget makes
                # the live API origin visible without allowing accidental edits.
                self._wrapped.session_state[key] = api_value
                self._wrapped.session_state[marker] = True
                call_kwargs = dict(kwargs)
                call_kwargs["disabled"] = True
                call_kwargs["help"] = "Auto-filled from a fresh exact-ID Kyre Sports API / FanDuel market. Projection influence remains 0.0%."
                return self._wrapped.text_input(label, *args, **call_kwargs)

        # If a prior rerun auto-filled this key but the API is no longer fresh,
        # clear it before restoring the certified manual fail-closed fallback.
        if self._wrapped.session_state.get(marker):
            self._wrapped.session_state.pop(key, None)
            self._wrapped.session_state.pop(marker, None)
        return self._wrapped.text_input(label, value=value, *args, **kwargs)


def render_nfl_passing_yards_hub() -> None:
    st.markdown(_API_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="kpy20-api"><b>🔌 KYRE SPORTS API BRIDGE — STEP 10 AUTO MARKET</b>'
        '<span>Exact ESPN event + QB athlete IDs only • fresh FanDuel Passing Yards line/O-U prices • post-model context only • projection influence 0.0% • manual verified fallback stays fail-closed.</span></div>',
        unsafe_allow_html=True,
    )

    context: dict[str, Any] = {
        "event_id": "",
        "athlete_ids": [],
        "api_attempted": False,
        "event_market": {},
        "athlete_markets": {},
    }

    original_identity_builder = step7_ui.identity.resolve_matchup_identity
    original_step10_st = step10_ui.st

    def capture_identity(*args, **kwargs):
        result = original_identity_builder(*args, **kwargs)
        game = args[0] if args else kwargs.get("game") or {}
        event_id = _safe((game or {}).get("game_id"))
        context["event_id"] = event_id if event_id.isdigit() else ""
        context["athlete_ids"] = _qb_athlete_ids(result or {})
        return result

    step7_ui.identity.resolve_matchup_identity = capture_identity
    step10_ui.st = _Step10StreamlitProxy(original_step10_st, context)
    try:
        prior.render_nfl_passing_yards_hub()
    finally:
        step7_ui.identity.resolve_matchup_identity = original_identity_builder
        step10_ui.st = original_step10_st

    if context.get("api_attempted"):
        event_market = context.get("event_market") or {}
        ready_rows = [row for row in (context.get("athlete_markets") or {}).values() if row.get("ready")]
        if event_market.get("ready") and ready_rows:
            age = event_market.get("age_seconds")
            age_text = f"{float(age):.0f}s old" if isinstance(age, (int, float)) else "fresh"
            st.success(
                f"✅ KYRE SPORTS API MARKET GREEN • event {context.get('event_id')} • {len(ready_rows)} exact QB market(s) auto-loaded • FanDuel snapshot {age_text} • sportsbook projection influence 0.0%."
            )
        else:
            st.warning(
                "⚠️ KYRE SPORTS API MARKET CHECK • "
                + _safe(event_market.get("reason"), "fresh exact-ID market unavailable")
                + " • Step 10 stayed fail-closed and kept the manual verified-market fallback."
            )

    st.caption(
        f"{MODEL_VERSION} • V19 model/source protections preserved • Kyre Sports API affects Step 10 market fields only • sportsbook projection influence = 0.0% • stake sizing OFF"
    )


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "_Step10StreamlitProxy",
    "_api_value",
    "_qb_athlete_ids",
    "render_nfl_passing_yards_hub",
]
