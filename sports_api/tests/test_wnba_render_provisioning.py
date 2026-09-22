import unittest

import httpx

import sports_api.wnba_render_provisioning as s


class Step5ZTests(unittest.TestCase):
    def setUp(self):
        self.revision = "a" * 40
        self.image = f"ghcr.io/kyrepeak/kyre-sports-api@sha256:{'b'*64}"
        self.release_id = "wnba-step5z-test"
        self.owner_id = "tea-" + "c" * 20
        self.service_id = "srv-" + "d" * 20
        self.disk_id = "dsk-" + "e" * 20
        self.registry_id = "rgc-" + "f" * 20
        self.service_url = "https://kyre-sports-api-staging.onrender.com"

    def plan(self):
        return s.build_render_provisioning_plan(
            release_id=self.release_id,
            revision=self.revision,
            image_ref=self.image,
            owner_id=self.owner_id,
        )

    def service(self, image=None):
        return {
            "id": self.service_id,
            "name": s.DEFAULT_SERVICE_NAME,
            "ownerId": self.owner_id,
            "type": "web_service",
            "image": {"imagePath": image or self.image},
            "serviceDetails": {
                "runtime": "image",
                "url": self.service_url,
                "plan": s.DEFAULT_PLAN,
                "region": s.DEFAULT_REGION,
            },
        }

    def disk(self):
        return {
            "id": self.disk_id,
            "name": s.DEFAULT_DISK_NAME,
            "mountPath": s.DEFAULT_DISK_MOUNT_PATH,
            "sizeGB": 1,
            "serviceId": self.service_id,
        }

    def env_rows(self):
        return [
            {"key": "WNBA_PRODUCTION_RUNTIME_ENABLED", "value": "false"},
            {"key": "SPORTSGAMEODDS_API_KEY", "value": "provider-secret"},
            {"key": "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET", "value": "archive-secret"},
        ]

    def validate(self, *, service=None, disks=None, instances=None, env_vars=None):
        return s.validate_image_backed_service(
            service=self.service() if service is None else service,
            disks=[self.disk()] if disks is None else disks,
            instances=[{"id": "ins-one"}] if instances is None else instances,
            env_vars=self.env_rows() if env_vars is None else env_vars,
            expected_owner_id=self.owner_id,
            expected_image_ref=self.image,
            expected_service_name=s.DEFAULT_SERVICE_NAME,
        )

    def test_01_plan_requires_release_id(self):
        with self.assertRaises(s.WNBARenderProvisioningConfigurationError):
            s.build_render_provisioning_plan(release_id="", revision=self.revision, image_ref=self.image)

    def test_02_plan_requires_full_revision(self):
        with self.assertRaises(s.WNBARenderProvisioningConfigurationError):
            s.build_render_provisioning_plan(release_id="x", revision="abc", image_ref=self.image)

    def test_03_plan_requires_immutable_image(self):
        with self.assertRaises(s.WNBARenderProvisioningConfigurationError):
            s.build_render_provisioning_plan(release_id="x", revision=self.revision, image_ref="ghcr.io/x:latest")

    def test_04_plan_uses_image_runtime(self):
        self.assertEqual("image", self.plan()["service_payload"]["serviceDetails"]["runtime"])

    def test_05_plan_uses_single_instance(self):
        self.assertEqual(1, self.plan()["service_payload"]["serviceDetails"]["numInstances"])

    def test_06_plan_uses_starter(self):
        self.assertEqual("starter", self.plan()["paid_resources"]["service_plan"])

    def test_07_plan_uses_persistent_disk(self):
        disk = self.plan()["service_payload"]["serviceDetails"]["disk"]
        self.assertEqual(s.DEFAULT_DISK_MOUNT_PATH, disk["mountPath"])

    def test_08_plan_disables_runtime(self):
        rows = self.plan()["service_payload"]["envVars"]
        values = {row["key"]: row.get("value") for row in rows}
        self.assertEqual("false", values["WNBA_PRODUCTION_RUNTIME_ENABLED"])

    def test_09_plan_does_not_contain_secret_values(self):
        text = str(self.plan())
        self.assertNotIn("provider-secret", text)
        self.assertTrue(self.plan()["safety"]["secret_values_in_plan"] is False)

    def test_10_plan_marks_render_git_metadata_not_required(self):
        self.assertTrue(self.plan()["safety"]["render_git_metadata_not_required"])

    def test_11_status_is_network_free(self):
        self.assertTrue(s.get_render_provisioning_status(env={})["semantics"]["network_free"])

    def test_12_status_never_returns_tokens(self):
        env = {
            s.RENDER_API_KEY_ENV: "render-secret",
            s.GHCR_TOKEN_ENV: "ghcr-secret",
            s.GHCR_USERNAME_ENV: "user",
            s.SPORTSGAMEODDS_API_KEY_ENV: "provider-secret",
        }
        report = s.get_render_provisioning_status(env=env)
        self.assertNotIn("render-secret", str(report))
        self.assertNotIn("ghcr-secret", str(report))
        self.assertNotIn("provider-secret", str(report))

    def test_13_status_requires_paid_confirmation_for_attempt(self):
        env = {
            s.RENDER_API_KEY_ENV: "x",
            s.GHCR_TOKEN_ENV: "x",
            s.GHCR_USERNAME_ENV: "x",
            s.SPORTSGAMEODDS_API_KEY_ENV: "x",
        }
        self.assertFalse(s.get_render_provisioning_status(env=env)["ready_to_attempt_authenticated_provisioning"])

    def test_14_status_blocks_when_runtime_enabled(self):
        env = {
            s.RENDER_API_KEY_ENV: "x",
            s.GHCR_TOKEN_ENV: "x",
            s.GHCR_USERNAME_ENV: "x",
            s.SPORTSGAMEODDS_API_KEY_ENV: "x",
            s.ALLOW_PAID_PROVISIONING_ENV: "true",
            "WNBA_PRODUCTION_RUNTIME_ENABLED": "true",
        }
        self.assertFalse(s.get_render_provisioning_status(env=env)["ready_to_attempt_authenticated_provisioning"])

    def test_15_green_image_backed_validation(self):
        self.assertTrue(self.validate()["passed"])

    def test_16_validation_does_not_require_git_metadata(self):
        self.assertFalse(self.validate()["render_git_metadata_required"])

    def test_17_bad_service_id_fails(self):
        service = self.service(); service["id"] = "srv-bad"
        self.assertIn("service_id_invalid", self.validate(service=service)["failures"])

    def test_18_service_name_drift_fails(self):
        service = self.service(); service["name"] = "other"
        self.assertIn("service_name_mismatch", self.validate(service=service)["failures"])

    def test_19_owner_drift_fails(self):
        service = self.service(); service["ownerId"] = "tea-other"
        self.assertIn("owner_id_mismatch", self.validate(service=service)["failures"])

    def test_20_service_type_must_be_web(self):
        service = self.service(); service["type"] = "background_worker"
        self.assertIn("service_type_not_web_service", self.validate(service=service)["failures"])

    def test_21_runtime_must_be_image(self):
        service = self.service(); service["serviceDetails"]["runtime"] = "docker"
        self.assertIn("service_runtime_not_image", self.validate(service=service)["failures"])

    def test_22_image_drift_fails(self):
        service = self.service(f"ghcr.io/kyrepeak/kyre-sports-api@sha256:{'1'*64}")
        self.assertIn("immutable_image_mismatch", self.validate(service=service)["failures"])

    def test_23_non_render_url_fails(self):
        service = self.service(); service["serviceDetails"]["url"] = "https://example.com"
        self.assertIn("service_url_not_render_https", self.validate(service=service)["failures"])

    def test_24_missing_disk_fails(self):
        self.assertIn("persistent_disk_mismatch", self.validate(disks=[])["failures"])

    def test_25_two_disks_fail(self):
        self.assertIn("persistent_disk_mismatch", self.validate(disks=[self.disk(), self.disk()])["failures"])

    def test_26_bad_disk_id_fails(self):
        disk = self.disk(); disk["id"] = "dsk-bad"
        self.assertIn("persistent_disk_id_invalid", self.validate(disks=[disk])["failures"])

    def test_27_two_instances_fail(self):
        self.assertIn("instance_count_not_one", self.validate(instances=[{"id": "1"}, {"id": "2"}])["failures"])

    def test_28_runtime_activation_fails(self):
        rows = self.env_rows(); rows[0]["value"] = "true"
        self.assertIn("production_runtime_not_disabled", self.validate(env_vars=rows)["failures"])

    def test_29_missing_sportsbook_secret_fails(self):
        rows = [row for row in self.env_rows() if row["key"] != "SPORTSGAMEODDS_API_KEY"]
        self.assertIn("required_secret_missing:SPORTSGAMEODDS_API_KEY", self.validate(env_vars=rows)["failures"])

    def test_30_missing_archive_secret_fails(self):
        rows = [row for row in self.env_rows() if row["key"] != "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET"]
        self.assertIn("required_secret_missing:WNBA_BACKTEST_ARCHIVE_HMAC_SECRET", self.validate(env_vars=rows)["failures"])

    def test_31_validation_never_returns_secret_values(self):
        result = self.validate()
        self.assertFalse(result["secret_values_returned"])
        self.assertNotIn("provider-secret", str(result))
        self.assertNotIn("archive-secret", str(result))

    def test_32_client_rejects_empty_api_key(self):
        with self.assertRaises(s.WNBARenderProvisioningConfigurationError):
            s.RenderAPIClient(api_key="")

    def test_33_client_rejects_nonpositive_timeout(self):
        with self.assertRaises(s.WNBARenderProvisioningConfigurationError):
            s.RenderAPIClient(api_key="x", timeout_seconds=0)

    def test_34_paid_double_confirmation_is_required(self):
        with self.assertRaises(s.WNBARenderProvisioningPaymentConfirmationError):
            s.provision_render_staging(
                release_id=self.release_id,
                revision=self.revision,
                image_ref=self.image,
                api_key="render",
                ghcr_username="user",
                ghcr_token="token",
                sportsbook_key="provider",
                confirm_paid_provisioning=True,
                env={},
            )

    def test_35_runtime_true_blocks_before_network(self):
        with self.assertRaises(s.WNBARenderProvisioningConfigurationError):
            s.provision_render_staging(
                release_id=self.release_id,
                revision=self.revision,
                image_ref=self.image,
                api_key="render",
                ghcr_username="user",
                ghcr_token="token",
                sportsbook_key="provider",
                confirm_paid_provisioning=True,
                env={s.ALLOW_PAID_PROVISIONING_ENV: "true", "WNBA_PRODUCTION_RUNTIME_ENABLED": "true"},
            )

    def test_36_owner_resolves_when_exactly_one(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/v1/owners":
                return httpx.Response(200, json=[{"owner": {"id": self.owner_id, "name": "workspace"}, "cursor": "c"}])
            return httpx.Response(404, json={})
        with s.RenderAPIClient(api_key="token", transport=httpx.MockTransport(handler)) as client:
            self.assertEqual(self.owner_id, s.resolve_owner_id(client))

    def test_37_multiple_owners_require_explicit_id(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[{"owner": {"id": "one"}}, {"owner": {"id": "two"}}])
        with s.RenderAPIClient(api_key="token", transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(s.WNBARenderProvisioningConfigurationError):
                s.resolve_owner_id(client)

    def test_38_existing_service_image_drift_is_fail_closed(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/v1/services":
                service = self.service(f"ghcr.io/kyrepeak/kyre-sports-api@sha256:{'1'*64}")
                return httpx.Response(200, json=[{"service": service, "cursor": "c"}])
            return httpx.Response(404, json={})
        with s.RenderAPIClient(api_key="token", transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(s.WNBARenderProvisioningConflictError):
                s.ensure_service(
                    client,
                    owner_id=self.owner_id,
                    registry_credential_id=self.registry_id,
                    release_id=self.release_id,
                    revision=self.revision,
                    image_ref=self.image,
                    sportsbook_key="provider",
                )

    def test_39_full_mock_provisioning_completes_without_secret_leak(self):
        state = {
            "service": None,
            "env": {},
            "deploy_ids": ["dep-initial", "dep-final"],
        }

        def render_handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            method = request.method
            if method == "GET" and path == "/v1/owners":
                return httpx.Response(200, json=[{"owner": {"id": self.owner_id, "name": "workspace"}, "cursor": "c"}])
            if method == "GET" and path == "/v1/registrycredentials":
                return httpx.Response(200, json=[])
            if method == "POST" and path == "/v1/registrycredentials":
                return httpx.Response(200, json={"id": self.registry_id, "name": s.DEFAULT_REGISTRY_CREDENTIAL_NAME, "registry": "GITHUB", "username": "gh-user"})
            if method == "GET" and path == "/v1/services":
                if state["service"] is None:
                    return httpx.Response(200, json=[])
                return httpx.Response(200, json=[{"service": state["service"], "cursor": "c"}])
            if method == "POST" and path == "/v1/services":
                body = request.read().decode()
                payload = __import__("json").loads(body)
                state["env"] = {
                    row["key"]: ("generated-secret" if row.get("generateValue") else row.get("value", ""))
                    for row in payload["envVars"]
                }
                state["service"] = self.service()
                return httpx.Response(201, json={"service": state["service"], "deploy": {"id": "dep-initial", "status": "created"}})
            if method == "GET" and path == f"/v1/services/{self.service_id}":
                return httpx.Response(200, json=state["service"])
            if method == "GET" and path == "/v1/disks":
                return httpx.Response(200, json=[{"disk": self.disk(), "cursor": "c"}])
            if method == "GET" and path == f"/v1/services/{self.service_id}/instances":
                return httpx.Response(200, json=[{"instance": {"id": "ins-one"}, "cursor": "c"}])
            if method == "GET" and path == f"/v1/services/{self.service_id}/env-vars":
                return httpx.Response(200, json=[{"envVar": {"key": k, "value": v}, "cursor": "c"} for k, v in state["env"].items()])
            if method == "PUT" and path.startswith(f"/v1/services/{self.service_id}/env-vars/"):
                key = path.rsplit("/", 1)[-1]
                payload = __import__("json").loads(request.read().decode())
                state["env"][key] = payload.get("value", "generated-secret")
                return httpx.Response(200, json={"key": key, "value": state["env"][key]})
            if method == "POST" and path == f"/v1/services/{self.service_id}/deploys":
                return httpx.Response(201, json={"id": "dep-final", "status": "created"})
            if method == "GET" and path in {
                f"/v1/services/{self.service_id}/deploys/dep-initial",
                f"/v1/services/{self.service_id}/deploys/dep-final",
            }:
                return httpx.Response(200, json={"id": path.rsplit("/", 1)[-1], "status": "live"})
            return httpx.Response(404, json={"path": path, "method": method})

        def remote_handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/health":
                return httpx.Response(200, json={"status": "ok"})
            if request.url.path == "/api/v1/wnba/runtime/readiness":
                return httpx.Response(200, json={})
            if request.url.path == "/api/v1/wnba/runtime/health":
                return httpx.Response(503, json={})
            if request.url.path == "/api/v1/wnba/rankings/player-props/current":
                return httpx.Response(409, json={})
            if request.url.path == "/api/v1/wnba/runtime/render-provisioning":
                return httpx.Response(200, json={})
            return httpx.Response(404, json={})

        result = s.provision_render_staging(
            release_id=self.release_id,
            revision=self.revision,
            image_ref=self.image,
            api_key="render-api-secret",
            ghcr_username="gh-user",
            ghcr_token="ghcr-secret",
            sportsbook_key="sportsbook-secret",
            owner_id=self.owner_id,
            confirm_paid_provisioning=True,
            env={s.ALLOW_PAID_PROVISIONING_ENV: "true", "WNBA_PRODUCTION_RUNTIME_ENABLED": "false"},
            transport=httpx.MockTransport(render_handler),
            remote_transport=httpx.MockTransport(remote_handler),
            poll_seconds=0.001,
        )
        self.assertTrue(result["provisioning_complete"])
        self.assertTrue(result["remote_smoke"]["passed"])
        self.assertNotIn("render-api-secret", str(result))
        self.assertNotIn("ghcr-secret", str(result))
        self.assertNotIn("sportsbook-secret", str(result))
        self.assertFalse(result["safety"]["production_runtime_enabled"])


if __name__ == "__main__":
    unittest.main()
