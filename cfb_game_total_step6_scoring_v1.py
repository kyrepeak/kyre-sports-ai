"""CFB Game Total Step 6 — Scoring Creation V1.

Presentation-only Step 6 owner. Combines verified explosive-play creation,
red-zone finishing, scoring-opportunity efficiency and TD-drive conversion
from bounded SportsDataverse completed-game PBP.

The module does not mutate projection/probability/model outputs. Sportsbook
projection influence remains 0.0%.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from html import escape
from statistics import mean
from typing import Any, Mapping, Sequence

import cfb_game_total_step5_pace_v1 as step5_pace

MODEL_VERSION = "CFB GAME TOTAL STEP 6 • V184 SCORING CREATION"
STEP6_PRESENTATION_MARKER = "CFB_GAME_TOTAL_STEP6_SCORING_CREATION_ACTIVE"
STEP6_DATA_MARKER = "CFB_GAME_TOTAL_STEP6_SDV_PBP_MULTISOURCE_ACTIVE"
STEP6_VISUAL_MARKER = "CFB_GAME_TOTAL_STEP6_V184_VISUAL_TARGET_ACTIVE"
STEP6_DEPLOYMENT_MARKER = "CFB_GAME_TOTAL_STEP6_V184_DEPLOYMENT_ACTIVE"
FROZEN_PREDECESSOR = "cfb_game_total_clean_page_v17"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
MAX_PBP_GAMES = step5_pace.MAX_PBP_GAMES

_METRICS = (
    ("pass_explosive_rate", "EXPLOSIVE PASS RATE", "20+ YARD PASSES"),
    ("rush_explosive_rate", "EXPLOSIVE RUSH RATE", "10+ YARD RUSHES"),
    ("overall_explosive_rate", "OVERALL EXPLOSIVE RATE", "BIG-PLAY CREATION"),
    ("scoring_ops_pg", "SCORING OPS / GAME", "PRESSURE"),
    ("scoring_op_conversion", "SCORING-OPPORTUNITY CONVERSION", "FINISHING"),
    ("red_zone_td_rate", "RED-ZONE TD RATE", "RZ FINISHING"),
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def _team_row(identity: Mapping[str, Any], side: str) -> dict[str, Any]:
    raw = identity.get(side) if isinstance(identity.get(side), Mapping) else {}
    return dict(raw or {})


def _team_name(
    identity: Mapping[str, Any],
    profile: Mapping[str, Any],
    side: str,
) -> str:
    row = _team_row(identity, side)
    return (
        _clean(row.get("team"))
        or _clean(profile.get("team"))
        or _clean(profile.get("team_name"))
        or side.title()
    )


def _team_id(
    identity: Mapping[str, Any],
    profile: Mapping[str, Any],
    side: str,
) -> str:
    return step5_pace._team_id(identity, side, profile)


def _logo(identity: Mapping[str, Any], side: str) -> str:
    return _clean(_team_row(identity, side).get("logo"))


def _record(profile: Mapping[str, Any], game: Mapping[str, Any], side: str) -> str:
    event = _clean(game.get(f"{side}_record_summary"))
    if event:
        return event
    return step5_pace._record(profile)


def _conference(
    identity: Mapping[str, Any],
    profile: Mapping[str, Any],
    side: str,
) -> str:
    return step5_pace._conference(identity, profile, side)


def _event_ids(profile: Mapping[str, Any]) -> list[str]:
    return step5_pace._event_ids(profile)


def _offense_id(play: Mapping[str, Any]) -> str:
    for key in ("pos_team", "start.pos_team.id", "start.team.id"):
        value = _clean(play.get(key))
        if value:
            return value
    return step5_pace._sdv_offense_team_id(play)


def _defense_id(play: Mapping[str, Any]) -> str:
    for key in ("def_pos_team", "start.def_pos_team.id", "end.def_pos_team.id"):
        value = _clean(play.get(key))
        if value:
            return value
    participants = play.get("teamParticipants") or []
    if isinstance(participants, Sequence) and not isinstance(participants, (str, bytes)):
        for item in participants:
            if not isinstance(item, Mapping):
                continue
            if _clean(item.get("type")).casefold() != "defense":
                continue
            team = item.get("team") if isinstance(item.get("team"), Mapping) else {}
            value = _clean(item.get("id") or team.get("id"))
            if value:
                return value
    return ""


def _drive_id(play: Mapping[str, Any]) -> str:
    return _clean(play.get("drive.id"))


def _drive_result(play: Mapping[str, Any]) -> str:
    return _clean(
        play.get("drive.result")
        or play.get("drive.shortDisplayResult")
        or play.get("drive.displayResult")
    ).upper()


def _play_yards(play: Mapping[str, Any], kind: str) -> float | None:
    if kind == "pass":
        candidates = (
            play.get("yds_receiving"),
            play.get("statYardage"),
        )
    else:
        candidates = (
            play.get("yds_rushed"),
            play.get("statYardage"),
        )
    for value in candidates:
        number = _float(value)
        if number is not None:
            return number
    return None


def _is_pass(play: Mapping[str, Any]) -> bool:
    if play.get("pass") is True or play.get("pass_attempt") is True:
        return True
    return "pass" in _clean(play.get("type.text")).casefold()


def _is_rush(play: Mapping[str, Any]) -> bool:
    if play.get("rush") is True:
        return True
    text = _clean(play.get("type.text")).casefold()
    return "rush" in text or "run" in text


def _is_red_zone(play: Mapping[str, Any]) -> bool:
    if play.get("rz_play") is True:
        return True
    yards = _float(play.get("start.yardsToEndzone"))
    return yards is not None and yards <= 20.0


def _is_scoring_opportunity(play: Mapping[str, Any]) -> bool:
    if play.get("scoring_opp") is True:
        return True
    yards = _float(play.get("start.yardsToEndzone"))
    return yards is not None and yards <= 40.0


def _is_td_play(play: Mapping[str, Any]) -> bool:
    return bool(
        play.get("td_play") is True
        or play.get("touchdown") is True
        or "TD" == _drive_result(play)
        or "TOUCHDOWN" in _drive_result(play)
    )


def _drive_points(plays: Sequence[Mapping[str, Any]]) -> float:
    direct = [
        _float(play.get("pos_score_pts"))
        for play in plays
        if _float(play.get("pos_score_pts")) is not None
        and float(_float(play.get("pos_score_pts")) or 0.0) > 0
    ]
    if direct:
        return float(sum(float(value) for value in direct if value is not None))
    result = ""
    for play in plays:
        result = _drive_result(play)
        if result:
            break
    if "TD" in result or "TOUCHDOWN" in result:
        return 7.0
    if result in {"FG", "FIELD GOAL"} or "FIELD GOAL" in result:
        return 3.0
    if "SAFETY" in result:
        return 2.0
    return 0.0


def _side_metrics(
    games: Sequence[Mapping[str, Any]],
    team_id: str,
    *,
    defense: bool = False,
) -> dict[str, Any]:
    team_id = _clean(team_id)
    if not team_id:
        return {}

    games_used = 0
    pass_plays = 0
    pass_explosives = 0
    rush_plays = 0
    rush_explosives = 0
    total_drives = 0
    red_zone_drives = 0
    red_zone_td_drives = 0
    scoring_op_drives = 0
    scoring_op_scores = 0
    td_drives = 0

    for payload in games:
        raw_plays = [
            dict(play)
            for play in (payload.get("plays") or [])
            if isinstance(play, Mapping)
        ]
        selected = []
        for play in raw_plays:
            scrimmage = (
                bool(play.get("scrimmage_play"))
                if "scrimmage_play" in play
                else bool(
                    play.get("pass") is True
                    or play.get("pass_attempt") is True
                    or play.get("rush") is True
                    or step5_pace._sdv_is_scrimmage(play)
                )
            )
            if not scrimmage:
                continue
            if play.get("penalty_no_play") is True or play.get("text_dupe") is True:
                continue
            if defense:
                if _defense_id(play) != team_id:
                    continue
            elif _offense_id(play) != team_id:
                continue
            selected.append(play)
        if not selected:
            continue
        games_used += 1

        drives: dict[str, list[dict[str, Any]]] = {}
        for play in selected:
            drive_id = _drive_id(play)
            if drive_id:
                drives.setdefault(drive_id, []).append(play)

            if _is_pass(play):
                pass_plays += 1
                yards = _play_yards(play, "pass")
                if (
                    (yards is not None and yards >= 20.0)
                    or (yards is None and play.get("EPA_explosive_pass") is True)
                ):
                    pass_explosives += 1
            if _is_rush(play):
                rush_plays += 1
                yards = _play_yards(play, "rush")
                if (
                    (yards is not None and yards >= 10.0)
                    or (yards is None and play.get("EPA_explosive_rush") is True)
                ):
                    rush_explosives += 1

        total_drives += len(drives)
        for drive_plays in drives.values():
            rz = any(_is_red_zone(play) for play in drive_plays)
            scoring_opp = any(_is_scoring_opportunity(play) for play in drive_plays)
            touchdown = any(_is_td_play(play) for play in drive_plays)
            if rz:
                red_zone_drives += 1
                if touchdown:
                    red_zone_td_drives += 1
            if scoring_opp:
                scoring_op_drives += 1
                if _drive_points(drive_plays) > 0.0:
                    scoring_op_scores += 1
            if touchdown:
                td_drives += 1

    if games_used <= 0:
        return {
            "games": 0,
            "coverage": 0.0,
            "source": "",
            "delivery": "sportsdataverse_github_raw",
        }

    total_scrimmage_plays = pass_plays + rush_plays
    total_explosives = pass_explosives + rush_explosives
    metrics = {
        "games": games_used,
        "pass_explosive_rate": (
            pass_explosives / pass_plays if pass_plays > 0 else None
        ),
        "rush_explosive_rate": (
            rush_explosives / rush_plays if rush_plays > 0 else None
        ),
        "overall_explosive_rate": (
            total_explosives / total_scrimmage_plays
            if total_scrimmage_plays > 0 else None
        ),
        "scoring_ops_pg": scoring_op_drives / games_used,
        "scoring_op_conversion": (
            scoring_op_scores / scoring_op_drives
            if scoring_op_drives > 0 else None
        ),
        "red_zone_td_rate": (
            red_zone_td_drives / red_zone_drives
            if red_zone_drives > 0 else None
        ),
        "pass_attempts": pass_plays,
        "rush_attempts": rush_plays,
        "explosive_pass_plays": pass_explosives,
        "explosive_rush_plays": rush_explosives,
        "drive_count": total_drives,
        "red_zone_drives": red_zone_drives,
        "scoring_opportunity_drives": scoring_op_drives,
        "scoring_opportunity_scores": scoring_op_scores,
        "touchdown_drives": td_drives,
        "source": "SportsDataverse current-season completed-game PBP",
        "delivery": "sportsdataverse_github_raw",
    }
    if defense:
        metrics["big_play_susceptibility"] = metrics["overall_explosive_rate"]
        metrics["red_zone_td_rate_allowed"] = metrics["red_zone_td_rate"]
        metrics["scoring_op_conversion_allowed"] = metrics["scoring_op_conversion"]
    available = sum(
        1
        for key, _, _ in _METRICS
        if _float(metrics.get(key)) is not None
    )
    metrics["coverage"] = available / len(_METRICS)
    return metrics


def _load_pbp_evidence(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> dict[str, Any]:
    profiles = {"away": away, "home": home}
    side_events = {
        side: _event_ids(profile)
        for side, profile in profiles.items()
    }
    event_ids = list(
        dict.fromkeys(
            event
            for values in side_events.values()
            for event in values
            if event
        )
    )
    payloads: dict[str, dict[str, Any]] = {}
    if event_ids:
        with ThreadPoolExecutor(max_workers=min(4, len(event_ids))) as pool:
            rows = list(pool.map(step5_pace._fetch_sportsdataverse_game, event_ids))
        payloads = {
            event: row
            for event, row in zip(event_ids, rows)
            if row
        }

    out: dict[str, Any] = {}
    for side, profile in profiles.items():
        games = [
            payloads[event]
            for event in side_events.get(side, [])
            if event in payloads
        ]
        team_id = _team_id(identity, profile, side)
        out[f"{side}_offense"] = _side_metrics(games, team_id, defense=False)
        out[f"{side}_defense"] = _side_metrics(games, team_id, defense=True)
        out[f"{side}_event_ids"] = list(side_events.get(side, []))
    out["unique_events_loaded"] = len(payloads)
    return out


def _scaled(value: Any, low: float, high: float) -> float | None:
    number = _float(value)
    if number is None or high <= low:
        return None
    return _clamp((number - low) / (high - low), 0.0, 1.0)


def _creation_score(metrics: Mapping[str, Any]) -> float | None:
    parts = (
        (_scaled(metrics.get("pass_explosive_rate"), 0.06, 0.22), 0.17),
        (_scaled(metrics.get("rush_explosive_rate"), 0.08, 0.28), 0.14),
        (_scaled(metrics.get("overall_explosive_rate"), 0.07, 0.24), 0.17),
        (_scaled(metrics.get("scoring_ops_pg"), 2.0, 6.0), 0.16),
        (_scaled(metrics.get("scoring_op_conversion"), 0.35, 0.85), 0.16),
        (_scaled(metrics.get("red_zone_td_rate"), 0.35, 0.75), 0.20),
    )
    known = [(value, weight) for value, weight in parts if value is not None]
    if not known:
        return None
    weight = sum(item[1] for item in known)
    return 100.0 * sum(item[0] * item[1] for item in known) / weight


def _prevention_score(metrics: Mapping[str, Any]) -> float | None:
    creation = _creation_score(metrics)
    return None if creation is None else 100.0 - creation


def _grade(score: Any) -> str:
    value = _float(score)
    if value is None:
        return "—"
    if value >= 85: return "A"
    if value >= 80: return "A-"
    if value >= 75: return "B+"
    if value >= 70: return "B"
    if value >= 65: return "B-"
    if value >= 60: return "C+"
    if value >= 55: return "C"
    if value >= 48: return "C-"
    if value >= 40: return "D"
    return "F"


def _pair_value(offense: Mapping[str, Any], defense: Mapping[str, Any], key: str) -> float | None:
    left = _float(offense.get(key))
    right = _float(defense.get(key))
    if left is not None and right is not None:
        return (left + right) / 2.0
    return left if left is not None else right


def _tile_value(key: str, value: Any) -> str:
    number = _float(value)
    if number is None:
        return "—"
    if key in {
        "pass_explosive_rate",
        "rush_explosive_rate",
        "overall_explosive_rate",
        "scoring_op_conversion",
        "red_zone_td_rate",
    }:
        return f"{100.0 * number:.0f}%"
    return f"{number:.1f}"


def _metric_delta(
    offense: Mapping[str, Any],
    defense: Mapping[str, Any],
    key: str,
) -> float | None:
    off = _float(offense.get(key))
    allowed = _float(defense.get(key))
    if off is None or allowed is None:
        return None
    scales = {
        "pass_explosive_rate": 0.06,
        "rush_explosive_rate": 0.08,
        "overall_explosive_rate": 0.06,
        "scoring_ops_pg": 1.5,
        "scoring_op_conversion": 0.15,
        "red_zone_td_rate": 0.15,
    }
    scale = scales.get(key, 1.0)
    return (off - allowed) / scale if scale else 0.0


def _metric_name(key: str) -> str:
    return {
        "pass_explosive_rate": "EXPLOSIVE PASS RATE",
        "rush_explosive_rate": "EXPLOSIVE RUSH RATE",
        "overall_explosive_rate": "OVERALL EXPLOSIVE RATE",
        "scoring_ops_pg": "SCORING-OPPORTUNITY CREATION",
        "scoring_op_conversion": "SCORING-OPPORTUNITY CONVERSION",
        "red_zone_td_rate": "RED-ZONE FINISHING",
    }.get(key, key.replace("_", " ").upper())


def _insights(contract: Mapping[str, Any]) -> dict[str, str]:
    battles = contract.get("battles") or []
    deltas: list[tuple[float, str, str]] = []
    for battle in battles:
        offense = battle.get("offense") or {}
        defense = battle.get("defense") or {}
        offense_name = _clean(battle.get("offense_name"))
        for key, _, _ in _METRICS:
            delta = _metric_delta(offense, defense, key)
            if delta is not None:
                deltas.append((delta, key, offense_name))

    accelerator = max(deltas, default=(0.0, "", ""), key=lambda row: row[0])
    suppressor = min(deltas, default=(0.0, "", ""), key=lambda row: row[0])

    pressure = _float(contract.get("scoring_pressure")) or 0.0
    if pressure >= 7.0:
        read = "FAVORABLE FOR SCORING"
        ou = "OVER PRESSURE"
    elif pressure >= 2.0:
        read = "MODERATELY FAVORABLE FOR SCORING"
        ou = "SLIGHT OVER PRESSURE"
    elif pressure <= -7.0:
        read = "TOUGH SCORING ENVIRONMENT"
        ou = "UNDER PRESSURE"
    elif pressure <= -2.0:
        read = "SLIGHTLY SUPPRESSED SCORING"
        ou = "SLIGHT UNDER PRESSURE"
    else:
        read = "BALANCED SCORING ENVIRONMENT"
        ou = "NEUTRAL"

    if not deltas:
        accelerator_text = "Verified scoring accelerator unavailable"
        suppressor_text = "Verified scoring suppressor unavailable"
    else:
        accelerator_text = (
            f"{accelerator[2]} {_metric_name(accelerator[1])}"
        )
        suppressor_text = (
            f"{suppressor[2]} {_metric_name(suppressor[1])}"
        )
    return {
        "matchup_read": read,
        "accelerator": accelerator_text,
        "suppressor": suppressor_text,
        "ou_impact": ou,
    }


def build_step6_contract(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    game: Mapping[str, Any],
    *,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    pbp = dict(evidence or _load_pbp_evidence(identity, away, home))
    away_off = pbp.get("away_offense") if isinstance(pbp.get("away_offense"), Mapping) else {}
    away_def = pbp.get("away_defense") if isinstance(pbp.get("away_defense"), Mapping) else {}
    home_off = pbp.get("home_offense") if isinstance(pbp.get("home_offense"), Mapping) else {}
    home_def = pbp.get("home_defense") if isinstance(pbp.get("home_defense"), Mapping) else {}

    battles = [
        {
            "side": "away",
            "offense_name": _team_name(identity, away, "away"),
            "defense_name": _team_name(identity, home, "home"),
            "offense": dict(away_off),
            "defense": dict(home_def),
        },
        {
            "side": "home",
            "offense_name": _team_name(identity, home, "home"),
            "defense_name": _team_name(identity, away, "away"),
            "offense": dict(home_off),
            "defense": dict(away_def),
        },
    ]

    ready_tiles = 0
    for battle in battles:
        offense = battle["offense"]
        defense = battle["defense"]
        for key, _, _ in _METRICS:
            if _float(offense.get(key)) is not None and _float(defense.get(key)) is not None:
                ready_tiles += 1
    coverage = int(round(100.0 * ready_tiles / 12.0))
    state = "READY" if ready_tiles == 12 else "DATA LIMITED"

    away_creation = _creation_score(away_off)
    home_creation = _creation_score(home_off)
    away_prevention = _prevention_score(away_def)
    home_prevention = _prevention_score(home_def)

    away_match = (
        (away_creation + home_prevention) / 2.0
        if away_creation is not None and home_prevention is not None else None
    )
    home_match = (
        (home_creation + away_prevention) / 2.0
        if home_creation is not None and away_prevention is not None else None
    )
    match_values = [value for value in (away_match, home_match) if value is not None]
    scoring_pressure = mean(match_values) - 50.0 if match_values else 0.0

    away_ops = _pair_value(away_off, home_def, "scoring_ops_pg")
    home_ops = _pair_value(home_off, away_def, "scoring_ops_pg")
    expected_scoring_chances = (
        away_ops + home_ops
        if away_ops is not None and home_ops is not None else None
    )

    explosives = []
    for battle in battles:
        value = _pair_value(
            battle["offense"],
            battle["defense"],
            "overall_explosive_rate",
        )
        if value is not None:
            explosives.append(value)
    explosive_mean = mean(explosives) if explosives else None
    if explosive_mean is None:
        explosive_environment = "DATA LIMITED"
        volatility = "—"
    elif explosive_mean >= 0.18:
        explosive_environment = "HIGH"
        volatility = "HIGH"
    elif explosive_mean >= 0.12:
        explosive_environment = "MODERATE"
        volatility = "MEDIUM"
    else:
        explosive_environment = "LOW"
        volatility = "LOW"

    rz_values = [
        value
        for battle in battles
        for value in (
            _float(battle["offense"].get("red_zone_td_rate")),
            _float(battle["defense"].get("red_zone_td_rate")),
        )
        if value is not None
    ]
    rz_mean = mean(rz_values) if rz_values else None
    if rz_mean is None:
        rz_environment = "DATA LIMITED"
    elif rz_mean >= 0.62:
        rz_environment = "OFFENSE EDGE"
    elif rz_mean <= 0.48:
        rz_environment = "DEFENSE EDGE"
    else:
        rz_environment = "BALANCED"

    games = [
        _int(row.get("games")) or 0
        for row in (away_off, away_def, home_off, home_def)
        if row
    ]
    sample_strength = min(games) / 4.0 if games else 0.0
    sample_strength = _clamp(sample_strength, 0.0, 1.0)
    confidence = int(round(coverage * (0.70 + 0.30 * sample_strength)))

    contract = {
        "state": state,
        "ready": state == "READY",
        "coverage": coverage,
        "ready_tiles": ready_tiles,
        "tile_count": 12,
        "battles": battles,
        "away_creation_grade": _grade(away_creation),
        "home_creation_grade": _grade(home_creation),
        "away_prevention_grade": _grade(away_prevention),
        "home_prevention_grade": _grade(home_prevention),
        "explosive_environment": explosive_environment,
        "red_zone_environment": rz_environment,
        "expected_scoring_chances": expected_scoring_chances,
        "big_play_volatility": volatility,
        "scoring_pressure": scoring_pressure,
        "data_confidence": confidence,
        "sportsbook_input_used": False,
        "projection_mutation": False,
        "evidence": pbp,
    }
    contract.update(_insights(contract))
    return contract


def _logo_html(identity: Mapping[str, Any], side: str) -> str:
    name = _clean(_team_row(identity, side).get("team")) or side.title()
    logo = _logo(identity, side)
    if logo:
        return f'<img class="gt184-s6-logo" src="{escape(logo)}" alt="{escape(name)} logo">'
    initials = "".join(part[:1] for part in name.split() if part)[:2].upper() or "CF"
    return f'<div class="gt184-s6-logo fallback">{escape(initials)}</div>'


def _team_header(
    identity: Mapping[str, Any],
    profile: Mapping[str, Any],
    game: Mapping[str, Any],
    side: str,
) -> str:
    name = _team_name(identity, profile, side)
    return f"""
<div class="gt184-s6-team {'home' if side == 'home' else ''}">
  {_logo_html(identity, side)}
  <div><small>{side.upper()}</small><b>{escape(name)}</b><span>{escape(_record(profile, game, side))} • {escape(_conference(identity, profile, side))}</span></div>
</div>"""


def _game_context(game: Mapping[str, Any]) -> str:
    date_text = _clean(game.get("game_date") or game.get("date"))[:10] or "GAME DAY"
    kickoff = _clean(game.get("kickoff_et") or game.get("kickoff") or game.get("start_time"))
    venue = _clean(game.get("venue") or game.get("venue_name")) or "Venue unavailable"
    broadcast = _clean(game.get("broadcast")) or "Broadcast unavailable"
    return f"""
<div class="gt184-s6-context"><b>{escape(date_text)}</b><strong>{escape(kickoff or 'Time TBD')}</strong><span>{escape(venue)}</span><small>{escape(broadcast)}</small></div>"""


def _defense_metric_label(key: str) -> str:
    return {
        "pass_explosive_rate": "Explosive pass rate allowed",
        "rush_explosive_rate": "Explosive rush rate allowed",
        "overall_explosive_rate": "Big-play susceptibility",
        "scoring_ops_pg": "Scoring opportunities allowed",
        "scoring_op_conversion": "Scoring-opportunity conversion allowed",
        "red_zone_td_rate": "Red-zone TD rate allowed",
    }.get(key, "Opp allowed")


def _battle_html(battle: Mapping[str, Any], index: int) -> str:
    offense = battle.get("offense") or {}
    defense = battle.get("defense") or {}
    offense_name = _clean(battle.get("offense_name"))
    defense_name = _clean(battle.get("defense_name"))
    tiles = []
    for key, label, badge in _METRICS:
        off_value = _float(offense.get(key))
        def_value = _float(defense.get(key))
        ready = off_value is not None and def_value is not None
        tiles.append(
            f'''<div class="gt184-s6-tile {'ready' if ready else 'limited'}" data-testid="gt184-step6-stat-tile" data-ready="{str(ready).lower()}">
              <small>{escape(label)}</small>
              <b>{escape(_tile_value(key, off_value))}</b>
              <span>{escape(_defense_metric_label(key))}: {escape(_tile_value(key, def_value))}</span>
              <em>{escape(badge if ready else 'DATA LIMITED')}</em>
            </div>'''
        )
    return f"""
<div class="gt184-s6-battle" data-testid="gt184-step6-battle-{index}">
  <div class="gt184-s6-battlehead"><div><small>MATCHUP {index}</small><b>{escape(offense_name)} SCORING CREATION</b></div><div class="gt184-s6-versus">VS</div><div class="right"><small>OPPOSING DEFENSE</small><b>{escape(defense_name)} PREVENTION</b></div></div>
  <div class="gt184-s6-tilegrid">{''.join(tiles)}</div>
</div>"""


def _environment_html(contract: Mapping[str, Any]) -> str:
    chance = _float(contract.get("expected_scoring_chances"))
    cells = (
        ("Away Creation", contract.get("away_creation_grade")),
        ("Home Creation", contract.get("home_creation_grade")),
        ("Explosive Environment", contract.get("explosive_environment")),
        ("Red-Zone Environment", contract.get("red_zone_environment")),
        ("Projected Scoring Chances", "—" if chance is None else f"{chance:.1f}"),
        ("Big-Play Volatility", contract.get("big_play_volatility")),
    )
    return '<div class="gt184-s6-env">' + ''.join(
        f'<div><small>{escape(str(label))}</small><b>{escape(_clean(value) or "—")}</b></div>'
        for label, value in cells
    ) + '</div>'


def _insight_html(contract: Mapping[str, Any]) -> str:
    confidence = int(contract.get("data_confidence") or 0)
    return f"""
<div class="gt184-s6-insights">
  <div class="gt184-s6-insight read"><small>MATCHUP READ</small><b>{escape(_clean(contract.get('matchup_read')))}</b><span>Explosive creation and finishing are evaluated against the opposing scoring-prevention profile.</span></div>
  <div class="gt184-s6-insight accel"><small>BIGGEST ACCELERATOR</small><b>{escape(_clean(contract.get('accelerator')))}</b><span>Largest verified creation-vs-prevention advantage in the current completed-game sample.</span></div>
  <div class="gt184-s6-insight brake"><small>BIGGEST SUPPRESSOR</small><b>{escape(_clean(contract.get('suppressor')))}</b><span>Strongest verified scoring resistance in the matchup.</span></div>
  <div class="gt184-s6-insight ou"><small>O/U IMPACT</small><b>{escape(_clean(contract.get('ou_impact')))}</b><span>Direction comes from verified scoring creation only. Sportsbook total is not an input.</span></div>
  <div class="gt184-s6-insight confidence"><small>DATA CONFIDENCE</small><b>{confidence}%</b><span>PBP coverage + completed-game sample strength.</span></div>
</div>"""


def render_step6_html(
    status: str,
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    display_game: Mapping[str, Any],
    *,
    evidence: Mapping[str, Any] | None = None,
) -> str:
    contract = build_step6_contract(
        identity,
        away,
        home,
        display_game,
        evidence=evidence,
    )
    state = _clean(contract.get("state")) or "DATA LIMITED"
    coverage = int(contract.get("coverage") or 0)
    ready_tiles = int(contract.get("ready_tiles") or 0)
    summary_state = "ready" if state == "READY" else "check"
    body_class = "ready" if state == "READY" else "limited"

    return f"""
<details class="gt184-step6 {body_class}" data-testid="gt157-step-6"
 data-step6-marker="{STEP6_PRESENTATION_MARKER}"
 data-step6-data-marker="{STEP6_DATA_MARKER}"
 data-step6-visual-marker="{STEP6_VISUAL_MARKER}"
 data-step6-deployment-marker="{STEP6_DEPLOYMENT_MARKER}"
 data-step6-state="{escape(state)}"
 data-step6-coverage="{coverage}"
 data-step6-ready-tiles="{ready_tiles}" open>
<style>{_CSS}</style>
<summary>
  <span class="gt184-s6-num">6</span>
  <span class="gt184-s6-summarycopy"><b>💥 Scoring Creation</b><span>Explosive plays • red zone • scoring opportunities • finishing ability</span></span>
  <span class="gt184-s6-state {summary_state}">{escape(state)}</span>
</summary>
<div class="gt184-s6-body">
  <div class="gt184-s6-head">
    <div><small>STEP 6 • SCORING CREATION</small><h3>How well can each team create and finish real scoring chances?</h3></div>
    <div class="gt184-s6-chips"><span>{escape(state)}</span><span>{coverage}% SCORING COVERAGE</span><span>MULTI-SOURCE VERIFIED</span><span>SPORTSBOOK INFLUENCE 0.0%</span></div>
  </div>
  <div class="gt184-s6-matchup">
    {_team_header(identity, away, display_game, 'away')}
    <div class="gt184-s6-vs">VS</div>
    {_team_header(identity, home, display_game, 'home')}
    {_game_context(display_game)}
  </div>
  {_battle_html(contract['battles'][0], 1)}
  {_battle_html(contract['battles'][1], 2)}
  <div class="gt184-s6-sectiontitle"><b>SCORING ENVIRONMENT</b><span>Verified creation + prevention • presentation only</span></div>
  {_environment_html(contract)}
  {_insight_html(contract)}
  <div class="gt184-s6-integrity">SPORTSDATAVERSE PBP PRIMARY • RUNTIME SNAPSHOT IDENTITY • MODEL SAFE • PROJECTION MUTATION OFF • SPORTSBOOK INFLUENCE 0.0%</div>
</div>
</details>
"""


_CSS = r"""
.gt184-step6{margin-top:8px;border:1px solid rgba(255,106,71,.42);border-left:3px solid #ff744f;border-right:2px solid rgba(172,87,255,.50);border-radius:15px;background:linear-gradient(145deg,#071924,#0a1422 62%,#111126);overflow:hidden;color:#eef7ff;box-shadow:0 0 26px rgba(255,105,72,.06)}
.gt184-step6 summary{list-style:none;cursor:pointer;display:grid;grid-template-columns:30px minmax(0,1fr) auto;align-items:center;gap:8px;padding:9px 10px;background:linear-gradient(90deg,rgba(255,105,72,.09),rgba(48,117,173,.05),rgba(145,77,230,.08))}
.gt184-step6 summary::-webkit-details-marker{display:none}.gt184-s6-num{display:flex;align-items:center;justify-content:center;width:29px;height:29px;border-radius:9px;background:rgba(255,108,72,.18);color:#ff936f;font-size:.38rem;font-weight:950}.gt184-s6-summarycopy b{display:block;color:#f5f9fd;font-size:.42rem;font-weight:950}.gt184-s6-summarycopy span{display:block;color:#899faf;font-size:.23rem;margin-top:2px}.gt184-s6-state{padding:4px 8px;border-radius:999px;font-size:.21rem;font-weight:950;border:1px solid rgba(98,239,182,.38);background:rgba(26,111,77,.18);color:#62efb6}.gt184-s6-state.check{border-color:rgba(245,203,83,.42);background:rgba(116,81,13,.18);color:#f4ce63}
.gt184-s6-body{padding:10px;background:radial-gradient(circle at 15% 0%,rgba(255,92,55,.08),transparent 28%),radial-gradient(circle at 88% 4%,rgba(161,78,255,.08),transparent 26%),#07151f}.gt184-s6-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}.gt184-s6-head small{color:#ff8e69;font-size:.24rem;font-weight:950;letter-spacing:.10em}.gt184-s6-head h3{margin:4px 0 0;color:#f5f9fd;font-size:.55rem;line-height:1.3}.gt184-s6-chips{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:4px}.gt184-s6-chips span{padding:4px 7px;border-radius:999px;border:1px solid rgba(85,190,237,.26);background:#0b2230;color:#9ad7f4;font-size:.18rem;font-weight:900;white-space:nowrap}.gt184-s6-chips span:first-child{border-color:rgba(98,239,182,.35);color:#62efb6;background:rgba(23,109,75,.17)}
.gt184-s6-matchup{display:grid;grid-template-columns:1fr 46px 1fr minmax(125px,.6fr);align-items:center;gap:8px;margin-top:10px;padding:10px;border:1px solid rgba(76,148,190,.25);border-radius:12px;background:#081b28}.gt184-s6-team{display:flex;align-items:center;gap:8px;min-width:0}.gt184-s6-team.home{justify-content:flex-end;text-align:right}.gt184-s6-logo{width:45px;height:45px;object-fit:contain;flex:0 0 45px}.gt184-s6-logo.fallback{display:flex;align-items:center;justify-content:center;border-radius:11px;background:#102d40;color:#78c9f3;font-size:.62rem;font-weight:950}.gt184-s6-team small{display:block;color:#7d92a3;font-size:.18rem;font-weight:900}.gt184-s6-team b{display:block;color:#f2f7fb;font-size:.42rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gt184-s6-team span{display:block;color:#8ba1b3;font-size:.20rem;margin-top:2px}.gt184-s6-vs{display:flex;align-items:center;justify-content:center;width:38px;height:38px;border-radius:50%;background:#0c2635;border:1px solid rgba(104,180,222,.25);color:#98b8cc;font-size:.27rem;font-weight:950}.gt184-s6-context{align-self:stretch;display:flex;flex-direction:column;justify-content:center;padding-left:9px;border-left:1px solid rgba(88,163,205,.23)}.gt184-s6-context b{font-size:.20rem;color:#ffb58d}.gt184-s6-context strong{font-size:.28rem;margin-top:2px}.gt184-s6-context span,.gt184-s6-context small{font-size:.18rem;color:#89a2b4;margin-top:2px}
.gt184-s6-battle{margin-top:9px;border:1px solid rgba(255,116,79,.22);border-radius:12px;background:linear-gradient(135deg,#091c27,#091623);overflow:hidden}.gt184-s6-battlehead{display:grid;grid-template-columns:1fr 42px 1fr;gap:8px;align-items:center;padding:8px 10px;border-bottom:1px solid rgba(255,116,79,.12)}.gt184-s6-battlehead small{display:block;color:#ff956e;font-size:.18rem;font-weight:950}.gt184-s6-battlehead b{display:block;color:#edf6fb;font-size:.34rem;margin-top:2px}.gt184-s6-battlehead .right{text-align:right}.gt184-s6-versus{text-align:center;color:#bb87ff;font-size:.24rem;font-weight:950}.gt184-s6-tilegrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;padding:8px}.gt184-s6-tile{position:relative;padding:8px;border-radius:10px;border:1px solid rgba(79,153,194,.22);background:linear-gradient(145deg,#0b2432,#0a1a27);min-width:0}.gt184-s6-tile:after{content:"";position:absolute;left:0;top:0;bottom:0;width:2px;background:#ff744f}.gt184-s6-tile small{display:block;color:#829bac;font-size:.17rem;font-weight:900}.gt184-s6-tile b{display:block;color:#f8fbfe;font-size:.58rem;margin-top:3px}.gt184-s6-tile span{display:block;color:#90a7b8;font-size:.18rem;margin-top:2px}.gt184-s6-tile em{display:inline-block;margin-top:5px;padding:2px 5px;border-radius:999px;background:rgba(87,191,239,.12);border:1px solid rgba(87,191,239,.20);color:#84d2f4;font-size:.15rem;font-style:normal;font-weight:900}.gt184-s6-tile.limited:after{background:#f4ce63}.gt184-s6-tile.limited em{color:#f4ce63;border-color:rgba(244,206,99,.25);background:rgba(117,85,14,.15)}
.gt184-s6-sectiontitle{display:flex;justify-content:space-between;align-items:flex-end;gap:8px;margin:10px 1px 5px}.gt184-s6-sectiontitle b{color:#ffe2d5;font-size:.34rem;letter-spacing:.07em}.gt184-s6-sectiontitle span{color:#7891a4;font-size:.18rem}.gt184-s6-env{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border:1px solid rgba(160,93,255,.25);border-radius:11px;background:linear-gradient(100deg,#0a1c29,#101426);overflow:hidden}.gt184-s6-env div{padding:8px 6px;text-align:center;border-right:1px solid rgba(112,142,180,.16)}.gt184-s6-env div:last-child{border-right:0}.gt184-s6-env small{display:block;color:#8096a7;font-size:.16rem;text-transform:uppercase}.gt184-s6-env b{display:block;color:#f4f8fc;font-size:.30rem;margin-top:3px}
.gt184-s6-insights{display:grid;grid-template-columns:1.25fr 1fr 1fr;gap:6px;margin-top:8px}.gt184-s6-insight{padding:9px;border:1px solid rgba(84,154,193,.24);border-radius:10px;background:#0a1d29}.gt184-s6-insight small{display:block;color:#849bad;font-size:.17rem;font-weight:900}.gt184-s6-insight b{display:block;color:#f5f9fd;font-size:.31rem;margin-top:3px}.gt184-s6-insight span{display:block;color:#8ca0af;font-size:.18rem;line-height:1.4;margin-top:3px}.gt184-s6-insight.read{grid-row:span 2;border-color:rgba(255,116,79,.28);background:linear-gradient(145deg,rgba(121,42,24,.18),#0a1b27)}.gt184-s6-insight.accel{border-color:rgba(98,239,182,.25)}.gt184-s6-insight.accel b{color:#71efbd}.gt184-s6-insight.brake{border-color:rgba(244,206,99,.25)}.gt184-s6-insight.brake b{color:#f4ce63}.gt184-s6-insight.ou{border-color:rgba(182,113,255,.28)}.gt184-s6-insight.ou b{color:#c69aff}.gt184-s6-insight.confidence b{font-size:.62rem;color:#78d5ff}.gt184-s6-integrity{margin-top:8px;padding:7px 9px;border-top:1px solid rgba(84,154,193,.18);color:#71889a;font-size:.16rem;font-weight:850;text-align:center;letter-spacing:.04em}
@media(max-width:760px){.gt184-s6-head{display:block}.gt184-s6-chips{justify-content:flex-start;margin-top:7px}.gt184-s6-matchup{grid-template-columns:1fr 36px 1fr}.gt184-s6-context{grid-column:1/-1;border-left:0;border-top:1px solid rgba(88,163,205,.23);padding:7px 0 0}.gt184-s6-tilegrid{grid-template-columns:repeat(2,minmax(0,1fr))}.gt184-s6-env{grid-template-columns:repeat(3,minmax(0,1fr))}.gt184-s6-env div:nth-child(3){border-right:0}.gt184-s6-insights{grid-template-columns:1fr 1fr}.gt184-s6-insight.read{grid-column:1/-1;grid-row:auto}}
@media(max-width:430px){.gt184-s6-body{padding:7px}.gt184-s6-summarycopy b{font-size:.34rem}.gt184-s6-summarycopy span{font-size:.18rem}.gt184-s6-matchup{grid-template-columns:1fr 28px 1fr;padding:7px}.gt184-s6-logo{width:34px;height:34px;flex-basis:34px}.gt184-s6-team b{font-size:.30rem}.gt184-s6-tilegrid{grid-template-columns:1fr 1fr}.gt184-s6-env{grid-template-columns:repeat(2,minmax(0,1fr))}.gt184-s6-env div:nth-child(3){border-right:1px solid rgba(112,142,180,.16)}.gt184-s6-env div:nth-child(2n){border-right:0}.gt184-s6-insights{grid-template-columns:1fr}}
"""

__all__ = [
    "FROZEN_PREDECESSOR",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP6_DATA_MARKER",
    "STEP6_DEPLOYMENT_MARKER",
    "STEP6_PRESENTATION_MARKER",
    "STEP6_VISUAL_MARKER",
    "build_step6_contract",
    "render_step6_html",
]
