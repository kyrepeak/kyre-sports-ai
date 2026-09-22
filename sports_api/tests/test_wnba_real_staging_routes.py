import unittest

from sports_api.main import app


class Step5XRouteContractTests(unittest.TestCase):
    def test_staging_deployment_route_is_registered(self):
        self.assertIn("/api/v1/wnba/runtime/staging-deployment", app.openapi()["paths"])

    def test_staging_deployment_smoke_plan_route_is_registered(self):
        self.assertIn("/api/v1/wnba/runtime/staging-deployment-smoke-plan", app.openapi()["paths"])

    def test_step5x_routes_are_get_only(self):
        paths = app.openapi()["paths"]
        for path in (
            "/api/v1/wnba/runtime/staging-deployment",
            "/api/v1/wnba/runtime/staging-deployment-smoke-plan",
        ):
            self.assertIn("get", paths[path])
            self.assertNotIn("post", paths[path])


if __name__ == "__main__":
    unittest.main()
