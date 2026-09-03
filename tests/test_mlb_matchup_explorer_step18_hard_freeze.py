import hashlib
import json
import re
from pathlib import Path

import pandas as pd

import mlb_matchup_hub_v58 as step18


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "mlb_matchup_explorer_freeze_manifest_v1.json"


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _blob_sha(path: str) -> str:
    data = (ROOT / path).read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def _games():
    return pd.DataFrame(
        [
            {
                "game_pk": 9001,
                "game_date": "2026-09-03",
                "status": "Warmup",
                "first_pitch_et": "1:10 PM ET",
                "away_pitcher_id": 501,
                "home_pitcher_id": 502,
                "away_pitcher": "Jose Soriano",
                "home_pitcher": "Tanner Bibee",
            },
            {
                "game_pk": 9002,
                "game_date": "2026-09-03",
                "status": "Scheduled",
                "first_pitch_et": "4:10 PM ET",
                "away_pitcher_id": 601,
                "home_pitcher_id": 602,
                "away_pitcher": "Other Away",
                "home_pitcher": "Other Home",
            },
        ]
    )


def _snapshot():
    # Deliberately make player_index stale/wrong. Step 18 must choose by MLB ID.
    return {
        "game_pk": 9001,
        "game_index": 0,
        "player_id": 111,
        "player_index": 1,
        "players": [
            {
                "id": 111,
                "name": "Brett Bateman",
                "team": "Toronto Blue Jays",
                "position": "CF",
                "source": "CONFIRMED LINEUP",
                "slot": 1,
                "lineup_role": True,
                "side": "away",
                "opponent_pitcher_id": 502,
            },
            {
                "id": 222,
                "name": "Drew Gilbert",
                "team": "San Francisco Giants",
                "position": "CF",
                "source": "CONFIRMED LINEUP",
                "slot": 1,
                "lineup_role": True,
                "side": "away",
                "opponent_pitcher_id": 999,
            },
        ],
    }


def test_router_points_to_step18():
    source = _text("mlb_matchup_hub_v27.py")
    assert "from mlb_matchup_hub_v58 import" in source
    assert "from mlb_matchup_hub_v57 import" not in source


def test_step18_is_additive_over_frozen_step17_and_step16():
    source = _text("mlb_matchup_hub_v58.py")
    assert "import mlb_matchup_hub_v57 as current" in source
    assert "import mlb_matchup_hub_v56 as identity_layer" in source
    assert 'FROZEN_STEP16_PRESENTATION = "mlb_matchup_hub_v56"' in source
    assert 'FROZEN_STEP17_PRESENTATION = "mlb_matchup_hub_v57"' in source


def test_committed_snapshot_ignores_stale_numeric_player_index():
    context = step18._context_from_snapshot(_games(), _snapshot())
    assert context is not None
    assert context["row"]["game_pk"] == 9001
    assert context["player"]["id"] == 111
    assert context["player"]["name"] == "Brett Bateman"
    assert context["player"]["team"] == "Toronto Blue Jays"
    assert context["player_index"] == 0


def test_step17_cache_key_is_built_from_same_committed_player_and_game():
    context = step18._cache_context_from_snapshot(_games(), _snapshot())
    assert context is not None
    assert context["game_pk"] == 9001
    assert context["player_id"] == 111
    assert context["fingerprint"][:2] == (9001, 111)
    assert 222 not in context["fingerprint"]


def test_mismatched_cached_or_final_profile_is_rejected():
    snapshot = _snapshot()
    assert step18._profile_matches_snapshot({"game_pk": 9001, "player_id": 111}, snapshot)
    assert not step18._profile_matches_snapshot({"game_pk": 9001, "player_id": 222}, snapshot)
    assert not step18._profile_matches_snapshot({"game_pk": 9002, "player_id": 111}, snapshot)


def test_fast_sync_card_uses_only_committed_player_identity():
    context = step18._context_from_snapshot(_games(), _snapshot())
    html = step18._syncing_spotlight_html(context)
    assert "Brett Bateman" in html
    assert "Toronto Blue Jays" in html
    assert "MLB player 111" in html
    assert "Drew Gilbert" not in html
    assert "San Francisco Giants" not in html


def test_runtime_patches_are_always_restored():
    source = _text("mlb_matchup_hub_v58.py")
    assert "finally:" in source
    assert "spotlight_ui._render_spotlight = original_spotlight" in source
    assert "current._selection_context = original_cache_context" in source
    assert "hero_helpers._selected_context = original_context" in source
    assert "identity_layer._render_identity_selectors = original_selector" in source


def test_step18_does_not_reimplement_model_math_or_change_simulation_count():
    source = _text("mlb_matchup_hub_v58.py")
    for forbidden in (
        "build_probability_profile(",
        "build_final_intelligence(",
        "monte_carlo_distribution(",
        "5_000_000",
        "np.random",
        "default_rng",
        "render_daily_rankings(",
        "mlb_moneyline_hub",
    ):
        assert forbidden not in source


def test_permanent_freeze_manifest_protects_every_completed_cleanup_runtime_layer():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    protected = set(manifest["baseline_paths"]) | set(manifest["exact_blobs"])
    for version in range(41, 59):
        assert f"mlb_matchup_hub_v{version}.py" in protected
    assert manifest["baseline_commit"] == "c672e256ede0ab854ef0f8f08a73cd40dcd3dc2b"


def test_current_router_target_is_frozen_in_manifest():
    router = _text("mlb_matchup_hub_v27.py")
    match = re.search(r"from mlb_matchup_hub_v(\d+) import", router)
    assert match
    current_path = f"mlb_matchup_hub_v{match.group(1)}.py"
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    protected = set(manifest["baseline_paths"]) | set(manifest["exact_blobs"])
    assert current_path in protected


def test_step18_blob_is_self_frozen_by_exact_git_blob_sha():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = manifest["exact_blobs"]["mlb_matchup_hub_v58.py"]
    assert _blob_sha("mlb_matchup_hub_v58.py") == expected


def test_freeze_manifest_paths_exist():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for path in manifest["baseline_paths"]:
        assert (ROOT / path).exists(), path
    for path in manifest["exact_blobs"]:
        assert (ROOT / path).exists(), path


def test_historical_step17_exact_scope_is_now_branch_scoped():
    source = _text(".github/workflows/mlb-matchup-explorer-cleanup-step17-deep-research-performance.yml")
    assert "Historical exact-scope certification belongs only to Cleanup Step 17." in source
    assert "github.head_ref == 'mlb-matchup-explorer-cleanup-step17-deep-research-performance'" in source
