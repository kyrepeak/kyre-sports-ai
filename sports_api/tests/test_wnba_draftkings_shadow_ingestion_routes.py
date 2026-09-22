import unittest

from fastapi.testclient import TestClient

from sports_api.main import app


class Step6GShadowRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.path = "/api/v1/wnba/markets/direct/draftkings/shadow-readiness"

    def test_01_route_registered(self):
        response = self.client.get(self.path)
        self.assertEqual(200, response.status_code)
        self.assertEqual("wnba_step6g_shadow_readiness", response.json()["data_type"])

    def test_02_route_is_get_only(self):
        self.assertEqual(405, self.client.post(self.path).status_code)

    def test_03_route_does_not_activate_sync(self):
        data = self.client.get(self.path).json()
        self.assertFalse(data["automatic_sync_enabled_by_step6g"])
        self.assertFalse(data["production_runtime_enabled_by_step6g"])

    def test_04_no_public_shadow_run_route(self):
        paths = {path for route in app.routes if (path := getattr(route, "path", None))}
        self.assertNotIn("/api/v1/wnba/markets/direct/draftkings/shadow-run", paths)


if __name__ == "__main__":
    unittest.main()
