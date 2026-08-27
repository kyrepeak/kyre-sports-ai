from __future__ import annotations

import json
import unittest

import sports_api.wnba_render_provisioning_step6c as s
from sports_api.wnba_render_provisioning import (
    ALLOW_PAID_PROVISIONING_ENV,
    WNBARenderProvisioningConfigurationError,
    WNBARenderProvisioningPaymentConfirmationError,
)


class Step6CRenderProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.revision = "a" * 40
        self.image = f"ghcr.io/kyrepeak/kyre-sports-api@sha256:{'b'*64}"
        self.release_id = "wnba-step6c-test"
        self.owner_id = "tea-" + "c" * 20
        self.service_id = "srv-" + "d" * 20
        self.disk_id = "dsk-" + "e" * 20
        self.service_url = "https://kyre-sports-api-staging.onrender.com"

    def plan(self):
        return s.build_step6c_render_plan(
            release_id=self.release_id,
            revision=self.revision,
            image_ref=self.image,
            owner_id=self.owner_id,
        )

    def service(self, image=None):
        return {
            "id": self.service_id,
            "name": "kyre-sports-api-staging",
            "ownerId": self.owner_id,
            "type": "web_service",
            "image": {"imagePath": image or self.image},
            "serviceDetails": {"runtime": "image", "url": self.service_url},
        }

    def disk(self):
        return {
            "id": self.disk_id,
            "name": "kyre-sports-api-staging-data",
            "mountPath": "/var/lib/kyre-sports-api",
            "sizeGB": 1,
        }

    def env_rows(self):
        return [
            {"key": "WNBA_PRODUCTION_RUNTIME_ENABLED", "value": "false"},
            {"key": "WNBA_MARKET_PROVIDER_MODE", "value": "kyre"},
            {"key": "WNBA_KYRE_MARKET_FEED_PATH", "value": "/var/lib/kyre-sports-api/wnba_market_feed.json"},
            {"key": "WNBA_PROP_FEED_FAILOVER_ORDER", "value": "kyre"},
            {"key": "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET", "value": "archive-secret"},
            {"key": "WNBA_KYRE_MARKET_INGEST_TOKEN", "value": "ingest-secret"},
        ]

    def validate(self, **changes):
        return s.validate_step6c_render_state(
            service=changes.get("service", self.service()),
            disks=changes.get("disks", [self.disk()]),
            instances=changes.get("instances", [{"id": "ins-one"}]),
            env_vars=changes.get("env_vars", self.env_rows()),
            expected_owner_id=self.owner_id,
            expected_image_ref=self.image,
            expected_service_name="kyre-sports-api-staging",
        )

    def test_01_plan_requires_full_revision(self):
        with self.assertRaises(WNBARenderProvisioningConfigurationError):
            s.build_step6c_render_plan(release_id="x", revision="abc", image_ref=self.image)

    def test_02_plan_requires_immutable_image(self):
        with self.assertRaises(WNBARenderProvisioningConfigurationError):
            s.build_step6c_render_plan(release_id="x", revision=self.revision, image_ref="ghcr.io/x:latest")

    def test_03_operator_secrets_are_render_and_ghcr_only(self):
        self.assertEqual(
            self.plan()["required_operator_secrets"],
            ["RENDER_API_KEY", "GHCR_RENDER_USERNAME", "GHCR_RENDER_TOKEN"],
        )

    def test_04_sportsgameodds_is_removed_dependency(self):
        plan = self.plan()
        self.assertIn("SPORTSGAMEODDS_API_KEY", plan["removed_required_dependencies"])
        self.assertNotIn("SPORTSGAMEODDS_API_KEY", plan["non_secret_environment"])

    def test_05_plan_sets_kyre_mode(self):
        self.assertEqual(self.plan()["non_secret_environment"]["WNBA_MARKET_PROVIDER_MODE"], "kyre")

    def test_06_plan_sets_owned_feed_path(self):
        self.assertEqual(
            self.plan()["non_secret_environment"]["WNBA_KYRE_MARKET_FEED_PATH"],
            "/var/lib/kyre-sports-api/wnba_market_feed.json",
        )

    def test_07_plan_sets_failover_to_kyre_only(self):
        self.assertEqual(self.plan()["non_secret_environment"]["WNBA_PROP_FEED_FAILOVER_ORDER"], "kyre")

    def test_08_plan_keeps_runtime_off(self):
        self.assertEqual(self.plan()["non_secret_environment"]["WNBA_PRODUCTION_RUNTIME_ENABLED"], "false")

    def test_09_plan_is_single_instance(self):
        self.assertEqual(self.plan()["service"]["num_instances"], 1)

    def test_10_plan_has_persistent_disk(self):
        self.assertEqual(self.plan()["service"]["persistent_disk"]["mount_path"], "/var/lib/kyre-sports-api")

    def test_11_runtime_generates_hmac_and_ingest_token(self):
        self.assertEqual(
            set(self.plan()["runtime_generated_secret_keys"]),
            {"WNBA_BACKTEST_ARCHIVE_HMAC_SECRET", "WNBA_KYRE_MARKET_INGEST_TOKEN"},
        )

    def test_12_payload_contains_no_sgo_key(self):
        payload = s._service_payload(
            owner_id=self.owner_id,
            registry_credential_id="rgc-" + "f" * 20,
            release_id=self.release_id,
            revision=self.revision,
            image_ref=self.image,
            service_name="kyre-sports-api-staging",
        )
        self.assertNotIn("SPORTSGAMEODDS_API_KEY", json.dumps(payload))

    def test_13_payload_generates_ingest_token(self):
        payload = s._service_payload(
            owner_id=self.owner_id,
            registry_credential_id="rgc-" + "f" * 20,
            release_id=self.release_id,
            revision=self.revision,
            image_ref=self.image,
            service_name="kyre-sports-api-staging",
        )
        rows = {row["key"]: row for row in payload["envVars"]}
        self.assertTrue(rows["WNBA_KYRE_MARKET_INGEST_TOKEN"]["generateValue"])

    def test_14_green_state_validation(self):
        self.assertTrue(self.validate()["passed"])

    def test_15_validation_does_not_require_sgo(self):
        result = self.validate()
        self.assertFalse(result["sportsgameodds_required"])
        self.assertTrue(result["passed"])

    def test_16_wrong_mode_fails(self):
        rows = self.env_rows()
        rows[1]["value"] = "legacy_sportsgameodds"
        self.assertIn("market_mode_not_kyre", self.validate(env_vars=rows)["failures"])

    def test_17_wrong_feed_path_fails(self):
        rows = self.env_rows()
        rows[2]["value"] = "/tmp/feed.json"
        self.assertIn("kyre_market_path_mismatch", self.validate(env_vars=rows)["failures"])

    def test_18_wrong_failover_order_fails(self):
        rows = self.env_rows()
        rows[3]["value"] = "sportsgameodds"
        self.assertIn("failover_order_not_kyre", self.validate(env_vars=rows)["failures"])

    def test_19_missing_hmac_fails(self):
        rows = [row for row in self.env_rows() if row["key"] != "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET"]
        self.assertIn("archive_hmac_missing", self.validate(env_vars=rows)["failures"])

    def test_20_missing_ingest_token_fails(self):
        rows = [row for row in self.env_rows() if row["key"] != "WNBA_KYRE_MARKET_INGEST_TOKEN"]
        self.assertIn("market_ingest_token_missing", self.validate(env_vars=rows)["failures"])

    def test_21_runtime_true_fails(self):
        rows = self.env_rows()
        rows[0]["value"] = "true"
        self.assertIn("runtime_not_fail_closed", self.validate(env_vars=rows)["failures"])

    def test_22_image_drift_fails(self):
        service = self.service(f"ghcr.io/kyrepeak/kyre-sports-api@sha256:{'1'*64}")
        self.assertIn("immutable_image_mismatch", self.validate(service=service)["failures"])

    def test_23_two_instances_fail(self):
        self.assertIn("instance_count_not_one", self.validate(instances=[{"id": "1"}, {"id": "2"}])["failures"])

    def test_24_validation_never_returns_secret_values(self):
        result = self.validate()
        self.assertFalse(result["secret_values_returned"])
        self.assertNotIn("archive-secret", str(result))
        self.assertNotIn("ingest-secret", str(result))

    def test_25_paid_confirmation_required(self):
        with self.assertRaises(WNBARenderProvisioningPaymentConfirmationError):
            s.provision_step6c_render_staging(
                release_id=self.release_id,
                revision=self.revision,
                image_ref=self.image,
                api_key="render",
                ghcr_username="user",
                ghcr_token="token",
                env={ALLOW_PAID_PROVISIONING_ENV: "true"},
                confirm_paid_provisioning=False,
            )

    def test_26_runtime_true_blocks_before_network(self):
        with self.assertRaises(WNBARenderProvisioningConfigurationError):
            s.provision_step6c_render_staging(
                release_id=self.release_id,
                revision=self.revision,
                image_ref=self.image,
                api_key="render",
                ghcr_username="user",
                ghcr_token="token",
                env={ALLOW_PAID_PROVISIONING_ENV: "true", "WNBA_PRODUCTION_RUNTIME_ENABLED": "true"},
                confirm_paid_provisioning=True,
            )

    def test_27_missing_operator_credential_blocks_before_network(self):
        with self.assertRaises(WNBARenderProvisioningConfigurationError):
            s.provision_step6c_render_staging(
                release_id=self.release_id,
                revision=self.revision,
                image_ref=self.image,
                api_key="render",
                ghcr_username="user",
                ghcr_token="",
                env={ALLOW_PAID_PROVISIONING_ENV: "true"},
                confirm_paid_provisioning=True,
            )

    def test_28_remote_smoke_uses_get_only_contract(self):
        self.assertIn("owned_market_status", s._remote_pre_activation.__code__.co_consts)


if __name__ == "__main__":
    unittest.main()
