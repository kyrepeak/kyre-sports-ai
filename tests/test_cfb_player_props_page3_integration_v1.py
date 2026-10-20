from pathlib import Path
import json

import cfb_player_props_model_v1 as frozen_model
import universal_runtime_v5_loader_nfl_daily_picks_command_v3 as loader
from universal_runtime_v5_state import RuntimeRoute

ROOT=Path(__file__).resolve().parents[1]
FREEZE='MONSTER_CFB_PLAYER_PROPS_PAGE3_V1_FROZEN'


def test_runtime_v3_is_canonical_cfb_player_props_destination():
    adapter=loader.resolve_destination(RuntimeRoute('cfb','player-props',{'date':'2026-10-20','game_id':'g1','player_id':'p1','prop':'passing_yards'},31,'tap'))
    assert adapter.route_key==('cfb','player-props')
    assert adapter.source_version=='CFB_PLAYER_PROPS_RUNTIME_V3'
    assert adapter.ttl_ms==30_000


def test_page3_scope_exists_without_app_or_frozen_model_mutation():
    expected={
        'cfb_player_props_runtime_v3.py','cfb_player_props_page3_context_v1.py',
        'cfb_player_props_page3_line_lab_v1.py','cfb_player_props_page3_history_v1.py',
        'cfb_player_props_page3_analysis_v1.py','cfb_player_props_page3_v1.py',
    }
    assert all((ROOT/name).exists() for name in expected)
    assert 'cfb_player_props' not in (ROOT/'app.py').read_text()
    assert frozen_model.SPORTSBOOK_PROJECTION_INFLUENCE==0.0


def test_page3_navigation_contract_is_pinned_in_ui_source():
    source=(ROOT/'cfb_player_props_page3_v1.py').read_text()
    assert '← Back to Game Props' in source
    assert 'href="#cfbpp3-top"' in source
    assert '↑ TOP' in source


def test_control_plane_files_bind_page3_freeze_and_runless_contract():
    ledger=json.loads((ROOT/'devsystem/task_ledgers/monster-cfb-player-props-page3-v1.json').read_text())
    proof=json.loads((ROOT/'devsystem/runless_proof_plans/monster-cfb-player-props-page3-v1.json').read_text())
    assert ledger['freeze_token']==FREEZE
    assert proof['freeze_token']==FREEZE
    assert proof['required_check']=='runless-final-gate'
    assert proof['required_app_id']==5204253
    assert proof['sportsbook_projection_influence']==0.0
    assert proof['public_runtime_required'] is False
    assert all(command[:2]==['python','-m'] for command in proof['commands'])
    assert all(command[2] != 'pip' for command in proof['commands'])
    assert any(command[2]=='pytest' for command in proof['commands'])
    assert any(command[2]=='devsystem.api2_universal_runtime_v5_cert' for command in proof['commands'])
