"""WNBA Rebounds V3.1.2 — Step-18 verified-player market reconciliation.

Preserves the complete V3.1.1 visual layer, V3.0 Production Readiness Guard,
Steps 1–20 model/market math, Monte Carlo, qualification and Daily Picks payload.

Root-cause repair:
Step 13 intentionally retains every SportsGameOdds rebound quote on matched slate
events. Step 14 can successfully de-vig a paired quote before its provider player
identity is reconciled to the verified current-player frame. Such an orphan row
may therefore carry ``No-vig state == VERIFIED`` while Player/Team are blank.
V2.7 Step 18 previously evaluated every VERIFIED no-vig row and required a
Step-17 model/PMF join for each one, so one orphan provider quote could lock the
entire otherwise-verified 61-player slate.

V3.1.2 changes only the Step-18 input reconciliation:
- evaluate only Step-14 quote rows whose exact normalized Player+Team identity is
  present in the VERIFIED Step-14 player frame;
- keep all original Step-14 quote rows untouched for display/audit and the V3.0
  freshness guard;
- record excluded provider-only rows in a read-only audit;
- fail closed if no verified-player market rows remain.

No rebound projection, PMF, 5M Monte Carlo, line probability, fair odds, EV,
ranking, qualification, quote freshness, or production guard formula changes.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v311 as base
import wnba_rebounds_hub_v27 as step18

MODEL_VERSION = (
    "WNBA REBOUNDS V3.1.2 • STEP-18 VERIFIED-PLAYER MARKET RECONCILIATION "
    "• V3.1.1 MODEL/VISUALS PRESERVED"
)

_ORIGINAL_STEP18_BUILDER = step18._build_step18
_AUDIT_KEY = "wnba_rebounds_step18_identity_reconciliation_v312"


def _frame(value) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, (list, tuple)):
        try:
            return pd.DataFrame(list(value))
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def _verified_player_keys(players14: pd.DataFrame) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    if players14 is None or players14.empty:
        return keys
    for _, row in players14.iterrows():
        if str(row.get("Step14 state") or "") != "VERIFIED":
            continue
        key = step18._key(row.get("Player"), row.get("Team"))
        if key[0] and key[1]:
            keys.add(key)
    return keys


def _reconcile_quotes():
    players14 = _frame(st.session_state.get("wnba_rebounds_step14_players"))
    quotes14 = _frame(st.session_state.get("wnba_rebounds_step14_quotes"))
    verified_keys = _verified_player_keys(players14)

    if quotes14.empty:
        return quotes14, pd.DataFrame(), {
            "raw_quote_rows": 0,
            "verified_player_keys": len(verified_keys),
            "eligible_quote_rows": 0,
            "excluded_quote_rows": 0,
            "excluded_verified_novig_rows": 0,
        }

    mask = quotes14.apply(
        lambda row: step18._key(row.get("Player"), row.get("Team")) in verified_keys,
        axis=1,
    )
    eligible = quotes14.loc[mask].copy()
    excluded = quotes14.loc[~mask].copy()

    excluded_verified = 0
    if not excluded.empty and "No-vig state" in excluded.columns:
        excluded_verified = int(
            excluded["No-vig state"].astype(str).str.upper().eq("VERIFIED").sum()
        )

    return eligible, excluded, {
        "raw_quote_rows": int(len(quotes14)),
        "verified_player_keys": int(len(verified_keys)),
        "eligible_quote_rows": int(len(eligible)),
        "excluded_quote_rows": int(len(excluded)),
        "excluded_verified_novig_rows": excluded_verified,
    }


def _build_step18_reconciled():
    raw_state = st.session_state.get("wnba_rebounds_step14_quotes")
    eligible, excluded, diag = _reconcile_quotes()

    # Step 18 is allowed to consume only verified-player market rows. Restore the
    # exact original Step-14 payload immediately after the inherited builder so
    # Step-14 display and V3.0 quote-freshness reconciliation stay unchanged.
    st.session_state["wnba_rebounds_step14_quotes"] = (
        eligible.to_dict("records") if not eligible.empty else []
    )
    try:
        players18, lines18, info = _ORIGINAL_STEP18_BUILDER()
    finally:
        st.session_state["wnba_rebounds_step14_quotes"] = raw_state

    audit_cols = [
        c for c in (
            "Event ID", "SportsGameOdds Player ID", "Provider player",
            "Player", "Team", "Opponent", "Book", "Bookmaker ID", "Line",
            "No-vig state",
        ) if c in excluded.columns
    ]
    audit_rows = excluded[audit_cols].copy() if audit_cols else excluded.copy()
    if not audit_rows.empty:
        audit_rows["Exclusion reason"] = (
            "NO EXACT VERIFIED STEP-14 PLAYER+TEAM IDENTITY"
        )

    diag = {
        **diag,
        "step18_ready_after_reconciliation": bool(info.get("ready")),
        "step18_player_states": int(info.get("player_states", 0) or 0),
        "step18_players": int(info.get("players", 0) or 0),
        "step18_verified_lines": int(info.get("covered_markets", 0) or 0),
        "step18_line_rows": int(info.get("market_rows", 0) or 0),
    }
    st.session_state[_AUDIT_KEY] = {
        "diag": diag,
        "excluded": audit_rows.to_dict("records") if not audit_rows.empty else [],
    }
    return players18, lines18, info


def _render_reconciliation_audit():
    raw = st.session_state.get(_AUDIT_KEY)
    payload = dict(raw) if isinstance(raw, dict) else {}
    diag = dict(payload.get("diag") or {})
    excluded = _frame(payload.get("excluded"))

    with st.expander("🧩 Step-18 verified-player market reconciliation", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Step-14 raw quotes", int(diag.get("raw_quote_rows", 0)))
        c2.metric("Step-18 eligible quotes", int(diag.get("eligible_quote_rows", 0)))
        c3.metric("Provider-only excluded", int(diag.get("excluded_quote_rows", 0)))
        c4.metric(
            "Excluded VERIFIED no-vig",
            int(diag.get("excluded_verified_novig_rows", 0)),
        )

        st.caption(
            "Only exact Player+Team identities already VERIFIED by Step 14 may "
            "enter Step 18. Excluded provider-only rows remain untouched in the "
            "Step-14 source payload and can never create or change a projection."
        )
        if excluded.empty:
            st.success("✅ No provider-only Step-14 quote rows required exclusion.")
        else:
            st.warning(
                "⚠️ Provider quote row(s) without an exact verified current-player "
                "identity were excluded from Step-18 probability evaluation instead "
                "of deadlocking every valid player."
            )
            st.dataframe(excluded, use_container_width=True, hide_index=True)

        p = int(diag.get("step18_player_states", 0))
        pt = int(diag.get("step18_players", 0))
        l = int(diag.get("step18_verified_lines", 0))
        lt = int(diag.get("step18_line_rows", 0))
        st.write(
            f"Step-18 reconciliation result: player states {p}/{pt} • "
            f"line probabilities {l}/{lt} • "
            f"ready={bool(diag.get('step18_ready_after_reconciliation'))}"
        )
        st.write("Projection / PMF / 5M / probability / fair-odds math changes: 0")


def render_wnba_rebounds_hub(*args, **kwargs):
    # v28/v29/v30/v31 resolve the V2.7 builder through this shared module object,
    # so one bounded temporary patch repairs Step 18 without copying the model.
    original = step18._build_step18
    step18._build_step18 = _build_step18_reconciled
    try:
        st.caption(
            "🛡️ Rebounds V3.1.2 • Step-18 verified-player market reconciliation ACTIVE "
            "• Steps 1–17 + Step-18 math + Steps 19–20/production guard preserved"
        )
        out = base.render_wnba_rebounds_hub(*args, **kwargs)
    finally:
        step18._build_step18 = original

    _render_reconciliation_audit()
    return out


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
