"""MLB H+R+RBI V1.0.9 — Step-4 pitch-usage validation hotfix.

Presentation-only wrapper around verified H+R+RBI V1.0.8 Steps 1-6.

The Step-4 Statcast arsenal display previously trusted an ambiguous Savant usage
column before pitch counts. On some pitchers that produced impossible top-pitch
shares whose sum exceeded 100% (for example 90% + 48% + 27%). V1.0.9 repairs
only that display seam:
- prefer Statcast pitch counts and calculate each pitch's share of ALL pitcher
  pitches in the selected season,
- de-duplicate pitch-type rows before calculating the denominator,
- when counts are unavailable, validate/normalize the reported usage weights so
  the full arsenal cannot exceed 100%,
- retain the same batter pitch-type xBA/xSLG join and Step-4 matchup grade.

No H/R/RBI component rate, candidate pool, lineup rule, Monte Carlo simulation,
threshold probability, ranking, confidence, fair odds, Step-5 environment value,
or Step-6 opportunity value is changed.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import mlb_hrrbi_hub_v108 as prior
import mlb_hrrbi_hub_v106 as step4

MODEL_VERSION = "H+R+RBI V1.0.9"
base = prior.base
core = prior.core


def _validated_pitch_type_matchup(result):
    """Return Step-4 pitch rows with mathematically valid arsenal usage shares."""
    year = step4._selected_season()
    pitcher_id = step4._safe_id(result.get("starter_id"))
    batter_id = step4._safe_id(result.get("player_id"))

    pitcher_rows = step4._savant_rows_for_player(
        step4._savant_arsenal_table("pitcher", year), pitcher_id
    )
    batter_rows = step4._savant_rows_for_player(
        step4._savant_arsenal_table("batter", year), batter_id
    )
    if pitcher_rows.empty:
        return []

    pitch_col = step4._col(pitcher_rows, ["pitch_type", "pitch type"])
    name_col = step4._col(pitcher_rows, ["pitch_name", "pitch name", "pitch"])
    pitches_col = step4._col(pitcher_rows, ["pitches", "pitch_count", "pitch count"])
    usage_col = step4._col(
        pitcher_rows,
        ["pitch_usage", "pitch_usage_pct", "usage", "usage_pct", "%"],
    )
    if pitch_col is None:
        return []

    work = pitcher_rows.copy()
    work["__code"] = work[pitch_col].astype(str).str.strip().str.upper()
    work = work[work["__code"].ne("") & work["__code"].ne("NAN")].copy()
    if work.empty:
        return []

    # Savant tables can occasionally contain repeated pitch-type rows. Keep the
    # row with the largest pitch sample before deriving the full-arsenal share.
    if pitches_col is not None:
        work["__pitches"] = pd.to_numeric(work[pitches_col], errors="coerce").fillna(0.0)
        work = work.sort_values("__pitches", ascending=False).drop_duplicates("__code", keep="first")
    else:
        work = work.drop_duplicates("__code", keep="first")
        work["__pitches"] = 0.0

    total_pitches = float(work["__pitches"].clip(lower=0).sum())
    if total_pitches > 0:
        work["__usage"] = 100.0 * work["__pitches"].clip(lower=0) / total_pitches
        usage_source = "pitch counts"
    elif usage_col is not None:
        raw = pd.to_numeric(work[usage_col], errors="coerce").fillna(0.0).clip(lower=0)
        if len(raw) and float(raw.max()) <= 1.001:
            raw = raw * 100.0
        raw_sum = float(raw.sum())
        # If the provider's reported values are not already a valid percentage
        # distribution, treat them only as relative weights and normalize once.
        if raw_sum > 105.0 or (len(raw) and float(raw.max()) > 100.0):
            work["__usage"] = 100.0 * raw / raw_sum if raw_sum > 0 else 0.0
            usage_source = "normalized usage weights"
        else:
            work["__usage"] = raw
            usage_source = "reported usage"
    else:
        work["__usage"] = -1.0
        usage_source = "unavailable"

    work = work.sort_values("__usage", ascending=False).head(3)
    batter_pitch_col = step4._col(batter_rows, ["pitch_type", "pitch type"])
    batter_pa_col = step4._col(batter_rows, ["pa", "PA"])

    out = []
    for _, prow in work.iterrows():
        code = str(prow.get("__code") or "").upper()
        pitch_name = step4._row_text(prow, [name_col] if name_col else [], code or "Pitch")
        usage_value = step4._row_num(prow, ["__usage"], None)

        brow = None
        if code and batter_pitch_col is not None and not batter_rows.empty:
            matched = batter_rows[
                batter_rows[batter_pitch_col].astype(str).str.strip().str.upper() == code
            ].copy()
            if not matched.empty:
                if batter_pa_col is not None:
                    matched["__pa"] = pd.to_numeric(matched[batter_pa_col], errors="coerce").fillna(0)
                    matched = matched.sort_values("__pa", ascending=False)
                brow = matched.iloc[0]

        out.append(
            {
                "code": code,
                "name": pitch_name,
                "usage": usage_value,
                "usage_source": usage_source,
                "batter_pa": step4._to_int(step4._row_num(brow, ["pa", "PA"], 0)) if brow is not None else 0,
                "batter_xba": step4._row_num(brow, ["est_ba", "xBA", "xba"], None) if brow is not None else None,
                "batter_xslg": step4._row_num(brow, ["est_slg", "xSLG", "xslg"], None) if brow is not None else None,
                "batter_ba": step4._row_num(brow, ["ba", "BA", "avg"], None) if brow is not None else None,
            }
        )

    # Final display invariant: a top-N subset of an arsenal may never exceed 100%.
    valid = [float(x["usage"]) for x in out if x.get("usage") is not None and float(x["usage"]) >= 0]
    if valid and sum(valid) > 100.05:
        denom = sum(valid)
        for row in out:
            if row.get("usage") is not None and float(row["usage"]) >= 0:
                row["usage"] = 100.0 * float(row["usage"]) / denom
                row["usage_source"] = "validated normalized shares"
    return out


# Repair only the Step-4 display helper. The existing Step-4 renderer resolves
# this global at card-render time, so Steps 1-6 remain byte-for-byte otherwise.
step4._pitch_type_matchup = _validated_pitch_type_matchup


def render_hrrbi_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(
        '<div style="display:inline-flex;border:1px solid #315b74;background:#081b29;color:#8ed8ff;border-radius:999px;padding:5px 8px;font-size:.52rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin:0 0 9px">'
        '🧮 H+R+RBI V1.0.9 • Steps 1–6 active • validated Statcast pitch shares'
        '</div>',
        unsafe_allow_html=True,
    )
    return prior.render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
