import unittest

from sports_api.main import app


class Step5WRouteContractTests(unittest.TestCase):
    def test_staging_activation_plan_route_is_registered(self):
        self.assertIn("/api/v1/wnba/runtime/staging-activation-plan", app.openapi()["paths"])

    def test_step5t_activation_plan_route_remains_registered(self):
        self.assertIn("/api/v1/wnba/runtime/activation-plan", app.openapi()["paths"])


if __name__ == "__main__":
    unittest.main()
