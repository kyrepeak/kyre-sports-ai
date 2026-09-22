"""MLB H+R+RBI V1.0.6 — Step 4 pitch-mix + platoon matchup context.

Presentation/context-only wrapper around verified H+R+RBI V1.0.5. Strongest 2+
cards retain Steps 1-3 and add:
- official MLB batter platoon split vs the starter hand,
- official MLB starter split vs the batter's effective side,
- current starter top Statcast pitch mix,
- batter Statcast results versus those same pitch types when available.

All Step-4 lookups are cached, optional and card-level fail-safe. No H/R/RBI
component rate, candidate pool, lineup rule, finalist selection, Monte Carlo,
threshold probability, ranking, confidence or fair-odds math is changed.
"""
from __future__ import annotations

from html import escape
from io import StringIO

import pandas as pd
import requests
import streamlit as st

import mlb_hrrbi_hub_v105 as prior

MODEL_VERSION = "H+R+RBI V1.0.6"
base = prior.base
core = prior.core
MLB_API = "https://statsapi.mlb.com/api/v1"
SAVANT = "https://baseballsavant.mlb.com"
_HEADERS = {"User-Agent": "Mozilla/5.0 KyreSportsAI/1.0"}


def _safe_id(value):
    return prior._safe_id(value)


def _selected_season():
    return prior._selected_season()


def _sf(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
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


@st.cache_data(ttl=1800, show_spinner=False)
def _savant_arsenal_table(kind, season_year):
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


def _fmt_num(value, digits=3):
    x = _sf(value, None)
    if x is None:
        return "—"
    return f"{x:.{digits}f}"


def _savant_rows_for_player(df, player_id):
    pid = _safe_id(player_id)
    if pid is None or df is None or df.empty:
        return pd.DataFrame()
    id_col = _col(df, ["player_id", "pitcher", "batter", "id"])
    if id_col is None:
        return pd.DataFrame()
    ids = pd.to_numeric(df[id_col], errors="coerce")
    return df.loc[ids == int(pid)].copy()


def _pitch_type_matchup(result):
    year = _selected_season()
    pitcher_id = _safe_id(result.get("starter_id"))
    batter_id = _safe_id(result.get("player_id"))

    pitcher_rows = _savant_rows_for_player(
        _savant_arsenal_table("pitcher", year), pitcher_id
    )
    batter_rows = _savant_rows_for_player(
        _savant_arsenal_table("batter", year), batter_id
    )
    if pitcher_rows.empty:
        return []

    pitch_col = _col(pitcher_rows, ["pitch_type", "pitch type"])
    name_col = _col(pitcher_rows, ["pitch_name", "pitch name", "pitch"])
    usage_col = _col(pitcher_rows, ["pitch_usage", "pitch_usage_pct", "usage", "%"])
    pitches_col = _col(pitcher_rows, ["pitches"])
    if pitch_col is None:
        return []

    if usage_col is not None:
        usage = pd.to_numeric(pitcher_rows[usage_col], errors="coerce").fillna(-1)
        pitcher_rows["__usage"] = usage.where(usage > 1.0, usage * 100.0)
    elif pitches_col is not None:
        counts = pd.to_numeric(pitcher_rows[pitches_col], errors="coerce").fillna(0)
        total = float(counts.sum())
        pitcher_rows["__usage"] = (100.0 * counts / total) if total > 0 else -1
    else:
        pitcher_rows["__usage"] = -1

    pitcher_rows = pitcher_rows.sort_values("__usage", ascending=False).head(3)
    batter_pitch_col = _col(batter_rows, ["pitch_type", "pitch type"])

    out = []
    for _, prow in pitcher_rows.iterrows():
        code = _row_text(prow, [pitch_col], "").upper()
        pitch_name = _row_text(prow, [name_col] if name_col else [], code or "Pitch")
        usage_value = _row_num(prow, ["__usage"], None)

        brow = None
        if code and batter_pitch_col is not None and not batter_rows.empty:
            matched = batter_rows[
                batter_rows[batter_pitch_col].astype(str).str.upper() == code
            ]
            if not matched.empty:
                brow = matched.iloc[0]

        out.append(
            {
                "code": code,
                "name": pitch_name,
                "usage": usage_value,
                "batter_pa": _to_int(_row_num(brow, ["pa", "PA"], 0)) if brow is not None else 0,
                "batter_xba": _row_num(brow, ["est_ba", "xBA", "xba"], None) if brow is not None else None,
                "batter_xslg": _row_num(brow, ["est_slg", "xSLG", "xslg"], None) if brow is not None else None,
                "batter_ba": _row_num(brow, ["ba", "BA", "avg"], None) if brow is not None else None,
            }
        )
    return out


def _platoon_profile(result):
    year = _selected_season()
    batter_id = _safe_id(result.get("player_id"))
    pitcher_id = _safe_id(result.get("starter_id"))

    fallback_pitcher = result.get("pitcher")
    fallback_pitcher = fallback_pitcher if isinstance(fallback_pitcher, dict) else {}
    pitcher_hand = str(fallback_pitcher.get("hand") or "?").upper()
    if pitcher_hand not in {"R", "L"}:
        pitcher_hand = _person_hands(pitcher_id).get("pitch", "?")

    batter_side = _person_hands(batter_id).get("bat", "?")
    effective_side = _effective_batter_side(batter_side, pitcher_hand)

    batter_sit = "vr" if pitcher_hand == "R" else "vl" if pitcher_hand == "L" else None
    pitcher_sit = "vr" if effective_side == "R" else "vl" if effective_side == "L" else None

    batter_split = (
        _mlb_stat_split(batter_id, "hitting", batter_sit, year) if batter_sit else {}
    )
    pitcher_split = (
        _mlb_stat_split(pitcher_id, "pitching", pitcher_sit, year) if pitcher_sit else {}
    )

    return {
        "pitcher_hand": pitcher_hand,
        "batter_side": batter_side,
        "effective_side": effective_side,
        "batter_split": batter_split,
        "pitcher_split": pitcher_split,
    }


def _matchup_grade(profile, pitch_rows):
    """Display-only evidence label; never a model or ranking input."""
    batter_split = profile.get("batter_split") or {}
    pitcher_split = profile.get("pitcher_split") or {}

    score = 0.0
    weight = 0.0

    b_ab = _to_int(batter_split.get("atBats"))
    b_ops = _sf(batter_split.get("ops"), None)
    if b_ab >= 20 and b_ops is not None:
        rel = min(b_ab / 120.0, 1.0)
        score += max(min((b_ops - 0.720) / 0.220, 1.0), -1.0) * rel * 0.50
        weight += rel * 0.50

    p_ab = _to_int(pitcher_split.get("atBats"))
    p_ops = _sf(pitcher_split.get("ops"), None)
    if p_ab >= 20 and p_ops is not None:
        rel = min(p_ab / 150.0, 1.0)
        score += max(min((p_ops - 0.720) / 0.220, 1.0), -1.0) * rel * 0.30
        weight += rel * 0.30

    pitch_score = 0.0
    pitch_weight = 0.0
    for row in pitch_rows or []:
        xba = row.get("batter_xba")
        if xba is None:
            xba = row.get("batter_ba")
        usage = _sf(row.get("usage"), None)
        pa = _to_int(row.get("batter_pa"))
        if xba is None or usage is None or pa < 5:
            continue
        w = max(min(usage / 100.0, 0.70), 0.0) * min(pa / 40.0, 1.0)
        pitch_score += max(min((float(xba) - 0.245) / 0.110, 1.0), -1.0) * w
        pitch_weight += w
    if pitch_weight > 0:
        score += (pitch_score / pitch_weight) * 0.20
        weight += 0.20

    if weight <= 0.05:
        return "DATA LIMITED", "limited"
    normalized = score / weight
    if normalized >= 0.40:
        return "FAVORABLE", "good"
    if normalized <= -0.40:
        return "TOUGH", "tough"
    return "BALANCED", "neutral"


def _matchup_strip(result):
    profile = _platoon_profile(result)
    batter_split = profile.get("batter_split") or {}
    pitcher_split = profile.get("pitcher_split") or {}
    pitcher_hand = profile.get("pitcher_hand") or "?"
    effective_side = profile.get("effective_side") or profile.get("batter_side") or "?"

    b_ab = _to_int(batter_split.get("atBats"))
    b_hits = _to_int(batter_split.get("hits"))
    b_avg = batter_split.get("avg")
    b_ops = batter_split.get("ops")

    p_ab = _to_int(pitcher_split.get("atBats"))
    p_hits = _to_int(pitcher_split.get("hits"))
    p_avg = pitcher_split.get("avg")
    p_ops = pitcher_split.get("ops")

    split_rows = []
    if b_ab > 0:
        split_rows.append(
            f"Batter vs {pitcher_hand}HP: {b_hits}/{b_ab} • AVG {_fmt_avg(b_avg)}"
            + (f" • OPS {_fmt_num(b_ops)}" if _sf(b_ops, None) is not None else "")
        )
    else:
        split_rows.append(f"Batter vs {pitcher_hand}HP: official split unavailable")

    if p_ab > 0:
        split_rows.append(
            f"SP vs {effective_side}HB: {p_hits}/{p_ab} allowed • AVG {_fmt_avg(p_avg)}"
            + (f" • OPS {_fmt_num(p_ops)}" if _sf(p_ops, None) is not None else "")
        )
    else:
        split_rows.append(f"SP vs {effective_side}HB: official split unavailable")

    pitch_rows = _pitch_type_matchup(result)
    grade, grade_cls = _matchup_grade(profile, pitch_rows)

    pitch_bits = []
    for row in pitch_rows:
        usage = _sf(row.get("usage"), None)
        label = row.get("name") or row.get("code") or "Pitch"
        usage_text = f"{usage:.0f}%" if usage is not None and usage >= 0 else "usage —"
        sample = ""
        xba = row.get("batter_xba")
        if xba is None:
            xba = row.get("batter_ba")
        if xba is not None:
            sample = f" • batter xBA {_fmt_avg(xba)}"
        if row.get("batter_xslg") is not None:
            sample += f" • xSLG {_fmt_num(row.get('batter_xslg'))}"
        if _to_int(row.get("batter_pa")) > 0:
            sample += f" • {_to_int(row.get('batter_pa'))} PA"
        pitch_bits.append(f"{label} {usage_text}{sample}")

    if not pitch_bits:
        pitch_bits = ["Statcast pitch-type join unavailable — nothing inferred"]

    split_html = "".join(
        f'<div class="hrr106-split-row">{escape(text)}</div>' for text in split_rows
    )
    pitch_html = "".join(
        f'<div class="hrr106-pitch-row">{escape(text)}</div>' for text in pitch_bits
    )

    return (
        '<div class="hrr106-matchup">'
        '<div class="hrr106-head">'
        '<span>STEP 4 • PITCH MIX + PLATOON MATCHUP</span>'
        f'<b class="hrr106-grade {grade_cls}">{escape(grade)}</b>'
        '</div>'
        f'<div class="hrr106-splits">{split_html}</div>'
        '<div class="hrr106-arsenal-title">STARTER TOP STATCAST ARSENAL → BATTER RESULTS</div>'
        f'<div class="hrr106-pitches">{pitch_html}</div>'
        '<div class="hrr106-note">Context-only matchup grade • small pitch-type samples are not promoted into the H+R+RBI model.</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hrr106-matchup{margin:7px 0 5px;padding:9px 10px;border:1px solid #234d67;background:linear-gradient(145deg,#071a28,#081522);border-radius:12px}
.hrr106-head{display:flex;align-items:center;justify-content:space-between;gap:8px}
.hrr106-head>span{font-size:.43rem;letter-spacing:.08em;color:#62c7ff;font-weight:950;text-transform:uppercase}
.hrr106-grade{border:1px solid #36566d;border-radius:999px;padding:3px 7px;font-size:.46rem;letter-spacing:.04em;color:#b8ccda;white-space:nowrap}
.hrr106-grade.good{border-color:#1f6b4f;background:#0a3326;color:#79edb7}
.hrr106-grade.neutral{border-color:#6d5a18;background:#382f0d;color:#f1d36c}
.hrr106-grade.tough{border-color:#7a3b38;background:#351514;color:#ff9d98}
.hrr106-grade.limited{border-color:#465564;background:#16202a;color:#a6b3bf}
.hrr106-splits{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:7px}
.hrr106-split-row,.hrr106-pitch-row{border:1px solid #1b384e;background:#071521;border-radius:8px;padding:6px 7px;color:#dbe8f1;font-size:.52rem;line-height:1.4}
.hrr106-arsenal-title{font-size:.40rem;letter-spacing:.08em;color:#6e91a8;font-weight:950;text-transform:uppercase;margin-top:7px}
.hrr106-pitches{display:grid;grid-template-columns:1fr;gap:5px;margin-top:5px}
.hrr106-note{color:#71889a;font-size:.45rem;line-height:1.4;margin-top:6px}
.hrr106-step-badge{display:inline-flex;align-items:center;gap:5px;border:1px solid #2a6078;background:#071d2b;color:#79dfff;border-radius:999px;padding:5px 8px;font-size:.52rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin:0 0 9px}
@media(max-width:700px){.hrr106-splits{grid-template-columns:1fr}.hrr106-head{align-items:flex-start}.hrr106-grade{font-size:.43rem}}
</style>
"""

if "hrr106-matchup" not in base.CSS:
    base.CSS = base.CSS + _EXTRA_CSS


def _card_v106(r, rank, threshold):
    """Verified Steps 1-3 card first; optional Step 4 can never crash it."""
    html = prior._card_v105(r, rank, threshold)
    try:
        strip = _matchup_strip(r)
        marker = '<div class="hrr-prob">'
        if marker in html and strip:
            return html.replace(marker, strip + marker, 1)
    except Exception:
        pass
    return html


base._card = _card_v106


def render_hrrbi_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(
        '<div class="hrr106-step-badge">🎯 H+R+RBI V1.0.6 • Steps 1–4 active • pitch mix + platoon context</div>',
        unsafe_allow_html=True,
    )
    return core.render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
