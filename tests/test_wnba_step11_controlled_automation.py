from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from sports_api import wnba_step11_controlled_automation as step11e
from sports_api import wnba_step11_release_freeze as release
from sports_api import wnba_step11_draftkings_provider as dk
from sports_api import wnba_step11_fanduel_provider as fd
from sports_api import wnba_step9_threshold_pricing as pricing
from sports_api.wnba_step10_live_pipeline import WNBAStep10LivePipelineNotReadyError
from sports_api.wnba_step8_joint_monte_carlo import MODEL_VERSION as STEP8D_MODEL_VERSION, SCHEMA_VERSION as STEP8D_SCHEMA_VERSION


def env():
    return {
        "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED":"true","WNBA_STEP11D_MULTIBOOK_SHADOW_ENABLED":"true",
        "WNBA_STEP11C_FANDUEL_PROVIDER_ENABLED":"true","WNBA_STEP11B_NETWORK_REFRESH_ENABLED":"true","WNBA_STEP11A_DRAFTKINGS_PROVIDER_ENABLED":"true",
        "WNBA_STEP10_FASTAPI_ENABLED":"true","WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED":"true","WNBA_STEP10B_MARKET_ADAPTER_ENABLED":"true",
        "WNBA_STEP10C_MARKET_SNAPSHOT_ENABLED":"true","WNBA_STEP10D_REFRESH_CONTROLLER_ENABLED":"true","WNBA_STEP9_FASTAPI_ENABLED":"true",
        "WNBA_STEP9_THRESHOLD_PRICING_ENABLED":"true","WNBA_STEP9B_MARKET_COMPARISON_ENABLED":"true","WNBA_STEP9C_MULTIBOOK_CONSENSUS_ENABLED":"true",
        "WNBA_STEP9D_QUALIFICATION_RANKING_ENABLED":"true","WNBA_PRODUCTION_RUNTIME_ENABLED":"false","WNBA_BOARD_SCHEDULER_ENABLED":"false",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED":"false","WNBA_KYRE_RECONCILED_SYNC_ENABLED":"false","WNBA_STEP6J_CANARY_ENABLED":"false","WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED":"false",
    }


def step8():
    result={"data_type":"joint_player_stat_probability_distribution","schema_version":STEP8D_SCHEMA_VERSION,"model_version":STEP8D_MODEL_VERSION,"generated_at_utc":"2026-08-28T06:30:00+00:00","game_id":"1022600291","player_id":1642301,"team_key":"atlanta-dream","opponent_team_key":"portland-fire","simulation":{"simulations":5_000_000,"batch_size":250_000},"convergence":{"converged":True},"distributions":{"points":{"probability_mass":[{"value":20,"probability":0.36},{"value":21,"probability":0.64}]},"rebounds":{"probability_mass":[{"value":10,"probability":0.4},{"value":11,"probability":0.6}]},"assists":{"probability_mass":[{"value":4,"probability":0.4},{"value":5,"probability":0.6}]},"points_rebounds_assists":{"probability_mass":[{"value":39,"probability":0.4},{"value":40,"probability":0.6}]}}}
    surface=dict(result); surface.pop("generated_at_utc",None); result["result_content_sha256"]=pricing._canonical_hash(surface); return result


def shadow():
    return {"shadow_board_content_sha256":"a"*64,"lineage":{"step10_pipeline_content_sha256":"b"*64,"step9_ranking_content_sha256":"c"*64}}


def tick(at, previous_state=None, **kwargs):
    return step11e.run_step11e_controlled_automation_tick(season=2026,slate_date="2026-08-28",step8_distributions=[step8()],previous_state=previous_state,evaluated_at=at,env=env(),**kwargs)


def bridge(provider,evaluated):
    price=(-110,-110) if provider==dk.PROVIDER else (-105,-115)
    payload={"provider":provider,"price_format":"american","records":[{"game_id":"1022600291","player_id":1642301,"player_name":"Player 1642301","sportsbook":provider,"stat":"points","line":20.5,"over_price":price[0],"under_price":price[1],"market_captured_at":evaluated.isoformat()}]}
    if provider==dk.PROVIDER:
        result={"data_type":"wnba_step11a_draftkings_provider_bridge","schema_version":dk.SCHEMA_VERSION,"model_version":dk.MODEL_VERSION,"release_id":dk.RELEASE_ID,"generated_at_utc":evaluated.isoformat(),"provider":provider,"provider_refresh":{"provider":provider,"adapter_type":dk.ADAPTER_TYPE,"attempts":[{"ok":True,"payload":payload}]},"lineage":{"step10_frozen_git_sha":release.STEP10_FROZEN_SHA,"step10b_frozen_git_sha":release.STEP10B_FROZEN_SHA}}
    else:
        result={"data_type":"wnba_step11c_fanduel_provider_bridge","schema_version":fd.SCHEMA_VERSION,"model_version":fd.MODEL_VERSION,"release_id":fd.RELEASE_ID,"generated_at_utc":evaluated.isoformat(),"provider":provider,"provider_refresh":{"provider":provider,"adapter_type":fd.ADAPTER_TYPE,"attempts":[{"ok":True,"payload":payload}]},"lineage":{"step11b_frozen_git_sha":release.STEP11B_FROZEN_SHA,"step11a_frozen_git_sha":release.STEP11A_FROZEN_SHA,"step10_frozen_git_sha":release.STEP10_FROZEN_SHA,"step10b_frozen_git_sha":release.STEP10B_FROZEN_SHA}}
    result["guardrails"]={"sportsbook_network_fetch_performed":True,"sportsbook_http_methods":["GET"],"authentication_used":False,"cookies_used":False,"wager_action_performed":False,"paid_odds_vendor_used":False,"basketball_projection_changed":False,"step8_distribution_changed":False,"supabase_mutated":False,"persistence_mutated":False,"scheduler_started":False,"production_runtime_enabled":False,"production_activation_allowed":False}
    surface={k:v for k,v in result.items() if k!="generated_at_utc"}; result["provider_bridge_content_sha256"]=step11e.step11d._canonical_hash(surface); return result


def fetcher(provider):
    return lambda **kwargs: bridge(provider,kwargs["evaluated_at"])


class Tests(unittest.TestCase):
    def setUp(self): self.t0=datetime(2026,8,28,6,40,tzinfo=timezone.utc)
    def test_default_off(self): self.assertFalse(step11e.step11e_controlled_automation_enabled({})); self.assertFalse(release.DEFAULT_ENABLED)
    def test_prod_and_scheduler_off(self):
        for key in ("WNBA_PRODUCTION_RUNTIME_ENABLED","WNBA_BOARD_SCHEDULER_ENABLED"):
            e=env(); e[key]="true"
            with self.assertRaises(step11e.WNBAStep11ControlledAutomationDisabledError): step11e.run_step11e_controlled_automation_tick(season=2026,slate_date="2026-08-28",step8_distributions=[step8()],evaluated_at=self.t0,env=e)
    def test_lower_gate_required(self):
        e=env(); e["WNBA_STEP9C_MULTIBOOK_CONSENSUS_ENABLED"]="false"
        with self.assertRaises(step11e.WNBAStep11ControlledAutomationDisabledError): step11e.run_step11e_controlled_automation_tick(season=2026,slate_date="2026-08-28",step8_distributions=[step8()],evaluated_at=self.t0,env=e)
    def test_policy_bounds(self):
        for kw in ({"refresh_interval_seconds":14},{"failure_threshold":0},{"circuit_cooldown_seconds":29},{"provider_attempts":6}):
            with self.assertRaises(step11e.WNBAStep11ControlledAutomationInputError): tick(self.t0,**kw)
    def test_initial_success(self):
        with patch.object(step11e.step11d,"run_step11d_multibook_shadow_board",return_value=shadow()): r=tick(self.t0)
        self.assertEqual(r["status"],"healthy"); self.assertEqual(r["automation_state"]["circuit_state"],"closed"); self.assertFalse(r["guardrails"]["background_scheduler_started"])
    def test_not_due_skips(self):
        with patch.object(step11e.step11d,"run_step11d_multibook_shadow_board",return_value=shadow()): first=tick(self.t0)
        with patch.object(step11e.step11d,"run_step11d_multibook_shadow_board") as m: second=tick(self.t0+timedelta(seconds=30),first["automation_state"])
        m.assert_not_called(); self.assertEqual(second["status"],"not_due")
    def test_tampered_state(self):
        with patch.object(step11e.step11d,"run_step11d_multibook_shadow_board",return_value=shadow()): first=tick(self.t0)
        bad=deepcopy(first["automation_state"]); bad["consecutive_failure_count"]=9
        with self.assertRaises(step11e.WNBAStep11ControlledAutomationIntegrityError): tick(self.t0+timedelta(seconds=60),bad)
    def test_policy_change_requires_reset(self):
        with patch.object(step11e.step11d,"run_step11d_multibook_shadow_board",return_value=shadow()): first=tick(self.t0)
        with self.assertRaises(step11e.WNBAStep11ControlledAutomationInputError): tick(self.t0+timedelta(seconds=60),first["automation_state"],refresh_interval_seconds=120)
    def test_time_reversal(self):
        with patch.object(step11e.step11d,"run_step11d_multibook_shadow_board",return_value=shadow()): first=tick(self.t0)
        with self.assertRaises(step11e.WNBAStep11ControlledAutomationInputError): tick(self.t0-timedelta(seconds=1),first["automation_state"])
    def test_transient_degraded(self):
        exc=step11e.step11d.WNBAStep11MultiBookShadowNotReadyError("outage")
        with patch.object(step11e.step11d,"run_step11d_multibook_shadow_board",side_effect=exc): r=tick(self.t0)
        self.assertEqual(r["status"],"transient_failure"); self.assertEqual(r["automation_state"]["consecutive_failure_count"],1)
    def test_three_failures_open_circuit(self):
        exc=step11e.step11d.WNBAStep11MultiBookShadowNotReadyError("outage"); state=None
        for off in (0,60,120):
            with patch.object(step11e.step11d,"run_step11d_multibook_shadow_board",side_effect=exc): r=tick(self.t0+timedelta(seconds=off),state); state=r["automation_state"]
        self.assertEqual(r["status"],"circuit_opened"); self.assertEqual(state["circuit_state"],"open"); self.assertEqual(state["circuit_open_until_utc"],(self.t0+timedelta(seconds=300)).isoformat())
    def test_open_circuit_skips(self):
        exc=step11e.step11d.WNBAStep11MultiBookShadowNotReadyError("outage"); state=None
        for off in (0,60,120):
            with patch.object(step11e.step11d,"run_step11d_multibook_shadow_board",side_effect=exc): state=tick(self.t0+timedelta(seconds=off),state)["automation_state"]
        with patch.object(step11e.step11d,"run_step11d_multibook_shadow_board") as m: r=tick(self.t0+timedelta(seconds=180),state)
        m.assert_not_called(); self.assertEqual(r["status"],"circuit_open")
    def test_half_open_recovers(self):
        exc=step11e.step11d.WNBAStep11MultiBookShadowNotReadyError("outage"); state=None
        for off in (0,60,120):
            with patch.object(step11e.step11d,"run_step11d_multibook_shadow_board",side_effect=exc): state=tick(self.t0+timedelta(seconds=off),state)["automation_state"]
        with patch.object(step11e.step11d,"run_step11d_multibook_shadow_board",return_value=shadow()): r=tick(self.t0+timedelta(seconds=300),state)
        self.assertEqual(r["status"],"half_open_recovered"); self.assertEqual(r["automation_state"]["consecutive_failure_count"],0)
    def test_market_not_ready_does_not_trip_circuit(self):
        with patch.object(step11e.step11d,"run_step11d_multibook_shadow_board",side_effect=WNBAStep10LivePipelineNotReadyError("no consensus")): r=tick(self.t0)
        self.assertEqual(r["status"],"market_not_ready"); self.assertEqual(r["automation_state"]["consecutive_failure_count"],0)
    def test_terminal_identity_propagates(self):
        with patch.object(step11e.step11d,"run_step11d_multibook_shadow_board",side_effect=dk.WNBAStep11DraftKingsProviderIdentityError("bad identity")):
            with self.assertRaises(dk.WNBAStep11DraftKingsProviderIdentityError): tick(self.t0)
    def test_real_frozen_step11d_integration(self):
        r=tick(self.t0,draftkings_fetcher=fetcher(dk.PROVIDER),fanduel_fetcher=fetcher(fd.PROVIDER)); s=r["shadow_board_result"]
        self.assertEqual(r["status"],"healthy"); self.assertEqual(s["market_audit"]["exact_line_multibook_group_count"],1); self.assertEqual(s["shadow_summary"]["qualified_prop_count"],1)
    def test_guardrails(self):
        with patch.object(step11e.step11d,"run_step11d_multibook_shadow_board",return_value=shadow()): r=tick(self.t0)
        for key in ("background_scheduler_started","sleep_performed","state_persisted","public_fastapi_route_added","supabase_mutated","persistence_mutated","production_runtime_enabled","production_activation_allowed","wager_action_performed"):
            self.assertFalse(r["guardrails"][key],key)

if __name__=="__main__": unittest.main(verbosity=2)
