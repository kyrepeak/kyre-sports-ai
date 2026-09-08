"""Regression checks for Moneyline Step 3 starter-vs-lineup evidence."""
import mlb_moneyline_hub_v168 as m


def _feed(lineup_count=9):
    players = {
        "ID99": {"fullName": "Home Starter", "pitchHand": {"code": "R"}},
        "ID88": {"fullName": "Away Starter", "pitchHand": {"code": "L"}},
    }
    away = []
    home = []
    for i in range(1, 10):
        players[f"ID{i}"] = {
            "fullName": f"Away Hitter {i}",
            "batSide": {"code": "S" if i == 1 else ("L" if i % 2 else "R")},
        }
        players[f"ID{20+i}"] = {
            "fullName": f"Home Hitter {i}",
            "batSide": {"code": "S" if i == 1 else ("R" if i % 2 else "L")},
        }
        away.append(i)
        home.append(20 + i)
    return {
        "gameData": {
            "probablePitchers": {
                "home": {"id": 99, "fullName": "Home Starter"},
                "away": {"id": 88, "fullName": "Away Starter"},
            },
            "players": players,
        },
        "liveData": {
            "boxscore": {
                "teams": {
                    "away": {"battingOrder": away[:lineup_count]},
                    "home": {"battingOrder": home[:lineup_count]},
                }
            }
        },
    }


def test_effective_batter_side_handles_switch_hitters():
    assert m._effective_batter_side("S", "R") == "L"
    assert m._effective_batter_side("S", "L") == "R"
    assert m._effective_batter_side("L", "R") == "L"


def test_aggregate_lineup_pools_verified_split_sample():
    rows = [
        {"pa": 100, "ab": 90, "hits": 27, "avg": 0.300, "ops": 0.800, "k_pct": 0.20, "bb_pct": 0.10},
        {"pa": 80, "ab": 70, "hits": 14, "avg": 0.200, "ops": 0.650, "k_pct": 0.25, "bb_pct": 0.05},
    ]
    out = m._aggregate_lineup(rows)
    assert out["hitters"] == 2
    assert out["pa"] == 180
    assert out["ab"] == 160
    assert round(out["avg"], 4) == round(41 / 160, 4)
    assert out["ops"] is not None


def test_aggregate_starter_sides_tracks_lineup_coverage():
    left = {"bf": 200, "avg": 0.260, "ops": 0.750, "k_pct": 0.20, "bb_pct": 0.09}
    right = {"bf": 250, "avg": 0.230, "ops": 0.680, "k_pct": 0.27, "bb_pct": 0.06}
    out = m._aggregate_starter_sides(left, right, ["L", "L", "R", "R"])
    assert out["coverage"] == 1.0
    assert round(out["avg"], 3) == 0.245


def test_matchup_score_direction_is_stable():
    strong_lineup = {"avg": 0.285, "ops": 0.820, "k_pct": 0.17, "bb_pct": 0.11}
    vulnerable_starter = {"avg": 0.280, "ops": 0.810, "k_pct": 0.16, "bb_pct": 0.11}
    tough_lineup = {"avg": 0.205, "ops": 0.620, "k_pct": 0.31, "bb_pct": 0.05}
    dominant_starter = {"avg": 0.205, "ops": 0.610, "k_pct": 0.32, "bb_pct": 0.04}

    hitter_edge = m._matchup_score(strong_lineup, vulnerable_starter)
    pitcher_edge = m._matchup_score(tough_lineup, dominant_starter)

    assert hitter_edge["score"] > 50
    assert hitter_edge["label_cls"] == "hitter"
    assert pitcher_edge["score"] < 50
    assert pitcher_edge["label_cls"] == "pitcher"


def test_side_matchup_fails_closed_without_full_official_lineup(monkeypatch):
    feed = _feed(lineup_count=8)
    called = {"splits": 0}

    def no_network(*args, **kwargs):
        called["splits"] += 1
        raise AssertionError("split fetch should not happen for partial lineup")

    monkeypatch.setattr(m, "_fetch_hitter_splits", no_network)
    out = m._side_matchup(feed, "away", "home")

    assert out["status"] == "PENDING"
    assert out["lineup_confirmed"] is False
    assert out["score"] is None
    assert called["splits"] == 0


def test_side_matchup_grades_only_after_split_thresholds(monkeypatch):
    feed = _feed()

    hitter_row = {
        "status": "VERIFIED",
        "pa": 100,
        "ab": 90,
        "hits": 25,
        "avg": 25 / 90,
        "ops": 0.760,
        "k_pct": 0.20,
        "bb_pct": 0.09,
    }
    monkeypatch.setattr(
        m,
        "_fetch_hitter_splits",
        lambda player_ids, sit_code: {int(pid): dict(hitter_row) for pid in player_ids},
    )

    def split(player_id, group, sit_code):
        assert group == "pitching"
        return {
            "status": "VERIFIED",
            "stat": {
                "battersFaced": 220,
                "hits": 54 if sit_code == "vl" else 49,
                "avg": "0.245" if sit_code == "vl" else "0.225",
                "ops": "0.710" if sit_code == "vl" else "0.670",
                "strikeOuts": 50 if sit_code == "vl" else 60,
                "baseOnBalls": 18 if sit_code == "vl" else 14,
            },
        }

    monkeypatch.setattr(m, "_stat_split", split)
    out = m._side_matchup(feed, "away", "home")

    assert out["status"] == "VERIFIED"
    assert out["lineup_confirmed"] is True
    assert out["lineup"]["hitters"] == 9
    assert out["lineup"]["pa"] == 900
    assert out["starter_splits"]["coverage"] == 1.0
    assert out["score"] is not None
    assert out["quality_score"] == 100


def test_overall_grade_fails_closed_when_either_side_missing():
    grade, cls, edge = m._overall_grade({"score": 60}, {"score": None})
    assert grade == "DATA LIMITED / PENDING"
    assert cls == "limited"
    assert edge is None
