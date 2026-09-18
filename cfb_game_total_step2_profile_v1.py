"""Universal presentation-only Step 2 Team Performance Profile for CFB Game Total.

Step 2 answers one question for every future matchup:
"Which team owns the stronger current scoring profile, and why?"

This module is intentionally display-only. It consumes already-reconciled team
evidence, normalizes a universal contract, renders the neon two-team profile
surface, and fails closed when advanced evidence is unavailable. It never
changes projection, distribution, qualification, ranking, odds, API, or model
behavior.
"""
from __future__ import annotations

from html import escape
import re
from typing import Any, Mapping

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

STEP2_REQUIRED_FIELDS = (
    "team",
    "record",
    "sample_games",
    "ppg",
    "allowed_pg",
    "point_diff_pg",
)

STEP2_ADVANCED_FIELDS = (
    "recent_form",
    "yards_per_play",
    "yards_per_play_allowed",
    "points_per_drive",
    "points_per_drive_allowed",
    "off_eff_rank",
    "def_eff_rank",
    "split_summary",
)

STEP2_PRESENTATION_MARKER = "CFB_GAME_TOTAL_STEP2_PERFORMANCE_PROFILE_V2_ACTIVE"

_UNAVAILABLE = {
    "",
    "—",
    "-",
    "none",
    "n/a",
    "na",
    "unavailable",
    "record unavailable",
    "data limited",
}

STEP2_CSS = r"""
<style>
.gt167-step2{grid-column:1/-1!important;position:relative;border:1px solid rgba(46,226,255,.72)!important;border-radius:17px!important;background:linear-gradient(145deg,#041426 0%,#061a2d 48%,#081426 100%)!important;box-shadow:0 0 0 2px rgba(106,255,193,.20),0 0 28px rgba(0,229,255,.15),0 0 48px rgba(255,58,215,.10)!important;overflow:hidden}
.gt167-step2:before{content:"";position:absolute;inset:-2px;z-index:0;border-radius:18px;padding:2px;background:linear-gradient(90deg,#6cff45,#00f5ff,#8f59ff,#ff2bd6,#ffd93d,#57ff7a);-webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;pointer-events:none}
.gt167-step2 summary,.gt167-step2-body{position:relative;z-index:1}
.gt167-step2 summary{min-height:64px!important;padding:11px 14px!important;grid-template-columns:44px minmax(0,1fr) auto!important;gap:12px!important;background:linear-gradient(90deg,rgba(2,33,55,.92),rgba(8,23,46,.84))!important}
.gt167-step2 .gt159-num{width:44px!important;height:44px!important;border-radius:12px!important;background:linear-gradient(145deg,#00dbff,#784eff 58%,#ff2bd6)!important;color:#fff!important;box-shadow:0 0 22px rgba(55,208,255,.42)!important;font-size:17px!important}
.gt167-step2 .gt159-stepcopy b{font-size:16px!important;color:#f6fbff!important}.gt167-step2 .gt159-stepcopy span{font-size:9px!important;color:#b3c8d8!important;margin-top:4px!important}
.gt167-step2 .gt159-state.ready{border-color:rgba(74,255,190,.65)!important;color:#66ffc0!important;background:rgba(6,83,61,.20)!important}
.gt167-step2 .gt159-state.check{border-color:rgba(255,226,76,.70)!important;color:#ffe865!important;background:rgba(108,83,0,.20)!important}
.gt167-step2 .gt159-state.limited{border-color:rgba(255,188,66,.62)!important;color:#ffc75f!important;background:rgba(90,56,0,.20)!important}
.gt167-step2-body{padding:12px 13px 14px!important}
.gt167-team-pair{display:grid;grid-template-columns:minmax(0,1fr) 34px minmax(0,1fr);gap:9px;align-items:stretch}
.gt167-vs{display:grid;place-items:center;align-content:center;color:#f3f8ff;font-size:14px;font-weight:1000;font-style:italic;text-shadow:0 0 14px #48dfff}.gt167-vs:before,.gt167-vs:after{content:"";display:block;width:2px;height:82px;background:linear-gradient(transparent,#00f5ff,#677cff,transparent);box-shadow:0 0 9px #00d9ff}
.gt167-profile{min-width:0;padding:11px;border:1px solid rgba(58,255,199,.62);border-radius:13px;background:linear-gradient(145deg,rgba(2,45,52,.97),rgba(3,26,43,.98));box-shadow:inset 0 0 26px rgba(19,255,183,.06),0 0 18px rgba(0,255,191,.09)}
.gt167-profile.home{border-color:rgba(255,214,83,.64);background:linear-gradient(145deg,rgba(48,42,19,.96),rgba(8,28,45,.98));box-shadow:inset 0 0 25px rgba(255,210,44,.06),0 0 18px rgba(255,214,57,.08)}
.gt167-teamhead{display:grid;grid-template-columns:62px minmax(0,1fr) auto;gap:9px;align-items:center}
.gt167-logo-wrap{height:52px;display:grid;place-items:center}.gt167-logo{max-width:58px;max-height:48px;object-fit:contain;filter:drop-shadow(0 0 8px rgba(0,0,0,.5))}
.gt167-teamname{min-width:0}.gt167-teamname b{display:block;color:#fff;font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gt167-teamname span{display:block;color:#9eb4c6;font-size:9px;margin-top:3px;text-transform:uppercase;letter-spacing:.04em}
.gt167-record{min-width:59px;padding:8px 8px;border:1px solid rgba(73,236,255,.45);border-radius:10px;text-align:center;background:rgba(3,32,54,.78)}.gt167-record b{display:block;color:#fff;font-size:15px}.gt167-record span{display:block;color:#9eb4c5;font-size:7px;margin-top:2px;letter-spacing:.05em}
.gt167-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:10px}.gt167-metric{min-width:0;padding:7px 4px;border:1px solid rgba(55,167,228,.28);border-radius:8px;background:linear-gradient(145deg,rgba(5,38,62,.92),rgba(5,28,48,.96));text-align:center}.gt167-metric b{display:block;color:#f7fbff;font-size:12px;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gt167-metric span{display:block;color:#88a4b8;font-size:6.4px;line-height:1.2;text-transform:uppercase;margin-top:4px;letter-spacing:.025em}.gt167-metric.good b{color:#4ff4bc}.gt167-metric.bad b{color:#ff6c68}.gt167-metric.info b{color:#a9d8ff}.gt167-metric.warn b{color:#ffd450}
.gt167-read-pair{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:8px}.gt167-read{position:relative;padding:8px 8px 8px 12px;border:1px solid rgba(53,167,211,.22);border-radius:8px;background:rgba(4,31,50,.74)}.gt167-read:before{content:"";position:absolute;left:5px;top:8px;bottom:8px;width:3px;border-radius:9px;background:#19e9cf}.gt167-profile.home .gt167-read:before{background:#ffd840}.gt167-read span{display:block;color:#8ca7bb;font-size:7px}.gt167-read b{display:block;color:#f6fbff;font-size:9px;line-height:1.25;margin-top:3px}
.gt167-edge{display:flex;align-items:center;gap:8px;margin-top:8px;padding:7px 9px;border:1px solid rgba(48,255,195,.48);border-radius:8px;background:rgba(2,80,65,.20);color:#58f4c2;font-size:8px;font-weight:900}.gt167-profile.home .gt167-edge{border-color:rgba(255,218,72,.48);background:rgba(98,71,3,.18);color:#ffe45f}.gt167-edge strong{margin-left:auto;color:inherit;font-size:9px}
.gt167-profile-read{position:relative;margin-top:8px;padding:9px 9px 9px 14px;border:1px solid rgba(75,161,208,.25);border-radius:9px;background:rgba(3,29,47,.76);min-height:57px}.gt167-profile-read:before{content:"";position:absolute;left:6px;top:9px;bottom:9px;width:4px;border-radius:8px;background:#61d9ff}.gt167-profile.home .gt167-profile-read:before{background:#ffdd4e}.gt167-profile-read span{display:block;color:#9db4c4;font-size:7px}.gt167-profile-read b{display:block;color:#eef6fb;font-size:8.5px;line-height:1.35;margin-top:3px}
.gt167-missing{margin-top:6px;color:#ffd170;font-size:7px;line-height:1.35}
.gt167-insights{margin-top:11px;padding:10px;border:1px solid rgba(38,216,255,.52);border-radius:11px;background:linear-gradient(145deg,rgba(4,36,61,.92),rgba(6,24,43,.96))}.gt167-insight-title{display:flex;align-items:center;gap:7px;color:#57e8ff;font-size:10px;font-weight:1000;letter-spacing:.04em}.gt167-insight-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:8px}.gt167-insight{padding:8px;border:1px solid rgba(56,245,190,.48);border-radius:9px;background:rgba(2,64,55,.18);min-width:0}.gt167-insight.red{border-color:rgba(255,83,99,.50);background:rgba(94,18,32,.16)}.gt167-insight.blue{border-color:rgba(42,207,255,.52);background:rgba(5,64,94,.16)}.gt167-insight.purple{border-color:rgba(217,73,255,.52);background:rgba(87,17,102,.16)}.gt167-insight span{display:block;color:#8ca7b8;font-size:6.7px}.gt167-insight b{display:block;color:#eaf7f4;font-size:8.4px;line-height:1.25;margin-top:3px}
.gt167-summary{display:grid;grid-template-columns:auto 1px minmax(0,1fr);gap:10px;align-items:center;margin-top:8px;padding:8px 10px;border:1px solid rgba(40,193,235,.30);border-radius:8px;background:rgba(4,33,54,.72)}.gt167-summary strong{color:#59e7ff;font-size:8px;white-space:nowrap}.gt167-summary i{height:25px;background:#36d7ff;opacity:.5}.gt167-summary span{color:#c6d7e3;font-size:7.5px;line-height:1.35}
@media(max-width:760px){.gt167-team-pair{grid-template-columns:1fr}.gt167-vs{display:none}.gt167-insight-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:520px){.gt167-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}.gt167-teamhead{grid-template-columns:54px minmax(0,1fr) auto}.gt167-read-pair{grid-template-columns:1fr}.gt167-insight-grid{grid-template-columns:1fr 1fr}}
</style>
"""


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _usable(value: Any) -> bool:
    text = _clean(value)
    return bool(text) and text.casefold() not in _UNAVAILABLE


def _float(value: Any) -> float | None:
    if value is None:
        return None
    text = _clean(value).replace(",", "").replace("%", "")
    if not text or text.casefold() in _UNAVAILABLE:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def _int(value: Any) -> int | None:
    number = _float(value)
    return int(number) if number is not None else None


def _display_num(value: Any, *, signed: bool = False) -> str:
    number = _float(value)
    if number is None:
        return "—"
    if signed:
        return f"{number:+.1f}"
    return f"{number:.1f}"


def _record_text(value: Any) -> str:
    if isinstance(value, Mapping):
        wins = int(value.get("wins") or 0)
        losses = int(value.get("losses") or 0)
        ties = int(value.get("ties") or 0)
        games = int(value.get("games") or wins + losses + ties)
        if games <= 0:
            return ""
        return f"{wins}-{losses}" + (f"-{ties}" if ties else "")
    text = _clean(value)
    return text if _usable(text) else ""


def _sample_games(evidence: Mapping[str, Any], record: str) -> int:
    for candidate in (
        evidence.get("sample_games"),
        (evidence.get("data_quality") or {}).get("sample_games")
        if isinstance(evidence.get("data_quality"), Mapping)
        else None,
        (evidence.get("record") or {}).get("games")
        if isinstance(evidence.get("record"), Mapping)
        else None,
    ):
        number = _int(candidate)
        if number is not None and number > 0:
            return number
    completed = evidence.get("completed_games")
    if isinstance(completed, list) and completed:
        return len([row for row in completed if isinstance(row, Mapping)])
    match = re.fullmatch(r"(\d+)-(\d+)(?:-(\d+))?", record)
    if match:
        return sum(int(x or 0) for x in match.groups())
    return 0


def _stat_row(evidence: Mapping[str, Any], metric: str) -> Mapping[str, Any]:
    stats = evidence.get("official_stats") or {}
    if not isinstance(stats, Mapping):
        return {}
    row = stats.get(metric) or {}
    return row if isinstance(row, Mapping) else {}


def _row_value(row: Mapping[str, Any], aliases: tuple[str, ...]) -> float | None:
    headers = [_clean(x).casefold() for x in row.get("headers") or []]
    cells = list(row.get("row") or [])
    for idx, header in enumerate(headers):
        compact = re.sub(r"[^a-z0-9]+", "", header)
        for alias in aliases:
            wanted = re.sub(r"[^a-z0-9]+", "", alias.casefold())
            if wanted and (compact == wanted or wanted in compact):
                if idx < len(cells):
                    value = _float(cells[idx])
                    if value is not None:
                        return value
    return None


def _rank_from_row(row: Mapping[str, Any]) -> int | None:
    rank = _row_value(row, ("rank", "rk"))
    if rank is not None:
        return int(rank)
    cells = list(row.get("row") or [])
    if cells:
        first = _int(cells[0])
        if first is not None and first > 0:
            return first
    return None


def _official_stat_value(row: Mapping[str, Any]) -> float | None:
    """Read the numeric value from one already-matched NCAA stat category row."""
    for key in ("value_numeric", "value", "display_value", "stat"):
        value = _float(row.get(key))
        if value is not None:
            return value
    direct = _row_value(
        row,
        ("ppg", "points per game", "pts/game", "pts per game", "avg", "average"),
    )
    if direct is not None:
        return direct
    cells = list(row.get("row") or [])
    for cell in reversed(cells):
        value = _float(cell)
        if value is not None:
            return value
    return None


def _yards_per_play_from_row(row: Mapping[str, Any]) -> float | None:
    direct = _row_value(
        row,
        ("yards per play", "yds/play", "yds per play", "ypp", "avg/play"),
    )
    if direct is not None:
        return direct
    yards = _row_value(row, ("total yards", "yards", "yds"))
    plays = _row_value(row, ("plays", "off plays", "def plays"))
    if yards is not None and plays is not None and plays > 0:
        return yards / plays
    return None


def _direct_metric(evidence: Mapping[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key in evidence:
            value = _float(evidence.get(key))
            if value is not None:
                return value
    return None


def _direct_rank(evidence: Mapping[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        if key in evidence:
            value = _int(evidence.get(key))
            if value is not None and value > 0:
                return value
    return None


def _split_summary(evidence: Mapping[str, Any], side: str) -> str:
    direct = _clean(
        evidence.get("split_summary")
        or evidence.get("home_away_split")
        or evidence.get(f"{side}_split_summary")
    )
    if _usable(direct):
        return direct

    point_diff = _direct_metric(
        evidence,
        (
            "home_point_diff_pg" if side == "home" else "away_point_diff_pg",
            "home_point_diff" if side == "home" else "away_point_diff",
        ),
    )
    if point_diff is not None:
        return f"{'Home' if side == 'home' else 'Away'} {point_diff:+.1f}"

    record = evidence.get("home_record" if side == "home" else "away_record")
    text = _record_text(record)
    if text:
        return f"{'Home' if side == 'home' else 'Away'} {text}"

    completed = evidence.get("completed_games")
    if isinstance(completed, list):
        wins = losses = ties = 0
        for row in completed:
            if not isinstance(row, Mapping):
                continue
            if _clean(row.get("location")).casefold() != side:
                continue
            result = _clean(row.get("result")).upper()
            if not result:
                margin = _float(row.get("margin"))
                if margin is None:
                    pf = _float(row.get("points_for"))
                    pa = _float(row.get("points_against"))
                    if pf is not None and pa is not None:
                        margin = pf - pa
                if margin is not None:
                    result = "W" if margin > 0 else "L" if margin < 0 else "T"
            if result == "W":
                wins += 1
            elif result == "L":
                losses += 1
            elif result == "T":
                ties += 1
        games = wins + losses + ties
        if games:
            record_text = f"{wins}-{losses}" + (f"-{ties}" if ties else "")
            return f"{'Home' if side == 'home' else 'Away'} {record_text}"
    return ""


def _offense_label(ppg: float | None, ypp: float | None, ppd: float | None) -> str:
    score = 0
    if ppg is not None:
        score += 2 if ppg >= 35 else 1 if ppg >= 28 else -1 if ppg < 21 else 0
    if ypp is not None:
        score += 2 if ypp >= 6.5 else 1 if ypp >= 5.8 else -1 if ypp < 4.8 else 0
    if ppd is not None:
        score += 2 if ppd >= 2.7 else 1 if ppd >= 2.2 else -1 if ppd < 1.6 else 0
    if score >= 4:
        return "Explosive + efficient"
    if score >= 2:
        return "Productive + efficient"
    if score <= -2:
        return "Scoring efficiency concern"
    return "Balanced scoring profile"


def _defense_label(
    allowed: float | None,
    ypp_allowed: float | None,
    ppd_allowed: float | None,
) -> str:
    score = 0
    if allowed is not None:
        score += 2 if allowed <= 17 else 1 if allowed <= 23 else -2 if allowed >= 31 else -1 if allowed >= 27 else 0
    if ypp_allowed is not None:
        score += 2 if ypp_allowed <= 4.6 else 1 if ypp_allowed <= 5.2 else -2 if ypp_allowed >= 6.2 else -1 if ypp_allowed >= 5.8 else 0
    if ppd_allowed is not None:
        score += 2 if ppd_allowed <= 1.5 else 1 if ppd_allowed <= 1.9 else -2 if ppd_allowed >= 2.5 else -1 if ppd_allowed >= 2.2 else 0
    if score >= 4:
        return "Fast, aggressive, limiting scores"
    if score >= 2:
        return "Strong scoring resistance"
    if score <= -3:
        return "Vulnerable to big gains"
    if score <= -1:
        return "Scoring prevention concern"
    return "Balanced defensive profile"


def _profile_score(contract: Mapping[str, Any]) -> float:
    score = float(contract.get("point_diff_pg") or 0.0)
    ypp = contract.get("yards_per_play")
    yppa = contract.get("yards_per_play_allowed")
    ppd = contract.get("points_per_drive")
    ppda = contract.get("points_per_drive_allowed")
    if ypp is not None and yppa is not None:
        score += (float(ypp) - float(yppa)) * 3.0
    if ppd is not None and ppda is not None:
        score += (float(ppd) - float(ppda)) * 5.0
    return score


def _profile_read(contract: Mapping[str, Any]) -> str:
    ppg = contract.get("ppg")
    allowed = contract.get("allowed_pg")
    ypp = contract.get("yards_per_play")
    form = _clean(contract.get("recent_form"))
    pieces: list[str] = []
    if ppg is not None:
        pieces.append(f"Scores {float(ppg):.1f} per game")
    if ypp is not None:
        pieces.append(f"creates {float(ypp):.1f} yards per play")
    if allowed is not None:
        pieces.append(f"allows {float(allowed):.1f} per game")
    if _usable(form):
        pieces.append(f"recent form {form}")
    if not pieces:
        return "Current performance evidence is still limited; no profile claim is forced."
    return ", ".join(pieces[:3]).capitalize() + "."


def build_team_profile_contract(
    evidence: Mapping[str, Any] | None,
    identity_side: Mapping[str, Any] | None = None,
    *,
    side: str = "",
) -> dict[str, Any]:
    evidence = evidence or {}
    identity_side = identity_side or {}
    side = _clean(side).lower() or _clean(evidence.get("side")).lower() or "away"

    team = _clean(
        evidence.get("team")
        or identity_side.get("team")
        or identity_side.get("team_name")
    )
    logo = _clean(identity_side.get("logo") or evidence.get("logo"))
    conference = _clean(evidence.get("conference") or identity_side.get("conference"))
    classification = _clean(
        evidence.get("classification")
        or evidence.get("division_context")
        or identity_side.get("classification")
        or identity_side.get("division_context")
    ).upper()
    record = _record_text(
        evidence.get("record_text")
        or evidence.get("record")
        or identity_side.get("record")
    )
    sample_games = _sample_games(evidence, record)

    ppg = _direct_metric(evidence, ("ppg", "points_per_game", "scoring_offense_pg"))
    allowed = _direct_metric(
        evidence,
        ("points_allowed_pg", "allowed_pg", "points_allowed_per_game"),
    )
    point_diff = _direct_metric(evidence, ("point_diff_pg", "point_differential_pg"))
    if point_diff is None and ppg is not None and allowed is not None:
        point_diff = ppg - allowed

    total_offense = _stat_row(evidence, "total_offense")
    total_defense = _stat_row(evidence, "total_defense")
    scoring_offense = _stat_row(evidence, "scoring_offense")
    scoring_defense = _stat_row(evidence, "scoring_defense")

    # The completed-game display sample can legitimately be empty even when
    # NCAA already has current scoring tables for the exact team. Reuse those
    # verified category rows before failing the universal Step 2 core profile.
    if ppg is None:
        ppg = _official_stat_value(scoring_offense)
    if allowed is None:
        allowed = _official_stat_value(scoring_defense)
    if point_diff is None and ppg is not None and allowed is not None:
        point_diff = ppg - allowed

    ypp = _direct_metric(
        evidence,
        ("yards_per_play", "yards_per_play_offense", "off_ypp", "ypp"),
    )
    if ypp is None:
        ypp = _yards_per_play_from_row(total_offense)

    ypp_allowed = _direct_metric(
        evidence,
        ("yards_per_play_allowed", "def_ypp", "ypp_allowed"),
    )
    if ypp_allowed is None:
        ypp_allowed = _yards_per_play_from_row(total_defense)

    ppd = _direct_metric(
        evidence,
        ("points_per_drive", "off_points_per_drive", "ppd"),
    )
    ppd_allowed = _direct_metric(
        evidence,
        ("points_per_drive_allowed", "def_points_per_drive", "ppd_allowed"),
    )

    off_rank = _direct_rank(
        evidence,
        ("off_eff_rank", "offensive_efficiency_rank", "offense_efficiency_rank"),
    )
    if off_rank is None:
        off_rank = _rank_from_row(scoring_offense) or _rank_from_row(total_offense)

    def_rank = _direct_rank(
        evidence,
        ("def_eff_rank", "defensive_efficiency_rank", "defense_efficiency_rank"),
    )
    if def_rank is None:
        def_rank = _rank_from_row(scoring_defense) or _rank_from_row(total_defense)

    recent_form = _clean(evidence.get("recent_form"))
    split_summary = _split_summary(evidence, side)

    contract: dict[str, Any] = {
        "side": side,
        "team": team,
        "logo": logo,
        "conference": conference,
        "classification": classification,
        "record": record,
        "sample_games": sample_games,
        "ppg": ppg,
        "allowed_pg": allowed,
        "yards_per_play": ypp,
        "yards_per_play_allowed": ypp_allowed,
        "points_per_drive": ppd,
        "points_per_drive_allowed": ppd_allowed,
        "off_eff_rank": off_rank,
        "def_eff_rank": def_rank,
        "point_diff_pg": point_diff,
        "split_summary": split_summary,
        "recent_form": recent_form,
    }

    missing_required: list[str] = []
    for field in STEP2_REQUIRED_FIELDS:
        value = contract.get(field)
        if field == "sample_games":
            if int(value or 0) <= 0:
                missing_required.append(field)
        elif field in {"ppg", "allowed_pg", "point_diff_pg"}:
            if value is None:
                missing_required.append(field)
        elif not _usable(value):
            missing_required.append(field)

    missing_advanced = [
        field
        for field in STEP2_ADVANCED_FIELDS
        if (
            not _usable(contract.get(field))
            if field in {"recent_form", "split_summary"}
            else contract.get(field) is None
        )
    ]
    advanced_available = len(STEP2_ADVANCED_FIELDS) - len(missing_advanced)

    contract["offense_label"] = _offense_label(ppg, ypp, ppd)
    contract["defense_label"] = _defense_label(allowed, ypp_allowed, ppd_allowed)
    contract["profile_read"] = _profile_read(contract)
    contract["missing_required"] = missing_required
    contract["missing_advanced"] = missing_advanced
    contract["required_complete"] = not missing_required
    contract["advanced_available"] = advanced_available
    contract["advanced_total"] = len(STEP2_ADVANCED_FIELDS)
    contract["profile_score"] = _profile_score(contract)

    if missing_required:
        state = "DATA LIMITED"
    elif missing_advanced:
        state = "CHECK"
    else:
        state = "READY"
    contract["state"] = state
    return contract


def _winner(
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    field: str,
    *,
    lower_is_better: bool = False,
) -> Mapping[str, Any] | None:
    av = away.get(field)
    hv = home.get(field)
    if av is None or hv is None:
        return None
    if float(av) == float(hv):
        return None
    if lower_is_better:
        return away if float(av) < float(hv) else home
    return away if float(av) > float(hv) else home


def _insights(away: Mapping[str, Any], home: Mapping[str, Any]) -> list[dict[str, str]]:
    scores = _winner(away, home, "ppg")
    gives_up = _winner(away, home, "allowed_pg")
    efficiency_field = ""
    if away.get("points_per_drive") is not None and home.get("points_per_drive") is not None:
        efficiency_field = "points_per_drive"
        efficiency_suffix = " pts/drive"
    elif away.get("yards_per_play") is not None and home.get("yards_per_play") is not None:
        efficiency_field = "yards_per_play"
        efficiency_suffix = " YPP"
    else:
        efficiency_field = "ppg"
        efficiency_suffix = " PPG"
    efficient = _winner(away, home, efficiency_field)
    edge = away if float(away.get("profile_score") or 0.0) >= float(home.get("profile_score") or 0.0) else home

    def line(team: Mapping[str, Any] | None, field: str, suffix: str) -> str:
        if not team:
            return "Even / insufficient data"
        value = team.get(field)
        return f"{_clean(team.get('team'))} — {_display_num(value)}{suffix}"

    return [
        {"label": "Who scores more", "value": line(scores, "ppg", " PPG"), "css": ""},
        {"label": "Who gives up more", "value": line(gives_up, "allowed_pg", " APG"), "css": "red"},
        {"label": "Who is more efficient", "value": line(efficient, efficiency_field, efficiency_suffix), "css": "blue"},
        {"label": "Best profile edge", "value": f"{_clean(edge.get('team'))} overall", "css": "purple"},
    ]


def _summary(away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    edge = away if float(away.get("profile_score") or 0.0) >= float(home.get("profile_score") or 0.0) else home
    other = home if edge is away else away
    reasons: list[str] = []
    if edge.get("ppg") is not None and other.get("ppg") is not None and float(edge["ppg"]) > float(other["ppg"]):
        reasons.append("higher scoring")
    if edge.get("allowed_pg") is not None and other.get("allowed_pg") is not None and float(edge["allowed_pg"]) < float(other["allowed_pg"]):
        reasons.append("better point prevention")
    if edge.get("yards_per_play") is not None and other.get("yards_per_play") is not None and float(edge["yards_per_play"]) > float(other["yards_per_play"]):
        reasons.append("better per-play efficiency")
    if edge.get("point_diff_pg") is not None and other.get("point_diff_pg") is not None and float(edge["point_diff_pg"]) > float(other["point_diff_pg"]):
        reasons.append("cleaner point differential")
    if not reasons:
        return "Step 2 has no forced edge yet; the available team-profile evidence is too close or incomplete."
    readable = ", ".join(reasons[:3])
    return f"{_clean(edge.get('team'))} owns the stronger current performance profile: {readable}."


def build_step2_contract(
    identity: Mapping[str, Any] | None,
    away: Mapping[str, Any] | None,
    home: Mapping[str, Any] | None,
) -> dict[str, Any]:
    identity = identity or {}
    away_contract = build_team_profile_contract(
        away,
        identity.get("away") or {},
        side="away",
    )
    home_contract = build_team_profile_contract(
        home,
        identity.get("home") or {},
        side="home",
    )
    states = {away_contract["state"], home_contract["state"]}
    if "DATA LIMITED" in states:
        state = "DATA LIMITED"
    elif "CHECK" in states:
        state = "CHECK"
    else:
        state = "READY"

    away_score = float(away_contract.get("profile_score") or 0.0)
    home_score = float(home_contract.get("profile_score") or 0.0)
    away_contract["profile_edge"] = (
        "Better scoring profile" if away_score >= home_score else "Profile disadvantage"
    )
    home_contract["profile_edge"] = (
        "Better scoring profile" if home_score > away_score else "Profile disadvantage"
    )
    return {
        "away": away_contract,
        "home": home_contract,
        "state": state,
        "ready": state == "READY",
        "insights": _insights(away_contract, home_contract),
        "summary": _summary(away_contract, home_contract),
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
    }


def _metric(label: str, value: Any, *, kind: str = "number", css: str = "", title: str = "") -> str:
    if kind == "rank":
        shown = f"#{int(value)}" if value is not None else "—"
    elif kind == "text":
        shown = _clean(value) or "—"
    elif kind == "signed":
        shown = _display_num(value, signed=True)
    else:
        shown = _display_num(value)
    return (
        f'<div class="gt167-metric {escape(css)}" title="{escape(title)}">'
        f'<b>{escape(shown)}</b><span>{escape(label)}</span></div>'
    )


def _card(team: Mapping[str, Any], *, home_side: bool) -> str:
    logo = _clean(team.get("logo"))
    logo_html = (
        f'<img class="gt167-logo" src="{escape(logo)}" alt="{escape(_clean(team.get("team")))} logo"/>'
        if logo
        else '<span style="font-size:24px">🏈</span>'
    )
    identity_meta = " • ".join(
        part
        for part in (
            _clean(team.get("conference")).upper(),
            _clean(team.get("classification")).upper(),
        )
        if part
    ) or "PROFILE"

    diff = team.get("point_diff_pg")
    diff_css = ""
    if diff is not None:
        diff_css = "good" if float(diff) >= 0 else "bad"

    off_rank_title = "Exact efficiency rank when supplied; otherwise current NCAA scoring/total-offense rank proxy."
    def_rank_title = "Exact efficiency rank when supplied; otherwise current NCAA scoring/total-defense rank proxy."

    missing = list(team.get("missing_required") or []) + list(team.get("missing_advanced") or [])
    missing_html = ""
    if missing:
        readable = ", ".join(str(field).replace("_", " ").title() for field in missing)
        missing_html = f'<div class="gt167-missing">Data still limited: {escape(readable)}</div>'

    return f"""
<div class="gt167-profile {'home' if home_side else 'away'}" data-testid="gt167-step2-{'home' if home_side else 'away'}">
  <div class="gt167-teamhead">
    <div class="gt167-logo-wrap">{logo_html}</div>
    <div class="gt167-teamname"><b>{escape(_clean(team.get('team')) or ('Home' if home_side else 'Away'))}</b><span>{escape(identity_meta)}</span></div>
    <div class="gt167-record"><b>{escape(_clean(team.get('record')) or '—')}</b><span>RECORD</span></div>
  </div>
  <div class="gt167-metrics">
    {_metric('Sample Games', team.get('sample_games'), kind='text')}
    {_metric('Points / Game', team.get('ppg'), css='info')}
    {_metric('Allowed / Game', team.get('allowed_pg'))}
    {_metric('Yards / Play', team.get('yards_per_play'), css='info')}
    {_metric('Pts / Drive', team.get('points_per_drive'))}
    {_metric('Off Eff Rank', team.get('off_eff_rank'), kind='rank', css='good', title=off_rank_title)}
    {_metric('YPP Allowed', team.get('yards_per_play_allowed'))}
    {_metric('Pts/Drive Allowed', team.get('points_per_drive_allowed'))}
    {_metric('Def Eff Rank', team.get('def_eff_rank'), kind='rank', css='info', title=def_rank_title)}
    {_metric('Point Diff / Game', team.get('point_diff_pg'), kind='signed', css=diff_css)}
    {_metric('Home/Away Split', team.get('split_summary'), kind='text')}
    {_metric('Recent Form', team.get('recent_form'), kind='text', css='good')}
  </div>
  <div class="gt167-read-pair">
    <div class="gt167-read"><span>Offense</span><b>{escape(_clean(team.get('offense_label')))}</b></div>
    <div class="gt167-read"><span>Defense</span><b>{escape(_clean(team.get('defense_label')))}</b></div>
  </div>
  <div class="gt167-edge"><span>🏆 PROFILE EDGE</span><span>»</span><strong>{escape(_clean(team.get('profile_edge')))}</strong></div>
  <div class="gt167-profile-read"><span>Profile Read</span><b>{escape(_clean(team.get('profile_read')))}</b></div>
  {missing_html}
</div>"""


def render_step2_html(
    status: str,
    identity: Mapping[str, Any] | None,
    away: Mapping[str, Any] | None,
    home: Mapping[str, Any] | None,
) -> str:
    contract = build_step2_contract(identity, away, home)
    a, h = contract["away"], contract["home"]
    state = str(contract["state"])
    state_css = "ready" if state == "READY" else "limited" if state == "DATA LIMITED" else "check"

    insight_html = "".join(
        f'<div class="gt167-insight {escape(row["css"])}"><span>{escape(row["label"])}</span><b>{escape(row["value"])}</b></div>'
        for row in contract["insights"]
    )
    subtitle = "Record • PPG • Allowed • Yards/Play • Pts/Drive • Efficiency • Point Diff • Splits • Recent Form"

    return f"""
<details class="gt159-step gt167-step2 {state_css}" data-testid="gt157-step-2" data-step2-state="{escape(state)}" open>
  <summary>
    <span class="gt159-num">2</span>
    <span class="gt159-stepcopy"><b>Team Performance Profile</b><span>{escape(subtitle)}</span></span>
    <span class="gt159-state {state_css}">{escape(state)}</span>
  </summary>
  <div class="gt159-stepbody gt167-step2-body">
    <div class="gt167-team-pair">
      {_card(a, home_side=False)}
      <div class="gt167-vs">VS</div>
      {_card(h, home_side=True)}
    </div>
    <div class="gt167-insights" data-testid="gt167-step2-insights">
      <div class="gt167-insight-title">💡 WHAT STEP 2 TELLS YOU</div>
      <div class="gt167-insight-grid">{insight_html}</div>
      <div class="gt167-summary" data-testid="gt167-step2-summary"><strong>▣ STEP 2 SUMMARY</strong><i></i><span>{escape(str(contract["summary"]))}</span></div>
    </div>
  </div>
</details>"""


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP2_ADVANCED_FIELDS",
    "STEP2_CSS",
    "STEP2_PRESENTATION_MARKER",
    "STEP2_REQUIRED_FIELDS",
    "build_step2_contract",
    "build_team_profile_contract",
    "render_step2_html",
]
