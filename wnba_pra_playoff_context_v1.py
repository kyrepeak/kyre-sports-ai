"""Playoff-aware slate context for the WNBA PRA product."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Mapping
import pandas as pd
import wnba_schedule_v25 as schedule
from wnba_api_client_v1 import KyreWNBAAPIClient, SUPPORTED_SEASON
from wnba_pra_source_fusion_v1 import SourceObservation, fuse_observations

@dataclass(frozen=True)
class PlayoffContext:
    selected_date: str
    effective_date: str
    today_has_game: bool
    games: pd.DataFrame
    next_game: Mapping[str, Any] | None
    competition_label: str
    series_label: str
    evidence_state: str
    sources: tuple[str, ...]
    off_day_message: str

def _corroborating_schedule(day: str) -> tuple[pd.DataFrame, Mapping[str, Any]]:
    schedule_fn = getattr(schedule, "_kyre_step7f_original_schedule_for_date", schedule.schedule_for_date)
    diag_fn = getattr(schedule, "_kyre_step7f_original_schedule_diagnostics", schedule.schedule_diagnostics)
    try:
        frame = schedule_fn(day)
        frame = frame.copy(deep=True) if isinstance(frame, pd.DataFrame) else pd.DataFrame()
    except Exception:
        frame = pd.DataFrame()
    try:
        diag = diag_fn(day)
        diag = dict(diag) if isinstance(diag, Mapping) else {}
    except Exception:
        diag = {}
    return frame, diag

def _team_name(team: Mapping[str, Any]) -> str:
    full = str(team.get("full_name") or "").strip()
    if full:
        return full
    return " ".join(str(team.get(k) or "").strip() for k in ("team_city", "team_name") if str(team.get(k) or "").strip())

def _api_frame(payload: Mapping[str, Any], day: str) -> tuple[pd.DataFrame, tuple[Mapping[str, Any], ...]]:
    games = payload.get("games") if isinstance(payload, Mapping) else None
    raw_games = tuple(g for g in (games or []) if isinstance(g, Mapping)) if isinstance(games, list) else ()
    rows = []
    for game in raw_games:
        away = game.get("away") if isinstance(game.get("away"), Mapping) else {}
        home = game.get("home") if isinstance(game.get("home"), Mapping) else {}
        aid, hid = away.get("official_team_id"), home.get("official_team_id")
        gid = str(game.get("game_id") or "").strip()
        if not gid or aid in (None, "") or hid in (None, ""):
            continue
        status = game.get("status") if isinstance(game.get("status"), Mapping) else {}
        rows.append({
            "game_id": gid,
            "game_date": str(game.get("official_schedule_date") or day),
            "first_tip_et": str(game.get("game_datetime_eastern") or status.get("text") or "TBD"),
            "status": str(status.get("category") or "scheduled").upper(),
            "status_text": str(status.get("text") or ""),
            "away_team_id": int(aid), "away_team": _team_name(away), "away_tricode": str(away.get("team_tricode") or ""),
            "home_team_id": int(hid), "home_team": _team_name(home), "home_tricode": str(home.get("team_tricode") or ""),
            "source": "Kyre Sports API • WNBA official schedule",
        })
    return pd.DataFrame(rows), raw_games

def _signature(frame: pd.DataFrame) -> tuple[tuple[int, int], ...]:
    if frame is None or frame.empty:
        return ()
    pairs = []
    for _, row in frame.iterrows():
        try:
            pairs.append((int(row.get("away_team_id")), int(row.get("home_team_id"))))
        except Exception:
            continue
    return tuple(sorted(pairs))

def _day_snapshot(day: str, api: KyreWNBAAPIClient):
    api_frame, raw_games, api_ok = pd.DataFrame(), (), False
    try:
        payload = api.games_for_date(day, SUPPORTED_SEASON)
        api_frame, raw_games = _api_frame(payload, day)
        api_ok = True
    except Exception:
        pass
    corroborating, diag = _corroborating_schedule(day)
    observations = []
    if api_ok:
        observations.append(SourceObservation("Kyre Sports API • WNBA official schedule", "schedule", day, _signature(api_frame), None, "CURRENT", 0, True))
    if bool(diag) or not corroborating.empty:
        source = str(diag.get("chosen_source") or "WNBA/ESPN schedule reconciliation")
        observations.append(SourceObservation(source, "schedule", day, _signature(corroborating), None, "CURRENT", 10, False))
    evidence = fuse_observations(observations)
    games = api_frame if api_ok else corroborating
    return games.reset_index(drop=True), raw_games, evidence

def _competition(raw_game: Mapping[str, Any] | None) -> tuple[str, str]:
    game = raw_game or {}
    comp = game.get("competition") if isinstance(game.get("competition"), Mapping) else {}
    label = str(comp.get("game_label") or "").strip()
    sub = str(comp.get("game_sub_label") or "").strip()
    return (" • ".join(x for x in (label, sub) if x) or "WNBA", str(comp.get("series_text") or "").strip())

def _next_game_mapping(games: pd.DataFrame, raw_games: tuple[Mapping[str, Any], ...]) -> Mapping[str, Any] | None:
    if raw_games:
        return dict(raw_games[0])
    if games is not None and not games.empty:
        return games.iloc[0].to_dict()
    return None

def resolve_playoff_context(selected_date: str, *, api_client: KyreWNBAAPIClient | None = None, lookahead_days: int = 14) -> PlayoffContext:
    selected = pd.to_datetime(selected_date).strftime("%Y-%m-%d")
    api = api_client or KyreWNBAAPIClient()
    games, raw_games, evidence = _day_snapshot(selected, api)
    if not games.empty:
        competition, series = _competition(raw_games[0] if raw_games else None)
        return PlayoffContext(selected, selected, True, games, _next_game_mapping(games, raw_games), competition, series, evidence.state, evidence.sources, "")
    for offset in range(1, max(0, int(lookahead_days)) + 1):
        day = (pd.to_datetime(selected).date() + timedelta(days=offset)).isoformat()
        future_games, future_raw, future_evidence = _day_snapshot(day, api)
        if future_games.empty:
            continue
        competition, series = _competition(future_raw[0] if future_raw else None)
        return PlayoffContext(selected, day, False, future_games, _next_game_mapping(future_games, future_raw), competition, series, future_evidence.state, future_evidence.sources, f"No WNBA game on {selected}. The next verified WNBA game is {day}.")
    return PlayoffContext(selected, selected, False, pd.DataFrame(), None, "WNBA", "", evidence.state, evidence.sources, "No WNBA game on this date. No verified future WNBA game was found in the current lookahead window.")

__all__ = ["PlayoffContext", "resolve_playoff_context"]
