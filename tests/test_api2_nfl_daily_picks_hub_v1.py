from datetime import date, datetime, timedelta, timezone

from nfl_daily_picks_core_v1 import DailyPickCandidate, MarketLoadResult
import nfl_daily_picks_hub_v1 as hub

NOW = datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc)
DAY = date(2026, 10, 18)


def candidate(i=1, market_id="spread", **changes):
    line = None if market_id == "moneyline" else changes.pop("market_line", 3.5)
    athlete = changes.pop("athlete_id", "QB1" if market_id == "passing-yards" else None)
    return DailyPickCandidate(
        market_id=market_id,
        market_label={"spread":"Spread","moneyline":"Moneyline","passing-yards":"Passing Yards"}.get(market_id, market_id),
        game_id=changes.pop("game_id", f"G{i}"),
        game_date=DAY,
        kickoff_at=NOW + timedelta(hours=2+i),
        team_id=changes.pop("team_id", f"T{i}"),
        opponent_team_id=changes.pop("opponent_team_id", f"O{i}"),
        athlete_id=athlete,
        subject_label=changes.pop("subject_label", f"Subject {i}"),
        matchup_label=changes.pop("matchup_label", f"T{i} at O{i}"),
        side=changes.pop("side", "AWAY" if market_id in {"spread","moneyline"} else "OVER"),
        market_line=line,
        model_projection=changes.pop("model_projection", None if market_id == "moneyline" else -1.0),
        model_probability=changes.pop("model_probability", 0.60 + i * 0.005),
        edge_value=changes.pop("edge_value", 3.0),
        source_ready=True,
        source_fresh_at=NOW - timedelta(seconds=10),
        source_age_seconds=10.0,
        data_quality=0.92,
        uncertainty=0.10,
        source_version="source-v1",
        reason_components=("Strong source-owned probability", "Fresh exact-ID market"),
        source_grade="A",
        source_state="READY",
        freshness_limit_seconds=120.0,
    )


def result(market_id, status="READY", candidates=(), diagnostic="ok"):
    return MarketLoadResult(market_id, status, tuple(candidates), f"{market_id}-v1", NOW, diagnostic)


def six_results(picks=(), error_market=None):
    out = []
    by_market = {}
    for pick in picks:
        by_market.setdefault(pick.market_id, []).append(pick)
    for market_id in hub.MARKET_ORDER:
        status = "ERROR" if market_id == error_market else "READY"
        out.append(result(market_id, status=status, candidates=by_market.get(market_id, ()), diagnostic=f"{market_id}:{status}"))
    return tuple(out)


def test_board_always_exposes_six_market_statuses(monkeypatch):
    monkeypatch.setattr(hub, "load_all_market_candidates", lambda day, now_utc, loaders=None: six_results())
    board = hub.build_daily_picks_board(DAY, now_utc=NOW)
    assert tuple(board["market_statuses"]) == hub.MARKET_ORDER
    assert len(board["market_statuses"]) == 6


def test_one_error_market_does_not_hide_healthy_picks(monkeypatch):
    pick = candidate(1)
    monkeypatch.setattr(hub, "load_all_market_candidates", lambda day, now_utc, loaders=None: six_results([pick], error_market="game-total"))
    board = hub.build_daily_picks_board(DAY, now_utc=NOW)
    assert board["market_statuses"]["game-total"] == "ERROR"
    assert len(board["ranked_picks"]) == 1
    assert board["healthy_market_count"] == 5


def test_fewer_than_ten_are_not_padded(monkeypatch):
    picks = [candidate(i) for i in range(1, 5)]
    monkeypatch.setattr(hub, "load_all_market_candidates", lambda day, now_utc, loaders=None: six_results(picks))
    board = hub.build_daily_picks_board(DAY, now_utc=NOW)
    assert len(board["ranked_picks"]) == 4
    assert board["candidate_count"] == 4


def test_card_payload_contains_required_fields(monkeypatch):
    pick = candidate(1, market_id="passing-yards", athlete_id="4431611", subject_label="C.J. Stroud", side="OVER", market_line=247.5, model_projection=263.2)
    monkeypatch.setattr(hub, "load_all_market_candidates", lambda day, now_utc, loaders=None: six_results([pick]))
    card = hub.build_daily_picks_board(DAY, now_utc=NOW)["ranked_picks"][0]
    required = {"rank","market","subject","matchup","line","side","probability","projection","confidence","why","risk","freshness","kickoff"}
    assert required <= set(card)
    assert card["subject"] == "C.J. Stroud"


class FakeSt:
    def __init__(self):
        self.session_state = {"nfl_v1_date": DAY}
        self.markdowns = []
        self.infos = []
        self.captions = []
    def markdown(self, body, *args, **kwargs): self.markdowns.append(str(body))
    def info(self, body, *args, **kwargs): self.infos.append(str(body))
    def warning(self, body, *args, **kwargs): self.infos.append(str(body))
    def caption(self, body, *args, **kwargs): self.captions.append(str(body))


def test_zero_candidates_renders_clean_message_and_diagnostics(monkeypatch):
    fake = FakeSt()
    monkeypatch.setattr(hub, "st", fake)
    calls = {"count": 0}
    def load(day, now_utc, loaders=None):
        calls["count"] += 1
        return six_results()
    monkeypatch.setattr(hub, "load_all_market_candidates", load)
    monkeypatch.setattr(hub, "_now_utc", lambda: NOW)
    hub.render_nfl_daily_picks_hub()
    assert calls["count"] == 1
    assert any("No qualified pregame picks are currently available." in msg for msg in fake.infos)
    rendered = "\n".join(fake.markdowns + fake.infos + fake.captions)
    assert "<article class=\"knfl-game\">" not in rendered
    assert "reserved and visible in navigation" not in rendered


def test_renderer_uses_one_controlled_card_path_without_old_foundation(monkeypatch):
    fake = FakeSt()
    monkeypatch.setattr(hub, "st", fake)
    monkeypatch.setattr(hub, "_now_utc", lambda: NOW)
    monkeypatch.setattr(hub, "load_all_market_candidates", lambda day, now_utc, loaders=None: six_results([candidate(1)]))
    hub.render_nfl_hub("Daily Picks")
    rendered = "\n".join(fake.markdowns)
    assert "kdp-card" in rendered
    assert "knfl-game" not in rendered
    assert "NFL Daily Picks" in rendered


def test_non_ready_market_cannot_publish_cached_ready_candidate(monkeypatch):
    stale_cached = candidate(9, market_id="spread", game_id="G9", team_id="BUF", opponent_team_id="MIA")
    healthy = candidate(10, market_id="moneyline", game_id="G10", team_id="KC", opponent_team_id="LV", market_line=None)
    results = []
    for market_id in hub.MARKET_ORDER:
        if market_id == "spread":
            results.append(result(market_id, status="ERROR", candidates=(stale_cached,), diagnostic="provider failed"))
        elif market_id == "moneyline":
            results.append(result(market_id, status="READY", candidates=(healthy,), diagnostic="ok"))
        else:
            results.append(result(market_id, status="READY", candidates=(), diagnostic="ok"))
    monkeypatch.setattr(hub, "load_all_market_candidates", lambda day, now_utc, loaders=None: tuple(results))

    board = hub.build_daily_picks_board(DAY, now_utc=NOW)

    assert board["market_statuses"]["spread"] == "ERROR"
    assert board["candidate_count"] == 1
    assert [card["subject"] for card in board["ranked_picks"]] == [healthy.subject_label]
