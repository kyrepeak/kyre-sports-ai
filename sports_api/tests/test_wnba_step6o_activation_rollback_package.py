import unittest

import sports_api.wnba_step6o_activation_rollback_package as s


REV = "a" * 40
OTHER_REV = "b" * 40
IMAGE = "ghcr.io/kyrepeak/kyre-sports-api@sha256:" + "c" * 64
PREV_IMAGE = "ghcr.io/kyrepeak/kyre-sports-api@sha256:" + "d" * 64


def release_report(*, ready=True, rollback=True):
    return {
        "release_ready": ready,
        "rollback_ready": rollback,
        "phase": "pre_activation_ready" if ready else "pre_activation_blocked",
        "release": {
            "revision": REV if ready else None,
            "image_ref": IMAGE if ready else None,
            "manifest_fingerprint_sha256": "e" * 64,
        },
        "rollback_target": {
            "revision": OTHER_REV if rollback else None,
            "image_ref": PREV_IMAGE if rollback else None,
            "persistent_volume_root": "/var/lib/kyre-sports-api",
            "preserve_persistent_volume": True,
            "delete_database_files": False,
        },
        "storage_identity_sha256": "f" * 64,
    }


def step6m_report(*, authorized=True, refresh=True, cycle=True):
    return {
        "scheduler_cycle_ready": cycle,
        "step_6l": {
            "production_refresh_ready": refresh,
            "step_6k": {"scheduler_authorized": authorized},
        },
    }


def obs(state="healthy"):
    return {
        "state": state,
        "incident_active": state in {"degraded", "critical"},
    }


class Step6OPackageTests(unittest.TestCase):
    def build(self, *, release=None, step6m=None, observation=None, env=None):
        return s.build_step6o_activation_rollback_package(
            env={} if env is None else env,
            release_getter=lambda **_: release if release is not None else release_report(),
            step6m_getter=lambda **_: step6m if step6m is not None else step6m_report(),
            observability_getter=lambda **_: observation if observation is not None else obs(),
        )

    def test_fully_ready_package_requires_all_modern_gates(self):
        report = self.build()
        self.assertTrue(report["package_ready"])
        self.assertTrue(report["live_activation_ready"])
        self.assertEqual(report["state"], "activation_ready")
        self.assertEqual(report["evidence"]["step_6n_state"], "healthy")
        self.assertEqual(len(report["manifest"]["manifest_sha256"]), 64)

    def test_safe_deferred_is_packageable_but_not_live_activation_ready(self):
        deferred_release = release_report(ready=False, rollback=False)
        deferred_release["rollback_target"].update({
            "preserve_persistent_volume": True,
            "delete_database_files": False,
        })
        report = self.build(
            release=deferred_release,
            step6m=step6m_report(authorized=False, refresh=False, cycle=False),
            observation=obs("safe_deferred"),
        )
        self.assertTrue(report["package_ready"])
        self.assertFalse(report["live_activation_ready"])
        self.assertEqual(report["state"], "safe_deferred")
        self.assertTrue(report["activation_blocking_reasons"])

    def test_target_revision_drift_blocks_activation(self):
        report = self.build(env={s.TARGET_REVISION_ENV: OTHER_REV})
        self.assertFalse(report["live_activation_ready"])
        self.assertTrue(any("drifts" in row for row in report["activation_blocking_reasons"]))

    def test_target_image_drift_blocks_activation(self):
        other_image = "ghcr.io/kyrepeak/kyre-sports-api@sha256:" + "1" * 64
        report = self.build(env={s.TARGET_IMAGE_REF_ENV: other_image})
        self.assertFalse(report["live_activation_ready"])
        self.assertTrue(any("image drifts" in row for row in report["activation_blocking_reasons"]))

    def test_step6n_degraded_blocks_final_live_acceptance(self):
        report = self.build(observation=obs("degraded"))
        self.assertTrue(report["package_ready"])
        self.assertFalse(report["live_activation_ready"])
        self.assertEqual(report["state"], "activation_blocked")

    def test_step6n_critical_blocks_package_and_activation(self):
        report = self.build(observation=obs("critical"))
        self.assertFalse(report["package_ready"])
        self.assertFalse(report["live_activation_ready"])

    def test_rollback_disables_runtime_and_refresh_before_image_recovery(self):
        report = self.build()
        steps = report["rollback_plan"]["steps"]
        actions = [row["action"] for row in steps]
        self.assertEqual(actions[0], "disable_production_runtime")
        self.assertEqual(actions[1], "disable_step6l_production_refresh_authority")
        self.assertEqual(actions[2], "force_global_step6j_canary_direct_reconciled_switches_off")
        image_index = actions.index("redeploy_previous_immutable_image_with_runtime_disabled")
        self.assertGreater(image_index, 2)
        self.assertTrue(report["rollback_plan"]["persistent_storage_preserved"])

    def test_manifest_hash_is_deterministic_for_same_contract(self):
        first = self.build()
        second = self.build()
        self.assertEqual(first["manifest"]["manifest_sha256"], second["manifest"]["manifest_sha256"])

    def test_plan_builder_has_no_executor_semantics(self):
        report = self.build()
        semantics = report["semantics"]
        self.assertTrue(semantics["package_builder_is_read_only"])
        self.assertFalse(semantics["package_builder_uses_network"])
        self.assertFalse(semantics["paid_host_created"])
        self.assertFalse(semantics["environment_mutated"])
        self.assertFalse(semantics["scheduler_started"])
        self.assertFalse(semantics["draftkings_called"])
        self.assertFalse(semantics["feed_write_performed"])
        self.assertFalse(semantics["monte_carlo_run"])
        self.assertFalse(semantics["wager_action_performed"])


if __name__ == "__main__":
    unittest.main()
