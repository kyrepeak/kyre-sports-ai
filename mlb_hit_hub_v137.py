"""MLB 1+ Hit UI V13.7 — Step 4 pitch-mix + platoon matchup context.

Presentation/context-only wrapper around the verified V13.6/V13.5/V13.4/V13.3
Top-5 scanner. Hit Model V13 probability math, Monte Carlo, full-slate candidate
pool, lineup handling, ranking, calibration and persistence are unchanged.

Step 4 adds four display-only matchup layers to each Top-5 card:
1) batter season platoon split versus the verified starter hand (MLB Stats),
2) pitcher split versus the batter's effective side (MLB Stats),
3) pitcher xERA when Baseball Savant publishes it, with MLB FIP only if actually
   supplied (never synthesized), and
4) a direct pitch-type join between the current starter's dominant Statcast arsenal
   and the batter's Statcast outcomes against those same pitch types.

All network data are cached and fail closed to an explicit unavailable label. No
Step-4 field is passed into prescreen, deep_scan, model_inputs, Monte Carlo,
confidence, calibration or ranking.
"""
from __future__ import annotations

from html import escape
from io import StringIO

import pandas as pd
import requests
import streamlit as st

import mlb_hit_hub_v136 as prior

active = prior.active
core = prior.core
visual = prior.visual
pitcher_ui = prior.prior  # V13.5 owns the verified opposing-starter profile/strip.

UI_VERSION = "V13.7"
MLB_API = "https://statsapi.mlb.com/api/v1"
SAVANT = "https://baseballsavant.mlb.com"
_HEADERS = {"User-Agent": "Mozilla/5.0 KyreSportsAI/1.0"}


def _safe_id(value):
    return pitcher_ui._safe_id(value)


def _selected_season():
    return pitcher_ui._selected_season()


def _sf(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _col(df, names):
    if df is None or df.empty:
        return None
    lower = {str(c).strip().lower(): c for c in df.columns}
    for name in names:
        key = str(name).strip().lower()
        if key in lower:
            return lower[key]
    return None


def _row_num(row, names, default=None):
    if row is None:
        return default
    for name in names:
        if name in row.index:
            value = _sf(row.get(name), None)
            if value is not None:
                return value
    return default


def _row_text(row, names, default=""):
    if row is None:
        return default
    for name in names:
        if name in row.index:
            value = row.get(name)
            if value is not None and not pd.isna(value):
                text = str(value).strip()
                if text:
                    return text
    return default


@st.cache_data(ttl=1800, show_spinner=False)
def _savant_arsenal_table(kind, season_year):
    """Bulk Savant pitch-type outcome table; display-only and cached."""
    if kind not in {"batter", "pitcher"}:
        return pd.DataFrame()
    try:
        r = requests.get(
            f"{SAVANT}/leaderboard/pitch-arsenal-stats",
            params={
                "type": kind,
                "pitchType": "",
                "year": int(season_year),
                "team": "",
                "min": 1,
                "csv": "true",
            },
            headers=_HEADERS,
            timeout=25,
        )
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
        return df if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=1800, show_spinner=False)
def _savant_pitcher_expected_table(season_year):
    """Savant expected-stat table containing xERA when available."""
    try:
        r = requests.get(
            f"{SAVANT}/leaderboard/expected_statistics",
            params={
                "type": "pitcher",
                "year": int(season_year),
                "position": "",
                "team": "",
                "filterType": "pa",
                "min": 1,
                "csv": "true",
            },
            headers=_HEADERS,
            timeout=25,
        )
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
        return df if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=1800, show_spinner=False)
def _person_hands(player_id):
    pid = _safe_id(player_id)
    if pid is None:
        return {"bat": "?", "pitch": "?"}
    try:
        r = requests.get(f"{MLB_API}/people/{pid}", headers=_HEADERS, timeout=10)
        r.raise_for_status()
        person = (r.json().get("people") or [{}])[0]
        return {
            "bat": str(((person.get("batSide") or {}).get("code") or "?")).upper(),
            "pitch": str(((person.get("pitchHand") or {}).get("code") or "?")).upper(),
        }
    except Exception:
        return {"bat": "?", "pitch": "?"}


@st.cache_data(ttl=1200, show_spinner=False)
def _mlb_stat_split(player_id, group, sit_code, season_year):
    """One official MLB statSplits row, never inferred."""
    pid = _safe_id(player_id)
    if pid is None or group not in {"hitting", "pitching"} or sit_code not in {"vr", "vl"}:
        return {}
    try:
        r = requests.get(
            f"{MLB_API}/people/{pid}/stats",
            params={
                "stats": "statSplits",
                "group": group,
                "gameType": "R",
                "sitCodes": sit_code,
                "season": int(season_year),
            },
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        for stat_group in r.json().get("stats") or []:
            for split in stat_group.get("splits") or []:
                stat = (split or {}).get("stat") or {}
                if stat:
                    return stat
    except Exception:
        pass
    return {}


def _effective_batter_side(bat_side, pitcher_hand):
    bat = str(bat_side or "?").upper()
    pit = str(pitcher_hand or "?").upper()
    if bat in {"R", "L"}:
        return bat
    if bat == "S" and pit == "R":
        return "L"
    if bat == "S" and pit == "L":
        return "R"
    return "?"


def _fmt_avg(value):
    x = _sf(value, None)
    if x is None:
        return "—"
    return f"{x:.3f}".lstrip("0")


def _fmt_pct(value, digits=1):
    x = _sf(value, None)
    if x is None:
        return "—"
    return f"{x:.{digits}f}%"


def _fmt_num(value, digits=2):
    x = _sf(value, None)
    if x is None:
        return "—"
    return f"{x:.{digits}f}"


def _savant_rows_for_player(df, player_id):
    pid = _safe_id(player_id)
    if pid is None or df is None or df.empty:
        return pd.DataFrame()
    id_col = _col(df, ["player_id", "pitcher", "id"])
    if id_col is None:
        return pd.DataFrame()
    ids = pd.to_numeric(df[id_col], errors="coerce")
    return df.loc[ids == int(pid)].copy()


def _pitch_type_matchup(result):
    year = _selected_season()
    pitcher_id = _safe_id(result.get("starter_id"))
    batter_id = _safe_id(result.get("player_id"))
    pitcher_rows = _savant_rows_for_player(_savant_arsenal_table("pitcher", year), pitcher_id)
    batter_rows = _savant_rows_for_player(_savant_arsenal_table("batter", year), batter_id)

    if pitcher_rows.empty:
        return []

    pitch_col = _col(pitcher_rows, ["pitch_type", "pitch type"])
    name_col = _col(pitcher_rows, ["pitch_name", "pitch name", "pitch"])
    usage_col = _col(pitcher_rows, ["pitch_usage", "pitch_usage_pct", "%"])
    pitches_col = _col(pitcher_rows, ["pitches"])
    if pitch_col is None:
        return []

    if usage_col is not None:
        pitcher_rows["__usage"] = pd.to_numeric(pitcher_rows[usage_col], errors="coerce").fillna(-1)
    elif pitches_col is not None:
        counts = pd.to_numeric(pitcher_rows[pitches_col], errors="coerce").fillna(0)
        total = float(counts.sum())
        pitcher_rows["__usage"] = 100.0 * counts / total if total > 0 else -1
    else:
        pitcher_rows["__usage"] = -1

    pitcher_rows = pitcher_rows.sort_values("__usage", ascending=False).head(3)

    batter_pitch_col = _col(batter_rows, ["pitch_type", "pitch type"])
    out = []
    for _, prow in pitcher_rows.iterrows():
        code = _row_text(prow, [pitch_col], "").upper()
        pitch_name = _row_text(prow, [name_col] if name_col else [], code or "Pitch")
        usage = _row_num(prow, ["__usage"], None)

        brow = None
        if code and batter_pitch_col is not None and not batter_rows.empty:
            match = batter_rows[batter_rows[batter_pitch_col].astype(str).str.upper() == code]
            if not match.empty:
                brow = match.iloc[0]

        out.append({
            "code": code,
            "name": pitch_name,
            "usage": usage,
            "pitcher_xba": _row_num(prow, ["est_ba", "xBA", "xba"], None),
            "pitcher_xslg": _row_num(prow, ["est_slg", "xSLG", "xslg"], None),
            "pitcher_ba": _row_num(prow, ["ba", "BA", "avg"], None),
            "pitcher_whiff": _row_num(prow, ["whiff_percent", "whiff_pct"], None),
            "batter_pa": _to_int(_row_num(brow, ["pa", "PA"], 0)) if brow is not None else 0,
            "batter_xba": _row_num(brow, ["est_ba", "xBA", "xba"], None) if brow is not None else None,
            "batter_xslg": _row_num(brow, ["est_slg", "xSLG", "xslg"], None) if brow is not None else None,
            "batter_ba": _row_num(brow, ["ba", "BA", "avg"], None) if brow is not None else None,
            "batter_hard_hit": _row_num(brow, ["hard_hit_percent", "hardhit_pct"], None) if brow is not None else None,
        })
    return out


def _savant_xera(pitcher_id):
    year = _selected_season()
    rows = _savant_rows_for_player(_savant_pitcher_expected_table(year), pitcher_id)
    if rows.empty:
        return None
    row = rows.iloc[0]
    return _row_num(row, ["xera", "xERA", "est_era"], None)


def _platoon_profile(result):
    year = _selected_season()
    batter_id = _safe_id(result.get("player_id"))
    pitcher_id = _safe_id(result.get("starter_id"))

    p_profile = pitcher_ui._pitcher_profile(result)
    pitcher_hand = str(p_profile.get("hand") or "?").upper()
    if pitcher_hand not in {"R", "L"}:
        pitcher_hand = _person_hands(pitcher_id).get("pitch", "?")

    batter_side = _person_hands(batter_id).get("bat", "?")
    effective_side = _effective_batter_side(batter_side, pitcher_hand)

    batter_sit = "vr" if pitcher_hand == "R" else "vl" if pitcher_hand == "L" else None
    pitcher_sit = "vr" if effective_side == "R" else "vl" if effective_side == "L" else None

    batter_split = _mlb_stat_split(batter_id, "hitting", batter_sit, year) if batter_sit else {}
    pitcher_split = _mlb_stat_split(pitcher_id, "pitching", pitcher_sit, year) if pitcher_sit else {}

    xera = _savant_xera(pitcher_id)
    fip = p_profile.get("fip")

    return {
        "pitcher_hand": pitcher_hand,
        "batter_side": batter_side,
        "effective_side": effective_side,
        "batter_split": batter_split,
        "pitcher_split": pitcher_split,
        "xera": xera,
        "fip": fip,
    }


def _matchup_strip(result):
    p = _platoon_profile(result)
    batter_split = p.get("batter_split") or {}
    pitcher_split = p.get("pitcher_split") or {}
    pitcher_hand = p.get("pitcher_hand") or "?"
    effective_side = p.get("effective_side") or p.get("batter_side") or "?"

    b_ab = _to_int(batter_split.get("atBats"))
    b_hits = _to_int(batter_split.get("hits"))
    b_avg = batter_split.get("avg")
    b_ops = batter_split.get("ops")

    p_ab = _to_int(pitcher_split.get("atBats"))
    p_hits = _to_int(pitcher_split.get("hits"))
    p_avg = pitcher_split.get("avg")
    p_ops = pitcher_split.get("ops")

    split_bits = []
    if b_ab > 0:
        split_bits.append(
            f"Batter vs {pitcher_hand}HP: {b_hits}/{b_ab} • AVG {_fmt_avg(b_avg)}"
            + (f" • OPS {_fmt_num(b_ops, 3)}" if _sf(b_ops, None) is not None else "")
        )
    else:
        split_bits.append(f"Batter vs {pitcher_hand}HP: split unavailable")

    if p_ab > 0:
        split_bits.append(
            f"SP vs {effective_side}HB: {p_hits}/{p_ab} allowed • AVG {_fmt_avg(p_avg)}"
            + (f" • OPS {_fmt_num(p_ops, 3)}" if _sf(p_ops, None) is not None else "")
        )

    quality_bits = []
    if p.get("xera") is not None:
        quality_bits.append(f"xERA {_fmt_num(p.get('xera'))}")
    if p.get("fip") not in (None, "", "N/A"):
        quality_bits.append(f"FIP {_fmt_num(p.get('fip'))}")
    quality_text = " • ".join(quality_bits) if quality_bits else "xERA/FIP unavailable — not synthesized"

    pitch_rows = _pitch_type_matchup(result)
    pitch_html = []
    for row in pitch_rows:
        batter_piece = "Batter pitch-type sample unavailable"
        if row.get("batter_xba") is not None or row.get("batter_ba") is not None:
            use_xba = row.get("batter_xba") if row.get("batter_xba") is not None else row.get("batter_ba")
            batter_piece = f"Batter xBA {_fmt_avg(use_xba)}"
            if row.get("batter_xslg") is not None:
                batter_piece += f" • xSLG {_fmt_num(row.get('batter_xslg'), 3)}"
            if row.get("batter_hard_hit") is not None:
                batter_piece += f" • HH {_fmt_pct(row.get('batter_hard_hit'))}"
            if row.get("batter_pa"):
                batter_piece += f" • {row.get('batter_pa')} PA"

        pitcher_piece = "SP pitch outcome unavailable"
        if row.get("pitcher_xba") is not None or row.get("pitcher_ba") is not None:
            use_xba = row.get("pitcher_xba") if row.get("pitcher_xba") is not None else row.get("pitcher_ba")
            pitcher_piece = f"SP xBA allowed {_fmt_avg(use_xba)}"
            if row.get("pitcher_xslg") is not None:
                pitcher_piece += f" • xSLG {_fmt_num(row.get('pitcher_xslg'), 3)}"

        usage = _fmt_pct(row.get("usage")) if row.get("usage") is not None else "—"
        pitch_html.append(
            '<div class="hit137-pitch-row">'
            f'<div class="hit137-pitch-name">{escape(str(row.get("name") or row.get("code") or "Pitch"))} <span>{escape(usage)} usage</span></div>'
            f'<div class="hit137-pitch-detail">{escape(batter_piece)}</div>'
            f'<div class="hit137-pitch-detail dim">{escape(pitcher_piece)}</div>'
            '</div>'
        )

    if not pitch_html:
        pitch_html.append(
            '<div class="hit137-pitch-row hit137-empty">'
            '<div class="hit137-pitch-name">Pitch-mix matchup unavailable</div>'
            '<div class="hit137-pitch-detail">No Savant pitch-type row is being inferred.</div>'
            '</div>'
        )

    return (
        '<div class="hit137-matchup">'
        '<div class="hit137-head">STEP 4 • MATCHUP PROFILE</div>'
        f'<div class="hit137-split">{escape(" | ".join(split_bits))}</div>'
        f'<div class="hit137-quality">Starter quality: {escape(quality_text)}</div>'
        '<div class="hit137-head hit137-pitch-head">DOMINANT PITCH MATCHUP • BASEBALL SAVANT</div>'
        + "".join(pitch_html)
        + '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hit137-matchup{margin:6px 0 5px;padding:8px 9px;border:1px solid #3a3a64;background:linear-gradient(145deg,#0c1121,#081521);border-radius:11px}
.hit137-head{font-size:.43rem;letter-spacing:.09em;color:#a9a7ff;font-weight:950;text-transform:uppercase}.hit137-split{font-size:.55rem;color:#eef0ff;font-weight:850;line-height:1.45;margin-top:3px}.hit137-quality{font-size:.50rem;color:#9fa8bd;line-height:1.4;margin-top:2px}.hit137-pitch-head{margin-top:7px;color:#68d5ff}.hit137-pitch-row{padding:5px 0;border-top:1px solid rgba(86,118,151,.22)}.hit137-pitch-row:first-of-type{border-top:0}.hit137-pitch-name{font-size:.56rem;color:#f3f8ff;font-weight:900}.hit137-pitch-name span{font-size:.47rem;color:#6fd7ff;margin-left:4px}.hit137-pitch-detail{font-size:.49rem;color:#b4c5d3;line-height:1.35;margin-top:1px}.hit137-pitch-detail.dim{color:#8497a8}.hit137-empty .hit137-pitch-name{color:#9ca8b4}
</style>
"""

if "hit137-matchup" not in core.HIT_CSS:
    core.HIT_CSS = core.HIT_CSS + _EXTRA_CSS


def _pick_html_v137(result, rank):
    sim = result["sim"]
    cls = "hit-pick rank1" if rank == 1 else "hit-pick"
    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "•"
    source = "✅ CONFIRMED" if result.get("lineup_confirmed") else "🕒 PROJECTED"
    player_name = result.get("player_name")
    team_name = result.get("team")

    player_img = visual._img(
        visual.mlb_player_headshot_url(result.get("player_id")),
        "hit134-photo",
        player_name,
    )
    team_img = visual._img(
        visual.mlb_team_logo_url(result.get("team_id")),
        "hit134-team-logo",
        team_name,
    )
    identity = (
        '<div class="hit134-identity">'
        f'{player_img}'
        '<div class="hit134-copy">'
        f'<div class="hit-pick-name">{core._e(player_name)}</div>'
        f'<div class="hit-pick-meta">{core._e(team_name)} vs {core._e(result.get("opponent"))}<br>'
        f'vs {core._e(result.get("starter_name"))} • Bat #{core._e(result.get("position"))} • {core._e(result.get("first_pitch"))}</div>'
        '<div class="hit134-source">MLB batter + team identity</div>'
        '</div>'
        f'{team_img}'
        '</div>'
    )

    return (
        f'<div class="{cls}">'
        f'<div class="hit-rank">{medal} Rank {rank} • {source}</div>'
        f'{identity}'
        f'{pitcher_ui._pitcher_strip(result)}'
        f'{prior._bvp_strip(result)}'
        f'{_matchup_strip(result)}'
        f'<div class="hit-pick-prob">{sim["p_one_plus"]*100:.1f}%</div>'
        f'<div class="hit-pick-sub">2+ {sim["p_two_plus"]*100:.1f}% • xH {sim["expected_hits"]:.2f}<br>'
        f'90% {sim["scenario_low"]*100:.1f}–{sim["scenario_high"]*100:.1f}% • Data {int(result.get("data_score",0) or 0)}/8</div>'
        f'<div class="hit-conf">{core._e(result.get("confidence","—"))}</div>'
        '</div>'
    )


# Replace only the active Top-5 HTML renderer. Step-4 data remains presentation-only.
active._pick_html = _pick_html_v137


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.caption(
        "🧬 Hit UI V13.7 • Step 4 pitch mix + platoon + Savant pitch-type matchup ACTIVE • "
        "presentation/context only • Hit Model V13 unchanged"
    )
    return active.render_hit_hub(games_df, section_header, status_info, team_logo, h)
