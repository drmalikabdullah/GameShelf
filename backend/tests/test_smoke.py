import unittest

import app


class PageAndApiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_primary_pages_load(self):
        for path in ("/", "/steam", "/ps3", "/ps4", "/dashboard", "/settings"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.addCleanup(response.close)
                self.assertEqual(response.status_code, 200)

    def test_read_only_apis_load(self):
        for path in (
            "/api/games",
            "/api/stats",
            "/api/dashboard",
            "/api/dashboard/lists",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.addCleanup(response.close)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.is_json)

    def test_invalid_platform_is_rejected(self):
        response = self.client.post(
            "/api/games",
            json={"title": "Invalid Platform Test", "platform": "museum"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("platform must be one of", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
