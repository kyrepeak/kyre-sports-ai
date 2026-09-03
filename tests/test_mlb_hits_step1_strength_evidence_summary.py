from pathlib import Path

import mlb_hit_hub_v1316 as hits

ROOT = Path(__file__).resolve().parents[1]


def test_app_activates_additive_router_v3():
    text = (ROOT / "app.py").read_text()
    assert "from streamlit_memory_lazy_router_v3 import render_app" in text


def test_router_changes_only_hits_route_and_delegates_everything_else():
    text = (ROOT / "streamlit_memory_lazy_router_v3.py").read_text()
    assert 'market != "1+ Hit"' in text
    assert "return _BASE_RENDER_MLB(market)" in text
    assert 'frozen._import("mlb_hit_hub_v1316")' in text
    assert "Matchup Explorer" in text
    assert "mlb_matchup_hub" not in text


def test_hits_wrapper_is_additive_over_frozen_v1315():
    text = (ROOT / "mlb_hit_hub_v1316.py").read_text()
    assert "import mlb_hit_hub_v1315 as prior" in text
    assert "_BASE_PICK_HTML = prior._pick_html_v1315" in text
    assert "active._pick_html=_pick_html_v1316" in text
    for forbidden in ("def deep_scan", "def monte", "def prescreen", "def _candidate_pool", "random.seed", "np.random"):
        assert forbidden not in text


def test_all_verified_hits_layers_have_grade_markers():
    assert set(hits.MARKERS) == set(range(1, 12))
    assert hits.MARKERS[1] == "MLB BATTER + TEAM IDENTITY"
    assert hits.MARKERS[11] == "STEP 11"


def test_quick_read_grades_cover_requested_visual_language():
    confirmed = {"lineup_confirmed": True, "position": 2, "expected_ab": 4.4}
    assert hits._grade(1, confirmed, "") == "CONFIRMED"
    assert hits._grade(4, {}, "Batter vs RHP AVG .335 • SP vs LHB AVG .286") == "FAVORABLE"
    assert hits._grade(5, {}, "Existing model environment combined +0.4%") == "NEAR NEUTRAL"
    assert hits._grade(6, confirmed, "") == "ELITE OPPORTUNITY"
    assert hits._grade(7, {}, "Last 5 • 1+ hit 4/5 • Last 10 • 1+ hit 6/10") == "ELITE RECENT FORM"
    assert hits._grade(8, {}, "1+ context: HURTS HITTER") == "STRONG"
    assert hits._grade(9, {}, "1+ context: HURTS HITTER") == "TOUGH"
    assert hits._grade(10, {}, "Hook profile • DEEPER-START LEAN") == "TOUGH"
    assert hits._grade(11, {}, "MLB has not posted a verifiable home-plate umpire") == "NOT YET PUBLISHED"


def test_final_summary_matches_hrrbi_style_without_reranking():
    result = {
        "lineup_confirmed": True,
        "confidence": "HIGH",
        "sim": {"p_one_plus": 0.72},
    }
    grades = {
        4: "FAVORABLE",
        5: "NEAR NEUTRAL",
        6: "ELITE OPPORTUNITY",
        7: "ELITE RECENT FORM",
        8: "WEAK",
        9: "NEUTRAL",
        10: "NEUTRAL",
    }
    html = hits._summary(result, grades)
    assert "FINAL • TOP-5 EVIDENCE SUMMARY" in html
    assert "RANKING UNCHANGED" in html
    assert "PICK STRENGTH •" in html
    assert "MATCHUP •" in html
    assert "OPPORTUNITY •" in html
    assert "EVIDENCE •" in html
    assert "✅ Supports:" in html
    assert "⚠️ Concerns:" in html
    assert "N/A / not scored:" in html
    assert "does not change 1+ Hit probability" in html


def test_badge_injection_preserves_existing_step_evidence():
    source = '<div class="x-head">STEP 8 • OPPONENT RUN PREVENTION + FIELDING</div><p>verified evidence</p>'
    out = hits._insert(source, "STEP 8", "STRONG")
    assert "hit1316-grade" in out
    assert ">STRONG</span>" in out
    assert "verified evidence" in out
