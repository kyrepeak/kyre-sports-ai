from __future__ import annotations

import json
from pathlib import Path

from devsystem import nfl_rb_wr_render_repair_step3_data_binding_v1 as cert

ROOT = Path(__file__).resolve().parents[1]


def test_step3_certifies_exact_rb_wr_binding_chain() -> None:
    report = cert.certify(ROOT)
    assert report["status"] == "GREEN"
    assert report["decision"] == "NFL_RB_WR_STEP3_DATA_BINDING_CERTIFIED"
    assert report["check_count"] >= 11
    assert report["sportsbook_projection_influence"] == 0.0
    assert report["product_runtime_mutations"] == 0
    assert report["names_are_identity_keys"] is False
    assert report["fuzzy_identity_matching"] is False
    assert all(row["status"] == "GREEN" for row in report["checks"])


def test_step3_exact_market_join_rejects_wrong_team_and_athlete() -> None:
    rows = {row["name"]: row for row in cert._exact_market_join_checks()}
    assert rows["RUSHING_MARKET_EXACT_JOIN"]["exact_id_fail_closed"] is True
    assert rows["RECEIVING_MARKET_EXACT_JOIN_BEHAVIOR"]["exact_id_fail_closed"] is True


def test_step3_keeps_step2_hardened_transport_and_exact_identity_images() -> None:
    rushing = (ROOT / "nfl_rushing_yards_hub_v4.py").read_text(encoding="utf-8")
    receiving = (ROOT / "nfl_receiving_yards_hub_v13.py").read_text(encoding="utf-8")
    assert "st.html(_COMPACT_CSS)" in rushing
    assert "compact_slot.html(board)" in rushing
    assert "headshot = _headshot_url(athlete_id)" in rushing
    assert "logo = _team_logo_url(team_abbr)" in rushing
    assert "st.html(_STEP13_CSS)" in receiving
    assert "face = headshot_url(athlete_id)" in receiving
    assert "logo = team_logo_url(team_abbr)" in receiving


def test_step3_plan_is_verification_only() -> None:
    plan = json.loads(
        (ROOT / "devsystem/execution_plans/nfl-rb-wr-render-repair-step3-data-binding.json")
        .read_text(encoding="utf-8")
    )
    assert plan["product_runtime_mutations"] == 0
    assert plan["router_mutations"] == 0
    assert plan["data_api_mutations"] == 0
    assert plan["sportsbook_logic_mutations"] == 0
    assert all(
        not path.startswith("nfl_") and not path.startswith("streamlit_")
        for path in plan["write_paths"]
    )
