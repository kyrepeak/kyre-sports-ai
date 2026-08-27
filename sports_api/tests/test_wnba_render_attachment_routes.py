import unittest

from sports_api.main import app


class Step5YRouteContractTests(unittest.TestCase):
    def test_render_attachment_route_is_registered(self):
        self.assertIn("/api/v1/wnba/runtime/render-attachment", app.openapi()["paths"])

    def test_render_attachment_plan_route_is_registered(self):
        self.assertIn("/api/v1/wnba/runtime/render-attachment-plan", app.openapi()["paths"])

    def test_step5y_routes_are_get_only(self):
        paths = app.openapi()["paths"]
        for path in (
            "/api/v1/wnba/runtime/render-attachment",
            "/api/v1/wnba/runtime/render-attachment-plan",
        ):
            self.assertIn("get", paths[path])
            self.assertNotIn("post", paths[path])


if __name__ == "__main__":
    unittest.main()
