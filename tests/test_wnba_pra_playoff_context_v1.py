from __future__ import annotations

import pandas as pd


def _game(gid, day, away_id=1, home_id=2, away="Atlanta Dream", home="Golden State Valkyries", label="WNBA Finals", sub="Game 2", series="GSV leads 1-0"):
    return {
        "game_id": gid,
        "official_schedule_date": day,
        "game_datetime_eastern": f"{day}T20:00:00-04:00",
        "away": {"official_team_id": away_id, "full_name": away, "team_tricode": "ATL"},
        "home": {"official_team_id": home_id, "full_name": home, "team_tricode": "GSV"},
        "status": {"category": "scheduled", "text": "8:00 PM ET"},
        "competition": {"game_label": label, "game_sub_label": sub, "series_text": series},
    }


def _frame(day, gid="g1", away_id=1, home_id=2):
    return pd.DataFrame([{
        "game_id": gid, "game_date": day, "away_team_id": away_id, "home_team_id": home_id,
        "away_team": "Atlanta Dream", "home_team": "Golden State Valkyries", "first_tip_et": "8:00 PM ET",
    }])


class FakeClient:
    def __init__(self, by_day): self.by_day = by_day
    def games_for_date(self, day, season): return self.by_day.get(day, {"season": season, "games": []})


def test_selected_date_with_verified_game_stays_selected(monkeypatch):
    import wnba_pra_playoff_context_v1 as ctx
    day = "2026-10-19"
    monkeypatch.setattr(ctx, "_corroborating_schedule", lambda d: (_frame(d), {"chosen_source": "WNBA/ESPN consensus"}))
    out = ctx.resolve_playoff_context(day, api_client=FakeClient({day: {"season": 2026, "games": [_game("g1", day)]}}))
    assert out.effective_date == day
    assert out.today_has_game is True
    assert out.evidence_state == "VERIFIED_MULTI_SOURCE"
    assert out.competition_label == "WNBA Finals • Game 2"
    assert out.series_label == "GSV leads 1-0"


def test_verified_off_day_advances_to_next_verified_game(monkeypatch):
    import wnba_pra_playoff_context_v1 as ctx
    selected, next_day = "2026-10-18", "2026-10-19"
    monkeypatch.setattr(ctx, "_corroborating_schedule", lambda d: ((_frame(d) if d == next_day else pd.DataFrame()), {"chosen_source": "WNBA/ESPN consensus"}))
    api = FakeClient({selected: {"season": 2026, "games": []}, next_day: {"season": 2026, "games": [_game("g2", next_day)]}})
    out = ctx.resolve_playoff_context(selected, api_client=api, lookahead_days=3)
    assert out.selected_date == selected
    assert out.effective_date == next_day
    assert out.today_has_game is False
    assert out.next_game["game_id"] == "g2"
    assert "No WNBA game" in out.off_day_message


def test_no_verified_future_game_stays_honestly_empty(monkeypatch):
    import wnba_pra_playoff_context_v1 as ctx
    monkeypatch.setattr(ctx, "_corroborating_schedule", lambda d: (pd.DataFrame(), {"chosen_source": "season verification"}))
    out = ctx.resolve_playoff_context("2026-10-18", api_client=FakeClient({}), lookahead_days=2)
    assert out.effective_date == "2026-10-18"
    assert out.games.empty
    assert out.next_game is None
    assert "No verified future" in out.off_day_message


def test_official_conflict_keeps_official_identity_but_marks_conflict(monkeypatch):
    import wnba_pra_playoff_context_v1 as ctx
    day = "2026-10-19"
    monkeypatch.setattr(ctx, "_corroborating_schedule", lambda d: (_frame(d, gid="other", away_id=3, home_id=4), {"chosen_source": "ESPN"}))
    out = ctx.resolve_playoff_context(day, api_client=FakeClient({day: {"season": 2026, "games": [_game("official", day)]}}))
    assert out.evidence_state == "CONFLICT"
    assert out.games.iloc[0]["game_id"] == "official"


def test_competition_copy_is_data_driven_not_hard_coded(monkeypatch):
    import wnba_pra_playoff_context_v1 as ctx
    day = "2026-09-30"
    game = _game("semi", day, label="WNBA Semifinals", sub="Game 4", series="Series tied 2-2")
    monkeypatch.setattr(ctx, "_corroborating_schedule", lambda d: (_frame(d, gid="semi"), {"chosen_source": "ESPN"}))
    out = ctx.resolve_playoff_context(day, api_client=FakeClient({day: {"season": 2026, "games": [game]}}))
    assert out.competition_label == "WNBA Semifinals • Game 4"
    assert "Finals" not in out.competition_label
