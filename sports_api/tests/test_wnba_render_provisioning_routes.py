import unittest

from sports_api.main import app


class Step5ZRouteContractTests(unittest.TestCase):
    def test_render_provisioning_status_route_registered(self):
        self.assertIn("/api/v1/wnba/runtime/render-provisioning", app.openapi()["paths"])

    def test_render_provisioning_status_route_is_get_only(self):
        methods = app.openapi()["paths"]["/api/v1/wnba/runtime/render-provisioning"]
        self.assertIn("get", methods)
        self.assertNotIn("post", methods)

    def test_no_public_provision_mutation_route_exists(self):
        paths = app.openapi()["paths"]
        self.assertNotIn("/api/v1/wnba/runtime/render-provisioning/run", paths)


if __name__ == "__main__":
    unittest.main()
