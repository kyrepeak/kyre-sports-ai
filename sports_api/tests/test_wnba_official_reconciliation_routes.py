import unittest

from fastapi.testclient import TestClient

from sports_api.main import app


class Step6HOfficialReconciliationRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.path = "/api/v1/wnba/markets/direct/draftkings/official-reconciliation-readiness"

    def test_01_route_registered(self):
        response = self.client.get(self.path)
        self.assertEqual(200, response.status_code)
        self.assertEqual("wnba_step6h_official_reconciliation_readiness", response.json()["data_type"])

    def test_02_route_is_get_only(self):
        self.assertEqual(405, self.client.post(self.path).status_code)

    def test_03_route_does_not_activate_anything(self):
        data = self.client.get(self.path).json()
        self.assertFalse(data["automatic_sync_enabled_by_step6h"])
        self.assertFalse(data["production_runtime_enabled_by_step6h"])
        self.assertFalse(data["scheduler_enabled_by_step6h"])

    def test_04_no_public_live_reconciliation_run_route(self):
        paths = {path for route in app.routes if (path := getattr(route, "path", None))}
        self.assertNotIn("/api/v1/wnba/markets/direct/draftkings/official-reconciliation-run", paths)


if __name__ == "__main__":
    unittest.main()
