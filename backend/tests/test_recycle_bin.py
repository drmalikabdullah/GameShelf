import sqlite3
import tempfile
import unittest
from pathlib import Path

import app


class RecycleBinTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "games.db"
        db = sqlite3.connect(self.db_path)
        db.executescript(
            (Path(app.__file__).parent / "schema.sql").read_text(encoding="utf-8")
        )
        db.execute(
            """
            INSERT INTO games (
                title, platform, steam_app_id, exe_path, logo_url,
                case_color, case_color_override
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Restore Test",
                "steam",
                "123",
                r"C:\Games\Test\game.exe",
                "/logos/1.png",
                "#112233",
                "#445566",
            ),
        )
        db.execute(
            "INSERT INTO game_screenshots (game_id, path, position) VALUES (1, ?, 0)",
            ("/screenshots/1/1.jpg",),
        )
        db.commit()
        db.close()

        self.original_db_path = app.DB_PATH
        app.DB_PATH = self.db_path
        self.client = app.app.test_client()

    def tearDown(self):
        app.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_restore_preserves_metadata_and_reconnects_screenshots(self):
        self.assertEqual(self.client.delete("/api/games/1").status_code, 204)

        deleted = self.client.get("/api/deleted_games").get_json()
        self.assertEqual(len(deleted), 1)
        response = self.client.post(
            f"/api/deleted_games/{deleted[0]['id']}/restore"
        )
        self.assertEqual(response.status_code, 201)
        restored = response.get_json()

        self.assertEqual(restored["steam_app_id"], "123")
        self.assertEqual(restored["exe_path"], r"C:\Games\Test\game.exe")
        self.assertEqual(restored["logo_url"], "/logos/1.png")
        self.assertEqual(restored["case_color"], "#112233")
        self.assertEqual(restored["case_color_override"], "#445566")
        self.assertEqual(
            self.client.get(
                f"/api/games/{restored['id']}/screenshots"
            ).get_json(),
            ["/screenshots/1/1.jpg"],
        )


class CachePolicyTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_api_responses_are_never_cached(self):
        response = self.client.get("/api/games")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_code_is_revalidated(self):
        response = self.client.get("/app.js")
        self.addCleanup(response.close)
        self.assertEqual(response.headers["Cache-Control"], "no-cache")

    def test_artwork_can_be_cached_locally(self):
        response = self.client.get("/covers/1.jpg")
        self.addCleanup(response.close)
        self.assertEqual(
            response.headers["Cache-Control"],
            "private, max-age=3600",
        )


class StaticPathSafetyTests(unittest.TestCase):
    def test_local_artwork_path_stays_inside_static(self):
        path = app.static_file_from_url("/covers/1.jpg")
        self.assertIsNotNone(path)
        self.assertEqual(path.parent, (app.BASE_DIR / "static" / "covers").resolve())

    def test_parent_traversal_is_rejected(self):
        self.assertIsNone(app.static_file_from_url("/../../games.db"))

    def test_absolute_path_is_kept_under_static(self):
        self.assertIsNone(app.static_file_from_url(r"C:\Windows\system.ini"))


if __name__ == "__main__":
    unittest.main()
