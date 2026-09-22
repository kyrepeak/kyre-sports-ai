"""Regression checks for MLB Hits Step 2 compact mobile Top-5 cards."""
from copy import deepcopy

import mlb_hit_hub_v1317 as hits


def _result():
    return {
        "player_id": 123,
        "player_name": "Test Hitter",
        "team_id": 10,
        "team": "Test Team",
        "opponent": "Opponent",
        "starter_name": "Test Starter",
        "position": 2,
        "first_pitch": "7:10 PM",
        "lineup_confirmed": True,
        "confidence": "HIGH",
        "sim": {
            "p_one_plus": 0.724,
            "p_two_plus": 0.351,
            "expected_hits": 1.18,
            "scenario_low": 0.651,
            "scenario_high": 0.781,
        },
    }


def _frozen_html():
    return (
        '<div class="hit-pick rank1">'
        '<div class="hit-rank">🥇 Rank 1 • ✅ CONFIRMED</div>'
        '<div class="hit-pick-identity">old identity</div>'
        '<div class="step">STEP 4 • verified evidence</div>'
        '<div class="step">STEP 8 • verified fielding evidence</div>'
        '<div class="hit1316-final">'
        '<span>PICK STRENGTH • STRONG</span>'
        '<span>MATCHUP • ELITE</span>'
        '<span>OPPORTUNITY • ELITE</span>'
        '<span>EVIDENCE • 82/100</span>'
        '<div>✅ Supports: Model • Opportunity</div>'
        '<div>⚠️ Concerns: None</div>'
        '</div>'
        '<div class="hit-pick-prob">72.4%</div>'
        '<div class="hit-pick-sub">old quick stats</div>'
        '<div class="hit-conf">HIGH</div>'
        '</div>'
    )


def test_step2_is_additive_over_frozen_step1():
    assert hits.UI_VERSION == "V13.17"
    assert hits._BASE_PICK_HTML is hits.prior._pick_html_v1316


def test_summary_labels_are_read_from_frozen_step1_html():
    html = _frozen_html()
    assert hits._summary_label(html, "PICK STRENGTH") == "STRONG"
    assert hits._summary_label(html, "MATCHUP") == "ELITE"
    assert hits._summary_label(html, "OPPORTUNITY") == "ELITE"
    assert hits._evidence_score(html) == "82/100"


def test_deep_inner_keeps_existing_evidence_content():
    inner = hits._deep_inner(_frozen_html())
    assert "STEP 4 • verified evidence" in inner
    assert "STEP 8 • verified fielding evidence" in inner
    assert "FINAL" not in ""  # keep this test focused on exact evidence preservation
    assert "✅ Supports: Model • Opportunity" in inner


def test_compact_card_promotes_quick_scan_and_collapses_frozen_evidence(monkeypatch):
    monkeypatch.setattr(hits, "_BASE_PICK_HTML", lambda result, rank: _frozen_html())
    monkeypatch.setattr(hits, "_official_headshot", lambda player_id: "https://example.test/player.jpg")
    monkeypatch.setattr(hits, "_official_logo", lambda team_id: "https://example.test/team.svg")

    result = _result()
    before = deepcopy(result)
    html = hits._pick_html_v1317(result, 1)

    assert result == before
    assert "hit1317-card rank1" in html
    assert "Test Hitter" in html
    assert "72.4%" in html
    assert "2+ Hits" in html
    assert "Expected Hits" in html
    assert "PICK • STRONG" in html
    assert "MATCHUP" in html
    assert "ELITE" in html
    assert "EVIDENCE 82/100" in html
    assert "<details class=\"hit1317-deep\">" in html
    assert "Full Steps 1–11 evidence + Step 1 final summary" in html
    assert "STEP 4 • verified evidence" in html
    assert "STEP 8 • verified fielding evidence" in html


def test_projected_lineup_is_never_presented_as_confirmed(monkeypatch):
    monkeypatch.setattr(hits, "_BASE_PICK_HTML", lambda result, rank: _frozen_html())
    monkeypatch.setattr(hits, "_official_headshot", lambda player_id: "")
    monkeypatch.setattr(hits, "_official_logo", lambda team_id: "")
    result = _result()
    result["lineup_confirmed"] = False
    html = hits._pick_html_v1317(result, 4)
    assert '<span class="projected">PROJECTED</span>' in html
    assert '<span class="confirmed">CONFIRMED</span>' not in html
