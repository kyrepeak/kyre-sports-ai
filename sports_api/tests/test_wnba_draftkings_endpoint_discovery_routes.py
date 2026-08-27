import unittest

from fastapi.testclient import TestClient

from sports_api.main import app


class Step6EDiscoveryRouteTests(unittest.TestCase):
    def test_01_discovery_route_registered(self):
        client = TestClient(app)
        response = client.get("/api/v1/wnba/markets/direct/draftkings/discovery")
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual("wnba_step6e_draftkings_endpoint_discovery_status", body["data_type"])
        self.assertEqual("94682", body["wnba_league_id"])

    def test_02_discovery_route_is_get_only(self):
        client = TestClient(app)
        response = client.post("/api/v1/wnba/markets/direct/draftkings/discovery")
        self.assertEqual(405, response.status_code)

    def test_03_route_does_not_claim_live_probe(self):
        client = TestClient(app)
        body = client.get("/api/v1/wnba/markets/direct/draftkings/discovery").json()
        self.assertFalse(body["live_probe_performed"])
        self.assertFalse(body["live_endpoint_verified"])


if __name__ == "__main__":
    unittest.main()
